"""
Week 6 - Validation.

The action plan for this week ends with: "Validate the preprocessing and
embedding pipeline on sample student queries to confirm it is ready for intent
detection." This script is that confirmation, and it prints a report you can
show directly in the review.

Checks performed
----------------
Preprocessing
  1. No query is destroyed by the pipeline (empty output check)
  2. Token reduction statistics
  3. Vocabulary size and coverage across intents
  4. Question words survive stop-word removal (they carry the intent signal)

Embeddings
  5. Correct shape, dtype, and no NaN/Inf values
  6. Vectors are unit length (so dot product == cosine similarity)
  7. Same-intent similarity is higher than different-intent similarity
  8. Leave-one-out nearest-neighbour intent accuracy

Check 8 is the headline number. It is *not* the Week 7 classifier - it just
answers "do these embeddings already separate the intent classes?" If a plain
nearest-neighbour lookup scores well, a trained classifier will do better.

Usage (from the project root):

    python -m backend.nlp.validate
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict

import numpy as np

from .config import (
    EMBEDDINGS_FILE,
    EMBEDDINGS_META_FILE,
    PROCESSED_QUERIES_FILE,
    VALIDATION_REPORT_FILE,
)

QUESTION_WORDS = {"what", "why", "how", "when", "where", "which", "who"}
PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"


def _line(char: str = "-", width: int = 68) -> str:
    return char * width


def load_processed() -> list[dict]:
    if not PROCESSED_QUERIES_FILE.exists():
        raise SystemExit(
            "processed_queries.json not found.\n"
            "Run this first:  python -m backend.nlp.build_dataset"
        )
    with open(PROCESSED_QUERIES_FILE, encoding="utf-8") as fh:
        return json.load(fh)


def validate_preprocessing(records: list[dict]) -> dict:
    print(_line("="))
    print("PREPROCESSING VALIDATION")
    print(_line("="))

    total = len(records)
    empty = [r for r in records if not r["processed_text"].strip()]

    raw_token_count = sum(len(r["tokens"]) for r in records)
    kept_token_count = sum(len(r["filtered_tokens"]) for r in records)
    reduction = (
        100 * (1 - kept_token_count / raw_token_count) if raw_token_count else 0.0
    )

    vocab = Counter()
    for r in records:
        vocab.update(r["processed_text"].split())

    intents = Counter(r["intent"] for r in records if r.get("intent"))

    # Did question words survive?
    raw_question_queries = [
        r
        for r in records
        if QUESTION_WORDS & set(r["normalized_text"].split())
    ]
    retained = [
        r
        for r in raw_question_queries
        if QUESTION_WORDS & set(r["processed_text"].split())
    ]
    retention_rate = (
        100 * len(retained) / len(raw_question_queries) if raw_question_queries else 100.0
    )

    print(f"\n[1] Queries processed              : {total}")
    print(f"    Empty after processing         : {len(empty)}  -> "
          f"{PASS if not empty else FAIL}")
    for r in empty[:5]:
        print(f"      ! '{r['raw_text']}'")

    # Duplicate detection. Exact duplicates make check 8 meaningless, because
    # every query finds its own copy as its nearest neighbour.
    seen: dict[str, int] = {}
    for r in records:
        key = r["normalized_text"].strip().lower()
        seen[key] = seen.get(key, 0) + 1
    duplicate_groups = {k: v for k, v in seen.items() if v > 1}
    num_duplicated_rows = sum(duplicate_groups.values()) - len(duplicate_groups)

    print(f"    Duplicate query texts          : {num_duplicated_rows}  -> "
          f"{PASS if not duplicate_groups else WARN}")
    if duplicate_groups:
        print("      ! Exact duplicates inflate check 8 - each query finds its")
        print("        own copy as nearest neighbour. Treat the accuracy below")
        print("        as invalid until the duplicates are removed.")
        for text, count in list(duplicate_groups.items())[:3]:
            print(f"        '{text}' x{count}")

    print(f"\n[2] Tokens before stop-word removal: {raw_token_count}")
    print(f"    Tokens after                   : {kept_token_count}")
    print(f"    Reduction                      : {reduction:.1f}%")

    print(f"\n[3] Vocabulary size                : {len(vocab)} unique tokens")
    print(f"    Intent classes                 : {len(intents)}")
    print(f"    Queries per intent             : "
          f"min {min(intents.values())}, max {max(intents.values())}")
    top = ", ".join(f"{w}({c})" for w, c in vocab.most_common(10))
    print(f"    Most frequent                  : {top}")

    print(f"\n[4] Queries containing a question word: {len(raw_question_queries)}")
    print(f"    Still containing one after filtering: {len(retained)} "
          f"({retention_rate:.0f}%)  -> "
          f"{PASS if retention_rate == 100 else WARN}")

    print("\n    Sample transformations:")
    for r in records[:5]:
        print(f"      '{r['raw_text']}'")
        print(f"        -> '{r['processed_text']}'")

    return {
        "total_queries": total,
        "empty_outputs": len(empty),
        "duplicate_rows": num_duplicated_rows,
        "tokens_before": raw_token_count,
        "tokens_after": kept_token_count,
        "reduction_percent": round(reduction, 2),
        "vocabulary_size": len(vocab),
        "intent_classes": len(intents),
        "question_word_retention_percent": round(retention_rate, 2),
        "status": PASS if not empty and retention_rate == 100 else WARN,
    }


def validate_embeddings(records: list[dict]) -> dict | None:
    print()
    print(_line("="))
    print("EMBEDDING VALIDATION")
    print(_line("="))

    if not EMBEDDINGS_FILE.exists():
        print("\n  Embeddings not found. Generate them with:")
        print("    python -m backend.nlp.build_dataset")
        print("  (skipping checks 5-8)")
        return None

    vectors = np.load(EMBEDDINGS_FILE)
    meta = {}
    if EMBEDDINGS_META_FILE.exists():
        with open(EMBEDDINGS_META_FILE, encoding="utf-8") as fh:
            meta = json.load(fh)

    labels = [r.get("intent") for r in records]

    # [5] shape / dtype / finite values
    shape_ok = vectors.ndim == 2 and vectors.shape[0] == len(records)
    finite_ok = bool(np.isfinite(vectors).all())

    print(f"\n[5] Model                          : {meta.get('model', 'unknown')}")
    print(f"    Array shape                    : {vectors.shape}  -> "
          f"{PASS if shape_ok else FAIL}")
    print(f"    dtype                          : {vectors.dtype}")
    print(f"    All values finite              : {finite_ok}  -> "
          f"{PASS if finite_ok else FAIL}")

    # [6] unit norms
    norms = np.linalg.norm(vectors, axis=1)
    norms_ok = bool(np.allclose(norms, 1.0, atol=1e-4))
    print(f"\n[6] Vector L2 norms                : "
          f"min {norms.min():.4f}, max {norms.max():.4f}")
    print(f"    Unit length (cosine-ready)     : {norms_ok}  -> "
          f"{PASS if norms_ok else WARN}")

    # [7] intra vs inter intent similarity
    unit = vectors / np.clip(norms, 1e-9, None)[:, None]
    sims = unit @ unit.T
    n = len(records)

    intra, inter = [], []
    for i in range(n):
        for j in range(i + 1, n):
            (intra if labels[i] == labels[j] else inter).append(sims[i, j])

    intra_mean = float(np.mean(intra)) if intra else 0.0
    inter_mean = float(np.mean(inter)) if inter else 0.0
    margin = intra_mean - inter_mean
    margin_ok = margin > 0

    print(f"\n[7] Mean similarity, same intent   : {intra_mean:.4f}")
    print(f"    Mean similarity, different     : {inter_mean:.4f}")
    print(f"    Separation margin              : {margin:+.4f}  -> "
          f"{PASS if margin_ok else FAIL}")

    # [8] leave-one-out 1-NN accuracy
    masked = sims.copy()
    np.fill_diagonal(masked, -np.inf)
    nearest = masked.argmax(axis=1)
    correct = [labels[i] == labels[nearest[i]] for i in range(n)]
    accuracy = 100 * sum(correct) / n

    per_intent = defaultdict(lambda: [0, 0])
    for i, ok in enumerate(correct):
        per_intent[labels[i]][1] += 1
        if ok:
            per_intent[labels[i]][0] += 1

    print(f"\n[8] Leave-one-out 1-NN intent accuracy: {accuracy:.1f}% "
          f"({sum(correct)}/{n})")
    print(f"    Random baseline                : "
          f"{100 / len(set(labels)):.1f}%")

    texts_seen: dict[str, int] = {}
    for r in records:
        key = r["normalized_text"].strip().lower()
        texts_seen[key] = texts_seen.get(key, 0) + 1
    has_duplicates = any(v > 1 for v in texts_seen.values())
    if has_duplicates:
        print("    !! INVALID: the dataset contains exact duplicate queries, so")
        print("       each one matches its own copy. Remove them and re-run.")

    print("\n    Per intent:")
    for intent, (hit, tot) in sorted(per_intent.items()):
        bar = "#" * int(10 * hit / tot) + "." * (10 - int(10 * hit / tot))
        print(f"      {intent:<22} {bar}  {hit}/{tot}")

    misses = [
        (records[i]["raw_text"], labels[i], labels[nearest[i]])
        for i in range(n)
        if not correct[i]
    ]
    if misses:
        print("\n    Confusions (query -> true / nearest neighbour):")
        for text, true_label, pred in misses[:8]:
            print(f"      '{text}'")
            print(f"        {true_label} -> {pred}")

    return {
        "model": meta.get("model"),
        "shape": list(vectors.shape),
        "dtype": str(vectors.dtype),
        "all_finite": finite_ok,
        "unit_norm": norms_ok,
        "intra_intent_similarity": round(intra_mean, 4),
        "inter_intent_similarity": round(inter_mean, 4),
        "separation_margin": round(margin, 4),
        "loo_1nn_accuracy_percent": round(accuracy, 2),
        "random_baseline_percent": round(100 / len(set(labels)), 2),
        "status": PASS if (shape_ok and finite_ok and margin_ok) else FAIL,
    }


def main() -> None:
    records = load_processed()

    pre_report = validate_preprocessing(records)
    emb_report = validate_embeddings(records)

    print()
    print(_line("="))
    print("WEEK 6 SUMMARY")
    print(_line("="))
    print(f"  Preprocessing pipeline : {pre_report['status']}")
    if emb_report:
        print(f"  Embedding pipeline     : {emb_report['status']}")
        ready = pre_report["status"] != FAIL and emb_report["status"] == PASS
        print(f"\n  Ready for Week 7 intent detection: "
              f"{'YES' if ready else 'NOT YET'}")
    else:
        print("  Embedding pipeline     : NOT GENERATED")
        print("\n  Ready for Week 7 intent detection: NOT YET "
              "(embeddings missing)")

    report = {"preprocessing": pre_report, "embeddings": emb_report}
    VALIDATION_REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(VALIDATION_REPORT_FILE, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(f"\n  Saved report -> {VALIDATION_REPORT_FILE.name}")


if __name__ == "__main__":
    main()
