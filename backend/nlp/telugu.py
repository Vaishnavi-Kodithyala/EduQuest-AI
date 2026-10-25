"""
Week 10 - Answering questions written in Telugu.

The intent classifier and both retrieval models are English DistilBERT models;
Telugu text is close to noise to them. Rather than force Telugu through models
that cannot read it, Telugu questions take their own route:

  1. Detect Telugu script (Unicode block U+0C00-U+0C7F).
  2. Split the Telugu chapters (and their quiz explanations) into sentences.
  3. Score every sentence against the question with character n-gram TF-IDF.

Character n-grams rather than words, because Telugu is agglutinative: "రైతు"
(farmer), "రైతులు" (farmers) and "రైతుల" (farmers') are different words but
share most of their characters. Splitting on whitespace would treat them as
unrelated; 2-4 character fragments match them naturally, with no Telugu
stemmer or model needed.

The content bank has two Telugu chapters, so this is deliberately small and
transparent. A full Telugu chatbot would need a multilingual model and many
more Telugu chapters.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from .config import DATA_DIR

MATCH_THRESHOLD = 0.25
NGRAM_SIZES = (2, 3, 4)

# Question words and light verbs. Left in, "రైతు ఏమి చేస్తాడు?" (what does
# the farmer do?) matched "సైనికుడు ... కృషి చేస్తాడు" (the soldier works...)
# on the shared verb rather than on "farmer". The same idea as the English
# stop-word list in Week 6, just much shorter.
STOPWORDS = {
    "ఏమి", "ఏమిటి", "ఎవరు", "ఎవరి", "ఎవరికి", "ఎందుకు", "ఎలా", "ఎప్పుడు", "ఎక్కడ",
    "ఏ", "ఏది", "ఏవి", "ఎన్ని", "ఎంత", "అంటే", "అని", "మరియు", "ఈ", "ఆ", "ఒక",
    "చేస్తాడు", "చేస్తారు", "చేస్తుంది", "చేయాలి", "ఉంది", "ఉన్నాయి", "ఉంటాయి", "ఉంటుంది",
    "చెబుతుంది", "చెప్పండి", "చెప్పు", "గురించి", "నేర్పుతుంది",
}

TELUGU_CHARS = re.compile(r"[ఀ-౿]")
GREETINGS = ("నమస్కారం", "నమస్తే", "హలో", "హాయ్", "శుభోదయం")


def is_telugu(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    return sum(1 for c in letters if TELUGU_CHARS.match(c)) / len(letters) >= 0.4


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?।])\s+|\n+|•", text)
    out = []
    for part in parts:
        part = re.sub(r"^[^ఀ-౿A-Za-z]+", "", part).strip()  # drop emoji bullets
        # At least three words: drops headings like "ముఖ్య సందేశం" (key message).
        if len(part.split()) >= 3 and TELUGU_CHARS.search(part):
            out.append(part)
    return out


def _grams(text: str) -> Counter:
    text = re.sub(r"[^ఀ-౿ ]", " ", text)
    text = " " + re.sub(r"\s+", " ", text).strip() + " "
    grams: Counter = Counter()
    for n in NGRAM_SIZES:
        for i in range(len(text) - n + 1):
            gram = text[i:i + n]
            if gram.strip():
                grams[gram] += 1
    return grams


@dataclass
class TeluguMatch:
    sentence: str
    score: float
    lesson: dict


class TeluguAnswerer:
    def __init__(self, lessons: list[dict] | None = None, quizzes: list[dict] | None = None) -> None:
        if lessons is None:
            with open(DATA_DIR / "lessons.json", encoding="utf-8") as fh:
                lessons = json.load(fh)
        if quizzes is None:
            with open(DATA_DIR / "quizzes.json", encoding="utf-8") as fh:
                quizzes = json.load(fh)

        explanations: dict[str, list[str]] = {}
        for quiz in quizzes:
            for q in quiz.get("questions", []):
                if q.get("explanation"):
                    explanations.setdefault(quiz["lesson_id"], []).append(q["explanation"])

        self.entries: list[tuple[str, dict]] = []
        for lesson in lessons:
            if lesson.get("subject") != "Telugu":
                continue
            text = "\n".join([lesson.get("summary", ""), lesson.get("content", "")]
                             + explanations.get(lesson["id"], []))
            ref = {k: lesson[k] for k in ("id", "title", "subject", "grade")}
            seen = set()
            for sentence in _sentences(text):
                if sentence not in seen:
                    seen.add(sentence)
                    self.entries.append((sentence, ref))

        docs = [_grams(s) for s, _ in self.entries]
        df = Counter(g for d in docs for g in d)
        n = max(len(docs), 1)
        self.idf = {g: math.log((1 + n) / (1 + c)) + 1 for g, c in df.items()}
        self.vocab = {g: i for i, g in enumerate(self.idf)}
        self.matrix = np.zeros((len(docs), len(self.vocab)), dtype=np.float32)
        for row, d in enumerate(docs):
            for g, count in d.items():
                self.matrix[row, self.vocab[g]] = (1 + math.log(count)) * self.idf[g]
        norms = np.linalg.norm(self.matrix, axis=1, keepdims=True)
        self.matrix /= np.maximum(norms, 1e-9)

    def _vector(self, text: str) -> np.ndarray:
        words = [w for w in re.findall(r"[\u0C00-\u0C7F]+", text) if w not in STOPWORDS]
        vec = np.zeros(len(self.vocab), dtype=np.float32)
        for g, count in _grams(" ".join(words) or text).items():
            if g in self.vocab:
                vec[self.vocab[g]] = (1 + math.log(count)) * self.idf[g]
        norm = float(np.linalg.norm(vec))
        return vec / norm if norm else vec

    def best(self, question: str) -> TeluguMatch | None:
        if not self.entries:
            return None
        scores = self.matrix @ self._vector(question)
        i = int(np.argmax(scores))
        return TeluguMatch(self.entries[i][0], round(float(scores[i]), 4), self.entries[i][1])

    def reply(self, question: str) -> dict:
        """A Telugu reply in the same shape as ChatResponder.respond()."""
        if any(question.strip().startswith(g) for g in GREETINGS) and len(question.split()) <= 3:
            return {
                "reply": "నమస్కారం! తెలుగు పాఠాల గురించి ఏదైనా అడగండి.",
                "understood": True, "lesson": None, "intent": "greeting", "confidence": 1.0,
                "answer": None,
            }

        match = self.best(question)
        if match is None or match.score < MATCH_THRESHOLD:
            return {
                "reply": (
                    "క్షమించండి, ఆ ప్రశ్నకు సమాధానం తెలుగు పాఠాలలో దొరకలేదు. "
                    "‘అభినందన’ లేదా ‘స్నేహబంధం’ పాఠాల గురించి అడగండి."
                ),
                "understood": False, "lesson": None, "intent": "telugu_question",
                "confidence": match.score if match else 0.0, "answer": None,
            }

        return {
            "reply": f"{match.sentence}\n\n— ‘{match.lesson['title']}’ పాఠం నుండి.",
            "understood": True,
            "lesson": match.lesson,
            "intent": "telugu_question",
            "confidence": match.score,
            "answer": {"text": match.sentence, "sentence": match.sentence,
                       "score": match.score, "source": "telugu"},
        }


@lru_cache(maxsize=1)
def get_telugu_answerer() -> TeluguAnswerer:
    return TeluguAnswerer()
