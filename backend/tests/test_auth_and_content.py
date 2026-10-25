"""Accounts, chapters and quizzes."""

from testkit import QUIZZES


# --- accounts ---------------------------------------------------------------

def test_register_creates_a_grade_6_student(client):
    response = client.post("/api/auth/register", json={"username": "asha", "password": "secret123"})
    assert response.status_code == 200
    user = response.json()["user"]
    assert user["grade"] == 6
    assert user["role"] == "student"
    assert "password_hash" not in user


def test_register_rejects_bad_input(client, register):
    register("asha")
    assert client.post("/api/auth/register", json={"username": "asha", "password": "secret123"}).status_code == 409
    assert client.post("/api/auth/register", json={"username": "ravi", "password": "secret123", "grade": 7}).status_code == 400
    assert client.post("/api/auth/register", json={"username": "ravi", "password": "secret123", "language": "fr"}).status_code == 400
    assert client.post("/api/auth/register", json={"username": "ravi", "password": "123"}).status_code == 422
    assert client.post("/api/auth/register", json={"username": "ab", "password": "secret123"}).status_code == 422


def test_sign_up_cannot_make_a_teacher(client):
    response = client.post("/api/auth/register",
                           json={"username": "sneaky", "password": "secret123", "role": "teacher"})
    assert response.json()["user"]["role"] == "student"


def test_login(client, register):
    register("asha", password="secret123")
    assert client.post("/api/auth/login", json={"username": "asha", "password": "secret123"}).status_code == 200
    assert client.post("/api/auth/login", json={"username": "asha", "password": "wrong-one"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "nobody", "password": "secret123"}).status_code == 401


def test_teacher_login_reports_the_role(client, teacher):
    user = client.post("/api/auth/login", json={"username": "mrs_rao", "password": "secret123"}).json()["user"]
    assert user["role"] == "teacher"


def test_passwords_are_salted_hashes(db, register):
    register("asha", password="secret123")
    register("ravi", password="secret123")
    hashes = [u["password_hash"] for u in db.users.find()]
    assert all("secret123" not in h for h in hashes)
    assert hashes[0] != hashes[1]  # same password, different salt


def test_change_language(client, register):
    user = register("asha")
    response = client.patch(f"/api/auth/profile/{user['id']}", json={"language": "te"})
    assert response.status_code == 200
    assert response.json()["user"]["language"] == "te"
    assert client.patch(f"/api/auth/profile/{user['id']}", json={"language": "xx"}).status_code == 400
    assert client.patch("/api/auth/profile/not-an-id", json={"language": "te"}).status_code == 400


# --- chapters and quizzes ---------------------------------------------------------

def test_all_40_chapters_in_textbook_order(client):
    lessons = client.get("/api/lessons", params={"grade": 6}).json()
    assert len(lessons) == 40
    maths = [l["id"] for l in lessons if l["subject"] == "Mathematics"]
    assert maths == [f"g6-math-{n}" for n in range(1, 11)]  # 10 after 9, not after 1
    subjects = [l["subject"] for l in lessons]
    assert subjects.index("English") < subjects.index("Mathematics") < subjects.index("Science") < subjects.index("Telugu")


def test_subject_filter_returns_only_that_subject(client):
    science = client.get("/api/lessons", params={"grade": 6, "subject": "Science"}).json()
    assert len(science) == 12
    assert {l["subject"] for l in science} == {"Science"}


def test_unknown_chapter_is_404(client):
    assert client.get("/api/lessons/g6-math-1").status_code == 200
    assert client.get("/api/lessons/g7-math-1").status_code == 404
    assert client.get("/api/quizzes/q-g7-math-1").status_code == 404


def test_every_chapter_has_a_quiz(client):
    lessons = {l["id"] for l in client.get("/api/lessons").json()}
    quizzes = client.get("/api/quizzes").json()
    assert {q["lesson_id"] for q in quizzes} == lessons


def test_quiz_answers_are_not_sent_to_the_browser(client):
    for quiz in client.get("/api/quizzes").json():
        for question in quiz["questions"]:
            assert "correct" not in question
            assert "explanation" not in question
    one = client.get("/api/quizzes/q-g6-sci-1").json()
    assert all("correct" not in q for q in one["questions"])


def test_quiz_bank_is_well_formed():
    assert len(QUIZZES) == 40
    positions = []
    for quiz in QUIZZES:
        for q in quiz["questions"]:
            assert len(q["options"]) == 4
            assert len(set(q["options"])) == 4, q["text"]
            assert 0 <= q["correct"] <= 3
            assert q["concept"] and q["explanation"]
            positions.append(q["correct"])
    # Correct answers are spread across A-D: always picking one letter cannot pass.
    for letter in range(4):
        assert 0.18 < positions.count(letter) / len(positions) < 0.32
