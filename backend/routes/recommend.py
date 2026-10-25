"""
Week 8 - Recommendation endpoint.

    GET /api/recommendations/{user_id}?grade=6&limit=5

Returns a ranked list of chapters the student should study next, each with the
reason it was chosen. See backend/recommender/engine.py for the rules.
"""

from fastapi import APIRouter, Query

from ..database import db
from ..models.recommend import RecommendationResponse
from ..recommender.engine import RecommendationEngine

router = APIRouter(tags=["Recommendations (Week 8)"])


@router.get("/recommendations/{user_id}", response_model=RecommendationResponse)
def get_recommendations(
    user_id: str,
    grade: int | None = Query(None, description="Restrict to one grade"),
    limit: int = Query(5, ge=1, le=20),
):
    engine = RecommendationEngine(db)
    return engine.recommend(user_id, grade=grade, limit=limit)
