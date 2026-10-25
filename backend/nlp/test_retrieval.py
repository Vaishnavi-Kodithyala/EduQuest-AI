"""
Week 7 - Retrieval diagnostic.

Shows which lesson the semantic search returns for a set of probe queries, with
the actual similarity scores. Use it to check that on-topic questions find the
right chapter, and to choose RELEVANCE_THRESHOLD from real numbers rather than
guessing.

Run from the project root:
    python -m backend.nlp.test_retrieval
    python -m backend.nlp.test_retrieval "how do camels survive"
"""

from __future__ import annotations

import sys

import numpy as np

from .pipeline import get_pipeline
from .retriever import RELEVANCE_THRESHOLD, get_retriever

# (query, expected lesson id or None if nothing should match)
PROBES = [
    ("how do camels survive in the desert", "g6-sci-2"),
    ("explain lines and angles", "g6-math-2"),
    ("how do magnets attract iron", "g6-sci-4"),
    ("tell me about number patterns", "g6-math-1"),
    ("what did Rama Natha learn", "g6-eng-1"),
    ("the elephant and the dog story", "g6-eng-2"),
    ("what is a prime number", "g6-math-5"),
    ("what are negative numbers", "g6-math-10"),
    ("how do scientists ask questions", "g6-sci-1"),
    ("the clever fox who tricked the raven", "g6-eng-3"),
    # Off-topic controls - these SHOULD fall below the threshold.
    ("book me a hotel room", None),
    ("who won the cricket match yesterday", None),
    ("what is the weather today", None),
]


def run(queries: list[tuple[str, str | None]]) -> None:
    pipeline = get_pipeline()
    retriever = get_retriever()

    on_topic_scores: list[float] = []
    off_topic_scores: list[float] = []
    correct = 0
    expected_count = 0

    print("=" * 72)
    print("RETRIEVAL DIAGNOSTIC")
    print("=" * 72)
    print(f"\n  Current RELEVANCE_THRESHOLD = {RELEVANCE_THRESHOLD}\n")

    for text, expected in queries:
        processed = pipeline.preprocess(text)
        vector = pipeline.retrieval_embedder.encode_one(
            processed.normalized_text or text
        )
        results = retriever.search(vector, top_k=3, query_text=text)

        print(f"  '{text}'")
        if expected is None:
            print("    (should match nothing)")
        for rank, lesson in enumerate(results, start=1):
            hit = ""
            if expected and lesson["id"] == expected and rank == 1:
                hit = "  <- expected"
            passes = "PASS" if lesson["score"] >= RELEVANCE_THRESHOLD else "below"
            print(f"    {rank}. {lesson['score']:.4f} {passes:>5}  "
                  f"(sem {lesson.get('semantic_score', 0):.3f} "
                  f"lex {lesson.get('lexical_score', 0):.2f})  "
                  f"{lesson['id']:<11} {lesson['title']}{hit}")

        if results:
            top = results[0]
            if expected is None:
                off_topic_scores.append(top["score"])
            else:
                expected_count += 1
                on_topic_scores.append(top["score"])
                if top["id"] == expected:
                    correct += 1
        print()

    print("-" * 72)
    if expected_count:
        print(f"  Correct top-1 on on-topic queries: {correct}/{expected_count} "
              f"({100 * correct / expected_count:.0f}%)")
    if on_topic_scores:
        print(f"  On-topic  top-1 score: min {min(on_topic_scores):.4f}  "
              f"mean {np.mean(on_topic_scores):.4f}  max {max(on_topic_scores):.4f}")
    if off_topic_scores:
        print(f"  Off-topic top-1 score: min {min(off_topic_scores):.4f}  "
              f"mean {np.mean(off_topic_scores):.4f}  max {max(off_topic_scores):.4f}")

    if on_topic_scores and off_topic_scores:
        low = min(on_topic_scores)
        high = max(off_topic_scores)
        print()
        if low > high:
            suggested = round((low + high) / 2, 3)
            print(f"  The two groups separate cleanly. A threshold anywhere between")
            print(f"  {high:.4f} and {low:.4f} works. Suggested: {suggested}")
        else:
            print("  The groups OVERLAP - no threshold separates them perfectly.")
            print(f"  Lowest on-topic {low:.4f} sits below highest off-topic {high:.4f}.")
            print("  Favour a higher threshold: refusing to answer beats answering wrongly.")
    print()


def main() -> None:
    if len(sys.argv) > 1:
        run([(" ".join(sys.argv[1:]), None)])
    else:
        run(PROBES)


if __name__ == "__main__":
    main()
