"""
Week 7 - Train and evaluate the intent classifier.

Reads the Week 6 embeddings, trains the linear head, and prints an evaluation
report: held-out accuracy, per-intent precision and recall, a confusion matrix,
and a confidence-threshold analysis.

Run from the project root:

    python -m backend.nlp.train_intent
    python -m backend.nlp.train_intent --folds 5     # cross-validation only
    python -m backend.nlp.train_intent --epochs 600

Prerequisite: python -m backend.nlp.build_dataset (needs the embeddings).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter

import numpy as np

from .classifier import CONFIDENCE_THRESHOLD, RANDOM_SEED, IntentClassifier
from .config import (
    EMBEDDINGS_FILE,
    PROCESSED_DIR,
    PROCESSED_QUERIES_FILE,
)

REPORT_FILE = PROCESSED_DIR / "week7_training_report.json"


def load_data() -> tuple[np.ndarray, list[str], list[dict]]:
    if not EMBEDDINGS_FILE.exists():
        raise SystemExit(
            "Embeddings not found. Run this first:\n"
            "    python -m backend.nlp.build_dataset"
        )

    vectors = np.load(EMBEDDINGS_FILE)
    with open(PROCESSED_QUERIES_FILE, encoding="utf-8") as fh:
        records = json.load(fh)

    if len(records) != vectors.shape[0]:
        raise SystemExit(
            f"Mismatch: {len(records)} queries but {vectors.shape[0]} embeddings.\n"
            "Re-run: python -m backend.nlp.build_dataset"
        )

    labels = [r["intent"] for r in records]
    return vectors, labels, records


def stratified_split(
    labels: list[str], test_fraction: float = 0.2, seed: int = RANDOM_SEED
) -> tuple[np.ndarray, np.ndarray]:
    """
    Split indices so every intent keeps the same proportion in train and test.

    A plain random split on a small set can easily leave an intent with zero
    test examples, which makes the per-class metrics meaningless.
    """
    rng = np.random.default_rng(seed)
    by_label: dict[str, list[int]] = {}
    for i, label in enumerate(labels):
        by_label.setdefault(label, []).append(i)

    train_idx: list[int] = []
    test_idx: list[int] = []

    for label in sorted(by_label):
        indices = np.array(by_label[label])
        rng.shuffle(indices)
        n_test = max(1, int(round(len(indices) * test_fraction)))
        test_idx.extend(indices[:n_test].tolist())
        train_idx.extend(indices[n_test:].tolist())

    return np.array(sorted(train_idx)), np.array(sorted(test_idx))


def stratified_folds(
    labels: list[str], n_folds: int = 5, seed: int = RANDOM_SEED
) -> list[np.ndarray]:
    """Split indices into n stratified folds for cross-validation."""
    rng = np.random.default_rng(seed)
    folds: list[list[int]] = [[] for _ in range(n_folds)]

    by_label: dict[str, list[int]] = {}
    for i, label in enumerate(labels):
        by_label.setdefault(label, []).append(i)

    for label in sorted(by_label):
        indices = np.array(by_label[label])
        rng.shuffle(indices)
        for position, index in enumerate(indices):
            folds[position % n_folds].append(int(index))

    return [np.array(sorted(f)) for f in folds]


def per_class_metrics(
    true_labels: list[str], predicted: list[str], classes: list[str]
) -> dict[str, dict]:
    """Precision, recall and F1 per intent, computed without sklearn."""
    metrics = {}
    for cls in classes:
        tp = sum(1 for t, p in zip(true_labels, predicted) if t == cls and p == cls)
        fp = sum(1 for t, p in zip(true_labels, predicted) if t != cls and p == cls)
        fn = sum(1 for t, p in zip(true_labels, predicted) if t == cls and p != cls)

        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall)
            else 0.0
        )
        metrics[cls] = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "support": tp + fn,
        }
    return metrics


def print_confusion(true_labels: list[str], predicted: list[str], classes: list[str]) -> None:
    """Compact confusion matrix. Rows are true, columns are predicted."""
    index = {c: i for i, c in enumerate(classes)}
    matrix = np.zeros((len(classes), len(classes)), dtype=int)
    for t, p in zip(true_labels, predicted):
        matrix[index[t]][index[p]] += 1

    header = "    " + " ".join(f"{i:>3}" for i in range(len(classes)))
    print(f"\n    {'':22}{header}")
    for i, cls in enumerate(classes):
        row = " ".join(f"{matrix[i][j]:>3}" for j in range(len(classes)))
        print(f"    {i:>2} {cls:<20} {row}")
    print("\n    Rows = true intent, columns = predicted. Diagonal is correct.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Week 7 intent classifier training")
    parser.add_argument("--epochs", type=int, default=400)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--test-fraction", type=float, default=0.2)
    parser.add_argument(
        "--seed",
        type=int,
        default=RANDOM_SEED,
        help="split seed. Change it to see how much the score depends on which "
             "examples happen to land in the test set.",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="run cross-validation with this many different seeds and report "
             "the spread. With 15 examples per intent a single run is noisy; "
             "3-5 repeats give a far more honest number.",
    )
    args = parser.parse_args()

    vectors, labels, records = load_data()
    classes = sorted(set(labels))
    label_to_index = {c: i for i, c in enumerate(classes)}
    y = np.array([label_to_index[l] for l in labels])

    print("=" * 68)
    print("WEEK 7 - INTENT CLASSIFIER TRAINING")
    print("=" * 68)
    print(f"\n  Queries      : {len(labels)}")
    print(f"  Intents      : {len(classes)}")
    print(f"  Per intent   : {dict(sorted(Counter(labels).items()))}")
    print(f"  Feature dim  : {vectors.shape[1]}")

    # --- Cross-validation ---------------------------------------------------
    print(f"\n{'-' * 68}")
    print(f"CROSS-VALIDATION ({args.folds} folds)")
    print("-" * 68)
    print(f"  Each fold trains on the rest and tests on itself. With {len(labels)} samples")
    print("  a single split is noisy, so the average across folds is the number")
    print("  to trust.\n")

    all_scores: list[float] = []
    run_means: list[float] = []

    for repeat in range(args.repeat):
        seed = args.seed + repeat
        folds = stratified_folds(labels, args.folds, seed=seed)
        fold_scores: list[float] = []

        for fold_number, test_idx in enumerate(folds, start=1):
            train_idx = np.array(
                [i for i in range(len(labels)) if i not in set(test_idx.tolist())]
            )
            classifier = IntentClassifier(classes)
            classifier.fit(
                vectors[train_idx], y[train_idx], epochs=args.epochs, verbose=False
            )
            probs = classifier.predict_proba(vectors[test_idx])
            predicted = probs.argmax(axis=1)
            accuracy = float((predicted == y[test_idx]).mean())
            fold_scores.append(accuracy)

            if args.repeat == 1:
                print(f"    fold {fold_number}  n={len(test_idx):>3}  "
                      f"accuracy {accuracy * 100:.1f}%")

        all_scores += fold_scores
        run_means.append(float(np.mean(fold_scores)))
        if args.repeat > 1:
            print(f"    seed {seed}  mean {np.mean(fold_scores) * 100:.1f}%")

    mean_cv = float(np.mean(all_scores))
    std_cv = float(np.std(all_scores))
    print(f"\n    mean {mean_cv * 100:.1f}%   std {std_cv * 100:.1f}%")
    if args.repeat > 1:
        print(f"    across {args.repeat} seeds: "
              f"{min(run_means) * 100:.1f}% to {max(run_means) * 100:.1f}%")
    print(f"    random baseline {100 / len(classes):.1f}%")

    # --- Held-out evaluation ------------------------------------------------
    print(f"\n{'-' * 68}")
    print(f"HELD-OUT EVALUATION ({int(args.test_fraction * 100)}% test split)")
    print("-" * 68)

    train_idx, test_idx = stratified_split(labels, args.test_fraction, seed=args.seed)
    print(f"\n  Train {len(train_idx)}   Test {len(test_idx)}\n")

    classifier = IntentClassifier(classes)
    classifier.fit(vectors[train_idx], y[train_idx], epochs=args.epochs, verbose=True)

    probs = classifier.predict_proba(vectors[test_idx])
    predicted_idx = probs.argmax(axis=1)
    confidences = probs.max(axis=1)

    true_names = [classes[i] for i in y[test_idx]]
    pred_names = [classes[i] for i in predicted_idx]
    accuracy = float((predicted_idx == y[test_idx]).mean())

    print(f"\n  Held-out accuracy : {accuracy * 100:.1f}% "
          f"({int((predicted_idx == y[test_idx]).sum())}/{len(test_idx)})")
    print(f"  Mean confidence   : {confidences.mean():.3f}")

    metrics = per_class_metrics(true_names, pred_names, classes)
    print(f"\n  {'intent':<22}{'prec':>7}{'rec':>7}{'f1':>7}{'n':>5}")
    for cls in classes:
        m = metrics[cls]
        print(f"  {cls:<22}{m['precision']:>7.2f}{m['recall']:>7.2f}"
              f"{m['f1']:>7.2f}{m['support']:>5}")

    print_confusion(true_names, pred_names, classes)

    errors = [
        (records[test_idx[i]]["raw_text"], true_names[i], pred_names[i], confidences[i])
        for i in range(len(test_idx))
        if predicted_idx[i] != y[test_idx][i]
    ]
    if errors:
        print("\n  Misclassified:")
        for text, true_label, pred, conf in errors:
            print(f"    '{text}'")
            print(f"      true {true_label}  ->  predicted {pred} ({conf:.2f})")

    # --- Confidence threshold ----------------------------------------------
    print(f"\n{'-' * 68}")
    print("CONFIDENCE THRESHOLD")
    print("-" * 68)
    print("  Below the threshold the chatbot should say it did not understand")
    print("  rather than act on a weak guess.\n")

    thresholds = sorted({0.3, 0.4, 0.5, 0.6, 0.7, 0.8, CONFIDENCE_THRESHOLD})
    for threshold in thresholds:
        above = confidences >= threshold
        n_above = int(above.sum())
        if n_above:
            acc_above = float((predicted_idx[above] == y[test_idx][above]).mean())
            marker = "  <- current" if abs(threshold - CONFIDENCE_THRESHOLD) < 1e-9 else ""
            print(f"    >= {threshold:.2f}   answered {n_above:>3}/{len(test_idx)}   "
                  f"accuracy when answering {acc_above * 100:.1f}%{marker}")

    # --- Retrain on everything and save ------------------------------------
    print(f"\n{'-' * 68}")
    print("FINAL MODEL")
    print("-" * 68)
    print(f"\n  Retraining on all {len(labels)} queries for deployment.")
    print("  The scores above are the honest estimate of its performance;")
    print("  the shipped model simply gets to use every example.\n")

    final = IntentClassifier(classes)
    final.fit(vectors, y, epochs=args.epochs, verbose=True)
    final.save()

    print(f"\n  Saved intent_classifier.pt and intent_labels.json")

    report = {
        "num_queries": len(labels),
        "num_intents": len(classes),
        "intents": classes,
        "epochs": args.epochs,
        "cross_validation": {
            "folds": args.folds,
            "scores": [round(s, 4) for s in fold_scores],
            "mean_accuracy": round(mean_cv, 4),
            "std": round(std_cv, 4),
        },
        "held_out": {
            "test_size": len(test_idx),
            "accuracy": round(accuracy, 4),
            "mean_confidence": round(float(confidences.mean()), 4),
            "per_class": metrics,
        },
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "random_baseline": round(1 / len(classes), 4),
    }
    with open(REPORT_FILE, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    print(f"  Saved {REPORT_FILE.name}")
    print("\n  Next: python -m backend.nlp.predict_intent \"what is a fraction\"")


if __name__ == "__main__":
    main()
