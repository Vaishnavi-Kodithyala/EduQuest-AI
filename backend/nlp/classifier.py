"""
Week 7 - Intent detection.

A linear classifier head trained on the frozen DistilBERT embeddings produced
in Week 6.

Why a single linear layer
-------------------------
The training set is 150 examples across 10 intents. A deeper network has more
parameters than we have examples and will memorise the training set instead of
learning anything. A linear layer on top of good frozen features is the
standard approach at this data size, and it is what "linear probing" means in
the literature.

The DistilBERT weights are NOT updated. Week 6 produces the features, Week 7
learns the decision boundary over them. This keeps training to a few seconds on
CPU and means the embeddings only have to be computed once.

Confidence threshold
--------------------
The classifier always returns *some* intent, even for input it has never seen.
`predict` therefore also returns the softmax probability, and callers should
treat anything below CONFIDENCE_THRESHOLD as "not understood" rather than
acting on a low-confidence guess. This is what stops the chatbot from
confidently answering nonsense.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np

from .config import EMBEDDING_DIM, PROCESSED_DIR

MODEL_FILE = PROCESSED_DIR / "intent_classifier.pt"
LABELS_FILE = PROCESSED_DIR / "intent_labels.json"

# Chosen from the threshold table printed by train_intent.
#
# At 0.60 the classifier answers 29 of 33 held-out queries at 96.6% accuracy;
# at 0.65 it answers only 27 at 96.3%. The higher bar refuses two extra
# questions and buys nothing.
#
# This matters less than it used to. A low-confidence query no longer means an
# outright refusal - the responder still runs lesson retrieval and answers from
# content if anything matches. See backend/chatbot/responder.py.
CONFIDENCE_THRESHOLD = 0.60
RANDOM_SEED = 42


class IntentClassifier:
    """Linear softmax classifier over 768-dimensional embeddings."""

    def __init__(self, labels: list[str], input_dim: int = EMBEDDING_DIM) -> None:
        import torch
        import torch.nn as nn

        self.torch = torch
        self.labels = list(labels)
        self.input_dim = input_dim
        self.model = nn.Linear(input_dim, len(self.labels))

    # -- Training -----------------------------------------------------------
    def fit(
        self,
        vectors: np.ndarray,
        label_indices: np.ndarray,
        epochs: int = 400,
        learning_rate: float = 0.01,
        weight_decay: float = 0.01,
        verbose: bool = True,
    ) -> list[float]:
        """
        Train on the full batch. 150x768 fits in memory comfortably, so there
        is no reason to mini-batch and full-batch gives a smoother loss curve.
        """
        torch = self.torch
        torch.manual_seed(RANDOM_SEED)

        x = torch.tensor(vectors, dtype=torch.float32)
        y = torch.tensor(label_indices, dtype=torch.long)

        optimiser = torch.optim.AdamW(
            self.model.parameters(), lr=learning_rate, weight_decay=weight_decay
        )
        loss_fn = torch.nn.CrossEntropyLoss()

        self.model.train()
        history: list[float] = []

        for epoch in range(epochs):
            optimiser.zero_grad()
            logits = self.model(x)
            loss = loss_fn(logits, y)
            loss.backward()
            optimiser.step()
            history.append(float(loss.item()))

            if verbose and (epoch + 1) % 100 == 0:
                print(f"      epoch {epoch + 1:>4}  loss {loss.item():.4f}")

        self.model.eval()
        return history

    # -- Inference ----------------------------------------------------------
    def predict_proba(self, vectors: np.ndarray) -> np.ndarray:
        """Softmax probabilities, shape (n_samples, n_labels)."""
        torch = self.torch
        if vectors.ndim == 1:
            vectors = vectors[None, :]

        self.model.eval()
        with torch.no_grad():
            logits = self.model(torch.tensor(vectors, dtype=torch.float32))
            probs = torch.softmax(logits, dim=1)
        return probs.numpy()

    def predict(self, vector: np.ndarray) -> tuple[str, float]:
        """Predict one embedding. Returns (intent, confidence)."""
        probs = self.predict_proba(vector)[0]
        index = int(np.argmax(probs))
        return self.labels[index], float(probs[index])

    def predict_top_k(self, vector: np.ndarray, k: int = 3) -> list[tuple[str, float]]:
        """Top k intents with their probabilities, for debugging and the UI."""
        probs = self.predict_proba(vector)[0]
        order = np.argsort(probs)[::-1][:k]
        return [(self.labels[i], float(probs[i])) for i in order]

    # -- Persistence --------------------------------------------------------
    def save(self, model_path: Path = MODEL_FILE, labels_path: Path = LABELS_FILE) -> None:
        model_path.parent.mkdir(parents=True, exist_ok=True)
        self.torch.save(self.model.state_dict(), model_path)
        with open(labels_path, "w", encoding="utf-8") as fh:
            json.dump(
                {"labels": self.labels, "input_dim": self.input_dim},
                fh,
                indent=2,
            )

    @classmethod
    def load(
        cls, model_path: Path = MODEL_FILE, labels_path: Path = LABELS_FILE
    ) -> "IntentClassifier":
        if not model_path.exists() or not labels_path.exists():
            raise FileNotFoundError(
                "Trained classifier not found. Run:\n"
                "    python -m backend.nlp.train_intent"
            )

        with open(labels_path, encoding="utf-8") as fh:
            meta = json.load(fh)

        classifier = cls(meta["labels"], input_dim=meta.get("input_dim", EMBEDDING_DIM))
        state = classifier.torch.load(model_path, map_location="cpu")
        classifier.model.load_state_dict(state)
        classifier.model.eval()
        return classifier


@lru_cache(maxsize=1)
def get_classifier() -> IntentClassifier:
    """Shared instance so the API loads the model only once."""
    return IntentClassifier.load()
