"""Teacher dashboard: access, the latest-attempt rule, flags, weak concepts, trend days, demo class."""

from datetime import datetime, timedelta, timezone

import pytest

from backend import seed_demo_class
from backend.gamification.engine import IST, ist_day
from backend.teacher.analytics import TeacherAnalytics
from testkit import QUIZZES

NOW = datetime(2026, 10, 22, 11, 0, tzinfo=timezone.utc)          # 16:30 IST
QUIZ = {q["id"]: q for q in QUIZZES}


def student(db, name, **extra):
    return str(db.users.insert_one({"username": name, "password_hash": "x", "grade": 6,
                                    "language": "en", "role": "student", **extra}).inserted_id)


def attempt(db, user_id, quiz_id, right, when, wrong_concepts=()):
    """Store an attempt the way POST /quiz-attempts does, with chosen questions wrong."""
    questions = QUIZ[quiz_id]["questions"]
    results = []
    for i, q in enumerate(questions):
        ok = i < right and q["concept"] not in wrong_concepts
        results.append({"concept": q["concept"], "correct": ok})
    correct = sum(r["correct"] for r in results)
    db.quiz_attempts.insert_one({
        "user_id": user_id, "quiz_id": quiz_id, "lesson_id": QUIZ[quiz_id]["lesson_id"],
        "subject": QUIZ[quiz_id]["subject"], "results": results, "correct": correct,
        "total": len(questions), "score": round(correct * 100 / len(questions)), "submitted_at": when,
    })


def report(db):
    return TeacherAnalytics(db, now=NOW).class_report(grade=6)


def row(rep, name):
    return next(r for r in rep["students"] if r["username"] == name)


# --- access --------------------------------------------------------------------

def test_only_teachers_can_open_the_dashboard(client, register, teacher):
    kid = register("asha")
    assert client.get("/api/teacher/class", params={"teacher_id": teacher["id"]}).status_code == 200
    assert client.get("/api/teacher/class", params={"teacher_id": kid["id"]}).status_code == 403
    assert client.get("/api/teacher/class", params={"teacher_id": "nonsense"}).status_code == 400
    assert client.get("/api/teacher/class").status_code == 422
    detail = client.get(f"/api/teacher/students/{kid['id']}", params={"teacher_id": teacher["id"]})
    assert detail.status_code == 200 and detail.json()["username"] == "asha"
    assert client.get(f"/api/teacher/students/{kid['id']}", params={"teacher_id": kid["id"]}).status_code == 403
    # A teacher is not a student in the class.
    assert client.get(f"/api/teacher/students/{teacher['id']}", params={"teacher_id": teacher["id"]}).status_code == 404


def test_empty_class(db, teacher):
    rep = report(db)
    assert rep["overview"]["students"] == 0
    assert rep["overview"]["average_score"] is None
    assert rep["weak_concepts"] == [] and rep["chat"]["questions"] == 0


# --- the latest-attempt rule and flags ---------------------------------------------

def test_scores_use_the_latest_attempt(db):
    uid = student(db, "kiran")
    attempt(db, uid, "q-g6-math-1", 2, NOW - timedelta(days=3))     # 40%
    attempt(db, uid, "q-g6-math-1", 5, NOW - timedelta(days=1))     # 100% on the retake
    r = row(report(db), "kiran")
    assert r["average_score"] == 100
    assert (r["quizzes_taken"], r["quiz_attempts"]) == (1, 2)
    assert r["subjects"]["Mathematics"]["average"] == 100
    assert r["flags"] == []


def test_flags(db):
    low = student(db, "suresh")
    attempt(db, low, "q-g6-math-1", 2, NOW - timedelta(days=1))
    attempt(db, low, "q-g6-sci-1", 1, NOW - timedelta(days=1))
    away = student(db, "meena")
    attempt(db, away, "q-g6-eng-1", 5, NOW - timedelta(days=9))
    student(db, "raju")
    fine = student(db, "asha")
    attempt(db, fine, "q-g6-eng-1", 4, NOW - timedelta(hours=2))

    rep = report(db)
    codes = {r["username"]: [f["code"] for f in r["flags"]] for r in rep["students"]}
    assert codes == {"suresh": ["low_score"], "meena": ["inactive"], "raju": ["not_started"], "asha": []}
    assert rep["overview"]["needs_attention"] == 3
    assert rep["overview"]["active_this_week"] == 2
    assert row(rep, "meena")["days_inactive"] == 9


def test_one_low_quiz_is_not_a_pattern(db):
    uid = student(db, "arjun")
    attempt(db, uid, "q-g6-math-1", 1, NOW - timedelta(days=1))
    assert row(report(db), "arjun")["flags"] == []


# --- weak concepts --------------------------------------------------------------------

def test_weak_concepts_name_the_struggling_students(db):
    quiz = "q-g6-math-5"
    hard = QUIZ[quiz]["questions"][0]["concept"]
    for name in ("a1", "a2", "a3", "a4", "a5"):
        attempt(db, student(db, name), quiz, 5, NOW - timedelta(days=1), wrong_concepts={hard})
    rep = report(db)
    weak = {c["concept"]: c for c in rep["weak_concepts"]}
    assert hard in weak
    assert weak[hard]["accuracy"] == 0
    assert weak[hard]["struggling_names"] == ["a1", "a2", "a3", "a4", "a5"]
    assert weak[hard]["chapter"]["id"] == "g6-math-5"
    # Concepts the class got right are not listed.
    others = {q["concept"] for q in QUIZ[quiz]["questions"]} - {hard}
    assert not others & set(weak)


def test_too_few_answers_are_not_judged(db):
    attempt(db, student(db, "solo"), "q-g6-math-5", 0, NOW - timedelta(days=1))
    assert report(db)["weak_concepts"] == []           # one student, under 5 answers per concept


def test_a_fixed_concept_is_no_longer_weak(db):
    quiz = "q-g6-math-5"
    hard = QUIZ[quiz]["questions"][0]["concept"]
    for name in ("a1", "a2", "a3", "a4", "a5"):
        uid = student(db, name)
        attempt(db, uid, quiz, 5, NOW - timedelta(days=3), wrong_concepts={hard})
        attempt(db, uid, quiz, 5, NOW - timedelta(days=1))           # retake, all right
    assert hard not in {c["concept"] for c in report(db)["weak_concepts"]}


# --- trend -----------------------------------------------------------------------------

def test_trend_days_are_indian_days(db):
    uid = student(db, "asha")
    late = datetime(2026, 10, 21, 23, 50, tzinfo=IST).astimezone(timezone.utc)
    early = datetime(2026, 10, 22, 0, 10, tzinfo=IST).astimezone(timezone.utc)
    attempt(db, uid, "q-g6-eng-1", 5, late)
    attempt(db, uid, "q-g6-eng-2", 0, early)
    points = {p["date"]: p for p in report(db)["trend"]["points"]}
    assert points["2026-10-21"]["attempts"] == 1 and points["2026-10-21"]["average_score"] == 100
    assert points["2026-10-22"]["attempts"] == 1 and points["2026-10-22"]["average_score"] == 0
    assert len(points) == 21


def test_this_week_against_last_week(db):
    uid = student(db, "asha")
    attempt(db, uid, "q-g6-eng-1", 5, NOW - timedelta(days=2))
    attempt(db, uid, "q-g6-eng-2", 3, NOW - timedelta(days=9))
    trend = report(db)["trend"]
    assert trend["this_week"] == {"attempts": 1, "average_score": 100, "students": 1}
    assert trend["last_week"] == {"attempts": 1, "average_score": 60, "students": 1}


def test_old_grade_7_attempts_are_ignored(db):
    uid = student(db, "asha")
    db.quiz_attempts.insert_one({"user_id": uid, "quiz_id": "q-g7-math-1", "score": 0,
                                 "correct": 0, "total": 5, "submitted_at": NOW - timedelta(days=1)})
    r = row(report(db), "asha")
    assert r["quiz_attempts"] == 0 and r["average_score"] is None


# --- chatbot questions ----------------------------------------------------------------

def test_unanswered_questions_are_grouped(db):
    ids = [student(db, n) for n in ("asha", "ravi")]
    for uid in ids:
        db.chat_history.insert_one({"user_id": uid, "message": "when is the exam", "understood": False,
                                    "answered": False, "lesson_id": None, "asked_at": NOW - timedelta(hours=1)})
    db.chat_history.insert_one({"user_id": ids[0], "message": "What is the SI unit of length?", "understood": True,
                                "answered": True, "lesson_id": "g6-sci-5", "asked_at": NOW - timedelta(hours=2)})
    chat = report(db)["chat"]
    assert chat["questions"] == 3 and chat["answered_pct"] == 33
    assert chat["unanswered"] == [{"message": "when is the exam", "times": 2, "students": ["asha", "ravi"],
                                   "last_asked": (NOW - timedelta(hours=1)).isoformat()}]
    assert chat["top_chapters"][0]["id"] == "g6-sci-5"


# --- the demo class -------------------------------------------------------------------

def test_demo_class_figures_add_up_and_remove_cleanly(db):
    real = student(db, "realkid")
    result = seed_demo_class.create(now=NOW)
    assert len(result["students"]) == 12 and result["attempts"] > 50

    rep = report(db)
    assert rep["overview"]["students"] == 13 and rep["overview"]["demo_students"] == 12
    # Recount the class average from the raw attempts.
    latest = {}
    for a in sorted(db.quiz_attempts.find(), key=lambda a: a["submitted_at"]):
        latest[(a["user_id"], a["quiz_id"])] = a["score"]
    assert rep["overview"]["average_score"] == round(sum(latest.values()) / len(latest))
    assert rep["overview"]["quiz_attempts"] == db.quiz_attempts.count_documents({})
    # Nothing is stamped in the future.
    assert all(ist_day(a["submitted_at"]) <= ist_day(NOW) for a in db.quiz_attempts.find())
    # Suresh is the low scorer and raju never started.
    assert [f["code"] for f in row(rep, "suresh")["flags"]] == ["low_score"]
    assert [f["code"] for f in row(rep, "raju")["flags"]] == ["not_started"]

    seed_demo_class.remove()
    assert [u["username"] for u in db.users.find()] == ["realkid"]
    assert db.quiz_attempts.count_documents({}) == 0 and db.chat_history.count_documents({}) == 0
    assert real == str(db.users.find_one()["_id"])


def test_demo_class_skips_names_already_taken(db):
    student(db, "arjun")
    result = seed_demo_class.create(now=NOW)
    assert result["skipped"] == ["arjun"]
    assert db.users.count_documents({"username": "arjun"}) == 1


@pytest.mark.parametrize("args", [["mrs_rao", "--password", "secret99"]])
def test_create_teacher_command(db, monkeypatch, args, capsys):
    from backend import create_teacher
    monkeypatch.setattr("sys.argv", ["create_teacher", *args])
    create_teacher.main()
    assert db.users.find_one({"username": "mrs_rao"})["role"] == "teacher"
    # Running it for an existing student promotes them without touching the password.
    db.users.insert_one({"username": "ravi", "password_hash": "keep", "grade": 6, "language": "en", "role": "student"})
    monkeypatch.setattr("sys.argv", ["create_teacher", "ravi"])
    create_teacher.main()
    ravi = db.users.find_one({"username": "ravi"})
    assert ravi["role"] == "teacher" and ravi["password_hash"] == "keep"
    monkeypatch.setattr("sys.argv", ["create_teacher", "shorty", "--password", "123"])
    with pytest.raises(SystemExit):
        create_teacher.main()
