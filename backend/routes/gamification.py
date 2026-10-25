"""
Week 9 - Gamification endpoints.

    GET  /api/gamification/{user_id}        XP, level, streak, badges, rewards
    GET  /api/leaderboard?grade=6&user_id=   class ranking by XP
    POST /api/lessons/{lesson_id}/complete   mark a chapter as read (+XP)
"""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from pymongo.errors import DuplicateKeyError

from ..database import db, lesson_completions, lessons
from ..gamification.engine import GamificationEngine, diff
from .quiz import store_points

router = APIRouter(tags=["Gamification"])


class CompleteLessonRequest(BaseModel):
    user_id: str


@router.get("/gamification/{user_id}")
def get_gamification(user_id: str):
    return GamificationEngine(db).profile(user_id)


@router.get("/leaderboard")
def get_leaderboard(
    grade: int | None = Query(None, description="Only students in this grade"),
    user_id: str | None = Query(None, description="Mark this student's row"),
    limit: int = Query(10, ge=1, le=100),
):
    return GamificationEngine(db).leaderboard(grade=grade, limit=limit, user_id=user_id)


@router.post("/lessons/{lesson_id}/complete")
def complete_lesson(lesson_id: str, req: CompleteLessonRequest):
    if not lessons.find_one({"id": lesson_id}, {"_id": 1}):
        raise HTTPException(404, "Lesson not found")

    engine = GamificationEngine(db)
    before = engine.profile(req.user_id)
    try:
        lesson_completions.insert_one({
            "user_id": req.user_id,
            "lesson_id": lesson_id,
            "completed_at": datetime.now(timezone.utc),
        })
        already = False
    except DuplicateKeyError:
        already = True  # reading a chapter twice earns XP once

    after = engine.profile(req.user_id)
    store_points(req.user_id, after["xp"])
    return {"already_completed": already, **diff(before, after)}
