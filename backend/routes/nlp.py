"""
Week 6 - Inspection endpoints for the NLP preprocessing pipeline.

These exist so the pipeline can be demonstrated live during the review instead
of only through terminal output. They deliberately stop at preprocessing and
embedding: intent *prediction* is Week 7, and the chatbot response endpoint is
Week 8.

DistilBERT is loaded lazily on the first call to /api/nlp/embed, so adding this
router does not slow down server startup.
"""

import json

from fastapi import APIRouter, HTTPException

from ..models.nlp import (
    EmbedResponse,
    NLPStatusResponse,
    PreprocessRequest,
    PreprocessResponse,
)
from ..nlp.config import (
    EMBEDDINGS_FILE,
    EMBEDDING_MODEL_NAME,
    PROCESSED_QUERIES_FILE,
    SPACY_MODEL,
)
from ..nlp.pipeline import get_pipeline

router = APIRouter(prefix="/nlp", tags=["NLP Pipeline (Week 6)"])


@router.get("/status", response_model=NLPStatusResponse)
def nlp_status():
    """Which parts of the Week 6 pipeline are set up and ready."""
    pipeline = get_pipeline()

    num_processed = None
    if PROCESSED_QUERIES_FILE.exists():
        try:
            with open(PROCESSED_QUERIES_FILE, encoding="utf-8") as fh:
                num_processed = len(json.load(fh))
        except (json.JSONDecodeError, OSError):
            num_processed = None

    return NLPStatusResponse(
        spacy_model=SPACY_MODEL,
        embedding_model=EMBEDDING_MODEL_NAME,
        embedding_model_loaded=pipeline._embedder is not None,
        processed_dataset_ready=PROCESSED_QUERIES_FILE.exists(),
        embeddings_ready=EMBEDDINGS_FILE.exists(),
        num_processed_queries=num_processed,
    )


@router.post("/preprocess", response_model=PreprocessResponse)
def preprocess_query(payload: PreprocessRequest):
    """Run cleaning, tokenization, lemmatization and stop-word removal."""
    result = get_pipeline().preprocess(payload.text)
    return PreprocessResponse(**result.to_dict())


@router.post("/embed", response_model=EmbedResponse)
def embed_query(payload: PreprocessRequest):
    """
    Generate the DistilBERT embedding for a query.

    Returns only the first 8 dimensions - a full 768-value array is not useful
    in a JSON response and the norm is enough to confirm the vector is valid.
    """
    pipeline = get_pipeline()
    processed = pipeline.preprocess(payload.text)
    source = processed.normalized_text or payload.text

    try:
        embedder = pipeline.embedder
        vector = embedder.encode_one(source)
    except ImportError as exc:
        raise HTTPException(
            503,
            "torch/transformers are not installed. Run: "
            "pip install -r requirements.txt",
        ) from exc
    except OSError as exc:
        raise HTTPException(
            503,
            f"Could not load '{EMBEDDING_MODEL_NAME}'. The first run needs "
            "internet access to download the model weights.",
        ) from exc

    return EmbedResponse(
        text=source,
        model=embedder.model_name,
        embedding_dim=int(vector.shape[0]),
        wordpiece_tokens=embedder.token_preview(source),
        vector_preview=[round(float(v), 5) for v in vector[:8]],
        l2_norm=round(float((vector @ vector) ** 0.5), 5),
    )
