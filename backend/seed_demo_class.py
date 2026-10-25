"""
A demo class for the teacher dashboard.

    python -m backend.seed_demo_class            create (or re-create) the demo class
    python -m backend.seed_demo_class --remove   delete it again

Creates a teacher account and twelve Grade 6 students with three weeks of
simulated activity: chapters read, quizzes taken (with retakes), and questions
asked to the chatbot. Every document it writes is marked `demo: true`, so
`--remove` deletes exactly what it created and never touches real accounts.

The simulation is seeded, so it produces the same class every time. Each
student has a different pattern, so every part of the dashboard has something
to show:

    asha     strong in every subject, studies almost every day
    ravi     very good at Mathematics, weak in English
    kiran    struggles with Mathematics, retakes quizzes
    suresh   low scores in every subject (flagged)
    meena    stopped using the app eleven days ago (flagged)
    venkat   stopped eight days ago (flagged)
    kavya    joined four days ago
    raju     registered but never started (flagged)
    ...

Teacher login:  teacher / teacher123
Student logins: any of the names below / student123
"""

from __future__ import annotations

import argparse
import random
from datetime import date, datetime, time, timedelta, timezone

from bson import ObjectId

from .content_order import sort_textbook
from .database import chat_history, db, ensure_indexes, lesson_completions, lessons, quiz_attempts, quizzes, users
from .gamification.engine import IST, GamificationEngine
from .routes.auth import hash_password

DAYS = 21
TEACHER = ("teacher", "teacher123")
STUDENT_PASSWORD = "student123"

E, M, S, T = "English", "Mathematics", "Science", "Telugu"

# name, avatar, chance of studying on a given day, ability per subject,
# first active day (days ago), last active day (days ago), subjects in the
# order they like to study them.
STUDENTS = [
    ("asha",    "🦉", 0.85, {E: .88, M: .86, S: .90, T: .88}, 21, 0, [S, M, E, T]),
    ("ravi",    "🐯", 0.70, {E: .42, M: .92, S: .76, T: .66}, 21, 0, [M, E, S, M, T]),
    ("lakshmi", "🦄", 0.75, {E: .78, M: .62, S: .72, T: .82}, 21, 0, [E, T, S, M]),
    ("kiran",   "🦊", 0.65, {E: .70, M: .34, S: .66, T: .70}, 20, 0, [M, E, M, S, T]),
    ("meena",   "🐼", 0.85, {E: .74, M: .68, S: .72, T: .76}, 21, 11, [E, S, M, T]),
    ("arjun",   "🦁", 0.55, {E: .62, M: .60, S: .58, T: .66}, 19, 1, [S, E, M, T]),
    ("divya",   "🐨", 0.70, {E: .70, M: .66, S: .94, T: .72}, 21, 0, [S, M, S, E, T]),
    ("suresh",  "🐸", 0.55, {E: .40, M: .34, S: .42, T: .50}, 18, 2, [M, S, E, T]),
    ("kavya",   "🐧", 0.95, {E: .80, M: .76, S: .78, T: .82}, 4, 0, [E, M, S, T]),
    ("venkat",  "🐙", 0.60, {E: .58, M: .54, S: .60, T: .62}, 21, 8, [M, E, S, T]),
    ("sita",    "🦄", 0.80, {E: .88, M: .58, S: .68, T: .90}, 21, 0, [E, T, S, M]),
    ("raju",    "🐼", 0.00, {E: .60, M: .60, S: .60, T: .60}, 0, 0, []),
]

# Questions demo students "asked" the chatbot, by chapter. The intent and
# whether an exact answer was given match what the chatbot does with them.
QUESTIONS = {
    "g6-sci-5": [("What is the SI unit of length?", "factual_question", True),
                 ("how do we measure a curved line", "concept_explanation", False)],
    "g6-sci-7": [("What is the normal temperature of a healthy human body?", "factual_question", True),
                 ("difference between clinical and laboratory thermometer", "concept_explanation", False)],
    "g6-sci-8": [("What is the change of water into water vapour called?", "definition", True)],
    "g6-sci-9": [("What is the process of separating grains from stalks called?", "definition", True),
                 ("explain winnowing", "concept_explanation", False)],
    "g6-sci-3": [("Which disease is caused by a lack of vitamin C?", "factual_question", False)],
    "g6-sci-4": [("what are the poles of a magnet", "definition", False),
                 ("why does a magnet attract iron", "concept_explanation", False)],
    "g6-sci-2": [("how do camels survive in the desert", "concept_explanation", False)],
    "g6-sci-12": [("Which star appears nearly stationary in the north?", "factual_question", True)],
    "g6-math-5": [("what is a prime number", "definition", False),
                  ("is 91 a prime number", "calculation", True),
                  ("HCF of 12 and 18", "calculation", True)],
    "g6-math-7": [("what is 1/3 + 1/6", "calculation", True),
                  ("how to add fractions with different denominators", "concept_explanation", False)],
    "g6-math-10": [("What are positive numbers, negative numbers and zero together called?", "definition", True),
                   ("how to subtract a negative number", "concept_explanation", False)],
    "g6-math-6": [("area of a rectangle 5 m by 4 m", "calculation", True),
                  ("difference between perimeter and area", "concept_explanation", False)],
    "g6-math-2": [("explain lines and angles", "concept_explanation", False)],
    "g6-math-1": [("give me an example of a number pattern", "example_request", False)],
    "g6-math-3": [("What is Kaprekar's magic number?", "factual_question", True)],
    "g6-eng-3": [("What is the name of the fox in the poem?", "factual_question", True)],
    "g6-eng-1": [("What did Rama Natha have to collect?", "factual_question", True),
                 ("what did Rama Natha learn about wealth", "concept_explanation", False)],
    "g6-eng-16": [("When was the National War Memorial established?", "factual_question", True)],
    "g6-eng-2": [("the story about the elephant and the dog", "concept_explanation", False)],
    "g6-eng-12": [("What does the Sanskrit root yuj mean?", "definition", True)],
    "g6-tel-1": [("రైతు ఏమి చేస్తాడు?", "telugu_question", True)],
    "g6-tel-2": [("నిజమైన స్నేహం అంటే ఏమిటి?", "telugu_question", True)],
}

# Questions the chatbot could not match to any chapter. The dashboard lists
# these so the teacher can pick them up in class.
UNANSWERED = [
    "why does the moon change its shape",
    "how to draw an angle without protractor",
    "meaning of muttered",
    "what is a mixed fraction",
    "sir when is the exam",
    "how many marks for the quiz",
    "what is the difference between weight and mass",
    "why is the sky blue",
]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _question_difficulty(quiz_id: str, index: int) -> float:
    """Fixed per question. About one question in six is much harder than the rest."""
    rng = random.Random(f"eduquest-demo-difficulty-{quiz_id}-{index}")
    return 0.62 if rng.random() < 0.17 else rng.uniform(0.93, 1.10)


class Clock:
    """Session times: after school (16:00-20:30 IST), never in the future."""

    def __init__(self, now: datetime) -> None:
        self.now = now
        self.today = now.astimezone(IST).date()

    def session_start(self, rng: random.Random, days_ago: int) -> datetime | None:
        day: date = self.today - timedelta(days=days_ago)
        start = datetime.combine(day, time(16, 0), IST) + timedelta(minutes=rng.randint(0, 270))
        if days_ago == 0:
            latest = self.now - timedelta(minutes=45)
            midnight = datetime.combine(day, time(0, 5), IST)
            if latest < midnight:
                return None  # just after midnight: nothing for today yet
            start = min(start, max(midnight, latest - timedelta(minutes=rng.randint(0, 180))))
        return start.astimezone(timezone.utc)


def remove() -> dict:
    ids = [str(u["_id"]) for u in users.find({"demo": True}, {"_id": 1})]
    removed = {
        "quiz attempts": quiz_attempts.delete_many({"$or": [{"demo": True}, {"user_id": {"$in": ids}}]}).deleted_count,
        "chapters read": lesson_completions.delete_many({"$or": [{"demo": True}, {"user_id": {"$in": ids}}]}).deleted_count,
        "chatbot questions": chat_history.delete_many({"$or": [{"demo": True}, {"user_id": {"$in": ids}}]}).deleted_count,
        "accounts": users.delete_many({"demo": True}).deleted_count,
    }
    return removed


def create(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    clock = Clock(now)
    ensure_indexes()

    lesson_list = sort_textbook(list(lessons.find({"grade": 6}, {"_id": 0, "id": 1, "subject": 1, "title": 1})))
    quiz_by_lesson = {q["lesson_id"]: q for q in quizzes.find({"grade": 6}, {"_id": 0})}
    if not lesson_list or not quiz_by_lesson:
        raise SystemExit("No Grade 6 lessons or quizzes found. Run  python -m backend.seed  first.")
    by_subject: dict[str, list[dict]] = {}
    for lesson in lesson_list:
        by_subject.setdefault(lesson["subject"], []).append(lesson)

    # Teacher
    teacher_name = TEACHER[0]
    existing = users.find_one({"username": teacher_name})
    if existing and not existing.get("demo"):
        teacher_note = (f"An account called '{teacher_name}' already exists, so no demo teacher was "
                        f"made. Make one with:  python -m backend.create_teacher <name>")
    else:
        users.insert_one({"username": teacher_name, "password_hash": hash_password(TEACHER[1]),
                          "grade": 6, "language": "en", "points": 0, "role": "teacher",
                          "avatar": "🧑‍🏫", "demo": True})
        teacher_note = f"Teacher login: {TEACHER[0]} / {TEACHER[1]}"

    created, skipped = [], []
    attempts, reads, chats = [], [], []
    for name, avatar, diligence, ability, first_day, last_day, order in STUDENTS:
        if users.find_one({"username": name}):
            skipped.append(name)
            continue
        uid = str(users.insert_one({
            "username": name, "password_hash": hash_password(STUDENT_PASSWORD), "grade": 6,
            "language": "en", "points": 0, "role": "student", "avatar": avatar, "demo": True,
        }).inserted_id)
        created.append((uid, name))
        if not order:
            continue  # registered, never started

        rng = random.Random(f"eduquest-demo-{name}")
        read: list[dict] = []
        tries: dict[str, int] = {}
        last_score: dict[str, int] = {}
        next_subject = 0

        for days_ago in range(first_day, last_day - 1, -1):
            # Always active on the first and last day, so "last active" is exact.
            if days_ago not in (first_day, last_day) and rng.random() > diligence:
                continue
            start = clock.session_start(rng, days_ago)
            if start is None:
                continue
            moment = start
            growth = 0.004 * (first_day - days_ago)  # a little better every day

            def take_quiz(lesson: dict) -> None:
                nonlocal moment
                quiz = quiz_by_lesson.get(lesson["id"])
                if quiz is None:
                    return
                moment += timedelta(minutes=rng.randint(6, 14))
                practice = 0.08 * tries.get(quiz["id"], 0)  # retakes go a little better
                answers, results = [], []
                for i, q in enumerate(quiz["questions"]):
                    chance = _clamp((ability[lesson["subject"]] + growth + practice)
                                    * _question_difficulty(quiz["id"], i), 0.05, 0.97)
                    right = rng.random() < chance
                    wrong_options = [o for o in range(len(q["options"])) if o != q["correct"]]
                    answers.append(q["correct"] if right else rng.choice(wrong_options))
                    results.append({"concept": q.get("concept", ""), "correct": right})
                correct = sum(r["correct"] for r in results)
                score = round(correct * 100 / len(results))
                attempts.append({
                    "user_id": uid, "quiz_id": quiz["id"], "lesson_id": lesson["id"],
                    "subject": lesson["subject"], "answers": answers, "results": results,
                    "correct": correct, "total": len(results), "score": score,
                    "submitted_at": moment, "demo": True,
                })
                tries[quiz["id"]] = tries.get(quiz["id"], 0) + 1
                last_score[quiz["id"]] = score

            # Retake a failed quiz now and then.
            failed = [l for l in read if last_score.get(quiz_by_lesson.get(l["id"], {}).get("id"), 100) < 60]
            if failed and rng.random() < 0.5:
                take_quiz(rng.choice(failed))

            for _ in range(rng.choice([1, 1, 1, 2])):
                for _attempt in range(len(order)):
                    subject = order[next_subject % len(order)]
                    next_subject += 1
                    unread = [l for l in by_subject.get(subject, []) if l not in read]
                    if unread:
                        break
                else:
                    break  # read everything
                lesson = unread[0]
                moment += timedelta(minutes=rng.randint(8, 20))
                read.append(lesson)
                reads.append({"user_id": uid, "lesson_id": lesson["id"],
                              "completed_at": moment, "demo": True})
                if rng.random() < 0.85:
                    take_quiz(lesson)

            if rng.random() < 0.45:
                asked_about = [l for l in read if l["id"] in QUESTIONS]
                if asked_about:
                    lesson = rng.choice(asked_about)
                    message, intent, answered = rng.choice(QUESTIONS[lesson["id"]])
                    moment += timedelta(minutes=rng.randint(1, 5))
                    chats.append({"user_id": uid, "message": message, "intent": intent,
                                  "confidence": round(rng.uniform(0.62, 0.98), 4), "understood": True,
                                  "lesson_id": lesson["id"], "answered": answered,
                                  "asked_at": moment, "demo": True})
            if rng.random() < 0.10:
                moment += timedelta(minutes=rng.randint(1, 5))
                chats.append({"user_id": uid, "message": rng.choice(UNANSWERED),
                              "intent": "out_of_scope", "confidence": round(rng.uniform(0.2, 0.55), 4),
                              "understood": False, "lesson_id": None, "answered": False,
                              "asked_at": moment, "demo": True})

    # Nothing may be stamped later than now (a late session today could run past it).
    for rows, field in ((attempts, "submitted_at"), (reads, "completed_at"), (chats, "asked_at")):
        for row in rows:
            row[field] = min(row[field], now - timedelta(minutes=1))

    if attempts:
        quiz_attempts.insert_many(attempts)
    if reads:
        lesson_completions.insert_many(reads)
    if chats:
        chat_history.insert_many(chats)

    # users.points mirrors XP (the chatbot reads it).
    profiles = GamificationEngine(db, now=now).profiles([uid for uid, _ in created])
    for uid, profile in profiles.items():
        users.update_one({"_id": ObjectId(uid)}, {"$set": {"points": profile["xp"]}})

    return {"students": [n for _, n in created], "skipped": skipped, "teacher_note": teacher_note,
            "attempts": len(attempts), "reads": len(reads), "chats": len(chats)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or remove the demo class.")
    parser.add_argument("--remove", action="store_true", help="Delete the demo class.")
    args = parser.parse_args()

    removed = remove()
    if args.remove:
        print("Removed the demo class: " + ", ".join(f"{n} {k}" for k, n in removed.items()) + ".")
        return

    if removed["accounts"]:
        print("Removed the previous demo class first.")
    result = create()
    print(f"Demo class ready: {len(result['students'])} students, {result['reads']} chapters read, "
          f"{result['attempts']} quiz attempts and {result['chats']} chatbot questions "
          f"over the last {DAYS} days.")
    if result["skipped"]:
        print("Skipped (an account with that name already exists): " + ", ".join(result["skipped"]))
    print(result["teacher_note"])
    print(f"Student logins: {', '.join(result['students'])} / {STUDENT_PASSWORD}")
    print("Remove it again with:  python -m backend.seed_demo_class --remove")


if __name__ == "__main__":
    main()
