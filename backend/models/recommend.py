from pydantic import BaseModel
from typing import List, Optional


class RecommendationItem(BaseModel):
    lesson_id: str
    title: str
    subject: str
    grade: int
    reason: str
    kind: str
    priority: int
    quiz_id: Optional[str] = None
    score: Optional[int] = None


class RecommendationBasis(BaseModel):
    quiz_attempts: int
    average_score: int
    chat_questions: int
    chapters_attempted: int
    chapters_read: int = 0


class RecommendationResponse(BaseModel):
    recommendations: List[RecommendationItem]
    based_on: RecommendationBasis
