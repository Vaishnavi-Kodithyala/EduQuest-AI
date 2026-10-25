"""Data and small helpers shared by the tests."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

with open(DATA_DIR / "lessons.json", encoding="utf-8") as f:
    LESSONS = json.load(f)
with open(DATA_DIR / "quizzes.json", encoding="utf-8") as f:
    QUIZZES = json.load(f)

ANSWER_KEY = {q["id"]: [question["correct"] for question in q["questions"]] for q in QUIZZES}


def answers(quiz_id: str, right: int) -> list[int]:
    """Answers to a quiz with the first `right` questions correct and the rest wrong."""
    key = ANSWER_KEY[quiz_id]
    return [c if i < right else (c + 1) % 4 for i, c in enumerate(key)]
