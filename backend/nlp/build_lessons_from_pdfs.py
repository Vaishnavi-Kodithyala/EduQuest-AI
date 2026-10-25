"""
Expand the content bank from NCERT chapter PDFs.

NCERT distributes each textbook as a zip of one PDF per chapter, named with an
opaque code (fegp101.pdf, fegp102.pdf ...) plus a prelims file. This script
reads a folder of those PDFs, works out each chapter's number and title, pulls
the text, and generates lessons.json entries.

How chapters are identified
---------------------------
**Numbers come from the filename.** NCERT names files fegp101..fegp110 and
fecu101..fecu112 - the trailing digits are the chapter number, and the file
ending "ps" is the prelims. This is completely reliable and costs nothing.

**Titles come from the book's own contents page**, which lives in the prelims
PDF and lists every chapter:

    Chapter 1
    The Wonderful World of Science 1
    Chapter 2
    Diversity in the Living World
     9

Earlier versions read titles from the first page of each chapter, or from an
InDesign artifact in the text layer. Both worked on the Maths book and broke on
Science: chapter 4 there prints its number before its title, chapter 9 has no
title on page one at all, and the InDesign marker carries no title. The
contents page is the one place every title appears in a consistent form.

Reading the first page is kept only as a fallback for books with no usable
contents page.

Workflow
--------
1. Download a textbook's "complete book" zip from ncert.nic.in and extract it
   into its own folder under data/chapters/, named <grade>-<subject>:

       data/chapters/g6-math/fegp101.pdf
       data/chapters/g6-math/fegp102.pdf
       ...
       data/chapters/g7-sci/...

2. Check what is detected:

       python -m backend.nlp.build_lessons_from_pdfs --detect g6-math

3. Generate the lessons file:

       python -m backend.nlp.build_lessons_from_pdfs --generate

   This writes data/lessons_expanded.json. The hand-written lessons are kept
   exactly as they are - they have matching quizzes and better summaries than
   anything generated from raw text.

4. Review it, then swap it in and rebuild the index:

       copy data\\lessons_expanded.json data\\lessons.json
       python -m backend.nlp.build_lesson_index
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .config import DATA_DIR

CHAPTERS_DIR = DATA_DIR / "chapters"
LESSONS_FILE = DATA_DIR / "lessons.json"
OUTPUT_FILE = DATA_DIR / "lessons_expanded.json"

SUBJECT_CODES = {
    "math": "Mathematics",
    "maths": "Mathematics",
    "sci": "Science",
    "eng": "English",
    "tel": "Telugu",
}

# Filename -> chapter number. "fegp107.pdf" -> 7, "fecu112.pdf" -> 12.
FILENAME_CHAPTER = re.compile(r"^[a-z]+\d(\d{2})$", re.I)

# Prelims files end in "ps" ("fegp1ps.pdf").
FILENAME_PRELIMS = re.compile(r"^[a-z]+\dps$", re.I)

# A "Chapter N" line on the contents page.
CONTENTS_HEADING = re.compile(r"^chapter\s+(\d+)\s*$", re.I)

# English readers group several pieces under "Unit N: Theme" instead.
CONTENTS_UNIT = re.compile(r"^unit\s+(\d+)\s*[:.]?\s*(.*)$", re.I)

# Fallback only: a title running into its number on a chapter's first page,
# e.g. "The Wonderful World of Science1Chapter".
FIRSTPAGE_TITLE = re.compile(r"^\s*(.{4,70}?)\s*(\d{1,2})\s*chapter\b", re.I | re.S)

# Lines that are page furniture rather than content.
NOISE_PATTERNS = [
    re.compile(r"\.indd\s", re.I),                  # InDesign artifacts
    re.compile(r"^\s*reprint\s+\d{4}", re.I),       # "Reprint 2026-27"
    re.compile(r"^\s*\d+\s*$"),                     # bare page numbers
    re.compile(r"^[\s\-_=•·—–]+$"),                 # rules and stray bullets
    re.compile(r"\|\s*grade\s*\d", re.I),           # "Ganita Prakash | Grade 6"
    re.compile(r"^\s*ganita\s+prakash\s*$", re.I),  # running book title
]

# Control characters that survive PDF extraction and render as junk.
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

MIN_CHAPTER_CHARS = 1000
SUMMARY_SENTENCES = 3

# Sentences that are classroom instructions rather than content. English
# chapters open with a page of pre-reading exercises, so a summary taken from
# the very start reads "Let us do these activities before we read" for every
# single piece.
EXERCISE_OPENERS = re.compile(
    r"^\s*(let us\b|i+\s|[ivx]+\.|\d+\.|answer the|read the following|"
    r"look at the|circle the|write two|identify the|discuss the|"
    r"which games|now,? find)",
    re.I,
)
MAX_SUMMARY_CHARS = 300
MAX_CONTENT_CHARS = 20000

# Passage sizing for the search index. The embedding model truncates at 64
# word-pieces, so a whole 20,000-character chapter indexed as one entry would
# lose all but its opening line. Roughly 60 words keeps each passage inside
# that window; the overlap means a fact sitting on a boundary still appears
# whole in one of the two passages either side of it.
PASSAGE_WORDS = 60
PASSAGE_MIN_WORDS = 20
PASSAGE_OVERLAP_WORDS = 12


def parse_folder_name(name: str) -> tuple[int, str, str] | None:
    """'g6-math' -> (6, 'math', 'Mathematics')."""
    match = re.match(r"^g(\d+)-([a-z]+)$", name.lower())
    if not match:
        return None
    grade = int(match.group(1))
    code = match.group(2)
    subject = SUBJECT_CODES.get(code)
    return (grade, code, subject) if subject else None


def read_pdf_text(pdf_path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise SystemExit("pypdf is not installed. Run:\n    pip install pypdf")

    reader = PdfReader(str(pdf_path))
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            parts.append("")
    return "\n".join(parts)


# A page whose text contains a standalone "Contents" heading. NCERT typesets
# it with odd capitalisation ("coNteNtS"), so the match is case-insensitive.
CONTENTS_PAGE = re.compile(r"^\s*c\s*o\s*n\s*t\s*e\s*n\s*t\s*s\s*$", re.I | re.M)


def read_contents_page(prelims_path: Path) -> str:
    """
    Just the contents page from a prelims PDF.

    Parsing the whole file does not work: the "About the Book" section
    describes each unit in prose and contains headings like "Unit 1: Fables and
    Folk Tales", which the contents parser then reads as real entries and
    swallows several pages of narrative into the first title.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        raise SystemExit("pypdf is not installed. Run:\n    pip install pypdf")

    reader = PdfReader(str(prelims_path))
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:
            continue
        if CONTENTS_PAGE.search(text):
            return text

    # No recognisable contents page - fall back to the whole document and let
    # the caller's own checks decide whether the result is usable.
    return read_pdf_text(prelims_path)


def _rejoin_wrapped(lines: list[str]) -> list[str]:
    """
    Rejoin words split across lines on the contents page.

    The English contents wraps mid-word - "A Friend's Pra" / "yer 52",
    "Fables and F" / "olk Tales" - so parsing line by line yields fragments.
    A line is a continuation when the previous line ends in a letter and it
    begins with a lowercase letter, and the two are joined with no space.

    "Chapter 2" followed by a title is not affected, because that line ends in
    a digit. Nor is a page number on its own line, because it starts with one.
    """
    merged: list[str] = []
    for line in lines:
        if (
            merged
            and merged[-1]
            and line
            and merged[-1][-1].isalpha()
            and line[0].islower()
        ):
            merged[-1] += line
        else:
            merged.append(line)
    return merged


def parse_contents_page(prelims_path: Path) -> dict:
    """
    Read the book's contents page.

    Two layouts exist. Maths and Science list numbered chapters:

        Chapter 3
        Mindful Eating: A Path to a Healthy Body
         35

    English readers group several pieces under a themed unit:

        Unit 1: Fables and Folk Tales
         A Bottle of Dew 1
         The Raven and the Fox 13

    Returns {"chapters": {n: title}} or {"units": {n: [titles]}}, whichever the
    book uses. Empty dict if neither is found.
    """
    raw = read_contents_page(prelims_path)
    lines = _rejoin_wrapped(
        [line.strip() for line in raw.split("\n") if line.strip()]
    )

    chapters: dict[int, str] = {}
    units: dict[int, list[str]] = {}

    current_chapter: int | None = None
    current_unit: int | None = None
    parts: list[str] = []
    pending_piece: list[str] = []

    def flush_chapter() -> None:
        nonlocal current_chapter, parts
        if current_chapter is None:
            return
        text = " ".join(parts).strip()
        text = re.sub(r"\s*\d{1,3}\s*$", "", text).strip()
        text = re.sub(r"\s+", " ", text)
        if text:
            chapters[current_chapter] = text
        current_chapter, parts = None, []

    for line in lines:
        if not line or re.search(r"\.indd|reprint\s+\d{4}", line, re.I):
            continue

        unit_match = CONTENTS_UNIT.match(line)
        if unit_match:
            flush_chapter()
            current_unit = int(unit_match.group(1))
            units.setdefault(current_unit, [])
            continue

        heading = CONTENTS_HEADING.match(line)
        if heading:
            flush_chapter()
            current_chapter = int(heading.group(1))
            parts = []
            continue

        if current_chapter is not None:
            if re.fullmatch(r"\d{1,3}", line):
                parts.append(line)
                flush_chapter()
                continue
            parts.append(line)
            if re.search(r"\s\d{1,3}$", line):
                flush_chapter()
            continue

        if current_unit is not None:
            # A piece entry ends with its page number. A title too long for one
            # line is split across two, with the number on the second
            # ("Ila Sachani:" / "Embroidering Dreams with her Feet 151"), so
            # lines without a number are held over and prepended to the next.
            if re.search(r"\s+\d{1,3}$", line):
                title = re.sub(r"\s+\d{1,3}$", "", line).strip()
                title = " ".join(pending_piece + [title])
                title = re.sub(r"\s+", " ", title).strip()
                pending_piece = []
                if len(title) > 2:
                    units[current_unit].append(title)
            else:
                pending_piece.append(line)

    flush_chapter()

    if chapters:
        return {"chapters": chapters}
    units = {n: titles for n, titles in units.items() if titles}
    if units:
        return {"units": units}
    return {}


def title_from_first_page(raw_text: str, number: int) -> str | None:
    """
    Fallback title source: the chapter's own first page.

    Only used when the contents page is missing or does not list this chapter.
    Unreliable - some chapters print the number before the title, and some
    print no title on page one at all - hence the preference for contents.
    """
    match = FIRSTPAGE_TITLE.match(raw_text.strip()[:200])
    if not match:
        return None
    title, found_number = match.group(1), int(match.group(2))
    if found_number != number:
        return None
    title = re.sub(r"\s+", " ", title).strip(" -—:")
    return title or None


def normalise_title(text: str) -> str:
    """
    Loose form of a title, for matching it inside body text.

    Necessary because the same title is typeset differently in the contents
    and in the chapter itself: "Yoga-A Way of Life" appears as "Yoga-a WaY of
    Life", and dash characters vary between en-dash, em-dash and hyphen.
    """
    text = re.sub(r"[\u2010-\u2015\u2212]", "-", text)
    text = re.sub(r"[\u2018\u2019]", "'", text)
    text = re.sub(r"\s*-\s*", "-", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def split_unit_text(text: str, piece_titles: list[str]) -> list[tuple[str, str]]:
    """
    Cut one unit's text into its individual pieces.

    Each piece starts where its title appears in the body. Titles are located
    on the normalised text so typesetting differences do not defeat the match,
    then the offset is used to slice the original.
    """
    normalised = normalise_title(text)

    found: list[tuple[int, str]] = []
    for title in piece_titles:
        position = normalised.find(normalise_title(title))
        if position >= 0:
            found.append((position, title))

    if not found:
        return []

    found.sort()
    # Offsets come from the normalised string, which differs slightly in
    # length from the original. Rescale so slices land close enough - piece
    # boundaries do not need to be exact to the character.
    scale = len(text) / max(len(normalised), 1)

    pieces: list[tuple[str, str]] = []
    for index, (position, title) in enumerate(found):
        start = int(position * scale)
        end = int(found[index + 1][0] * scale) if index + 1 < len(found) else len(text)
        body = text[start:end].strip()
        if body:
            pieces.append((title, body))
    return pieces


def clean_text(raw: str) -> str:
    """
    Strip page furniture and rejoin wrapped lines.

    Lines are joined with a space. A handful of words are split mid-word by the
    PDF's line breaks ("pla" / "ying"), but those are rare - one case in 45
    across a sample chapter - and joining without a space would instead damage
    the 44 legitimate word boundaries.
    """
    kept = []
    for line in raw.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if any(pattern.search(stripped) for pattern in NOISE_PATTERNS):
            continue
        kept.append(stripped)

    text = " ".join(kept)
    text = CONTROL_CHARS.sub(" ", text)
    text = re.sub(r"(\w)-\s+(\w)", r"\1\2", text)   # hyphenated line breaks
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_passages(text: str) -> list[str]:
    """Overlapping, sentence-aligned passages for the search index."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]

    passages: list[str] = []
    current: list[str] = []
    current_words = 0

    for sentence in sentences:
        current.append(sentence)
        current_words += len(sentence.split())
        if current_words < PASSAGE_WORDS:
            continue

        passages.append(" ".join(current))
        tail: list[str] = []
        tail_words = 0
        for previous in reversed(current):
            tail.insert(0, previous)
            tail_words += len(previous.split())
            if tail_words >= PASSAGE_OVERLAP_WORDS:
                break
        current, current_words = tail, tail_words

    remainder = " ".join(current).strip()
    if remainder and len(remainder.split()) >= PASSAGE_MIN_WORDS:
        if not passages or remainder != passages[-1]:
            passages.append(remainder)

    return passages


def make_summary(text: str, title: str = "") -> str:
    """
    First few sentences, skipping the chapter heading.

    Extracted text opens with the title in block capitals ("THE OTHER SIDE OF
    ZERO"), sometimes preceded by a section word. Left in, the summary reads as
    a jumble of heading fragments rather than a sentence.
    """
    body = text.strip()

    if title:
        # Drop everything up to and including the title heading, if it appears
        # near the start. Matched on a word boundary and only in the first 200
        # characters, so a chapter called "Fractions" is not cut at the first
        # ordinary mention of the word several paragraphs in.
        # Trailing \d* because the extracted heading often runs straight into
        # the chapter number - "NUMBER PLAY3", "SYMMETRY9".
        match = re.search(
            r"\b" + re.escape(title) + r"\d*", body[:200], re.I
        )
        if match:
            body = body[match.end():].lstrip(" .:-—")

    # Drop a leading bare chapter number ("3 Numbers are used ...") and the
    # word "Chapter" itself. The Science book lays headings out as
    # "<title><number>Chapter", so removing the title leaves "Chapter" behind.
    body = body.lstrip()
    for _ in range(3):
        before = body
        body = re.sub(r"^chapter\b\s*", "", body, flags=re.I)
        body = re.sub(r"^\d{1,2}(\.\d+)?\s+", "", body)
        if body == before:
            break

    # Drop any remaining run of block-capital words at the start.
    words = body.split()
    index = 0
    while index < len(words) and index < 12:
        word = words[index].strip(".,:;!?")
        if len(word) > 1 and word.isupper() and word.isalpha():
            index += 1
        else:
            break
    body = " ".join(words[index:])

    # Several chapters open with a Sanskrit verse before any English prose.
    # Skip ahead to the first sentence that is mostly Latin script, so the
    # summary is readable to someone scanning the lesson list.
    sentences_all = [x for x in re.split(r"(?<=[.!?])\s+", body) if x.strip()]
    for index, sentence in enumerate(sentences_all):
        letters = [c for c in sentence if c.isalpha()]
        if letters and sum(c.isascii() for c in letters) / len(letters) > 0.7:
            body = " ".join(sentences_all[index:])
            break

    # If what is left opens mid-sentence, skip to the next sentence start.
    # Chapter openings are laid out in columns and text boxes, so extraction
    # order sometimes drops us into the middle of a line.
    body = body.strip()
    if body and body[0].islower():
        boundary = re.search(r"[.!?]\s+(?=[A-Z])", body)
        if boundary:
            body = body[boundary.end():]

    # English pieces print a page of pre-reading exercises, then "Let us read"
    # immediately before the story or poem itself. Where that marker appears
    # early, the content starts after it.
    marker = re.search(r"\blet us read\b", body[:4000], re.I)
    if marker:
        body = body[marker.end():].lstrip(" .:-—")

    # Skip past classroom instructions to the first substantial sentence.
    sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+", body.strip()) if x.strip()]
    for index, sentence in enumerate(sentences):
        if len(sentence) >= 60 and not EXERCISE_OPENERS.match(sentence):
            sentences = sentences[index:]
            break

    summary = " ".join(sentences[:SUMMARY_SENTENCES]).strip()
    if len(summary) > MAX_SUMMARY_CHARS:
        summary = summary[:MAX_SUMMARY_CHARS].rsplit(" ", 1)[0] + "..."
    return summary


def load_existing_titles() -> dict[str, str]:
    """Normalised title -> existing lesson id, from lessons.json."""
    try:
        with open(LESSONS_FILE, encoding="utf-8") as fh:
            lessons = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    return {normalise_title(l["title"]): l["id"] for l in lessons if l.get("title")}


def scan_folder(folder: Path) -> list[dict]:
    """
    Every chapter (or piece) in a book folder, ordered as the book orders them.

    Ids are assigned by title where a lesson of that name already exists, and
    by position otherwise. That matters for English: the existing lesson "The
    Unlikely Best Friends" is g6-eng-2, but it is the *fourth* piece in the
    book. Numbering purely by position would hand g6-eng-2 to "The Raven and
    the Fox" and silently attach its text to the wrong lesson.
    """
    parsed = parse_folder_name(folder.name)
    if parsed is None:
        return []
    grade, code, subject = parsed

    pdfs = sorted(folder.glob("*.pdf"))
    contents: dict = {}
    for pdf_path in pdfs:
        if FILENAME_PRELIMS.match(pdf_path.stem):
            try:
                contents = parse_contents_page(pdf_path)
            except Exception:
                contents = {}
            break

    units = contents.get("units") or {}
    chapter_titles = contents.get("chapters") or {}

    # --- collect raw entries in book order ---
    entries: list[dict] = []
    skipped: list[dict] = []

    for pdf_path in pdfs:
        stem = pdf_path.stem

        if FILENAME_PRELIMS.match(stem):
            skipped.append({"file": pdf_path.name, "skip": "prelims"})
            continue

        match = FILENAME_CHAPTER.match(stem)
        if not match:
            skipped.append({"file": pdf_path.name, "skip": "unrecognised filename"})
            continue

        number = int(match.group(1))
        cleaned = clean_text(read_pdf_text(pdf_path))

        if len(cleaned) < MIN_CHAPTER_CHARS:
            skipped.append({"file": pdf_path.name, "skip": "too little text"})
            continue

        piece_titles = units.get(number) or units.get(str(number))
        if piece_titles:
            pieces = split_unit_text(cleaned, list(piece_titles))
            if not pieces:
                skipped.append({"file": pdf_path.name, "skip": "could not split unit"})
                continue
            for title, body in pieces:
                if len(body) < MIN_CHAPTER_CHARS:
                    continue
                entries.append(
                    {
                        "file": pdf_path.name,
                        "title": title,
                        "title_source": "contents",
                        "text": body,
                        "unit": number,
                    }
                )
            continue

        raw_first = read_pdf_text(pdf_path)
        title = chapter_titles.get(number) or title_from_first_page(raw_first, number)
        source = "contents" if chapter_titles.get(number) else "first page"
        if not title:
            title, source = f"Chapter {number}", "placeholder"

        entries.append(
            {
                "file": pdf_path.name,
                "title": title,
                "title_source": source,
                "text": cleaned,
                "number": number,
            }
        )

    # --- assign ids ---
    existing = load_existing_titles()
    used: set[str] = set(existing.values())
    next_free = 1

    def allocate() -> str:
        nonlocal next_free
        while f"g{grade}-{code}-{next_free}" in used:
            next_free += 1
        lesson_id = f"g{grade}-{code}-{next_free}"
        used.add(lesson_id)
        return lesson_id

    results: list[dict] = []
    for position, entry in enumerate(entries, start=1):
        matched_id = existing.get(normalise_title(entry["title"]))
        lesson_id = matched_id or allocate()
        results.append(
            {
                **entry,
                "id": lesson_id,
                "number": entry.get("number", position),
                "grade": grade,
                "subject": subject,
            }
        )

    return results + skipped


def cmd_detect(folder_name: str) -> None:
    folder = CHAPTERS_DIR / folder_name
    if not folder.is_dir():
        raise SystemExit(
            f"Not found: {folder}\n"
            "Extract the NCERT zip into a folder named like g6-math."
        )
    if parse_folder_name(folder.name) is None:
        raise SystemExit(
            f"Folder name '{folder.name}' must look like g6-math, g7-sci, "
            f"g6-eng or g6-tel."
        )

    chapters = scan_folder(folder)
    if not chapters:
        raise SystemExit("No PDFs found in that folder.")

    print(f"Folder: {folder_name}\n")
    usable = 0
    for chapter in chapters:
        if "skip" in chapter:
            print(f"  [skip] {chapter['file']:<16} {chapter['skip']}")
            continue
        usable += 1
        flag = "" if chapter["title_source"] == "contents" else f"  <- title from {chapter['title_source']}"
        print(f"  [{chapter['id']:<11}] {chapter['file']:<16} "
              f"{len(chapter['text']):>6} chars  {chapter['title']}{flag}")

    print(f"\n{usable} usable chapters")
    if usable:
        print("\nSample of the first chapter's cleaned text:")
        first = next(c for c in chapters if "skip" not in c)
        print(f"  {first['text'][:300]}...")


def cmd_generate() -> None:
    folders = sorted(
        p for p in CHAPTERS_DIR.iterdir()
        if p.is_dir() and parse_folder_name(p.name)
    )
    if not folders:
        raise SystemExit(
            f"No book folders in {CHAPTERS_DIR}.\n"
            "Extract each NCERT zip into a folder named like g6-math, g7-sci."
        )

    with open(LESSONS_FILE, encoding="utf-8") as fh:
        existing = json.load(fh)
    existing_ids = {lesson["id"] for lesson in existing}

    lessons = list(existing)
    passages_out: list[dict] = []
    added = 0
    kept = 0

    for folder in folders:
        print(f"{folder.name}:")
        for chapter in scan_folder(folder):
            if "skip" in chapter:
                continue
            # Every chapter contributes search passages, including the ones
            # already in lessons.json - their hand-written summaries stay, but
            # the chatbot gains real textbook text to quote from.
            chapter_passages = split_passages(chapter["text"])
            for i, passage in enumerate(chapter_passages, start=1):
                passages_out.append(
                    {
                        "lesson_id": chapter["id"],
                        "title": chapter["title"],
                        "subject": chapter["subject"],
                        "grade": chapter["grade"],
                        "language": "en",
                        "heading": f"From the chapter (part {i})",
                        "text": passage,
                        "source": chapter["file"],
                    }
                )

            if chapter["id"] in existing_ids:
                # Never overwrite a hand-written lesson. Those have matching
                # quizzes and much better summaries than anything generated
                # from raw textbook text.
                kept += 1
                print(f"  {chapter['id']:<12} kept existing, "
                      f"{len(chapter_passages)} passages")
                continue

            lessons.append(
                {
                    "id": chapter["id"],
                    "grade": chapter["grade"],
                    "subject": chapter["subject"],
                    "language": "en",
                    "title": chapter["title"],
                    "summary": make_summary(chapter["text"], chapter["title"]),
                    "content": chapter["text"][:MAX_CONTENT_CHARS],
                }
            )
            added += 1
            print(f"  {chapter['id']:<12} added  {chapter['title']} "
                  f"({len(chapter_passages)} passages)")

    lessons.sort(key=lambda l: (l["grade"], l["subject"], l["id"]))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as fh:
        json.dump(lessons, fh, indent=2, ensure_ascii=False)

    passages_file = DATA_DIR / "chapter_passages.json"
    with open(passages_file, "w", encoding="utf-8") as fh:
        json.dump(passages_out, fh, indent=2, ensure_ascii=False)

    print(f"\nWrote {OUTPUT_FILE.name}")
    print(f"  {len(existing)} existing lessons preserved ({kept} matched a PDF)")
    print(f"  {added} new chapters added")
    print(f"  {len(lessons)} total")
    print(f"  {len(passages_out)} search passages -> chapter_passages.json")
    print("\nNOTE: new chapters have no quiz. quizzes.json still covers only")
    print("      the original hand-written lessons.")
    print("\nReview the file, then:")
    print("  copy data\\lessons_expanded.json data\\lessons.json")
    print("  python -m backend.nlp.build_lesson_index")


def main() -> None:
    parser = argparse.ArgumentParser(description="Expand lessons from NCERT PDFs")
    parser.add_argument("--detect", metavar="FOLDER", help="inspect one book folder")
    parser.add_argument("--generate", action="store_true", help="build lessons_expanded.json")
    args = parser.parse_args()

    CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)

    if args.detect:
        cmd_detect(args.detect)
    elif args.generate:
        cmd_generate()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
