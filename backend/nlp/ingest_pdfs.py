"""
Week 8 - Ingest chapter PDFs into the content bank.

The hand-written summaries in lessons.json are around 800 characters per
chapter. That is enough for the retriever to identify *which* chapter is
relevant, but not enough to actually answer a question - which is why replies
end up saying "open the chapter" instead of explaining anything.

This script reads the real chapter PDFs, splits them into passages, and writes
them to data/chapter_passages.json. The lesson index then embeds those passages
alongside the summaries, so the chatbot can quote real material.

Setup - option A: one PDF per chapter
--------------------------------------
Name each file after the lesson id. Nothing else to configure.

    data/chapters/g6-sci-2.pdf
    data/chapters/g6-math-2.pdf

Setup - option B: whole textbooks with page ranges
---------------------------------------------------
Drop in the full book and add data/chapters/chapter_map.json saying which
pages belong to which lesson. Pages are 1-based and inclusive, matching the
page numbers your PDF viewer shows.

    {
      "g6-math-1": {"pdf": "g6-maths-textbook.pdf", "pages": [1, 18]},
      "g6-math-2": {"pdf": "g6-maths-textbook.pdf", "pages": [19, 34]}
    }

Only the listed page ranges are indexed. This matters: a textbook holds far
more chapters than lessons.json does, and indexing all of them would let the
chatbot quote material the student has no way to open in the app.

Lesson ids are listed in data/lessons.json. Run with --list to see them.

Usage
-----
    python -m backend.nlp.ingest_pdfs --list        # show expected filenames
    python -m backend.nlp.ingest_pdfs               # ingest everything found
    python -m backend.nlp.ingest_pdfs --inspect g6-sci-2   # check one file

Requires: pip install pypdf
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .config import DATA_DIR

CHAPTERS_DIR = DATA_DIR / "chapters"
CHAPTER_MAP_FILE = CHAPTERS_DIR / "chapter_map.json"
LESSONS_FILE = DATA_DIR / "lessons.json"
PASSAGES_FILE = DATA_DIR / "chapter_passages.json"

# Passage sizing. The embedding model truncates at 64 word-pieces, so very long
# passages lose their tail. Around 60 words keeps each passage inside that
# window while still being a complete thought.
TARGET_WORDS = 60
MIN_WORDS = 20
OVERLAP_WORDS = 12

# Lines matching these are page furniture, not content.
NOISE_PATTERNS = [
    re.compile(r"^\s*\d+\s*$"),                    # bare page numbers
    re.compile(r"^\s*page\s+\d+", re.I),
    re.compile(r"^\s*chapter\s+\d+\s*$", re.I),
    re.compile(r"^[\s\-_=•·—–]+$"),                # rules and bullets alone
    re.compile(r"^\s*(reprint|ncert|not to be republished)", re.I),
]


def load_lessons() -> list[dict]:
    with open(LESSONS_FILE, encoding="utf-8") as fh:
        return json.load(fh)


def load_chapter_map() -> dict[str, dict]:
    """Optional lesson id -> {pdf, pages} mapping for whole-textbook PDFs."""
    if not CHAPTER_MAP_FILE.exists():
        return {}
    with open(CHAPTER_MAP_FILE, encoding="utf-8") as fh:
        return json.load(fh)


def resolve_source(lesson_id: str, chapter_map: dict) -> tuple[Path, tuple[int, int] | None] | None:
    """
    Where a lesson's text comes from.

    A chapter_map entry wins over a per-chapter file, so a whole textbook can
    be used for some subjects and individual chapters for others.
    """
    entry = chapter_map.get(lesson_id)
    if entry:
        pdf_path = CHAPTERS_DIR / entry["pdf"]
        pages = entry.get("pages")
        page_range = (int(pages[0]), int(pages[1])) if pages else None
        return (pdf_path, page_range) if pdf_path.exists() else None

    direct = CHAPTERS_DIR / f"{lesson_id}.pdf"
    return (direct, None) if direct.exists() else None


def extract_text(pdf_path: Path, page_range: tuple[int, int] | None = None) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise SystemExit(
            "pypdf is not installed. Run:\n    pip install pypdf"
        )

    reader = PdfReader(str(pdf_path))
    total = len(reader.pages)

    if page_range:
        first, last = page_range
        if first < 1 or last > total or first > last:
            raise SystemExit(
                f"{pdf_path.name} has {total} pages; page range "
                f"{first}-{last} is out of bounds."
            )
        selected = reader.pages[first - 1 : last]
    else:
        selected = reader.pages

    pages = []
    for page in selected:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    return "\n".join(pages)


def clean_text(raw: str) -> str:
    """Drop page furniture, join hyphenated line breaks, normalise whitespace."""
    lines = []
    for line in raw.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if any(pattern.match(stripped) for pattern in NOISE_PATTERNS):
            continue
        lines.append(stripped)

    text = "\n".join(lines)
    # "compre-\nhension" -> "comprehension"
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_passages(text: str) -> list[str]:
    """
    Split into overlapping, sentence-aligned passages.

    Sentence alignment matters because a passage cut mid-sentence embeds badly
    and reads badly when quoted back to a student. The overlap means a fact
    sitting on a boundary still appears whole in one of the two passages.
    """
    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in sentences if s.strip()]

    passages: list[str] = []
    current: list[str] = []
    current_words = 0

    for sentence in sentences:
        words = sentence.split()
        current.append(sentence)
        current_words += len(words)

        if current_words >= TARGET_WORDS:
            passages.append(" ".join(current))
            # Carry the tail forward so boundaries overlap.
            tail: list[str] = []
            tail_words = 0
            for previous in reversed(current):
                tail.insert(0, previous)
                tail_words += len(previous.split())
                if tail_words >= OVERLAP_WORDS:
                    break
            current = tail
            current_words = tail_words

    remainder = " ".join(current).strip()
    if remainder and len(remainder.split()) >= MIN_WORDS:
        if not passages or remainder != passages[-1]:
            passages.append(remainder)

    return passages


def ingest_one(lesson: dict, pdf_path: Path, page_range=None) -> list[dict]:
    raw = extract_text(pdf_path, page_range)
    cleaned = clean_text(raw)
    passages = split_passages(cleaned)

    return [
        {
            "lesson_id": lesson["id"],
            "title": lesson["title"],
            "subject": lesson["subject"],
            "grade": lesson["grade"],
            "language": lesson.get("language", "en"),
            "heading": f"From the chapter (part {i})",
            "text": passage,
            "source": pdf_path.name,
        }
        for i, passage in enumerate(passages, start=1)
    ]


def cmd_list(lessons: list[dict]) -> None:
    chapter_map = load_chapter_map()
    print(f"PDF source for each lesson (in {CHAPTERS_DIR}):\n")
    for lesson in lessons:
        resolved = resolve_source(lesson["id"], chapter_map)
        if resolved is None:
            where = f"missing - expected {lesson['id']}.pdf"
        else:
            pdf_path, page_range = resolved
            where = pdf_path.name
            if page_range:
                where += f" pages {page_range[0]}-{page_range[1]}"
        print(f"  {lesson['id']:<11} g{lesson['grade']} {lesson['subject']:<12} "
              f"{lesson['title'][:34]:<36} {where}")
    if chapter_map:
        print(f"\n  chapter_map.json covers {len(chapter_map)} lessons")


def cmd_inspect(lessons: list[dict], lesson_id: str) -> None:
    lesson = next((l for l in lessons if l["id"] == lesson_id), None)
    if lesson is None:
        raise SystemExit(f"No lesson with id '{lesson_id}'. Use --list.")

    resolved = resolve_source(lesson_id, load_chapter_map())
    if resolved is None:
        raise SystemExit(
            f"No PDF for {lesson_id}. Expected {CHAPTERS_DIR / (lesson_id + '.pdf')} "
            f"or an entry in chapter_map.json."
        )
    pdf_path, page_range = resolved

    raw = extract_text(pdf_path, page_range)
    cleaned = clean_text(raw)
    passages = split_passages(cleaned)

    print(f"File      : {pdf_path.name}"
          + (f" pages {page_range[0]}-{page_range[1]}" if page_range else ""))
    print(f"Raw chars : {len(raw)}")
    print(f"Clean     : {len(cleaned)}")
    print(f"Passages  : {len(passages)}")

    if len(cleaned) < 200:
        print("\n  WARNING: almost no text extracted. The PDF is probably")
        print("  scanned images rather than text. It would need OCR.")
        return

    print("\nFirst two passages:\n")
    for passage in passages[:2]:
        print(f"  {passage[:300]}...")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest chapter PDFs")
    parser.add_argument("--list", action="store_true", help="show expected filenames")
    parser.add_argument("--inspect", metavar="LESSON_ID", help="check one PDF")
    args = parser.parse_args()

    lessons = load_lessons()
    CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)

    if args.list:
        cmd_list(lessons)
        return

    if args.inspect:
        cmd_inspect(lessons, args.inspect)
        return

    all_passages: list[dict] = []
    found = 0
    skipped: list[str] = []

    chapter_map = load_chapter_map()

    for lesson in lessons:
        resolved = resolve_source(lesson["id"], chapter_map)
        if resolved is None:
            skipped.append(lesson["id"])
            continue
        pdf_path, page_range = resolved

        passages = ingest_one(lesson, pdf_path, page_range)
        if not passages:
            print(f"  {lesson['id']}: no text extracted (scanned PDF?)")
            skipped.append(lesson["id"])
            continue

        found += 1
        all_passages += passages
        print(f"  {lesson['id']}: {len(passages)} passages")

    if not all_passages:
        print("\nNo PDFs found. Run with --list to see expected filenames.")
        return

    with open(PASSAGES_FILE, "w", encoding="utf-8") as fh:
        json.dump(all_passages, fh, indent=2, ensure_ascii=False)

    print(f"\nIngested {found} chapters, {len(all_passages)} passages")
    print(f"  wrote {PASSAGES_FILE.name}")
    if skipped:
        print(f"  no PDF for: {', '.join(skipped)}")
        print("  (those chapters keep using their lessons.json summaries)")
    print("\nNext:")
    print("  python -m backend.nlp.build_lesson_index")
    print("  python -m backend.nlp.test_retrieval")


if __name__ == "__main__":
    main()
