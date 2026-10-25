"""What-to-study-next rules (Week 8, extended in Week 9)."""

from datetime import datetime, timedelta, timezone

from testkit import answers

NOW = datetime.now(timezone.utc)


def recs(client, user):
    return client.get(f"/api/recommendations/{user['id']}", params={"grade": 6}).json()


def test_new_student_starts_with_chapter_1_of_each_subject(client, register):
    body = recs(client, register("asha"))
    first = body["recommendations"][:4]
    assert [r["lesson_id"] for r in first] == ["g6-eng-1", "g6-math-1", "g6-sci-1", "g6-tel-1"]
    assert all(r["kind"] == "next_chapter" for r in first)


def test_read_but_not_tested_suggests_the_quiz(client, register):
    user = register("asha")
    client.post("/api/lessons/g6-sci-4/complete", json={"user_id": user["id"]})
    top = recs(client, user)["recommendations"][0]
    assert (top["lesson_id"], top["kind"]) == ("g6-sci-4", "take_quiz")
    assert recs(client, user)["based_on"]["chapters_read"] == 1


def test_failed_quiz_comes_first_with_its_score(client, register):
    user = register("asha")
    client.post("/api/quiz-attempts", json={"user_id": user["id"], "quiz_id": "q-g6-math-5", "answers": answers("q-g6-math-5", 1)})
    top = recs(client, user)["recommendations"][0]
    assert (top["lesson_id"], top["kind"], top["score"]) == ("g6-math-5", "retry", 20)


def test_a_passed_retake_clears_the_retry(client, register):
    user = register("asha")
    for right in (1, 5):
        client.post("/api/quiz-attempts", json={"user_id": user["id"], "quiz_id": "q-g6-math-5", "answers": answers("q-g6-math-5", right)})
    kinds = {r["lesson_id"]: r["kind"] for r in recs(client, user)["recommendations"]}
    assert kinds.get("g6-math-5") != "retry"


def test_repeated_chatbot_questions_suggest_that_chapter(client, register, db):
    user = register("asha")
    for minutes in (5, 10):
        db.chat_history.insert_one({"user_id": user["id"], "message": "how do magnets work",
                                    "lesson_id": "g6-sci-4", "asked_at": NOW - timedelta(minutes=minutes)})
    top = recs(client, user)["recommendations"][0]
    assert (top["lesson_id"], top["kind"]) == ("g6-sci-4", "asked_about")


def test_no_chapter_is_suggested_twice(client, register):
    user = register("asha")
    client.post("/api/lessons/g6-math-5/complete", json={"user_id": user["id"]})
    ids = [r["lesson_id"] for r in recs(client, user)["recommendations"]]
    assert len(ids) == len(set(ids))
