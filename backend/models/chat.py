from pydantic import BaseModel, Field
from typing import List, Optional, Tuple


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    user_id: Optional[str] = None
    grade: Optional[int] = None
    language: str = "en"


class LessonRef(BaseModel):
    id: str
    title: str
    subject: str
    grade: int


class AnswerInfo(BaseModel):
    """The exact answer, when the bot found one (Week 10)."""
    text: str
    source: str                     # "textbook", "math" or "telugu"
    score: float
    sentence: Optional[str] = None  # textbook sentence the answer came from
    working: List[str] = []         # steps, for calculations


class ChatResponse(BaseModel):
    reply: str
    intent: str
    confidence: float
    understood: bool
    lesson: Optional[LessonRef] = None
    top_intents: List[Tuple[str, float]] = []
    answer: Optional[AnswerInfo] = None


class ChatStatusResponse(BaseModel):
    classifier_ready: bool
    lesson_index_ready: bool
    intents: List[str] = []
    confidence_threshold: float
