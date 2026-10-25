"""
Textbook order for chapters and quizzes.

Lesson ids end in the chapter number ("g6-math-10"). Sorting them as strings
puts chapter 10 before chapter 2, and the Lessons page numbers chapters by
position, so string order showed the wrong chapter numbers. Everything that
lists chapters sorts with these keys instead.
"""

from __future__ import annotations

import re

SUBJECT_ORDER = {"English": 0, "Mathematics": 1, "Science": 2, "Telugu": 3}


def chapter_number(item_id: str | None) -> int:
    """The trailing number of an id: "g6-math-10" -> 10, "q-g6-sci-2" -> 2."""
    match = re.search(r"(\d+)$", item_id or "")
    return int(match.group(1)) if match else 0


def textbook_order(doc: dict) -> tuple:
    """Sort key: grade, then subject, then chapter number."""
    item_id = doc.get("lesson_id") or doc.get("id")
    return (
        doc.get("grade", 0),
        SUBJECT_ORDER.get(doc.get("subject"), len(SUBJECT_ORDER)),
        doc.get("subject") or "",
        chapter_number(item_id),
    )


def sort_textbook(docs: list[dict]) -> list[dict]:
    return sorted(docs, key=textbook_order)
