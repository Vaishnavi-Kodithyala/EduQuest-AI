"""
Week 6 - The NLP pipeline entry point.

This is the single object the rest of the application should talk to. Week 7's
intent classifier and the Week 8 chatbot endpoint import ``get_pipeline()``
rather than touching the preprocessing or embedding modules directly, so the
internals can change without breaking callers.

    from backend.nlp.pipeline import get_pipeline

    pipeline = get_pipeline()
    result = pipeline.run("Whats the formula for simple interest?")
    result["processed_text"]   -> 'what be formula simple interest'
    result["embedding"]        -> np.ndarray, shape (768,)
"""

from __future__ import annotations

from functools import lru_cache
from typing import List, Optional, Sequence

import numpy as np

from .preprocess import ProcessedQuery, get_preprocessor


class NLPPipeline:
    """Preprocessing + DistilBERT embedding, behind one interface."""

    def __init__(self, load_embedder: bool = False) -> None:
        self.preprocessor = get_preprocessor()
        self._embedder = None
        self._retrieval_embedder = None
        if load_embedder:
            self._load_embedder()

    def _load_embedder(self):
        if self._embedder is None:
            from .embeddings import get_embedder

            self._embedder = get_embedder()
        return self._embedder

    @property
    def embedder(self):
        """Classification embedder. Loads DistilBERT on first access."""
        return self._load_embedder()

    @property
    def retrieval_embedder(self):
        """
        Retrieval embedder, a separate DistilBERT checkpoint.

        See config.py for why lesson search and intent classification use
        different models. Loaded lazily and independently, so a deployment that
        only classifies never pays for the retrieval model.
        """
        if self._retrieval_embedder is None:
            from .embeddings import get_retrieval_embedder

            self._retrieval_embedder = get_retrieval_embedder()
        return self._retrieval_embedder

    def embed_for_retrieval(self, texts):
        """Embed text in the retrieval model's space."""
        if isinstance(texts, str):
            texts = [texts]
        return self.retrieval_embedder.encode(list(texts))

    # -- Preprocessing only -------------------------------------------------
    def preprocess(self, text: str) -> ProcessedQuery:
        return self.preprocessor.process(text)

    def preprocess_batch(self, texts: Sequence[str]) -> List[ProcessedQuery]:
        return self.preprocessor.process_batch(list(texts))

    # -- Embedding ----------------------------------------------------------
    def embed(self, texts: Sequence[str]) -> np.ndarray:
        """
        Embed already-cleaned text.

        Note the input here is ``normalized_text``, not ``processed_text``:
        DistilBERT is trained on natural sentences and performs worse on a
        stop-word-stripped bag of lemmas.
        """
        return self.embedder.encode(list(texts))

    # -- Full run -----------------------------------------------------------
    def run(self, text: str, with_embedding: bool = True) -> dict:
        """Preprocess one query and optionally attach its embedding."""
        processed = self.preprocessor.process(text)
        result = processed.to_dict()

        if with_embedding:
            source = processed.normalized_text or text
            result["embedding"] = self.embedder.encode_one(source)
            result["embedding_model"] = self.embedder.model_name
            result["wordpiece_tokens"] = self.embedder.token_preview(source)

        return result

    def run_batch(
        self, texts: Sequence[str], with_embeddings: bool = True
    ) -> tuple[List[ProcessedQuery], Optional[np.ndarray]]:
        """Preprocess many queries, and embed them in batches."""
        processed = self.preprocess_batch(texts)

        if not with_embeddings:
            return processed, None

        sources = [p.normalized_text or p.raw_text for p in processed]
        return processed, self.embed(sources)


@lru_cache(maxsize=1)
def get_pipeline() -> NLPPipeline:
    """Shared pipeline instance."""
    return NLPPipeline()
