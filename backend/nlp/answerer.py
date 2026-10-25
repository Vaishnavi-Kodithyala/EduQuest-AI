"""
Week 10 - Extractive question answering over the textbook.

Retrieval finds the passages that are about a student's question; this module
reads those passages and picks out the exact words that answer it.

    "What is the SI unit of length?"
        retrieval -> "...The system of units now used is known as the
                      International System of Units or SI units. The SI unit
                      of length is metre. A metre scale is shown..."
        answer    -> "metre"  (in the sentence "The SI unit of length is metre.")

Model
-----
`distilbert-base-cased-distilled-squad`: DistilBERT fine-tuned on SQuAD, a
dataset of 100,000 questions whose answers are spans of a Wikipedia passage.
It keeps the project on one model family (DistilBERT, as in the action plan)
and, because it can only point at words that are already in the passage, it
cannot invent an answer - every answer is a quotation from the NCERT text.

The model always proposes some span, so each answer carries a confidence (the
probability of its start token times that of its end token). Below
ANSWER_THRESHOLD the chatbot shows the passage instead of a guess.

Choosing between passages
-------------------------
The first measured run (25/35) showed the model's confidence cannot tell
look-alike definitions apart: asked "what is the change of water into water
vapour called?" it answered "condensation" with 0.99 confidence, because the
passage it was given defined condensation ("conversion of water vapour into
its liquid state") and the evaporation passage was not among the three read.

So more passages are read, and each candidate is re-ranked by *support*: how
many of the question's content words appear, in the same order, in the
sentence the answer came from (longest common subsequence). Word order is what
separates the pairs - "water into ... vapour" (evaporation) against "water
vapour into" (condensation), "only two factors" (prime) against "more than two
factors" (composite) - and a "not" in the sentence that the question lacks
("can be seen, but not clearly" - translucent) counts against it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from .config import QA_MODEL_NAME

# Below this the extracted span is not shown as "the answer". Tuned with
# `python -m backend.nlp.test_answers`.
ANSWER_THRESHOLD = 0.30

# How much the model's confidence counts against word-order support when
# ranking candidates: rank = score * (RANK_BASE + (1 - RANK_BASE) * support).
# At 0.4 (run 2), support dominated and a sentence that merely repeated the
# question ("find the temperature range of a laboratory thermometer") beat the
# real answer ("Its range is from -10 C to 110 C"). 0.6 keeps the look-alike
# fixes (evaporation, prime, transparent) - see docs/week-status.md.
RANK_BASE = 0.6

MAX_ANSWER_TOKENS = 30   # longer spans are almost always wrong
MAX_LENGTH = 384         # question + passage tokens per window
STRIDE = 96              # overlap when a passage needs more than one window

# "Tell me about magnets" and "give me an example" want a passage, not a
# three-word span, so they are not treated as answerable questions.
QUESTION_START = re.compile(
    r"^\s*(what|what's|whats|which|who|whom|whose|when|where|why|how|"
    r"is|are|was|were|does|do|did|can|could|name|define)\b",
    re.IGNORECASE,
)


def is_question(text: str) -> bool:
    """A question that a short span can answer, rather than 'explain X'."""
    return bool(text) and (text.strip().endswith("?") or bool(QUESTION_START.match(text)))


# Questions whose answer is an explanation, not a few words. In the first
# sample report the span model answered "what is a prime number" with "2" and
# "how do camels survive in the desert" with "while a fish thrives in water";
# these now get the chapter passage, as before.
EXPLAIN = re.compile(r"^\s*(why|how)\b(?!\s+(many|much|long|far|old|big|tall|high|often)\b)")
OPEN_ENDED = re.compile(r"\b(learn|learnt|learned|lesson|moral|message|theme|main idea|about)\b")
DEFINITION = re.compile(
    r"^\s*(what is|what are|what's|whats|define|meaning of|what do you mean by)\s+"
    r"(a |an |the )?(.+?)\s*\??\s*$"
)


def wants_short_answer(text: str) -> bool:
    """
    True for specific questions ("what is the SI unit of length?"), False for
    ones that need an explanation ("what is a prime number", "why...", "how...").
    """
    q = (text or "").lower().strip()
    if EXPLAIN.match(q) or OPEN_ENDED.search(q):
        return False
    m = DEFINITION.match(q)
    if m:
        words = m.group(3).split()
        if "called" in words or "known" in words:
            return True                     # "what is moving air called?"
        if m.group(1) in ("define", "meaning of", "what do you mean by"):
            return False
        if (m.group(2) or "").strip() in ("a", "an"):
            return False                    # "what is a prime number"
        if not m.group(2) and len(words) <= 2:
            return False                    # "what is symmetry"
    return True


@dataclass
class Answer:
    text: str
    score: float           # the model's confidence in the span
    sentence: str
    passage: dict          # the retrieved section the answer came from
    support: float = 0.0   # question words found, in order, in the sentence
    rank: float = 0.0      # score combined with support; picks the winner


STOPWORDS = set("""a an the of is are was were be been to in on at by for with from and or that
this these those what which who whom whose when where why how do does did can could would should
will shall may might called known its it their there here as we you i me my your our his her them
they""".split())
NEGATIONS = {"not", "no", "never", "cannot", "nor"}


def _content_words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOPWORDS]


def _same_word(a: str, b: str) -> bool:
    # "see" matches "seen", "factor" matches "factors"
    return a == b or (min(len(a), len(b)) >= 3 and (a.startswith(b) or b.startswith(a)))


def support(question: str, sentence: str) -> float:
    """Share of the question's content words found in order in the sentence (0-1)."""
    q, s = _content_words(question), _content_words(sentence)
    if not q:
        return 0.0
    table = [[0] * (len(s) + 1) for _ in range(len(q) + 1)]
    for i in range(1, len(q) + 1):
        for j in range(1, len(s) + 1):
            table[i][j] = (table[i - 1][j - 1] + 1 if _same_word(q[i - 1], s[j - 1])
                           else max(table[i - 1][j], table[i][j - 1]))
    value = table[-1][-1] / len(q)
    if (NEGATIONS & set(s)) and not (NEGATIONS & set(q)):
        value *= 0.7
    return round(value, 4)


def sentence_around(context: str, start: int, end: int) -> str:
    """The sentence of `context` that contains characters start..end."""
    left = max(context.rfind(mark, 0, start) for mark in (". ", "? ", "! ", "\n"))
    left = 0 if left < 0 else left + 1
    right_candidates = [context.find(mark, end) for mark in (". ", "? ", "! ", "\n")]
    right_candidates = [r for r in right_candidates if r >= 0]
    right = min(right_candidates) + 1 if right_candidates else len(context)
    return context[left:right].strip()


def _clean_span(text: str) -> str:
    return text.strip().strip(",;:").strip()


def is_junk(text: str) -> bool:
    """Spans that are never an answer: exercise blanks and answer-key labels."""
    t = text.strip().strip(".:")
    return (
        not any(ch.isalnum() for ch in t)
        or "___" in t
        or t.lower() in {"ans", "answer", "q", "fig"}
    )


class AnswerExtractor:
    def __init__(self, model_name: str = QA_MODEL_NAME, tokenizer=None, model=None) -> None:
        self.model_name = model_name
        self._tokenizer = tokenizer
        self._model = model
        # SQuAD 2.0 models were also trained on questions the passage cannot
        # answer, and signal "no answer" by pointing at the first token. SQuAD
        # 1.1 models (like the DistilBERT default) always point at a span.
        self.can_abstain = "squad2" in model_name.lower()

    def _load(self):
        if self._model is None:
            from transformers import AutoModelForQuestionAnswering, AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModelForQuestionAnswering.from_pretrained(self.model_name)
            self._model.eval()
        return self._tokenizer, self._model

    def _best_span(self, question: str, context: str) -> tuple[str, float, int, int]:
        """Best answer span in one passage: (text, score, char_start, char_end)."""
        import torch

        tokenizer, model = self._load()
        encoded = tokenizer(
            question,
            context,
            truncation="only_second",
            max_length=MAX_LENGTH,
            stride=STRIDE,
            return_overflowing_tokens=True,
            return_offsets_mapping=True,
            padding=True,
            return_tensors="pt",
        )
        offsets = encoded.pop("offset_mapping").tolist()
        encoded.pop("overflow_to_sample_mapping", None)
        inputs = {k: v for k, v in encoded.items() if k in ("input_ids", "attention_mask")}

        with torch.no_grad():
            output = model(**inputs)
        starts = output.start_logits.numpy()
        ends = output.end_logits.numpy()

        best = ("", 0.0, 0, 0)
        for window in range(starts.shape[0]):
            sequence_ids = encoded.sequence_ids(window)
            in_context = np.array([sid == 1 for sid in sequence_ids])
            if not in_context.any():
                continue

            # Softmax over passage tokens only, as the Hugging Face pipeline
            # does - plus the first token for models that can say "no answer".
            allowed = in_context.copy()
            if self.can_abstain:
                allowed[0] = True
            start_logits = np.where(allowed, starts[window], -1e9)
            end_logits = np.where(allowed, ends[window], -1e9)
            start_p = np.exp(start_logits - start_logits.max())
            start_p /= start_p.sum()
            end_p = np.exp(end_logits - end_logits.max())
            end_p /= end_p.sum()

            # Every (start, end) pair inside the passage with
            # start <= end < start + MAX_ANSWER_TOKENS.
            in_passage = in_context.astype(float)
            pair = np.triu(np.outer(start_p * in_passage, end_p * in_passage))
            pair = np.tril(pair, MAX_ANSWER_TOKENS - 1)
            s, e = np.unravel_index(int(np.argmax(pair)), pair.shape)
            score = float(pair[s, e])
            if self.can_abstain and start_p[0] * end_p[0] >= score:
                continue  # the model says this window does not answer it
            if score > best[1]:
                char_start = offsets[window][s][0]
                char_end = offsets[window][e][1]
                best = (_clean_span(context[char_start:char_end]), score, char_start, char_end)
        return best

    def candidates(self, question: str, passages: list[dict]) -> list[Answer]:
        """The model's best span in each passage, best-ranked first."""
        found = []
        for passage in passages:
            context = (passage.get("text") or "").strip()
            if len(context.split()) < 5:
                continue
            text, score, start, end = self._best_span(question, context)
            if not text or is_junk(text):
                continue
            sentence = sentence_around(context, start, end)
            backing = support(question, sentence)
            found.append(Answer(
                text=text,
                score=round(score, 4),
                sentence=sentence,
                passage=passage,
                support=backing,
                rank=round(score * (RANK_BASE + (1 - RANK_BASE) * backing), 4),
            ))
        found.sort(key=lambda a: a.rank, reverse=True)
        return found

    def best_answer(self, question: str, passages: list[dict]) -> Answer | None:
        """Top-ranked candidate, however low its score."""
        found = self.candidates(question, passages)
        return found[0] if found else None

    def answer(self, question: str, passages: list[dict], threshold: float = ANSWER_THRESHOLD) -> Answer | None:
        """Best answer across the retrieved passages, or None if none is good enough."""
        best = self.best_answer(question, passages)
        if best is None or best.score < threshold:
            return None
        return best


@lru_cache(maxsize=1)
def get_answer_extractor() -> AnswerExtractor:
    return AnswerExtractor()
