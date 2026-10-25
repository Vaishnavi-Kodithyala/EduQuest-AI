from pydantic import BaseModel, Field
from typing import List, Optional


class PreprocessRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class PreprocessResponse(BaseModel):
    raw_text: str
    normalized_text: str
    tokens: List[str]
    lemmas: List[str]
    pos_tags: List[str]
    filtered_tokens: List[str]
    processed_text: str
    removed_stopwords: List[str]


class EmbedResponse(BaseModel):
    text: str
    model: str
    embedding_dim: int
    wordpiece_tokens: List[str]
    vector_preview: List[float]
    l2_norm: float


class NLPStatusResponse(BaseModel):
    spacy_model: str
    embedding_model: str
    embedding_model_loaded: bool
    processed_dataset_ready: bool
    embeddings_ready: bool
    num_processed_queries: Optional[int] = None
