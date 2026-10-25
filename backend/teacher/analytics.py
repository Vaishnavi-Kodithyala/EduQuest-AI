"""
Week 9 - Teacher dashboard analytics.

Every figure the teacher sees comes from what students already write:

    quiz_attempts        one document per submitted quiz, with each question's
                         result tagged by concept
    lesson_completions   one document per chapter marked as read
    chat_history         one document per question asked to the chatbot

The counting is done by MongoDB aggregation pipelines ($match, $sort, $group,
$lookup, $unwind, $facet), so the database does the work rather than Python.

Latest attempt, not every attempt
---------------------------------
Scores per student, subject, chapter and concept use each student's *latest*
attempt at each quiz. A student who scored 40% and then 90% on a retake has
learned the chapter; averaging the two to 65% would keep them on the teacher's
"needs help" list for something they have already fixed. (The Week 8
recommender judges students the same way.) The score trend is the exception:
it shows every attempt on the day it was made, because it answers "how did
quizzes go that day".

Two things are done in Python on purpose:
  * Grouping by calendar day. A day in India starts at 00:00 IST. A real
    MongoDB can do this with $dateToString's timezone option, but the
    in-memory database used for testing (mongomock) cannot, and the trend only
    reads a score and a timestamp per attempt, so it is cheap either way.
  * XP, level, streak and badges, which come from the gamification engine so
    the teacher sees exactly the numbers the student sees.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time, timedelta, timezone

from bson import ObjectId

from ..content_order import SUBJECT_ORDER, chapter_number, sort_textbook
from ..gamification.engine import (
    BASE_AVATARS,
    IST,
    PASS_SCORE,
    GamificationEngine,
    _as_utc,
    _iso,
    _stable_index,
    ist_day,
)

# A student is flagged when any of these is true.
INACTIVE_DAYS = 7          # no reading, quiz or chat question for a week
LOW_AVERAGE = PASS_SCORE   # current quiz average below the pass mark
MIN_QUIZZES_FOR_LOW = 2    # one bad quiz is not a pattern

# A concept is "weak" for the class when, over enough answers, fewer than
# this share were right. A student is "struggling" with a concept below half.
WEAK_ACCURACY = 0.6
STRUGGLING_ACCURACY = 0.5
MIN_CLASS_ANSWERS = 5

DEFAULT_TREND_DAYS = 21


def latest_attempts(user_ids: list[str]) -> list[dict]:
    """
    Pipeline stages giving each student's latest attempt at each quiz.

    $lookup joins the quiz for its chapter and subject; $unwind then drops
    attempts at quizzes that no longer exist (the removed Grade 7 quizzes),
    which is also what the gamification engine ignores.
    """
    return [
        {"$match": {"user_id": {"$in": user_ids}}},
        {"$sort": {"submitted_at": -1}},
        {"$group": {
            "_id": {"user": "$user_id", "quiz": "$quiz_id"},
            # The whole latest document, so a field missing from it (results
            # on attempts made before Week 9) is not filled from an older one.
            "latest": {"$first": "$$ROOT"},
            "attempts": {"$sum": 1},
            "best": {"$max": "$score"},
            "first_at": {"$min": "$submitted_at"},
        }},
        {"$lookup": {"from": "quizzes", "localField": "_id.quiz",
                     "foreignField": "id", "as": "quiz"}},
        {"$unwind": "$quiz"},
        {"$project": {
            "_id": 0,
            "user_id": "$_id.user",
            "quiz_id": "$_id.quiz",
            "lesson_id": "$quiz.lesson_id",
            "subject": "$quiz.subject",
            "score": "$latest.score",
            "correct": "$latest.correct",
            "total": "$latest.total",
            "results": "$latest.results",
            "submitted_at": "$latest.submitted_at",
            "attempts": 1,
            "best": 1,
            "first_at": 1,
        }},
    ]


def _passed():
    return {"$sum": {"$cond": [{"$gte": ["$score", PASS_SCORE]}, 1, 0]}}


def _round(value, digits=0):
    if value is None:
        return None
    return round(value, digits) if digits else round(value)


class TeacherAnalytics:
    def __init__(self, database, now: datetime | None = None) -> None:
        self.db = database
        self.now = _as_utc(now or datetime.now(timezone.utc))
        self.today = ist_day(self.now)
        self._lessons: dict[str, dict] | None = None

    # -- shared lookups ---------------------------------------------------------
    @property
    def lessons(self) -> dict[str, dict]:
        if self._lessons is None:
            self._lessons = {
                l["id"]: l
                for l in self.db["lessons"].find(
                    {}, {"_id": 0, "id": 1, "title": 1, "subject": 1, "grade": 1}
                )
            }
        return self._lessons

    def _chapter(self, lesson_id: str | None) -> dict | None:
        lesson = self.lessons.get(lesson_id or "")
        if lesson is None:
            return None
        return {"id": lesson["id"], "title": lesson["title"], "subject": lesson["subject"],
                "number": chapter_number(lesson["id"])}

    def _students(self, grade: int | None) -> list[dict]:
        query: dict = {"role": {"$ne": "teacher"}}
        if grade is not None:
            query["grade"] = grade
        return list(self.db["users"].find(
            query, {"username": 1, "avatar": 1, "grade": 1, "language": 1, "demo": 1}
        ).sort("username", 1))

    def _days_since(self, moment) -> int | None:
        if moment is None:
            return None
        return (self.today - ist_day(moment)).days

    def _subjects(self, grade: int | None) -> list[str]:
        found = {l["subject"] for l in self.lessons.values()
                 if grade is None or l.get("grade") == grade}
        return sorted(found, key=lambda s: (SUBJECT_ORDER.get(s, 99), s))

    # -- per student ----------------------------------------------------------------
    def _student_rows(self, students: list[dict]) -> list[dict]:
        ids = [str(s["_id"]) for s in students]
        if not ids:
            return []

        quiz = {
            r["_id"]: r
            for r in self.db["quiz_attempts"].aggregate(latest_attempts(ids) + [
                {"$group": {
                    "_id": "$user_id",
                    "quizzes": {"$sum": 1},
                    "attempts": {"$sum": "$attempts"},
                    "average": {"$avg": "$score"},
                    "passed": _passed(),
                    "last": {"$max": "$submitted_at"},
                }},
            ])
        }
        by_subject: dict[str, dict] = defaultdict(dict)
        for r in self.db["quiz_attempts"].aggregate(latest_attempts(ids) + [
            {"$group": {"_id": {"user": "$user_id", "subject": "$subject"},
                        "average": {"$avg": "$score"}, "quizzes": {"$sum": 1}}},
        ]):
            by_subject[r["_id"]["user"]][r["_id"]["subject"]] = {
                "average": _round(r["average"]), "quizzes": r["quizzes"]}

        reads = {
            r["_id"]: r
            for r in self.db["lesson_completions"].aggregate([
                {"$match": {"user_id": {"$in": ids}}},
                {"$group": {"_id": "$user_id", "chapters": {"$sum": 1},
                            "last": {"$max": "$completed_at"}}},
            ])
        }
        chats = {
            r["_id"]: r
            for r in self.db["chat_history"].aggregate([
                {"$match": {"user_id": {"$in": ids}}},
                {"$group": {"_id": "$user_id", "questions": {"$sum": 1},
                            "last": {"$max": "$asked_at"}}},
            ])
        }
        profiles = GamificationEngine(self.db, now=self.now).profiles(ids)

        rows = []
        for student in students:
            uid = str(student["_id"])
            q, r, c, p = quiz.get(uid, {}), reads.get(uid, {}), chats.get(uid, {}), profiles[uid]
            moments = [m for m in (q.get("last"), r.get("last"), c.get("last")) if m is not None]
            last_active = max(moments, key=_as_utc) if moments else None
            average = _round(q.get("average"))

            row = {
                "user_id": uid,
                "username": student["username"],
                "avatar": student.get("avatar") or BASE_AVATARS[_stable_index(student["username"])],
                "demo": bool(student.get("demo")),
                "xp": p["xp"],
                "level": p["level"],
                "title": p["title"],
                "streak": p["streak"]["current"],
                "badges": p["badges_earned"],
                "chapters_read": r.get("chapters", 0),
                "quizzes_taken": q.get("quizzes", 0),
                "quiz_attempts": q.get("attempts", 0),
                "quizzes_passed": q.get("passed", 0),
                "average_score": average,
                "subjects": by_subject.get(uid, {}),
                "chat_questions": c.get("questions", 0),
                "last_active": _iso(last_active),
                "days_inactive": self._days_since(last_active),
            }
            row["flags"] = self._flags(row)
            rows.append(row)
        return rows

    @staticmethod
    def _flags(row: dict) -> list[dict]:
        flags = []
        if row["last_active"] is None:
            flags.append({"code": "not_started", "label": "Has not started"})
        elif row["days_inactive"] >= INACTIVE_DAYS:
            flags.append({"code": "inactive", "label": f"Inactive for {row['days_inactive']} days"})
        if (row["average_score"] is not None and row["average_score"] < LOW_AVERAGE
                and row["quizzes_taken"] >= MIN_QUIZZES_FOR_LOW):
            flags.append({"code": "low_score", "label": f"Quiz average {row['average_score']}%"})
        return flags

    # -- class-wide ----------------------------------------------------------------
    def subject_performance(self, ids: list[str], grade: int | None = None) -> list[dict]:
        quiz = {
            r["_id"]: r
            for r in self.db["quiz_attempts"].aggregate(latest_attempts(ids) + [
                {"$group": {
                    "_id": "$subject",
                    "quizzes": {"$sum": 1},
                    "attempts": {"$sum": "$attempts"},
                    "average": {"$avg": "$score"},
                    "passed": _passed(),
                    "students": {"$addToSet": "$user_id"},
                }},
                {"$project": {"quizzes": 1, "attempts": 1, "average": 1, "passed": 1,
                              "students": {"$size": "$students"}}},
            ])
        }
        reads = {
            r["_id"]: r["chapters"]
            for r in self.db["lesson_completions"].aggregate([
                {"$match": {"user_id": {"$in": ids}}},
                {"$lookup": {"from": "lessons", "localField": "lesson_id",
                             "foreignField": "id", "as": "lesson"}},
                {"$unwind": "$lesson"},
                {"$group": {"_id": "$lesson.subject", "chapters": {"$sum": 1}}},
            ])
        }
        chapters_per_subject = defaultdict(int)
        for lesson in self.lessons.values():
            if grade is None or lesson.get("grade") == grade:
                chapters_per_subject[lesson["subject"]] += 1

        out = []
        for subject in self._subjects(grade):
            q = quiz.get(subject, {})
            possible = chapters_per_subject[subject] * len(ids)
            out.append({
                "subject": subject,
                "average_score": _round(q.get("average")),
                "pass_rate": _round(q["passed"] * 100 / q["quizzes"]) if q.get("quizzes") else None,
                "quizzes_taken": q.get("quizzes", 0),
                "quiz_attempts": q.get("attempts", 0),
                "students_tested": q.get("students", 0),
                "chapters": chapters_per_subject[subject],
                "chapters_read": reads.get(subject, 0),
                # Share of (student, chapter) pairs read: 100% = everyone read everything.
                "coverage": _round(reads.get(subject, 0) * 100 / possible) if possible else 0,
            })
        return out

    def chapter_performance(self, ids: list[str], grade: int | None = None) -> list[dict]:
        quiz = {
            r["_id"]: r
            for r in self.db["quiz_attempts"].aggregate(latest_attempts(ids) + [
                {"$group": {
                    "_id": "$lesson_id",
                    "students": {"$sum": 1},
                    "attempts": {"$sum": "$attempts"},
                    "average": {"$avg": "$score"},
                    "passed": _passed(),
                }},
            ])
        }
        readers = {
            r["_id"]: r["readers"]
            for r in self.db["lesson_completions"].aggregate([
                {"$match": {"user_id": {"$in": ids}}},
                {"$group": {"_id": "$lesson_id", "readers": {"$sum": 1}}},
            ])
        }
        asked = {
            r["_id"]: r["questions"]
            for r in self.db["chat_history"].aggregate([
                {"$match": {"user_id": {"$in": ids}, "lesson_id": {"$ne": None}}},
                {"$group": {"_id": "$lesson_id", "questions": {"$sum": 1}}},
            ])
        }

        lessons = [l for l in self.lessons.values() if grade is None or l.get("grade") == grade]
        out = []
        for lesson in sort_textbook(lessons):
            q = quiz.get(lesson["id"], {})
            out.append({
                **self._chapter(lesson["id"]),
                "readers": readers.get(lesson["id"], 0),
                "quiz_takers": q.get("students", 0),
                "quiz_attempts": q.get("attempts", 0),
                "average_score": _round(q.get("average")),
                "pass_rate": _round(q["passed"] * 100 / q["students"]) if q.get("students") else None,
                "chat_questions": asked.get(lesson["id"], 0),
            })
        return out

    def concepts(self, ids: list[str], names: dict[str, str] | None = None,
                 min_answers: int = MIN_CLASS_ANSWERS, below: float = WEAK_ACCURACY,
                 limit: int = 12) -> list[dict]:
        """
        Concepts answered wrongly most often, from each student's latest attempt.

        Grouped twice: first per student, so we know who is struggling with a
        concept, then per concept for the class figure.
        """
        rows = self.db["quiz_attempts"].aggregate(latest_attempts(ids) + [
            {"$unwind": "$results"},
            {"$group": {
                "_id": {"lesson": "$lesson_id", "concept": "$results.concept", "user": "$user_id"},
                "answers": {"$sum": 1},
                "correct": {"$sum": {"$cond": ["$results.correct", 1, 0]}},
            }},
            {"$group": {
                "_id": {"lesson": "$_id.lesson", "concept": "$_id.concept"},
                "answers": {"$sum": "$answers"},
                "correct": {"$sum": "$correct"},
                "students": {"$sum": 1},
                "per_student": {"$push": {"user": "$_id.user", "answers": "$answers",
                                          "correct": "$correct"}},
            }},
            {"$match": {"answers": {"$gte": min_answers}}},
            {"$project": {
                "_id": 0,
                "lesson_id": "$_id.lesson",
                "concept": "$_id.concept",
                "answers": 1,
                "correct": 1,
                "students": 1,
                "per_student": 1,
                "accuracy": {"$divide": ["$correct", "$answers"]},
            }},
            {"$match": {"accuracy": {"$lt": below}}},
            {"$sort": {"accuracy": 1, "answers": -1}},
            {"$limit": limit},
        ])

        out = []
        for row in rows:
            struggling = [
                s["user"] for s in row["per_student"]
                if s["correct"] / s["answers"] < STRUGGLING_ACCURACY
            ]
            out.append({
                "concept": row["concept"] or "General",
                "chapter": self._chapter(row["lesson_id"]),
                "answers": row["answers"],
                "correct": row["correct"],
                "accuracy": _round(row["accuracy"] * 100),
                "students": row["students"],
                "struggling": len(struggling),
                "struggling_names": sorted(names[u] for u in struggling if names and u in names),
            })
        return out

    def score_trend(self, ids: list[str], days: int = DEFAULT_TREND_DAYS) -> dict:
        """Quiz attempts and average score per day (IST), plus this week against last."""
        first_day = self.today - timedelta(days=days - 1)
        since = datetime.combine(first_day, time(0), IST).astimezone(timezone.utc)

        rows = self.db["quiz_attempts"].aggregate([
            {"$match": {"user_id": {"$in": ids}, "submitted_at": {"$gte": since}}},
            {"$lookup": {"from": "quizzes", "localField": "quiz_id",
                         "foreignField": "id", "as": "quiz"}},
            {"$unwind": "$quiz"},
            {"$project": {"_id": 0, "user_id": 1, "score": 1, "submitted_at": 1}},
        ])
        buckets: dict = {first_day + timedelta(days=i): [] for i in range(days)}
        for row in rows:
            day = ist_day(row["submitted_at"])
            if day in buckets:
                buckets[day].append(row)

        def summary(rows_: list[dict]) -> dict:
            scores = [r["score"] for r in rows_]
            return {
                "attempts": len(rows_),
                "average_score": _round(sum(scores) / len(scores)) if scores else None,
                "students": len({r["user_id"] for r in rows_}),
            }

        points = [{"date": day.isoformat(), **summary(rs)} for day, rs in buckets.items()]
        this_week = [r for day, rs in buckets.items() if (self.today - day).days < 7 for r in rs]
        last_week = [r for day, rs in buckets.items() if 7 <= (self.today - day).days < 14 for r in rs]
        return {"days": days, "points": points,
                "this_week": summary(this_week), "last_week": summary(last_week)}

    def chat_summary(self, ids: list[str], names: dict[str, str]) -> dict:
        facets = next(self.db["chat_history"].aggregate([
            {"$match": {"user_id": {"$in": ids}}},
            {"$facet": {
                "totals": [{"$group": {
                    "_id": None,
                    "questions": {"$sum": 1},
                    "answered": {"$sum": {"$cond": ["$answered", 1, 0]}},
                    "understood": {"$sum": {"$cond": ["$understood", 1, 0]}},
                    "students": {"$addToSet": "$user_id"},
                }}],
                "chapters": [
                    {"$match": {"lesson_id": {"$ne": None}}},
                    {"$group": {"_id": "$lesson_id", "questions": {"$sum": 1},
                                "students": {"$addToSet": "$user_id"}}},
                    {"$sort": {"questions": -1, "_id": 1}},
                    {"$limit": 6},
                ],
                # The same question from several students is one row.
                "unanswered": [
                    {"$match": {"understood": False}},
                    {"$group": {"_id": "$message", "times": {"$sum": 1},
                                "students": {"$addToSet": "$user_id"},
                                "last": {"$max": "$asked_at"}}},
                    {"$sort": {"last": -1}},
                    {"$limit": 8},
                ],
            }},
        ]), {})

        totals = (facets.get("totals") or [{}])[0]
        questions = totals.get("questions", 0)
        return {
            "questions": questions,
            "students": len(totals.get("students", [])),
            "answered_pct": _round(totals.get("answered", 0) * 100 / questions) if questions else None,
            "understood_pct": _round(totals.get("understood", 0) * 100 / questions) if questions else None,
            "top_chapters": [
                {**(self._chapter(r["_id"]) or {"id": r["_id"], "title": r["_id"]}),
                 "questions": r["questions"], "students": len(r["students"])}
                for r in facets.get("chapters", [])
            ],
            "unanswered": [
                {"message": r["_id"], "times": r["times"],
                 "students": sorted(names.get(u, "?") for u in r["students"]),
                 "last_asked": _iso(r.get("last"))}
                for r in facets.get("unanswered", [])
            ],
        }

    # -- public ----------------------------------------------------------------
    def class_report(self, grade: int | None = None, days: int = DEFAULT_TREND_DAYS) -> dict:
        students = self._students(grade)
        ids = [str(s["_id"]) for s in students]
        names = {str(s["_id"]): s["username"] for s in students}
        rows = self._student_rows(students)

        latest = list(self.db["quiz_attempts"].aggregate(latest_attempts(ids) + [
            {"$group": {"_id": None, "quizzes": {"$sum": 1}, "attempts": {"$sum": "$attempts"},
                        "average": {"$avg": "$score"}, "passed": _passed()}},
        ])) if ids else []
        latest = latest[0] if latest else {}
        trend = self.score_trend(ids, days)
        week_start = datetime.combine(self.today - timedelta(days=6), time(0), IST).astimezone(timezone.utc)
        chapters_this_week = self.db["lesson_completions"].count_documents(
            {"user_id": {"$in": ids}, "completed_at": {"$gte": week_start}}
        ) if ids else 0

        overview = {
            "students": len(rows),
            "demo_students": sum(1 for r in rows if r["demo"]),
            "active_this_week": sum(1 for r in rows
                                    if r["days_inactive"] is not None and r["days_inactive"] < 7),
            "needs_attention": sum(1 for r in rows if r["flags"]),
            "average_score": _round(latest.get("average")),
            "pass_rate": _round(latest["passed"] * 100 / latest["quizzes"]) if latest.get("quizzes") else None,
            "quiz_attempts": latest.get("attempts", 0),
            "quiz_attempts_this_week": trend["this_week"]["attempts"],
            "chapters_read": sum(r["chapters_read"] for r in rows),
            "chapters_read_this_week": chapters_this_week,
        }
        return {
            "grade": grade,
            "generated_at": _iso(self.now),
            "pass_score": PASS_SCORE,
            "overview": overview,
            "trend": trend,
            "subjects": self.subject_performance(ids, grade),
            "chapters": self.chapter_performance(ids, grade),
            "weak_concepts": self.concepts(ids, names),
            "chat": self.chat_summary(ids, names),
            "students": rows,
        }

    def student_detail(self, student_id: str) -> dict | None:
        try:
            oid = ObjectId(student_id)
        except Exception:
            return None
        student = self.db["users"].find_one(
            {"_id": oid, "role": {"$ne": "teacher"}},
            {"username": 1, "avatar": 1, "grade": 1, "language": 1, "demo": 1},
        )
        if student is None:
            return None

        ids = [student_id]
        row = self._student_rows([student])[0]
        profile = GamificationEngine(self.db, now=self.now).profile(student_id)

        quizzes = [
            {
                **(self._chapter(r["lesson_id"]) or {}),
                "quiz_id": r["quiz_id"],
                "latest_score": r["score"],
                "best_score": r["best"],
                "attempts": r["attempts"],
                "last_attempt": _iso(r["submitted_at"]),
            }
            for r in self.db["quiz_attempts"].aggregate(latest_attempts(ids))
        ]
        quizzes.sort(key=lambda q: q.get("last_attempt") or "", reverse=True)

        history = [
            {
                "quiz_id": r["quiz_id"],
                "chapter": self._chapter(r["quiz"].get("lesson_id")),
                "score": r["score"],
                "correct": r.get("correct"),
                "total": r.get("total"),
                "submitted_at": _iso(r["submitted_at"]),
            }
            for r in self.db["quiz_attempts"].aggregate([
                {"$match": {"user_id": student_id}},
                {"$lookup": {"from": "quizzes", "localField": "quiz_id",
                             "foreignField": "id", "as": "quiz"}},
                {"$unwind": "$quiz"},
                {"$sort": {"submitted_at": -1}},
                {"$limit": 10},
            ])
        ]

        reads = [
            {**(self._chapter(r["lesson_id"]) or {"id": r["lesson_id"], "title": r["lesson_id"]}),
             "completed_at": _iso(r["completed_at"])}
            for r in self.db["lesson_completions"].find({"user_id": student_id}).sort("completed_at", -1)
        ]
        chats = [
            {"message": r["message"], "intent": r.get("intent"),
             "understood": r.get("understood", True), "answered": r.get("answered", False),
             "chapter": self._chapter(r.get("lesson_id")), "asked_at": _iso(r.get("asked_at"))}
            for r in self.db["chat_history"].find({"user_id": student_id}).sort("asked_at", -1).limit(10)
        ]

        return {
            **row,
            "grade": student.get("grade"),
            "language": student.get("language"),
            "streak_best": profile["streak"]["best"],
            "badges_list": [b for b in profile["badges"] if b["earned"]],
            "subject_performance": self.subject_performance(ids, student.get("grade")),
            "weak_concepts": self.concepts(ids, min_answers=1, limit=8),
            "quizzes": quizzes,
            "recent_attempts": history,
            "chapters": reads,
            "recent_questions": chats,
        }
