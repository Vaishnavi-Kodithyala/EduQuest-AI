"""
Week 7 - Predict the intent of a query from the command line.

Useful for spot-checking the classifier and for demonstrating it in the review
without starting the server.

    python -m backend.nlp.predict_intent "what is a fraction"
    python -m backend.nlp.predict_intent          # interactive mode
"""

from __future__ import annotations

import sys

from .classifier import CONFIDENCE_THRESHOLD, get_classifier
from .pipeline import get_pipeline


def predict(text: str) -> None:
    pipeline = get_pipeline()
    classifier = get_classifier()

    processed = pipeline.preprocess(text)
    source = processed.normalized_text or text
    vector = pipeline.embedder.encode_one(source)  # classification model

    intent, confidence = classifier.predict(vector)
    top = classifier.predict_top_k(vector, k=3)

    print(f"\n  query      : {text}")
    print(f"  normalized : {source}")
    print(f"  processed  : {processed.processed_text}")

    if confidence < CONFIDENCE_THRESHOLD:
        print(f"\n  intent     : NOT UNDERSTOOD (best guess {intent}, {confidence:.3f})")
        print(f"               below the {CONFIDENCE_THRESHOLD} threshold")
    else:
        print(f"\n  intent     : {intent}  ({confidence:.3f})")

    print("\n  top 3:")
    for name, probability in top:
        bar = "#" * int(probability * 30)
        print(f"    {name:<22}{probability:.3f}  {bar}")
    print()


def main() -> None:
    if len(sys.argv) > 1:
        predict(" ".join(sys.argv[1:]))
        return

    print("Interactive intent prediction. Blank line or Ctrl+C to quit.")
    while True:
        try:
            text = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not text:
            return
        predict(text)


if __name__ == "__main__":
    main()
