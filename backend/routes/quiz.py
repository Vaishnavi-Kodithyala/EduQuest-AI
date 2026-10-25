from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..database import db, lesson_completions, quizzes, quiz_attempts, users
from ..gamification.engine import GamificationEngine, diff

router = APIRouter(tags=["Quiz"])


class QuizAttemptRequest(BaseModel):
    user_id: str
    quiz_id: str
    # One entry per question, in order: the index of the chosen option, or -1
    # for a question left unanswered.
    answers: list[int]


@router.post("/quiz-attempts")
def submit_quiz(req: QuizAttemptRequest):
    quiz = quizzes.find_one({"id": req.quiz_id})
    if not quiz:
        raise HTTPException(404, "Quiz not found")

    engine = GamificationEngine(db)
    before = engine.profile(req.user_id)

    review = []
    results = []
    for i, q in enumerate(quiz["questions"]):
        chosen = req.answers[i] if i < len(req.answers) else -1
        is_correct = chosen == q["correct"]
        review.append({
            "question": q["text"],
            "options": q["options"],
            "chosen": chosen,
            "correct": q["correct"],
            "is_correct": is_correct,
            "explanation": q.get("explanation", ""),
            "concept": q.get("concept", ""),
        })
        # Stored with the attempt so the teacher dashboard can find weak
        # concepts without depending on the quiz's current option order.
        results.append({"concept": q.get("concept", ""), "correct": is_correct})

    correct = sum(1 for r in results if r["correct"])
    total = len(quiz["questions"])
    score = round(correct * 100 / total) if total else 0

    quiz_attempts.insert_one({
        "user_id": req.user_id,
        "quiz_id": req.quiz_id,
        "lesson_id": quiz.get("lesson_id"),
        "subject": quiz.get("subject"),
        "answers": req.answers,
        "results": results,
        "correct": correct,
        "total": total,
        "score": score,
        "submitted_at": datetime.now(timezone.utc),
    })
    # XP, badges and level are recomputed from the full history, so the
    # result screen shows exactly what this attempt changed.
    after = engine.profile(req.user_id)
    gamification = diff(before, after)
    store_points(req.user_id, after["xp"])

    return {"score": score, "correct": correct, "total": total,
            "review": review, "gamification": gamification}


def store_points(user_id: str, xp: int) -> None:
    """Keep users.points equal to XP; the chatbot reads it for 'how many points do I have'."""
    try:
        users.update_one({"_id": ObjectId(user_id)}, {"$set": {"points": xp}})
    except Exception:
        pass


@router.get("/progress/{user_id}")
def get_progress(user_id: str):
    attempts = list(quiz_attempts.find({"user_id": user_id}, {"_id": 0, "score": 1}))
    return {
        "lessons_completed": lesson_completions.count_documents({"user_id": user_id}),
        "quiz_attempts": len(attempts),
        "average_score": round(sum(x["score"] for x in attempts) / len(attempts)) if attempts else 0,
    }
