"""
Build data/quizzes.json from the quiz bank.

Run from the project root:
    python -m backend.quizzes.build

Then load it into MongoDB:
    python -m backend.seed

Why a build step rather than editing the JSON by hand: in the original quizzes
the correct answer was always the first option, and the quiz page does not
shuffle, so a student could score 100% by always choosing A. Here every
question is written with its answer first (easy to review), and the build
places it at a varied position. Within each quiz the positions cycle through
A-D before repeating, and a fixed seed per chapter means rebuilding gives the
same quiz every time.
"""

from __future__ import annotations

import json
import random
from collections import Counter

from ..content_order import sort_textbook
from ..nlp.config import DATA_DIR
from .english import ENGLISH
from .maths import MATHS
from .model import Q
from .science import SCIENCE
from .telugu import TELUGU

LESSONS_FILE = DATA_DIR / "lessons.json"
QUIZZES_FILE = DATA_DIR / "quizzes.json"

BANK: dict[str, list[Q]] = {**ENGLISH, **MATHS, **SCIENCE, **TELUGU}

QUIZ_TITLE = {"Telugu": "పాఠ్య క్విజ్"}


def check(lesson_id: str, questions: list[Q]) -> list[str]:
    """Return a list of problems with one chapter's questions."""
    problems = []
    texts = set()
    for n, q in enumerate(questions, start=1):
        where = f"{lesson_id} Q{n}"
        if not q.concept.strip():
            problems.append(f"{where}: missing concept")
        if not q.explanation.strip():
            problems.append(f"{where}: missing explanation")
        if len(q.wrong) != 3:
            problems.append(f"{where}: needs exactly 3 wrong options, has {len(q.wrong)}")
        options = [q.answer, *q.wrong]
        if len({o.strip().lower() for o in options}) != len(options):
            problems.append(f"{where}: duplicate options")
        if q.text in texts:
            problems.append(f"{where}: duplicate question")
        texts.add(q.text)
    return problems


def answer_positions(lesson_id: str, count: int) -> list[int]:
    """Correct-answer positions for one quiz: A-D in shuffled order, repeated."""
    rng = random.Random(f"eduquest-{lesson_id}")
    positions: list[int] = []
    while len(positions) < count:
        block = [0, 1, 2, 3]
        rng.shuffle(block)
        positions += block
    return positions[:count]


def build_quiz(lesson: dict, questions: list[Q]) -> dict:
    rng = random.Random(f"eduquest-options-{lesson['id']}")
    positions = answer_positions(lesson["id"], len(questions))

    built = []
    for q, position in zip(questions, positions):
        options = list(q.wrong)
        rng.shuffle(options)
        options.insert(position, q.answer)
        built.append(
            {
                "text": q.text,
                "options": options,
                "correct": position,
                "concept": q.concept,
                "explanation": q.explanation,
            }
        )

    suffix = QUIZ_TITLE.get(lesson["subject"], "Chapter Quiz")
    return {
        "id": f"q-{lesson['id']}",
        "lesson_id": lesson["id"],
        "grade": lesson["grade"],
        "subject": lesson["subject"],
        "language": lesson.get("language", "en"),
        "title": f"{lesson['title']} — {suffix}",
        "questions": built,
    }


def main() -> None:
    with open(LESSONS_FILE, encoding="utf-8") as fh:
        lessons = sort_textbook(json.load(fh))

    problems = []
    missing = [l["id"] for l in lessons if l["id"] not in BANK]
    unknown = [lid for lid in BANK if lid not in {l["id"] for l in lessons}]
    if missing:
        problems.append(f"chapters with no quiz: {', '.join(missing)}")
    if unknown:
        problems.append(f"quizzes for chapters that do not exist: {', '.join(unknown)}")
    for lesson_id, questions in BANK.items():
        problems += check(lesson_id, questions)

    if problems:
        print("Quiz bank has problems - nothing was written:")
        for p in problems:
            print("  -", p)
        raise SystemExit(1)

    quizzes = [build_quiz(l, BANK[l["id"]]) for l in lessons if l["id"] in BANK]

    with open(QUIZZES_FILE, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(quizzes, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    all_questions = [q for quiz in quizzes for q in quiz["questions"]]
    letters = Counter("ABCD"[q["correct"]] for q in all_questions)
    concepts = Counter((quiz["subject"], q["concept"]) for quiz in quizzes for q in quiz["questions"])
    by_subject = Counter(quiz["subject"] for quiz in quizzes)

    print(f"Wrote {len(quizzes)} quizzes, {len(all_questions)} questions to {QUIZZES_FILE.name}")
    print("  quizzes per subject : " + ", ".join(f"{s} {n}" for s, n in sorted(by_subject.items())))
    print("  correct answer is   : " + ", ".join(f"{k} {letters[k]}" for k in "ABCD"))
    print(f"  concepts tagged     : {len(concepts)}")
    print("\nNext: python -m backend.seed")


if __name__ == "__main__":
    main()
