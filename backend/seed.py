import json
from pathlib import Path
from .database import lessons, quizzes, users, ensure_indexes

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def load():
    with open(DATA_DIR / "lessons.json", encoding="utf-8") as f:
        lesson_data = json.load(f)

    with open(DATA_DIR / "quizzes.json", encoding="utf-8") as f:
        quiz_data = json.load(f)

    lessons.delete_many({})
    quizzes.delete_many({})

    if lesson_data:
        lessons.insert_many(lesson_data)

    if quiz_data:
        quizzes.insert_many(quiz_data)

    ensure_indexes()

    print(f"Inserted {len(lesson_data)} lessons and {len(quiz_data)} quizzes.")

    # The project covers Grade 6 only. Accounts created when Grade 7 existed
    # would otherwise see no chapters at all.
    moved = users.update_many({"grade": {"$ne": 6}}, {"$set": {"grade": 6}})
    if moved.modified_count:
        print(f"Moved {moved.modified_count} existing account(s) to Grade 6.")


if __name__ == "__main__":
    load()