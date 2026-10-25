"""Quiz scoring and the gamification rules (XP, levels, streaks, badges, leaderboard)."""

from datetime import datetime, timedelta, timezone

import pytest

from backend.gamification.engine import (
    IST,
    XP_DAILY,
    XP_FIRST_PASS,
    XP_PER_CORRECT,
    XP_PER_LESSON,
    XP_PERFECT,
    GamificationEngine,
    level_info,
)
from testkit import ANSWER_KEY, answers

QUIZ = "q-g6-sci-1"            # 5 questions
LESSON = "g6-sci-1"


def submit(client, user, quiz_id, chosen):
    response = client.post("/api/quiz-attempts", json={"user_id": user["id"], "quiz_id": quiz_id, "answers": chosen})
    assert response.status_code == 200, response.text
    return response.json()


# --- quiz scoring -----------------------------------------------------------

def test_quiz_is_scored_on_the_server_with_a_review(client, register, db):
    user = register("asha")
    result = submit(client, user, QUIZ, answers(QUIZ, 3))
    assert (result["correct"], result["total"], result["score"]) == (3, 5, 60)
    review = result["review"]
    assert [r["is_correct"] for r in review] == [True, True, True, False, False]
    assert all(r["explanation"] and r["concept"] for r in review)
    assert review[3]["correct"] == ANSWER_KEY[QUIZ][3]

    stored = db.quiz_attempts.find_one({"user_id": user["id"]})
    assert stored["score"] == 60 and stored["lesson_id"] == LESSON and stored["subject"] == "Science"
    # Per-question results are kept for the teacher's weak-concept view.
    assert [r["correct"] for r in stored["results"]] == [True, True, True, False, False]


def test_blank_and_missing_answers_count_as_wrong(client, register):
    user = register("asha")
    key = ANSWER_KEY[QUIZ]
    result = submit(client, user, QUIZ, [key[0], -1])       # 1 right, 1 blank, 3 missing
    assert result["correct"] == 1 and result["score"] == 20
    assert result["review"][1]["chosen"] == -1


def test_unknown_quiz_is_404(client, register):
    user = register("asha")
    response = client.post("/api/quiz-attempts", json={"user_id": user["id"], "quiz_id": "q-g7-sci-1", "answers": [0]})
    assert response.status_code == 404


def test_progress_counts(client, register):
    user = register("asha")
    client.post(f"/api/lessons/{LESSON}/complete", json={"user_id": user["id"]})
    submit(client, user, QUIZ, answers(QUIZ, 5))
    submit(client, user, QUIZ, answers(QUIZ, 3))
    progress = client.get(f"/api/progress/{user['id']}").json()
    assert progress == {"lessons_completed": 1, "quiz_attempts": 2, "average_score": 80}


# --- XP -------------------------------------------------------------------------

def test_reading_a_chapter_earns_xp_once(client, register):
    user = register("asha")
    first = client.post(f"/api/lessons/{LESSON}/complete", json={"user_id": user["id"]}).json()
    again = client.post(f"/api/lessons/{LESSON}/complete", json={"user_id": user["id"]}).json()
    second = client.post("/api/lessons/g6-sci-2/complete", json={"user_id": user["id"]}).json()
    assert first["xp_gained"] == XP_PER_LESSON + XP_DAILY          # first activity today
    assert again["already_completed"] and again["xp_gained"] == 0
    assert second["xp_gained"] == XP_PER_LESSON                     # daily bonus already counted
    assert "first-chapter" in [b["id"] for b in first["new_badges"]]
    assert client.post("/api/lessons/g7-sci-1/complete", json={"user_id": user["id"]}).status_code == 404


def test_quiz_xp_cannot_be_farmed_but_improvement_counts(client, register, db):
    user = register("asha")
    first = submit(client, user, QUIZ, answers(QUIZ, 3))["gamification"]
    assert first["xp_gained"] == 3 * XP_PER_CORRECT + XP_FIRST_PASS + XP_DAILY

    same = submit(client, user, QUIZ, answers(QUIZ, 3))["gamification"]
    assert same["xp_gained"] == 0                                    # no XP for repeating

    better = submit(client, user, QUIZ, answers(QUIZ, 5))["gamification"]
    assert better["xp_gained"] == 2 * XP_PER_CORRECT + XP_PERFECT    # only the 2 new correct answers
    assert "perfect-score" in [b["id"] for b in better["new_badges"]]

    # users.points mirrors XP (the chatbot reads it for "how many points do I have").
    assert db.users.find_one({"username": "asha"})["points"] == better["xp"]


def test_comeback_badge_after_passing_a_failed_quiz(client, register):
    user = register("asha")
    submit(client, user, QUIZ, answers(QUIZ, 1))
    result = submit(client, user, QUIZ, answers(QUIZ, 4))["gamification"]
    assert "comeback" in [b["id"] for b in result["new_badges"]]


def test_levels_every_150_xp():
    assert level_info(0)["level"] == 1
    assert level_info(149)["level"] == 1
    assert level_info(150)["level"] == 2
    assert level_info(225)["pct"] == 50
    assert level_info(10_000)["title"] == "Legend"       # titles stop at the last one


# --- streaks (days in Indian Standard Time) -------------------------------------

def _read_at(db, user_id, lesson_id, moment):
    db.lesson_completions.insert_one({"user_id": user_id, "lesson_id": lesson_id, "completed_at": moment})


def ist(y, m, d, hh, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=IST).astimezone(timezone.utc)


def test_streak_follows_indian_days_not_utc(db):
    # 23:50 and 00:10 IST are 20 minutes apart but on two different days in India,
    # while both fall on the same UTC day (18:20 and 18:40 UTC).
    _read_at(db, "u1", "g6-sci-1", ist(2026, 10, 20, 23, 50))
    _read_at(db, "u1", "g6-sci-2", ist(2026, 10, 21, 0, 10))
    profile = GamificationEngine(db, now=ist(2026, 10, 21, 9)).profile("u1")
    assert profile["streak"]["current"] == 2
    assert profile["xp"] == 2 * XP_PER_LESSON + 2 * XP_DAILY


def test_streak_survives_until_the_end_of_the_next_day_then_resets(db):
    for day in (18, 19, 20):
        _read_at(db, "u1", f"g6-eng-{day - 17}", ist(2026, 10, day, 18))
    assert GamificationEngine(db, now=ist(2026, 10, 21, 22)).profile("u1")["streak"]["current"] == 3
    gone = GamificationEngine(db, now=ist(2026, 10, 22, 8)).profile("u1")["streak"]
    assert gone["current"] == 0 and gone["best"] == 3


def test_streak_badge(db):
    for day in range(1, 4):
        _read_at(db, "u1", f"g6-eng-{day}", ist(2026, 10, day, 18))
    badges = {b["id"]: b for b in GamificationEngine(db, now=ist(2026, 10, 3, 20)).profile("u1")["badges"]}
    assert badges["streak-3"]["earned"]
    assert not badges["streak-7"]["earned"] and badges["streak-7"]["progress"] == 3


# --- leaderboard and rewards ---------------------------------------------------

def test_leaderboard_ranks_by_xp_with_ties_and_no_teachers(client, register, teacher):
    a, b, c = register("asha"), register("ravi"), register("meena")
    for user in (a, b):
        client.post(f"/api/lessons/{LESSON}/complete", json={"user_id": user["id"]})
    client.post("/api/lessons/g6-sci-2/complete", json={"user_id": a["id"]})

    board = client.get("/api/leaderboard", params={"grade": 6, "user_id": b["id"]}).json()
    rows = [(r["rank"], r["username"], r["xp"]) for r in board["top"]]
    assert rows == [(1, "asha", 50), (2, "ravi", 30), (3, "meena", 0)]
    assert board["you"]["username"] == "ravi"
    assert board["students"] == 3                                # the teacher is not ranked

    client.post("/api/lessons/g6-sci-2/complete", json={"user_id": b["id"]})
    tied = client.get("/api/leaderboard", params={"grade": 6}).json()["top"]
    assert [(r["rank"], r["xp"]) for r in tied] == [(1, 50), (1, 50), (3, 0)]   # equal XP shares a rank


def test_reward_avatars_unlock_with_levels(client, register):
    user = register("asha")
    assert client.patch(f"/api/auth/profile/{user['id']}", json={"avatar": "🦅"}).status_code == 403
    for n in range(1, 8):                                       # 7 chapters = 150 XP -> level 2
        client.post(f"/api/lessons/g6-eng-{n}/complete", json={"user_id": user["id"]})
    assert client.get(f"/api/gamification/{user['id']}").json()["level"] == 2
    assert client.patch(f"/api/auth/profile/{user['id']}", json={"avatar": "🦅"}).status_code == 200
    assert client.patch(f"/api/auth/profile/{user['id']}", json={"avatar": "👑"}).status_code == 403


@pytest.mark.parametrize("right,passed", [(2, False), (3, True)])
def test_pass_mark_is_60_percent(client, register, right, passed):
    user = register("asha")
    profile = submit(client, user, QUIZ, answers(QUIZ, right))
    stats = client.get(f"/api/gamification/{user['id']}").json()["stats"]
    assert (stats["quizzes_passed"] == 1) is passed
    assert profile["score"] == right * 20


# --- data for the home and chapters pages (Week 10 redesign) ------------------------

def test_week_strip_marks_active_days(db):
    _read_at(db, "u1", "g6-eng-1", ist(2026, 10, 20, 18))
    _read_at(db, "u1", "g6-eng-2", ist(2026, 10, 22, 7))
    week = GamificationEngine(db, now=ist(2026, 10, 22, 9)).profile("u1")["week"]
    assert [d["date"] for d in week] == [f"2026-10-{n}" for n in range(16, 23)]
    assert [d["active"] for d in week] == [False, False, False, False, True, False, True]


def test_subject_report_and_chapter_marks(client, register):
    user = register("asha")
    client.post("/api/lessons/g6-sci-1/complete", json={"user_id": user["id"]})
    client.post("/api/lessons/g6-sci-2/complete", json={"user_id": user["id"]})
    submit(client, user, QUIZ, answers(QUIZ, 5))
    submit(client, user, QUIZ, answers(QUIZ, 2))                      # latest 40, best 100
    submit(client, user, "q-g6-math-1", answers("q-g6-math-1", 3))
    profile = client.get(f"/api/gamification/{user['id']}").json()

    report = {r["subject"]: r for r in profile["subjects"]}
    assert list(report) == ["English", "Mathematics", "Science", "Telugu"]
    assert report["Science"] == {"subject": "Science", "chapters": 12, "read": 2, "quizzes_taken": 1,
                                 "quizzes_passed": 1, "average": 40}
    assert report["Mathematics"]["average"] == 60 and report["Mathematics"]["read"] == 0
    assert report["English"]["average"] is None

    marks = profile["quiz_marks"]
    assert marks[LESSON] == {"latest": 40, "best": 100, "attempts": 2, "passed": True}
    assert marks["g6-math-1"]["latest"] == 60
