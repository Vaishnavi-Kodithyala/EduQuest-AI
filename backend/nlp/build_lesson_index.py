"""
Week 7 - Build the semantic lesson index.

Embeds every lesson's title and summary with the same DistilBERT model used for
student queries, so the two live in the same vector space and can be compared
directly.

Run from the project root:
    python -m backend.nlp.build_lesson_index
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np

from .config import PROCESSED_DIR, RETRIEVAL_MODEL_NAME
from .pipeline import NLPPipeline
from .retriever import (
    LESSONS_FILE,
    LESSON_INDEX_FILE,
    LESSON_META_FILE,
    section_index_text,
    split_sections,
)


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    with open(LESSONS_FILE, encoding="utf-8") as fh:
        lessons = json.load(fh)

    print(f"Loaded {len(lessons)} lessons")

    # Chapter passages extracted from PDFs, if ingest_pdfs has been run.
    # These are much richer than the hand-written summaries, so where a chapter
    # has them the bot can quote real material instead of a blurb.
    passages_file = LESSONS_FILE.parent / "chapter_passages.json"
    pdf_passages: dict[str, list[dict]] = {}
    if passages_file.exists():
        with open(passages_file, encoding="utf-8") as fh:
            for row in json.load(fh):
                pdf_passages.setdefault(row["lesson_id"], []).append(row)
        print(f"Found PDF passages for {len(pdf_passages)} chapters")

    # One index entry per section, not per chapter. A chapter-level index can
    # only ever answer "open this chapter"; sections let the bot return the
    # paragraph that actually addresses the question.
    records: list[dict] = []
    for lesson in lessons:
        # Real chapter text first, then the summary sections. Both are indexed:
        # the summary describes what a chapter is about, which helps broad
        # questions, while the passages answer specific ones.
        for passage in pdf_passages.get(lesson["id"], []):
            records.append(
                {
                    "id": lesson["id"],
                    "title": lesson["title"],
                    "subject": lesson["subject"],
                    "grade": lesson["grade"],
                    "language": lesson.get("language", "en"),
                    "summary": lesson.get("summary", ""),
                    "heading": passage["heading"],
                    "text": passage["text"],
                    "indexed_text": section_index_text(
                        lesson, {"heading": passage["heading"], "text": passage["text"]}
                    ),
                }
            )

        for section in split_sections(lesson):
            records.append(
                {
                    "id": lesson["id"],
                    "title": lesson["title"],
                    "subject": lesson["subject"],
                    "grade": lesson["grade"],
                    "language": lesson.get("language", "en"),
                    "summary": lesson.get("summary", ""),
                    "heading": section["heading"],
                    "text": section["text"],
                    "indexed_text": section_index_text(lesson, section),
                }
            )

    print(f"Split into {len(records)} sections")
    texts = [r["indexed_text"] for r in records]

    pipeline = NLPPipeline()
    print(f"Embedding with {RETRIEVAL_MODEL_NAME} ...")
    vectors = pipeline.embed_for_retrieval(texts)

    np.save(LESSON_INDEX_FILE, vectors)

    meta = {
        "model": RETRIEVAL_MODEL_NAME,
        "num_lessons": len(lessons),
        "num_sections": len(records),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lessons": records,
    }
    with open(LESSON_META_FILE, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, ensure_ascii=False)

    print(f"  wrote {LESSON_INDEX_FILE.name}  {tuple(vectors.shape)}")
    print(f"  wrote {LESSON_META_FILE.name}")
    print("\nDone. The chatbot can now find lessons by meaning.")


if __name__ == "__main__":
    main()
