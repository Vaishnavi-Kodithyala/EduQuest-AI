"""
Week 8 - Rule-based recommendation engine.

Suggests what a student should study next, using two signals:

  1. Quiz performance  - which quizzes they failed, which subjects they are
                         weak in, which chapters they have not attempted
  2. NLP analysis      - what they have been asking the chatbot about, taken
                         from the logged intents and matched lessons
  3. Reading (Week 9)  - chapters marked as read whose quiz has not been
                         taken yet, so reading leads straight into practice

Why rule-based
--------------
The action plan specifies it, and at this data scale it is also the only honest
option. A collaborative-filtering or learned recommender needs many students
and many interactions; this system has one student at a time and a 16-chapter
content bank. Explicit rules are transparent, debuggable, and every suggestion
can state exactly why it was made - which matters when the person acting on it
is a child.

Each rule produces candidates with a priority. Higher priority wins, ties are
broken by score, and the final list is deduplicated by lesson so a student is
never told to study the same chapter twice for different reasons.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, asdict

from ..content_order import chapter_number, textbook_order

# --- Tunable thresholds ----------------------------------------------------
# A quiz below this counts as "needs another attempt".
FAILING_SCORE = 60

# A subject whose average is below this counts as a weak subject.
WEAK_SUBJECT_SCORE = 70

# A subject needs at least this many attempts before we judge it. One bad quiz
# on a bad day should not label a whole subject as weak.
MIN_ATTEMPTS_TO_JUDGE = 2

# How many times a topic must come up in chat before it counts as an interest.
CHAT_INTEREST_MIN = 2

# Priorities. Higher surfaces first.
PRIORITY_RETRY = 100
PRIORITY_WEAK_SUBJECT = 80
PRIORITY_ASKED_ABOUT = 60
PRIORITY_TAKE_QUIZ = 50
PRIORITY_NEXT_CHAPTER = 40
PRIORITY_REVISION = 20


@dataclass
class Recommendation:
    lesson_id: str
    title: str
    subject: str
    grade: int
    reason: str
    kind: str
    priority: int
    quiz_id: str | None = None
    score: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class RecommendationEngine:
    """Builds a ranked study list for one student."""

    def __init__(self, database) -> None:
        self.db = database

    # -- Data gathering -----------------------------------------------------
    def _attempts(self, user_id: str) -> list[dict]:
        return list(
            self.db["quiz_attempts"].find(
                {"user_id": user_id},
                {"_id": 0, "quiz_id": 1, "score": 1, "submitted_at": 1},
            )
        )

    def _quizzes_by_id(self) -> dict[str, dict]:
        return {
            q["id"]: q
            for q in self.db["quizzes"].find(
                {}, {"_id": 0, "id": 1, "lesson_id": 1, "subject": 1, "grade": 1, "title": 1}
            )
        }

    def _lessons_by_id(self, grade: int | None) -> dict[str, dict]:
        query = {"grade": grade} if grade is not None else {}
        return {
            l["id"]: l
            for l in self.db["lessons"].find(
                query, {"_id": 0, "id": 1, "title": 1, "subject": 1, "grade": 1}
            )
        }

    def _chat_topics(self, user_id: str) -> Counter:
        """Which lessons the student has asked the chatbot about."""
        rows = self.db["chat_history"].find(
            {"user_id": user_id, "lesson_id": {"$ne": None}},
            {"_id": 0, "lesson_id": 1},
        )
        return Counter(r["lesson_id"] for r in rows if r.get("lesson_id"))

    # -- Rules --------------------------------------------------------------
    @staticmethod
    def _latest_per_quiz(attempts: list[dict]) -> dict[str, dict]:
        """
        Most recent attempt for each quiz.

        Every rule judges on the latest attempt, never the average of all of
        them. A student who scored 40 and then 90 has fixed the problem, and
        averaging those to 65 would keep telling them they are weak at a
        subject they have already improved in.
        """
        latest: dict[str, dict] = {}
        for attempt in attempts:
            quiz_id = attempt["quiz_id"]
            previous = latest.get(quiz_id)
            if previous is None or str(attempt.get("submitted_at", "")) >= str(
                previous.get("submitted_at", "")
            ):
                latest[quiz_id] = attempt
        return latest

    def _rule_retry_failed(self, latest, quizzes, lessons) -> list[Recommendation]:
        """Quizzes whose most recent attempt is below FAILING_SCORE."""
        out = []
        for quiz_id, attempt in latest.items():
            if attempt["score"] >= FAILING_SCORE:
                continue
            quiz = quizzes.get(quiz_id)
            if not quiz:
                continue
            lesson = lessons.get(quiz.get("lesson_id"))
            if not lesson:
                continue
            out.append(
                Recommendation(
                    lesson_id=lesson["id"],
                    title=lesson["title"],
                    subject=lesson["subject"],
                    grade=lesson["grade"],
                    reason=f"You scored {attempt['score']}% here. Re-read the chapter and try again.",
                    kind="retry",
                    priority=PRIORITY_RETRY,
                    quiz_id=quiz_id,
                    score=attempt["score"],
                )
            )
        return out

    def _rule_weak_subjects(self, latest, quizzes, lessons) -> list[Recommendation]:
        """Subjects averaging below WEAK_SUBJECT_SCORE across enough quizzes."""
        by_subject: dict[str, list[int]] = defaultdict(list)
        attempted_lessons: set[str] = set()

        for attempt in latest.values():
            quiz = quizzes.get(attempt["quiz_id"])
            if not quiz:
                continue
            by_subject[quiz["subject"]].append(attempt["score"])
            if quiz.get("lesson_id"):
                attempted_lessons.add(quiz["lesson_id"])

        out = []
        for subject, scores in by_subject.items():
            if len(scores) < MIN_ATTEMPTS_TO_JUDGE:
                continue
            average = sum(scores) / len(scores)
            if average >= WEAK_SUBJECT_SCORE:
                continue

            for lesson in lessons.values():
                if lesson["subject"] != subject or lesson["id"] in attempted_lessons:
                    continue
                out.append(
                    Recommendation(
                        lesson_id=lesson["id"],
                        title=lesson["title"],
                        subject=subject,
                        grade=lesson["grade"],
                        reason=f"Your {subject} average is {round(average)}%. More practice here will help.",
                        kind="weak_subject",
                        priority=PRIORITY_WEAK_SUBJECT,
                        score=round(average),
                    )
                )
        return out

    def _rule_asked_about(self, user_id, lessons, attempted_lessons) -> list[Recommendation]:
        """
        Chapters the student keeps asking the chatbot about but has not quizzed.

        This is the NLP half of the engine. The chat endpoint logs which lesson
        each question matched, so repeated questions about one chapter are a
        direct signal of what the student is struggling with - independent of
        whether they have attempted its quiz.
        """
        topics = self._chat_topics(user_id)
        out = []
        for lesson_id, count in topics.items():
            if count < CHAT_INTEREST_MIN or lesson_id in attempted_lessons:
                continue
            lesson = lessons.get(lesson_id)
            if not lesson:
                continue
            out.append(
                Recommendation(
                    lesson_id=lesson["id"],
                    title=lesson["title"],
                    subject=lesson["subject"],
                    grade=lesson["grade"],
                    reason=f"You have asked about this {count} times. Try its quiz to check your understanding.",
                    kind="asked_about",
                    priority=PRIORITY_ASKED_ABOUT,
                )
            )
        return out

    def _read_lessons(self, user_id: str) -> set[str]:
        return {
            row["lesson_id"]
            for row in self.db["lesson_completions"].find({"user_id": user_id}, {"lesson_id": 1})
        }

    def _rule_take_quiz(self, lessons, read_lessons, attempted_lessons) -> list[Recommendation]:
        """Chapters the student has read but not been quizzed on."""
        pending = sorted(
            (l for l in lessons.values() if l["id"] in read_lessons and l["id"] not in attempted_lessons),
            key=textbook_order,
        )
        return [
            Recommendation(
                lesson_id=lesson["id"],
                title=lesson["title"],
                subject=lesson["subject"],
                grade=lesson["grade"],
                reason="You read this chapter. Take its quiz to check what you remember.",
                kind="take_quiz",
                priority=PRIORITY_TAKE_QUIZ,
            )
            for lesson in pending
        ]

    def _rule_next_chapter(self, lessons, attempted_lessons, read_lessons=frozenset()) -> list[Recommendation]:
        """
        Chapters in the student's grade they have not started yet.

        Ordered by chapter number, then subject, so a new student is pointed at
        Chapter 1 of each subject rather than four English chapters in a row.
        """
        started = set(attempted_lessons) | set(read_lessons)
        pending = sorted(
            (l for l in lessons.values() if l["id"] not in started),
            key=lambda l: (chapter_number(l["id"]), textbook_order(l)),
        )
        return [
            Recommendation(
                lesson_id=lesson["id"],
                title=lesson["title"],
                subject=lesson["subject"],
                grade=lesson["grade"],
                reason="You have not started this chapter yet.",
                kind="next_chapter",
                priority=PRIORITY_NEXT_CHAPTER,
            )
            for lesson in pending
        ]

    def _rule_revision(self, latest, quizzes, lessons) -> list[Recommendation]:
        """
        Weakest passed chapters, as a fallback.

        Without this, a student who has passed everything sees an empty panel -
        the one student who is doing best gets the least useful screen. Their
        lowest passing scores are still the most useful thing to revise.
        """
        out = []
        for quiz_id, attempt in latest.items():
            if attempt["score"] < FAILING_SCORE:
                continue
            quiz = quizzes.get(quiz_id)
            if not quiz:
                continue
            lesson = lessons.get(quiz.get("lesson_id"))
            if not lesson:
                continue
            out.append(
                Recommendation(
                    lesson_id=lesson["id"],
                    title=lesson["title"],
                    subject=lesson["subject"],
                    grade=lesson["grade"],
                    reason=f"You scored {attempt['score']}% here. Revise it to push the score higher.",
                    kind="revision",
                    priority=PRIORITY_REVISION,
                    quiz_id=quiz_id,
                    score=attempt["score"],
                )
            )
        return out

    # -- Entry point --------------------------------------------------------
    def recommend(self, user_id: str, grade: int | None = None, limit: int = 5) -> dict:
        attempts = self._attempts(user_id)
        quizzes = self._quizzes_by_id()
        lessons = self._lessons_by_id(grade)

        attempted_lessons = {
            quizzes[a["quiz_id"]]["lesson_id"]
            for a in attempts
            if a["quiz_id"] in quizzes and quizzes[a["quiz_id"]].get("lesson_id")
        }

        latest = self._latest_per_quiz(attempts)
        read_lessons = self._read_lessons(user_id)

        candidates: list[Recommendation] = []
        candidates += self._rule_retry_failed(latest, quizzes, lessons)
        candidates += self._rule_weak_subjects(latest, quizzes, lessons)
        candidates += self._rule_asked_about(user_id, lessons, attempted_lessons)
        candidates += self._rule_take_quiz(lessons, read_lessons, attempted_lessons)
        candidates += self._rule_next_chapter(lessons, attempted_lessons, read_lessons)
        candidates += self._rule_revision(latest, quizzes, lessons)

        # Highest priority wins per lesson. Sorting first means the first time
        # a lesson is seen is always its strongest reason.
        candidates.sort(key=lambda r: (-r.priority, r.score if r.score is not None else 999))

        seen: set[str] = set()
        final: list[Recommendation] = []
        for candidate in candidates:
            if candidate.lesson_id in seen:
                continue
            seen.add(candidate.lesson_id)
            final.append(candidate)
            if len(final) >= limit:
                break

        scores = [a["score"] for a in attempts]
        return {
            "recommendations": [r.to_dict() for r in final],
            "based_on": {
                "quiz_attempts": len(attempts),
                "average_score": round(sum(scores) / len(scores)) if scores else 0,
                "chat_questions": sum(self._chat_topics(user_id).values()),
                "chapters_attempted": len(attempted_lessons),
                "chapters_read": len(read_lessons),
            },
        }
