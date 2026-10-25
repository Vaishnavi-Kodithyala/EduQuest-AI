"""
Week 9 - Gamification engine.

Turns a student's learning history (chapters marked as read, quiz attempts)
into XP, a level, a daily streak, badges and avatar rewards.

Everything is computed from the history rather than stored as running totals.
A running total drifts the moment a rule changes or a request fails halfway;
recomputing from the events means the numbers can always be explained, and the
teacher dashboard and leaderboard read exactly the same figures.

XP rules
--------
    +20  first time a chapter is marked as read
    +10  per correct answer, counted only above the best earlier attempt at
         that quiz, so retaking a quiz you already aced earns nothing, while
         improving a weak score is rewarded
    +25  first time a quiz is passed (60% or more)
    +25  first time a quiz is answered 100% correctly
    +10  for each day with any learning activity (a daily goal)

Levels are every 150 XP. A streak is the number of consecutive days, in Indian
Standard Time, with at least one chapter read or quiz submitted; it stays
alive until the end of the day after the last activity.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

# --- Tunable rules ---------------------------------------------------------
XP_PER_LESSON = 20
XP_PER_CORRECT = 10
XP_FIRST_PASS = 25
XP_PERFECT = 25
XP_DAILY = 10
PASS_SCORE = 60
XP_PER_LEVEL = 150

# Fixed offset rather than zoneinfo: zoneinfo needs the tzdata package on
# Windows, and India has no daylight saving to account for.
IST = timezone(timedelta(hours=5, minutes=30))

LEVEL_TITLES = [
    "Wayfarer", "Explorer", "Trailblazer", "Scholar", "Strategist",
    "Champion", "Luminary", "Vanguard", "Master", "Legend",
]

SUBJECTS = ("English", "Mathematics", "Science", "Telugu")

# Avatars every student can pick from the start.
BASE_AVATARS = ["🦊", "🐼", "🐯", "🦁", "🐨", "🦉", "🐸", "🐧", "🦄", "🐙"]

# Rewards: extra avatars unlocked by reaching a level.
AVATAR_REWARDS = [
    {"level": 2, "avatar": "🦅", "name": "Eagle"},
    {"level": 3, "avatar": "🐬", "name": "Dolphin"},
    {"level": 4, "avatar": "🦚", "name": "Peacock"},
    {"level": 5, "avatar": "🐘", "name": "Elephant"},
    {"level": 6, "avatar": "🐅", "name": "Tiger"},
    {"level": 8, "avatar": "🦋", "name": "Butterfly"},
    {"level": 10, "avatar": "👑", "name": "Crown"},
]

# id, icon, label, what to do, how progress is measured, target
BADGES = [
    ("first-chapter", "📖", "First Chapter", "Mark your first chapter as read", "lessons", 1),
    ("bookworm", "🐛", "Bookworm", "Read 5 chapters", "lessons", 5),
    ("chapter-champion", "📚", "Chapter Champion", "Read 20 chapters", "lessons", 20),
    ("first-quiz", "🎯", "First Quiz", "Finish your first quiz", "attempts", 1),
    ("quiz-whiz", "🧠", "Quiz Whiz", "Pass 5 different quizzes", "passed", 5),
    ("perfect-score", "💎", "Perfect Score", "Get 100% on a quiz", "perfect", 1),
    ("comeback", "💪", "Comeback", "Pass a quiz you did not pass before", "comebacks", 1),
    ("all-rounder", "🌈", "All-Rounder", "Pass a quiz in every subject", "subjects", len(SUBJECTS)),
    ("sharp-shooter", "🏹", "Sharp Shooter", "Average 80% or more over 5 quizzes", "sharp", 5),
    ("streak-3", "🔥", "On Fire", "Learn 3 days in a row", "streak", 3),
    ("streak-7", "⚡", "Unstoppable", "Learn 7 days in a row", "streak", 7),
]


def ist_day(moment) -> date:
    """Calendar day in India for a stored timestamp (naive values are UTC)."""
    if isinstance(moment, str):
        moment = datetime.fromisoformat(moment)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(IST).date()


def level_info(xp: int) -> dict:
    level = xp // XP_PER_LEVEL + 1
    into = xp % XP_PER_LEVEL
    return {
        "level": level,
        "title": LEVEL_TITLES[min(level - 1, len(LEVEL_TITLES) - 1)],
        "xpIntoLevel": into,
        "xpForNextLevel": XP_PER_LEVEL,
        "pct": round(into * 100 / XP_PER_LEVEL),
    }


def unlocked_avatars(level: int) -> list[str]:
    return BASE_AVATARS + [r["avatar"] for r in AVATAR_REWARDS if level >= r["level"]]


def longest_run(days: set[date]) -> int:
    best = run = 0
    previous = None
    for day in sorted(days):
        run = run + 1 if previous and day - previous == timedelta(days=1) else 1
        best = max(best, run)
        previous = day
    return best


def current_streak(days: set[date], today: date) -> int:
    """Consecutive active days ending today, or yesterday if today has nothing yet."""
    if today in days:
        cursor = today
    elif today - timedelta(days=1) in days:
        cursor = today - timedelta(days=1)
    else:
        return 0
    count = 0
    while cursor in days:
        count += 1
        cursor -= timedelta(days=1)
    return count


@dataclass
class _Walk:
    """Running state while replaying a student's history in time order."""

    xp: int = 0
    ledger: list = field(default_factory=list)
    lessons: set = field(default_factory=set)
    attempts: int = 0
    scores: list = field(default_factory=list)
    best_correct: dict = field(default_factory=dict)
    passed: set = field(default_factory=set)
    failed: set = field(default_factory=set)
    perfect: set = field(default_factory=set)
    comebacks: int = 0
    subjects_passed: set = field(default_factory=set)
    days: set = field(default_factory=set)
    run: int = 0
    best_run: int = 0
    last_day: date | None = None
    earned_at: dict = field(default_factory=dict)
    # Week 10, for the redesigned pages: per-subject reading and each
    # chapter's latest and best quiz score.
    read_by_subject: dict = field(default_factory=lambda: defaultdict(set))
    quiz_marks: dict = field(default_factory=dict)

    def gain(self, amount: int, reason: str, when) -> None:
        if amount > 0:
            self.xp += amount
            self.ledger.append({"xp": amount, "reason": reason, "at": when})

    def counts(self) -> dict:
        return {
            "lessons": len(self.lessons),
            "attempts": self.attempts,
            "passed": len(self.passed),
            "perfect": len(self.perfect),
            "comebacks": self.comebacks,
            "subjects": len(self.subjects_passed),
            "sharp": self._sharp_progress(),
            "streak": self.best_run,
        }

    def _sharp_progress(self) -> int:
        # Counts quizzes towards 5, but only while the average stays at 80+.
        if not self.scores:
            return 0
        average = sum(self.scores) / len(self.scores)
        return min(len(self.scores), 5) if average >= 80 else 0

    def check_badges(self, when) -> None:
        counts = self.counts()
        for badge_id, _icon, _label, _how, measure, target in BADGES:
            if badge_id not in self.earned_at and counts[measure] >= target:
                self.earned_at[badge_id] = when


class GamificationEngine:
    def __init__(self, database, now: datetime | None = None) -> None:
        self.db = database
        self.now = now

    # -- data ----------------------------------------------------------------
    def _events(self, user_ids: list[str]) -> dict[str, list[dict]]:
        quizzes = {
            q["id"]: q
            for q in self.db["quizzes"].find({}, {"_id": 0, "id": 1, "subject": 1, "title": 1, "lesson_id": 1})
        }
        lessons = {
            l["id"]: l
            for l in self.db["lessons"].find({}, {"_id": 0, "id": 1, "title": 1, "subject": 1})
        }
        self._chapters_per_subject = defaultdict(int)
        for lesson in lessons.values():
            self._chapters_per_subject[lesson.get("subject")] += 1
        events: dict[str, list[dict]] = defaultdict(list)

        for row in self.db["lesson_completions"].find({"user_id": {"$in": user_ids}}):
            lesson = lessons.get(row["lesson_id"], {})
            events[row["user_id"]].append({
                "kind": "lesson",
                "at": row["completed_at"],
                "lesson_id": row["lesson_id"],
                "title": lesson.get("title", row["lesson_id"]),
                "subject": lesson.get("subject"),
            })

        for row in self.db["quiz_attempts"].find({"user_id": {"$in": user_ids}}):
            quiz = quizzes.get(row["quiz_id"])
            if quiz is None:
                continue  # attempts at quizzes that no longer exist (old Grade 7)
            events[row["user_id"]].append({
                "kind": "quiz",
                "at": row["submitted_at"],
                "quiz_id": row["quiz_id"],
                "lesson_id": quiz.get("lesson_id"),
                "subject": quiz.get("subject"),
                "title": quiz.get("title", row["quiz_id"]),
                "correct": row.get("correct", 0),
                "score": row.get("score", 0),
            })

        for rows in events.values():
            rows.sort(key=lambda e: _as_utc(e["at"]))
        return events

    # -- replay ----------------------------------------------------------------
    def _replay(self, events: list[dict]) -> _Walk:
        walk = _Walk()
        for event in events:
            when = event["at"]
            day = ist_day(when)

            if day not in walk.days:
                walk.days.add(day)
                walk.gain(XP_DAILY, "Daily learning goal", when)
                if walk.last_day and day - walk.last_day == timedelta(days=1):
                    walk.run += 1
                else:
                    walk.run = 1
                walk.best_run = max(walk.best_run, walk.run)
                walk.last_day = day

            if event["kind"] == "lesson":
                if event["lesson_id"] not in walk.lessons:
                    walk.lessons.add(event["lesson_id"])
                    walk.read_by_subject[event.get("subject")].add(event["lesson_id"])
                    walk.gain(XP_PER_LESSON, f"Read \"{event['title']}\"", when)
            else:
                quiz_id = event["quiz_id"]
                walk.attempts += 1
                walk.scores.append(event["score"])
                mark = walk.quiz_marks.get(quiz_id, {"best": 0, "attempts": 0})
                walk.quiz_marks[quiz_id] = {
                    "lesson_id": event.get("lesson_id"),
                    "subject": event.get("subject"),
                    "latest": event["score"],
                    "best": max(mark["best"], event["score"]),
                    "attempts": mark["attempts"] + 1,
                }

                previous_best = walk.best_correct.get(quiz_id, 0)
                improvement = max(0, event["correct"] - previous_best)
                walk.best_correct[quiz_id] = max(previous_best, event["correct"])
                walk.gain(improvement * XP_PER_CORRECT, f"Correct answers in {event['title']}", when)

                if event["score"] >= PASS_SCORE:
                    if quiz_id not in walk.passed:
                        walk.passed.add(quiz_id)
                        walk.gain(XP_FIRST_PASS, f"Passed {event['title']}", when)
                        if quiz_id in walk.failed:
                            walk.comebacks += 1
                    if event.get("subject"):
                        walk.subjects_passed.add(event["subject"])
                else:
                    walk.failed.add(quiz_id)

                if event["score"] == 100 and quiz_id not in walk.perfect:
                    walk.perfect.add(quiz_id)
                    walk.gain(XP_PERFECT, f"Perfect score in {event['title']}", when)

            walk.check_badges(when)
        return walk

    def _profile_from(self, walk: _Walk) -> dict:
        today = ist_day(self.now or datetime.now(timezone.utc))
        counts = walk.counts()
        level = level_info(walk.xp)

        badges = []
        for badge_id, icon, label, how, measure, target in BADGES:
            earned = badge_id in walk.earned_at
            badges.append({
                "id": badge_id,
                "icon": icon,
                "label": label,
                "description": how,
                "earned": earned,
                "earned_at": _iso(walk.earned_at.get(badge_id)),
                "progress": min(counts[measure], target),
                "target": target,
            })

        rewards = [
            {**reward, "unlocked": level["level"] >= reward["level"]}
            for reward in AVATAR_REWARDS
        ]
        next_reward = next((r for r in rewards if not r["unlocked"]), None)

        return {
            "xp": walk.xp,
            **level,
            "streak": {
                "current": current_streak(walk.days, today),
                "best": walk.best_run,
                "active_today": today in walk.days,
            },
            "badges": badges,
            "badges_earned": sum(1 for b in badges if b["earned"]),
            "rewards": rewards,
            "next_reward": next_reward,
            "avatars": unlocked_avatars(level["level"]),
            "stats": {
                "lessons_completed": len(walk.lessons),
                "quiz_attempts": walk.attempts,
                "quizzes_passed": len(walk.passed),
                "average_score": round(sum(walk.scores) / len(walk.scores)) if walk.scores else 0,
            },
            "completed_lessons": sorted(walk.lessons),
            # Last 7 days in India, oldest first - the week strip on the home page.
            "week": [
                {"date": day.isoformat(), "active": day in walk.days}
                for day in (today - timedelta(days=n) for n in range(6, -1, -1))
            ],
            "subjects": self._subject_report(walk),
            # Latest and best score for each chapter's quiz, keyed by chapter id.
            "quiz_marks": {
                m["lesson_id"]: {"latest": m["latest"], "best": m["best"],
                                 "attempts": m["attempts"], "passed": m["best"] >= PASS_SCORE}
                for m in walk.quiz_marks.values() if m.get("lesson_id")
            },
            "recent_xp": [
                {**entry, "at": _iso(entry["at"])} for entry in reversed(walk.ledger[-8:])
            ],
        }

    def _subject_report(self, walk: _Walk) -> list[dict]:
        """Chapters read and current quiz average per subject (the progress report)."""
        report = []
        totals = getattr(self, "_chapters_per_subject", {})
        for subject in SUBJECTS:
            marks = [m for m in walk.quiz_marks.values() if m.get("subject") == subject]
            report.append({
                "subject": subject,
                "chapters": totals.get(subject, 0),
                "read": len(walk.read_by_subject.get(subject, ())),
                "quizzes_taken": len(marks),
                "quizzes_passed": sum(1 for m in marks if m["best"] >= PASS_SCORE),
                # Latest attempt at each quiz, as on the teacher dashboard.
                "average": round(sum(m["latest"] for m in marks) / len(marks)) if marks else None,
            })
        return report

    # -- public ----------------------------------------------------------------
    def profile(self, user_id: str) -> dict:
        events = self._events([user_id]).get(user_id, [])
        return self._profile_from(self._replay(events))

    def profiles(self, user_ids: list[str]) -> dict[str, dict]:
        events = self._events(user_ids)
        return {uid: self._profile_from(self._replay(events.get(uid, []))) for uid in user_ids}

    def leaderboard(self, grade: int | None = None, limit: int = 10, user_id: str | None = None) -> dict:
        query: dict = {"role": {"$ne": "teacher"}}
        if grade is not None:
            query["grade"] = grade
        students = list(self.db["users"].find(query, {"username": 1, "avatar": 1, "grade": 1}))
        ids = [str(s["_id"]) for s in students]
        profiles = self.profiles(ids)

        rows = []
        for student in students:
            uid = str(student["_id"])
            p = profiles[uid]
            rows.append({
                "user_id": uid,
                "username": student["username"],
                "avatar": student.get("avatar") or BASE_AVATARS[_stable_index(student["username"])],
                "xp": p["xp"],
                "level": p["level"],
                "title": p["title"],
                "streak": p["streak"]["current"],
                "badges": p["badges_earned"],
            })
        rows.sort(key=lambda r: (-r["xp"], r["username"].lower()))

        # Students on equal XP share a rank (1, 2, 2, 4).
        for index, row in enumerate(rows):
            if index and row["xp"] == rows[index - 1]["xp"]:
                row["rank"] = rows[index - 1]["rank"]
            else:
                row["rank"] = index + 1
            row["is_you"] = row["user_id"] == user_id

        you = next((r for r in rows if r["is_you"]), None)
        return {
            "students": len(rows),
            "top": rows[:limit],
            "you": you,
        }


def diff(before: dict, after: dict) -> dict:
    """What changed between two profiles - shown after a quiz or chapter."""
    earned_before = {b["id"] for b in before["badges"] if b["earned"]}
    new_badges = [b for b in after["badges"] if b["earned"] and b["id"] not in earned_before]
    new_rewards = [
        r for r in after["rewards"]
        if r["unlocked"] and not any(o["avatar"] == r["avatar"] and o["unlocked"] for o in before["rewards"])
    ]
    return {
        "xp_gained": after["xp"] - before["xp"],
        "xp": after["xp"],
        "level": after["level"],
        "level_up": after["level"] > before["level"],
        "new_badges": new_badges,
        "new_rewards": new_rewards,
        "streak": after["streak"]["current"],
    }


def _as_utc(moment) -> datetime:
    if isinstance(moment, str):
        moment = datetime.fromisoformat(moment)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


def _iso(moment) -> str | None:
    if moment is None:
        return None
    return _as_utc(moment).isoformat()


def _stable_index(text: str) -> int:
    """Same default avatar the frontend picks for a username (see gamify.js)."""
    h = 0
    for ch in text:
        h = ((h << 5) - h + ord(ch)) & 0xFFFFFFFF
    if h >= 2**31:
        h -= 2**32
    return abs(h) % len(BASE_AVATARS)
