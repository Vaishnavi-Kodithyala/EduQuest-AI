"""
Shared setup for the automated tests.

    python -m pytest            (from the project root)

The tests run against an in-memory MongoDB (mongomock), so they need neither a
running database nor the AI models, and the whole suite takes seconds. The
real database and the models are checked by

    python -m backend.check_system       the whole app, end to end
    python -m backend.nlp.test_answers   chatbot answer accuracy

`backend.database` connects to MongoDB when imported, so it is replaced here,
before any test imports the app, by a module with the same collection names
backed by mongomock.
"""

from __future__ import annotations

import sys
import types

import mongomock
import pytest

COLLECTIONS = ("users", "lessons", "quizzes", "quiz_attempts", "progress",
               "lesson_completions", "chat_history")

_client = mongomock.MongoClient()
_db = _client["eduquest_test"]


def _ensure_indexes() -> None:
    _db.users.create_index("username", unique=True)
    _db.lesson_completions.create_index([("user_id", 1), ("lesson_id", 1)], unique=True)


_fake = types.ModuleType("backend.database")
_fake.client = _client
_fake.db = _db
_fake.ensure_indexes = _ensure_indexes
for _name in COLLECTIONS:
    setattr(_fake, _name, _db[_name])
sys.modules["backend.database"] = _fake

# The tests never run the English NLP pipeline (it needs the models), but the
# chat route imports it, and it imports spaCy. Where spaCy is not installed,
# a stand-in lets the rest of the suite run.
try:
    import spacy  # noqa: F401
except ImportError:
    _pipeline = types.ModuleType("backend.nlp.pipeline")

    def _no_pipeline():
        raise RuntimeError("spaCy is not installed")

    _pipeline.get_pipeline = _no_pipeline
    sys.modules["backend.nlp.pipeline"] = _pipeline

from testkit import LESSONS, QUIZZES  # noqa: E402


@pytest.fixture
def db():
    """A fresh database with the 40 Grade 6 chapters and their quizzes."""
    # Emptied rather than dropped: the app modules hold these collection objects.
    for name in COLLECTIONS:
        _db[name].delete_many({})
    _ensure_indexes()
    _db.lessons.insert_many([dict(l) for l in LESSONS])
    _db.quizzes.insert_many([dict(q) for q in QUIZZES])
    return _db


@pytest.fixture
def client(db):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.routes import auth, chat, content, gamification, quiz, recommend, teacher

    app = FastAPI()
    for module in (auth, content, quiz, gamification, recommend, teacher, chat):
        app.include_router(module.router, prefix="/api")
    return TestClient(app)


@pytest.fixture
def register(client):
    """Register a student through the API and return the public user."""
    def make(username: str, password: str = "secret123", **extra) -> dict:
        response = client.post("/api/auth/register",
                               json={"username": username, "password": password, **extra})
        assert response.status_code == 200, response.text
        return response.json()["user"]
    return make


@pytest.fixture
def teacher(db):
    """A teacher account, created the way backend.create_teacher does it."""
    from backend.routes.auth import hash_password

    result = db.users.insert_one({"username": "mrs_rao", "password_hash": hash_password("secret123"),
                                  "grade": 6, "language": "en", "points": 0, "role": "teacher"})
    return {"id": str(result.inserted_id), "username": "mrs_rao"}

