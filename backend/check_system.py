"""
Week 10 - End-to-end system check.

    python -m backend.check_system        (from the project root, with MongoDB running)

Runs the real app - your MongoDB, the trained intent classifier, the lesson
index and the answer model - through what a student and a teacher actually do.
It uses FastAPI's test client, so the uvicorn server does not need to be
running (it is fine if it is).

  1. Setup        database reachable, chapters and quizzes seeded, model files present
  2. Student      a temporary student registers, logs in, reads a chapter,
                  fails its quiz, retakes it and passes with 100%
  3. Gamification XP, level, badges and the leaderboard agree with the rules
  4. Next steps   recommendations react to what the student did
  5. Chatbot      a textbook fact, a calculation, a Telugu question, an
                  explanation, an off-topic question and a progress question
  6. Teacher      a temporary teacher sees the student on the class dashboard
                  with the same numbers
  7. Clean-up     everything the check created is deleted again

The results are printed and saved to data/processed/system_check.md.
"""

from __future__ import annotations

import secrets
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

from .gamification.engine import IST

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORT = PROJECT_ROOT / "data" / "processed" / "system_check.md"
REQUIRED_FILES = [
    "data/processed/intent_classifier.pt",
    "data/processed/intent_labels.json",
    "data/processed/lesson_embeddings.npy",
    "data/processed/lesson_index_meta.json",
]

LESSON = "g6-sci-5"            # Measurement of Length and Motion
QUIZ = "q-g6-sci-5"

# message, what must be true of the reply, description
CHAT = [
    ("What is the SI unit of length?",
     lambda r, ctx: r["answer"] is not None and "metre" in r["answer"]["text"].lower(),
     "textbook fact: exact answer 'metre'"),
    ("what is 1/3 + 1/6",
     lambda r, ctx: r["intent"] == "calculation" and r["answer"]["text"].endswith("1/2"),
     "calculation: 1/2 with working"),
    ("రైతు ఏమి చేస్తాడు?",
     lambda r, ctx: r["intent"] == "telugu_question" and (r["lesson"] or {}).get("id") == "g6-tel-1",
     "Telugu: answered from అభినందన"),
    ("explain lines and angles",
     lambda r, ctx: (r["lesson"] or {}).get("id") == "g6-math-2" and r["answer"] is None,
     "explanation: points to Lines and Angles"),
    ("who won the cricket match",
     lambda r, ctx: r["intent"] == "out_of_scope" and r["answer"] is None,
     "off-topic: politely declined"),
    ("how many points do I have",
     lambda r, ctx: r["intent"] == "progress_help" and str(ctx["xp"]) in r["reply"],
     "progress: quotes the student's XP"),
]


class Checker:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, bool, str, float]] = []
        self.section = ""

    def start(self, section: str) -> None:
        self.section = section
        print(f"\n{section}")

    def check(self, name: str, ok: bool, detail: str = "", seconds: float = 0.0) -> bool:
        self.rows.append((self.section, name, bool(ok), detail, seconds))
        timing = f"  ({seconds:.1f}s)" if seconds >= 0.5 else ""
        print(f"  {'PASS' if ok else 'FAIL'}  {name}{timing}")
        if detail and not ok:
            print(f"        {detail}")
        return bool(ok)

    @property
    def failed(self) -> list:
        return [r for r in self.rows if not r[2]]


def timed(fn):
    start = time.perf_counter()
    result = fn()
    return result, time.perf_counter() - start


def run(c: Checker, chat_log: list) -> None:
    from fastapi.testclient import TestClient

    from .database import client as mongo, db
    from .main import app
    from .routes.auth import hash_password

    # 1. Setup ------------------------------------------------------------------
    c.start("1. Setup")
    try:
        mongo.admin.command("ping")
        c.check("MongoDB is reachable", True)
    except Exception as exc:
        c.check("MongoDB is reachable", False, f"{exc}. Start MongoDB and try again.")
        return
    lessons, quizzes = db["lessons"].count_documents({"grade": 6}), db["quizzes"].count_documents({"grade": 6})
    c.check("40 chapters and 40 quizzes are seeded", lessons == 40 and quizzes == 40,
            f"found {lessons} chapters and {quizzes} quizzes - run: python -m backend.seed")
    missing = [f for f in REQUIRED_FILES if not (PROJECT_ROOT / f).exists()]
    c.check("trained model files are present", not missing, f"missing: {', '.join(missing)}")

    tag = secrets.token_hex(3)
    names = {"student": f"check_{tag}", "teacher": f"check_teacher_{tag}"}
    created: list[str] = []
    try:
        with TestClient(app) as api:
            student_flow(c, api, db, names, created, hash_password, chat_log)
    finally:
        # 7. Clean-up --------------------------------------------------------------
        c.start("7. Clean-up")
        from bson import ObjectId
        for collection in ("quiz_attempts", "lesson_completions", "chat_history"):
            db[collection].delete_many({"user_id": {"$in": created}})
        db["users"].delete_many({"_id": {"$in": [ObjectId(i) for i in created]}})
        left = db["users"].count_documents({"username": {"$in": list(names.values())}})
        c.check("temporary accounts and their data deleted", left == 0)


def student_flow(c, api, db, names, created, hash_password, chat_log) -> None:
    # 2. Student ------------------------------------------------------------------
    c.start("2. Student")
    password = "check-" + secrets.token_hex(4)
    r = api.post("/api/auth/register", json={"username": names["student"], "password": password})
    if not c.check("register", r.status_code == 200, r.text):
        return
    student = r.json()["user"]
    created.append(student["id"])
    r = api.post("/api/auth/login", json={"username": names["student"], "password": password})
    c.check("log in", r.status_code == 200 and r.json()["user"]["role"] == "student", r.text)

    lessons = api.get("/api/lessons", params={"grade": 6}).json()
    c.check("chapter list (40, textbook order)",
            len(lessons) == 40 and lessons[0]["id"] == "g6-eng-1", f"{len(lessons)} chapters")
    lesson = api.get(f"/api/lessons/{LESSON}").json()
    c.check("open a chapter", lesson.get("title") == "Measurement of Length and Motion", str(lesson.get("title")))

    read = api.post(f"/api/lessons/{LESSON}/complete", json={"user_id": student["id"]}).json()
    c.check("mark it as read: +30 XP (20 + daily 10)", read.get("xp_gained") == 30, str(read))

    quiz = api.get(f"/api/quizzes/{QUIZ}").json()
    c.check("quiz arrives without its answers", all("correct" not in q for q in quiz["questions"]))
    key = [q["correct"] for q in db["quizzes"].find_one({"id": QUIZ})["questions"]]
    wrong = [k if i < 2 else (k + 1) % 4 for i, k in enumerate(key)]
    first = api.post("/api/quiz-attempts", json={"user_id": student["id"], "quiz_id": QUIZ, "answers": wrong}).json()
    c.check("first attempt scored 40% with a review", first.get("score") == 40 and len(first.get("review", [])) == len(key),
            str(first.get("score")))

    # 3. Gamification ----------------------------------------------------------------
    c.start("3. Gamification")
    c.check("40% earns +20 XP (2 correct answers, no pass bonus)", first["gamification"]["xp_gained"] == 20,
            str(first["gamification"]))
    recs = api.get(f"/api/recommendations/{student['id']}", params={"grade": 6}).json()["recommendations"]
    retry_first = bool(recs) and recs[0]["lesson_id"] == LESSON and recs[0]["kind"] == "retry"

    second = api.post("/api/quiz-attempts", json={"user_id": student["id"], "quiz_id": QUIZ, "answers": key}).json()
    game = second["gamification"]
    c.check("retake at 100%: +80 XP (3 new correct, pass, perfect)", game["xp_gained"] == 80, str(game))
    earned = {b["id"] for b in game["new_badges"]}
    c.check("badges: perfect score and comeback", {"perfect-score", "comeback"} <= earned, str(earned))
    profile = api.get(f"/api/gamification/{student['id']}").json()
    c.check("total 130 XP, level 1, 20 XP to level 2", (profile["xp"], profile["level"]) == (130, 1),
            f"xp {profile['xp']}, level {profile['level']}")
    c.check("streak started today", profile["streak"]["current"] == 1 and profile["streak"]["active_today"])
    board = api.get("/api/leaderboard", params={"grade": 6, "user_id": student["id"]}).json()
    c.check("on the leaderboard with the same XP", board["you"] and board["you"]["xp"] == 130, str(board["you"]))

    # 4. Recommendations ---------------------------------------------------------------
    c.start("4. Next steps")
    c.check("after the failed quiz: 'try again' comes first", retry_first, str(recs[:1]))
    recs = api.get(f"/api/recommendations/{student['id']}", params={"grade": 6}).json()["recommendations"]
    c.check("after passing: no retry, unread chapters suggested",
            recs and all(r["kind"] != "retry" for r in recs), str([r["kind"] for r in recs]))

    # 5. Chatbot -------------------------------------------------------------------------
    c.start("5. Chatbot (the first question loads the models)")
    status = api.get("/api/chat/status").json()
    c.check("classifier and lesson index ready", status["classifier_ready"] and status["lesson_index_ready"], str(status))
    context = {"xp": profile["xp"]}
    for message, expect, label in CHAT:
        response, seconds = timed(lambda: api.post("/api/chat", json={
            "message": message, "user_id": student["id"], "grade": 6}))
        if response.status_code != 200:
            c.check(label, False, f"HTTP {response.status_code}: {response.text[:200]}", seconds)
            continue
        body = response.json()
        try:
            ok = expect(body, context)
        except Exception:  # a missing field counts as a failure, not a crash
            ok = False
        c.check(label, ok, f"intent {body['intent']}, answer {body.get('answer')}, reply {body['reply'][:120]}", seconds)
        chat_log.append((message, body, seconds))

    # 6. Teacher ----------------------------------------------------------------------------
    c.start("6. Teacher")
    teacher_id = str(db["users"].insert_one({
        "username": names["teacher"], "password_hash": hash_password("check-teacher"),
        "grade": 6, "language": "en", "points": 0, "role": "teacher"}).inserted_id)
    created.append(teacher_id)
    r = api.post("/api/auth/login", json={"username": names["teacher"], "password": "check-teacher"})
    c.check("teacher logs in as a teacher", r.status_code == 200 and r.json()["user"]["role"] == "teacher")
    c.check("students cannot open the class dashboard",
            api.get("/api/teacher/class", params={"teacher_id": student["id"]}).status_code == 403)
    report, seconds = timed(lambda: api.get("/api/teacher/class", params={"teacher_id": teacher_id}).json())
    row = next((s for s in report.get("students", []) if s["user_id"] == student["id"]), None)
    c.check("class dashboard loads and lists the student", row is not None, "", seconds)
    if row:
        c.check("same numbers: 1 chapter, 1 quiz, 2 attempts, 100% (latest), 130 XP",
                (row["chapters_read"], row["quizzes_taken"], row["quiz_attempts"], row["average_score"], row["xp"])
                == (1, 1, 2, 100, 130), str({k: row[k] for k in ("chapters_read", "quizzes_taken", "quiz_attempts", "average_score", "xp")}))
        c.check(f"chatbot questions counted ({len(CHAT)})", row["chat_questions"] == len(CHAT), str(row["chat_questions"]))
    detail = api.get(f"/api/teacher/students/{student['id']}", params={"teacher_id": teacher_id})
    c.check("student detail opens", detail.status_code == 200 and len(detail.json()["recent_attempts"]) == 2)


def write_report(c: Checker, chat_log: list) -> None:
    now = datetime.now(IST).strftime("%d %b %Y, %H:%M IST")
    passed = len(c.rows) - len(c.failed)
    lines = [
        "# System check",
        "",
        f"Run on {now} with `python -m backend.check_system`: the real MongoDB and the",
        "real models, driven through the API the way a student and a teacher use the app.",
        "",
        f"**{passed} of {len(c.rows)} checks passed.**",
        "",
        "| Step | Check | Result | Time |",
        "|---|---|---|---|",
    ]
    for section, name, ok, detail, seconds in c.rows:
        note = "" if ok else f" ({detail[:150]})".replace("|", "/")
        lines.append(f"| {section} | {name}{note} | {'PASS' if ok else 'FAIL'} | {seconds:.1f}s |" if seconds >= 0.05
                     else f"| {section} | {name}{note} | {'PASS' if ok else 'FAIL'} | |")
    if chat_log:
        lines += ["", "## Chatbot replies", ""]
        for message, body, seconds in chat_log:
            answer = body.get("answer") or {}
            lines += [f"**Q:** {message}  ",
                      f"intent `{body['intent']}` ({body['confidence']:.0%}), "
                      f"{'answer **' + answer['text'] + '**, ' if answer else ''}{seconds:.1f}s  ",
                      f"> {body['reply'][:300]}".replace("\n", " "), ""]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    print("=" * 72)
    print("EDUQUEST SYSTEM CHECK  (real database, real models)")
    print("=" * 72)
    c = Checker()
    chat_log: list = []
    try:
        run(c, chat_log)
    except Exception:
        c.check("the check itself ran to the end", False, traceback.format_exc(limit=3))
    write_report(c, chat_log)
    print("\n" + "-" * 72)
    passed = len(c.rows) - len(c.failed)
    try:
        where = REPORT.relative_to(PROJECT_ROOT)
    except ValueError:
        where = REPORT
    print(f"{passed} of {len(c.rows)} checks passed.  Report: {where}")
    if c.failed:
        print("Failed:")
        for section, name, _ok, detail, _s in c.failed:
            print(f"  - [{section}] {name}")
    return 0 if not c.failed else 1


if __name__ == "__main__":
    sys.exit(main())
