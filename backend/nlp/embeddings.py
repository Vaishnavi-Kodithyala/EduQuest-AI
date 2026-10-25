"""
Week 6 - DistilBERT contextual embeddings.

Turns a student query into a fixed-length 768-dimensional vector using
``distilbert-base-uncased`` from Hugging Face Transformers.

Design notes
------------
* **Mean pooling, not [CLS].** ``distilbert-base-uncased`` is a plain masked
  language model; its [CLS] token was never trained as a sentence summary the
  way it is in a fine-tuned sentence-transformer. Averaging the token vectors
  (masked so padding is excluded) gives a far more stable sentence
  representation for short queries.
* **L2 normalisation.** With unit-length vectors, a dot product *is* the cosine
  similarity, which makes the Week 7 similarity search and classifier training
  simpler and numerically better behaved.
* **Lazy loading.** The model is only downloaded/loaded on first use, so
  importing this module stays cheap and the FastAPI server still starts fast.
* **Inference only.** Everything runs under ``torch.no_grad()`` in ``eval()``
  mode. Week 6 produces features; Week 7 does the training.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List, Sequence

import numpy as np

from .config import (
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_DIM,
    EMBEDDING_MODEL_NAME,
    MAX_SEQ_LENGTH,
    RETRIEVAL_MODEL_NAME,
)


class DistilBertEmbedder:
    """Wraps DistilBERT and produces mean-pooled sentence embeddings."""

    def __init__(
        self,
        model_name: str = EMBEDDING_MODEL_NAME,
        max_length: int = MAX_SEQ_LENGTH,
    ) -> None:
        # Imported here so that `import embeddings` does not pull in torch
        # unless an embedding is actually requested.
        import torch
        from transformers import AutoModel, AutoTokenizer

        self.torch = torch
        self.model_name = model_name
        self.max_length = max_length

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        self.model.eval()

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)

    # -- Pooling ------------------------------------------------------------
    def _mean_pool(self, last_hidden_state, attention_mask):
        """
        Average token vectors, ignoring padding.

        last_hidden_state: (batch, seq_len, hidden)
        attention_mask:    (batch, seq_len)
        """
        mask = attention_mask.unsqueeze(-1).float()          # (b, s, 1)
        summed = (last_hidden_state * mask).sum(dim=1)        # (b, h)
        counts = mask.sum(dim=1).clamp(min=1e-9)              # (b, 1)
        return summed / counts

    # -- Public API ---------------------------------------------------------
    def encode(
        self,
        texts: Sequence[str],
        batch_size: int = EMBEDDING_BATCH_SIZE,
        normalize: bool = True,
    ) -> np.ndarray:
        """
        Embed a list of texts.

        Returns an array of shape (len(texts), 768), float32.
        """
        if isinstance(texts, str):
            texts = [texts]
        if not texts:
            return np.zeros((0, EMBEDDING_DIM), dtype=np.float32)

        torch = self.torch
        all_vectors: List[np.ndarray] = []

        with torch.no_grad():
            for start in range(0, len(texts), batch_size):
                batch = list(texts[start : start + batch_size])

                encoded = self.tokenizer(
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=self.max_length,
                    return_tensors="pt",
                )
                encoded = {k: v.to(self.device) for k, v in encoded.items()}

                output = self.model(**encoded)
                pooled = self._mean_pool(
                    output.last_hidden_state, encoded["attention_mask"]
                )

                if normalize:
                    pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)

                all_vectors.append(pooled.cpu().numpy().astype(np.float32))

        return np.vstack(all_vectors)

    def encode_one(self, text: str, normalize: bool = True) -> np.ndarray:
        """Embed a single string. Returns shape (768,)."""
        return self.encode([text], normalize=normalize)[0]

    def token_preview(self, text: str) -> List[str]:
        """WordPiece tokens DistilBERT actually sees. Useful for the demo."""
        return self.tokenizer.tokenize(text)


@lru_cache(maxsize=4)
def get_embedder(model_name: str = EMBEDDING_MODEL_NAME) -> DistilBertEmbedder:
    """
    Shared instance per model name, so each checkpoint loads only once.

    Cached by argument, so get_embedder() and
    get_embedder(RETRIEVAL_MODEL_NAME) return two independent embedders that
    each stay in memory after first use.
    """
    return DistilBertEmbedder(model_name=model_name)


def cosine_similarity_matrix(vectors: np.ndarray) -> np.ndarray:
    """
    Pairwise cosine similarity for a stack of vectors.

    Vectors coming out of ``encode(normalize=True)`` are already unit length,
    but this re-normalises defensively so it is safe on any input.
    """
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.clip(norms, 1e-9, None)
    unit = vectors / norms
    return unit @ unit.T


def get_retrieval_embedder() -> DistilBertEmbedder:
    """The checkpoint used for lesson search."""
    return get_embedder(RETRIEVAL_MODEL_NAME)


if __name__ == "__main__":
    embedder = get_embedder()
    samples = [
        "what is a fraction",
        "define a fraction",
        "explain photosynthesis",
        "how many points do i have",
    ]
    vectors = embedder.encode(samples)
    print(f"model      : {embedder.model_name}")
    print(f"device     : {embedder.device}")
    print(f"shape      : {vectors.shape}")
    print(f"wordpieces : {embedder.token_preview(samples[0])}")

    sims = cosine_similarity_matrix(vectors)
    print("\ncosine similarity")
    for i, text in enumerate(samples):
        row = "  ".join(f"{sims[i][j]:.3f}" for j in range(len(samples)))
        print(f"  {row}   <- {text}")
