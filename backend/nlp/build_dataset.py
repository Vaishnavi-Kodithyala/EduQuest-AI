"""
Week 6 - Build the processed dataset and embedding artifacts.

Reads the Week 2 datasets, runs them through the preprocessing pipeline,
generates DistilBERT embeddings, and writes everything into data/processed/
so Week 7 can train the intent classifier without re-running any of this.

Usage (from the project root):

    python -m backend.nlp.build_dataset
    python -m backend.nlp.build_dataset --skip-embeddings   # preprocessing only
    python -m backend.nlp.build_dataset --include-intents   # also embed intents.json examples

Outputs
-------
data/processed/processed_queries.json   every stage, per query, human-readable
data/processed/query_embeddings.npy     float32 array, shape (n_queries, 768)
data/processed/embeddings_meta.json     row order, labels, model config
data/processed/vocabulary.json          vocabulary built from processed_text
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone

import numpy as np

from .config import (
    EMBEDDINGS_FILE,
    EMBEDDINGS_META_FILE,
    EMBEDDING_MODEL_NAME,
    INTENTS_FILE,
    MAX_SEQ_LENGTH,
    PROCESSED_DIR,
    PROCESSED_QUERIES_FILE,
    STUDENT_QUERIES_FILE,
    VOCABULARY_FILE,
)
from .pipeline import NLPPipeline


def load_student_queries() -> list[dict]:
    with open(STUDENT_QUERIES_FILE, encoding="utf-8") as fh:
        return json.load(fh)


def load_intent_examples() -> list[dict]:
    """Flatten intents.json into the same shape as student_queries.json."""
    with open(INTENTS_FILE, encoding="utf-8") as fh:
        intents = json.load(fh)

    rows: list[dict] = []
    for entry in intents:
        for i, example in enumerate(entry.get("examples", []), start=1):
            rows.append(
                {
                    "id": f"ex-{entry['intent']}-{i}",
                    "query": example,
                    "intent": entry["intent"],
                    "language": "en",
                    "source": "intents.json",
                }
            )
    return rows


def build_vocabulary(processed_texts: list[str]) -> dict:
    counter: Counter[str] = Counter()
    for text in processed_texts:
        counter.update(text.split())

    return {
        "size": len(counter),
        "total_tokens": sum(counter.values()),
        "tokens": dict(counter.most_common()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Week 6 dataset builder")
    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="run preprocessing only, do not load DistilBERT",
    )
    parser.add_argument(
        "--include-intents",
        action="store_true",
        help=(
            "also process the example phrases in intents.json. WARNING: as of "
            "the Week 2 dataset these are the SAME 50 texts as "
            "student_queries.json, so this creates exact duplicates and makes "
            "the validation nearest-neighbour score meaningless. Only use this "
            "once intents.json contains genuinely new phrases."
        ),
    )
    args = parser.parse_args()

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    rows = load_student_queries()
    for row in rows:
        row.setdefault("source", "student_queries.json")

    if args.include_intents:
        rows += load_intent_examples()

    print(f"Loaded {len(rows)} queries")

    pipeline = NLPPipeline()
    texts = [row["query"] for row in rows]

    print("Preprocessing (spaCy + NLTK) ...")
    processed = pipeline.preprocess_batch(texts)

    records = []
    for row, result in zip(rows, processed):
        record = result.to_dict()
        record.update(
            {
                "id": row.get("id"),
                "intent": row.get("intent"),
                "language": row.get("language", "en"),
                "source": row.get("source"),
            }
        )
        records.append(record)

    with open(PROCESSED_QUERIES_FILE, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False)
    print(f"  wrote {PROCESSED_QUERIES_FILE.relative_to(PROCESSED_DIR.parent.parent)}")

    vocabulary = build_vocabulary([r["processed_text"] for r in records])
    with open(VOCABULARY_FILE, "w", encoding="utf-8") as fh:
        json.dump(vocabulary, fh, indent=2, ensure_ascii=False)
    print(
        f"  wrote {VOCABULARY_FILE.relative_to(PROCESSED_DIR.parent.parent)} "
        f"({vocabulary['size']} unique tokens)"
    )

    if args.skip_embeddings:
        print("\nSkipped embeddings (--skip-embeddings).")
        return

    print(f"\nGenerating {EMBEDDING_MODEL_NAME} embeddings ...")
    print("  (first run downloads ~265 MB of model weights)")

    sources = [r["normalized_text"] or r["raw_text"] for r in records]
    vectors = pipeline.embed(sources)

    np.save(EMBEDDINGS_FILE, vectors)

    meta = {
        "model": EMBEDDING_MODEL_NAME,
        "embedding_dim": int(vectors.shape[1]),
        "max_seq_length": MAX_SEQ_LENGTH,
        "pooling": "mean_pooling_attention_masked",
        "normalized": True,
        "embedded_field": "normalized_text",
        "num_queries": int(vectors.shape[0]),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rows": [
            {
                "index": i,
                "id": r["id"],
                "intent": r["intent"],
                "text": r["normalized_text"],
            }
            for i, r in enumerate(records)
        ],
    }
    with open(EMBEDDINGS_META_FILE, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, ensure_ascii=False)

    print(f"  wrote embeddings array {tuple(vectors.shape)} -> {EMBEDDINGS_FILE.name}")
    print(f"  wrote metadata -> {EMBEDDINGS_META_FILE.name}")
    print("\nDone. Run `python -m backend.nlp.validate` next.")


if __name__ == "__main__":
    main()
