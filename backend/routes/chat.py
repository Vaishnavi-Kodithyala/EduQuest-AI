"""
Week 7 - The chatbot endpoint.

Receives a student query, runs it through the Week 6 NLP pipeline and the
Week 7 intent classifier, and returns an appropriate response.

Request flow
------------
    message
      -> Telugu?             (Week 10: Telugu chapter matcher)
      -> calculation?        (Week 10: maths solver with working)
      -> preprocess          (Week 6: clean, tokenize, lemmatize)
      -> embed               (Week 6: DistilBERT, 768-d)
      -> classify            (Week 7: linear head -> intent + confidence)
      -> retrieve            (Week 7: semantic lesson search)
      -> extract answer      (Week 10: DistilBERT-SQuAD reads the passages)
      -> respond             (Week 7: rule-based reply per intent)

The steps live in backend/chatbot/service.py so the endpoint, the demo script
and the answer test all run the same code.

Everything is lazy-loaded, so importing this router does not slow server
startup. The first chat request pays the model-loading cost.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from ..chatbot.service import ChatService
from ..database import db
from ..models.chat import ChatRequest, ChatResponse, ChatStatusResponse
from ..nlp.classifier import CONFIDENCE_THRESHOLD, get_classifier
from ..nlp.config import EMBEDDINGS_FILE
from ..nlp.pipeline import get_pipeline
from ..nlp.retriever import LESSON_INDEX_FILE, get_retriever

router = APIRouter(prefix="/chat", tags=["Chatbot (Week 7)"])

_MODEL_MISSING = (
    "The intent classifier has not been trained yet. From the project root run:\n"
    "  python -m backend.nlp.build_dataset\n"
    "  python -m backend.nlp.train_intent\n"
    "  python -m backend.nlp.build_lesson_index"
)


@router.get("/status", response_model=ChatStatusResponse)
def chat_status():
    """Whether the chatbot's models are trained and available."""
    intents: list[str] = []
    classifier_ready = True
    try:
        intents = get_classifier().labels
    except FileNotFoundError:
        classifier_ready = False

    return ChatStatusResponse(
        classifier_ready=classifier_ready,
        lesson_index_ready=LESSON_INDEX_FILE.exists(),
        intents=intents,
        confidence_threshold=CONFIDENCE_THRESHOLD,
    )


@router.post("", response_model=ChatResponse)
def chat(payload: ChatRequest):
    try:
        result = ChatService(database=db).reply(
            payload.message, grade=payload.grade, user_id=payload.user_id
        )
    except FileNotFoundError:
        raise HTTPException(503, _MODEL_MISSING)

    # Log the interaction. The Week 8 recommender reads this to work out which
    # chapters a student keeps asking about, which is a signal of struggle that
    # quiz scores alone do not capture.
    if payload.user_id:
        try:
            db["chat_history"].insert_one(
                {
                    "user_id": payload.user_id,
                    "message": payload.message,
                    "intent": result["intent"],
                    "confidence": round(result["confidence"], 4),
                    "understood": result["understood"],
                    "lesson_id": (result["lesson"] or {}).get("id"),
                    "answered": bool(result.get("answer")),
                    "asked_at": datetime.now(timezone.utc),
                }
            )
        except Exception:
            # Logging must never break the reply the student is waiting for.
            pass

    return ChatResponse(
        reply=result["reply"],
        intent=result["intent"],
        confidence=round(result["confidence"], 4),
        understood=result["understood"],
        lesson=result["lesson"],
        top_intents=[(name, round(prob, 4)) for name, prob in result.get("top_intents", [])],
        answer=result.get("answer"),
    )
