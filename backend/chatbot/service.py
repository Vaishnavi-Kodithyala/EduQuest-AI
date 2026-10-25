"""
The complete chatbot pipeline, in one place.

The chat endpoint, the sample-output script and the answer test all call
`ChatService.reply`, so what is demonstrated and measured is exactly what
students get. (Before this, the endpoint and the demo script each had their own
copy of the steps, and they had drifted: the live endpoint never searched the
textbook when the intent classifier was unsure, so the "I am not certain, but
this looks relevant" fallback only ever worked in the demo.)

Order of the steps:

  1. Telugu script        -> Telugu chapter matcher        (backend/nlp/telugu.py)
  2. A calculation        -> maths solver with working     (backend/nlp/math_solver.py)
  3. Everything else      -> Week 6 preprocessing, Week 7 intent classifier,
                             semantic retrieval, then
  4. A factual question   -> exact answer extracted from the retrieved
                             textbook passages             (backend/nlp/answerer.py)
  5. Otherwise            -> the Week 7/8 rule-based reply for the intent
"""

from __future__ import annotations

from ..nlp.answerer import ANSWER_THRESHOLD, get_answer_extractor, is_question, wants_short_answer
from ..nlp.classifier import CONFIDENCE_THRESHOLD, get_classifier
from ..nlp.math_solver import solve as solve_math
from ..nlp.pipeline import get_pipeline
from ..nlp.retriever import RELEVANCE_THRESHOLD, get_retriever
from ..nlp.telugu import get_telugu_answerer, is_telugu
from .responder import ChatResponder, _lesson_link, answer_reply, math_reply

# Intents whose reply depends on finding a chapter.
CONTENT_INTENTS = {
    "definition",
    "concept_explanation",
    "example_request",
    "formula_help",
    "homework_help",
    "clarification",
}

# Intents where a short exact answer is the right reply. Homework is left out
# on purpose: for homework the bot points to the method, not the answer.
ANSWER_INTENTS = CONTENT_INTENTS - {"homework_help"}

# Passages the answer model reads. Three was too few: the passage with the
# right definition was often fourth or fifth (see answerer.py).
PASSAGES_TO_READ = 6

# Passages down to this retrieval score are read, below the usual relevance bar,
# because an answer from one must also be backed by the question's own words
# (see MIN_SUPPORT) - two independent signals have to agree.
QA_MIN_RELEVANCE = 0.36   # run 3: the scurvy passage scored 0.382
MIN_SUPPORT = 0.5

# The intent classifier learned "off topic" from questions like "what is the
# weather", so textbook facts asked plainly ("which star appears stationary in
# the north?") were refused. Off-topic questions still go to the textbook, but
# an answer is only given when the textbook clearly supports it.


class ChatService:
    def __init__(self, database=None, extractor=None) -> None:
        self.db = database
        # Injected by test_answers.py to compare answer models.
        self.extractor = extractor

    def _lesson(self, lesson_id: str) -> dict | None:
        if self.db is None:
            return None
        return self.db["lessons"].find_one(
            {"id": lesson_id}, {"_id": 0, "id": 1, "title": 1, "subject": 1, "grade": 1}
        )

    def reply(self, message: str, grade: int | None = None, user_id: str | None = None) -> dict:
        # 1. Telugu
        if is_telugu(message):
            result = get_telugu_answerer().reply(message)
            return {**result, "top_intents": [], "cleaned": message, "processed": message}

        # 2. Calculations
        solution = solve_math(message)
        if solution is not None:
            lesson = self._lesson(solution.lesson_id)
            return {
                "reply": math_reply(solution, lesson),
                "intent": "calculation",
                "confidence": 1.0,
                "understood": True,
                "lesson": _lesson_link(lesson),
                "answer": {"text": solution.answer, "sentence": None, "score": 1.0,
                           "source": "math", "working": solution.working},
                "top_intents": [],
                "cleaned": message,
                "processed": message,
            }

        # 3. Intent and retrieval
        pipeline = get_pipeline()
        classifier = get_classifier()
        processed = pipeline.preprocess(message)
        source = processed.normalized_text or message

        intent_vector = pipeline.embedder.encode_one(source)
        intent, confidence = classifier.predict(intent_vector)
        top_intents = classifier.predict_top_k(intent_vector, k=3)
        confident = confidence >= CONFIDENCE_THRESHOLD

        try:
            retriever = get_retriever()
        except FileNotFoundError:
            retriever = None

        # Search the textbook for content intents, and also whenever the
        # classifier is unsure - an oddly phrased question may still be about
        # a chapter.
        asks_question = is_question(message)
        maybe_textbook = intent == "out_of_scope" and asks_question
        needs_retrieval = (confident and intent in CONTENT_INTENTS) or not confident or maybe_textbook
        retrieval_vector = (
            pipeline.retrieval_embedder.encode_one(source)
            if retriever is not None and needs_retrieval
            else None
        )

        base = {
            "intent": intent,
            "confidence": confidence,
            "top_intents": top_intents,
            "cleaned": source,
            "processed": processed.processed_text,
        }

        # 4. Exact answer from the textbook
        wants_answer = (
            asks_question
            and wants_short_answer(message)
            and (not confident or intent in ANSWER_INTENTS or maybe_textbook)
        )
        candidate = None
        if retrieval_vector is not None and wants_answer:
            found = retriever.search(
                retrieval_vector, grade=grade, top_k=PASSAGES_TO_READ, query_text=message
            )
            if found:
                base["top_passage"] = {"title": found[0]["title"], "score": found[0]["score"]}
            # Only the chapter the search ranked first: the answer should come
            # from the chapter the bot names ("Rah ul" came from Spices that
            # Heal Us for a question about the neem tree's name).
            passages = [
                p for p in found
                if p["score"] >= QA_MIN_RELEVANCE and p["id"] == found[0]["id"]
            ]
            ranked = []
            if passages:
                try:
                    ranked = (self.extractor or get_answer_extractor()).candidates(message, passages)
                except Exception:
                    # The answer model is optional: if it is missing or fails
                    # to load, fall back to the passage reply below.
                    ranked = []

            def acceptable(c) -> bool:
                if c.score < ANSWER_THRESHOLD:
                    return False
                weak_passage = c.passage["score"] < RELEVANCE_THRESHOLD
                return not ((weak_passage or maybe_textbook) and c.support < MIN_SUPPORT)

            # The best-ranked candidate that passes the checks. Taking only the
            # top one meant a rejected guess ("5683") hid a good one ("6174").
            answer = next((c for c in ranked if acceptable(c)), None)
            candidate = ranked[0] if ranked else None

            # Kept for test_answers.py: what the model proposed, shown or not.
            base["candidate"] = (
                {"text": candidate.text, "score": candidate.score,
                 "support": candidate.support, "rank": candidate.rank}
                if candidate else None
            )
            base["candidates"] = [
                {"text": c.text, "score": c.score, "support": c.support, "rank": c.rank,
                 "relevance": c.passage["score"], "accepted": acceptable(c)}
                for c in ranked[:3]
            ]
            if answer is not None:
                if maybe_textbook:
                    # Labelled off-topic, but the textbook answered it: report
                    # it as a factual question so the chat does not tag a
                    # correct answer "Off topic".
                    base["intent"] = "factual_question"
                return {
                    **base,
                    "reply": answer_reply(answer),
                    "understood": True,
                    "lesson": _lesson_link(answer.passage),
                    "answer": {"text": answer.text, "sentence": answer.sentence,
                               "score": answer.score, "source": "textbook"},
                }

        # 5. Rule-based reply for the intent
        result = ChatResponder(retriever=retriever, database=self.db).respond(
            intent=intent,
            confidence=confidence,
            query_vector=retrieval_vector,
            grade=grade,
            user_id=user_id,
            query_text=message,
        )
        return {**base, **result, "answer": None}
