"""
Week 10 - Readable passages for chatbot replies.

Chapter sections come from the NCERT PDFs in chunks of about 100 words, and
many chunks mix explanation with exercises, answer keys, glossary notes and
figure labels. Shown whole, a reply could open with "Q8. How many lines of
symmetry..." or quote a true-or-false exercise whose statements are false
("c. Prime numbers do not have any factors") as if they were facts.

Two fixes, both applied only to the text shown to the student - which chapter
is matched does not change:

  * `is_exercise` lets the retriever prefer another section of the same
    chapter when the best-scoring one is an exercise block.
  * `focus` keeps the sentences that best match the question (two or three,
    about 70 words), skipping questions, exercise items and fragments.
"""

from __future__ import annotations

import re

MAX_WORDS = 70
MAX_SENTENCES = 3

# Things that only appear in exercises, activities and answer keys.
EXERCISE_MARKERS = re.compile(
    r"\bAns\b\s*[.:]|\bQ\s*\d+\b|_{3,}|\.{5,}|"
    r"\b(let us (do|think|discuss|write|read|speak|listen|learn|explore|try|recall)|"
    r"check your answers?|think and reflect|fill in the blanks?|match the|tick the|"
    r"true or false|answer these questions|answer the following|discuss with|"
    r"circle the|identify whether|figure it out|try this|activity \d)\b",
    re.IGNORECASE,
)
# "a. There is...", "(ii) The...", "3. Find..." - numbered exercise items. An
# item number follows the end of a sentence; "powers of 2. Sometimes" is not one.
ENUMERATED = re.compile(
    r"(?:^|(?<=[.!?:;”\"’)\]])\s+)(?:\(?[a-h]\)|[a-h]\.|\([ivx]+\)|\d{1,2}[.)])\s+(?=[A-Z0-9∠(“\"])"
)
# Bullet characters from the PDFs (some come through as control characters).
BULLETS = re.compile("[\u0080-\u009f\u2022\u25aa\u25cf\u25e6\u27a2\uf0a7\uf0b7\uf076\uf0d8]")
SENTENCE_END = re.compile(r"(?<=[.!?])[\"”’]?\s+(?=[A-Z0-9“\"‘(])")
# Exercise instructions start with a command: "Name the angles...", "Find the...".
INSTRUCTION = re.compile(
    r"^(name|find|write|draw|identify|fill|match|measure|observe|complete|list|describe|compare|"
    r"arrange|calculate|look at|try|guess|predict|answer|circle|tick|colour|color|discuss|think|"
    r"read the|work in|share|note down|record|mention|imagine|talk|tell|recite|act out)\b",
    re.IGNORECASE,
)
# Figure labels that the PDF text runs into sentences: "10 170 70 120 60", "P O Q R S".
LABEL_RUN = re.compile(r"(?:\b\d+\s+){3,}(?=\D)|(?:\b[A-Z]\s+){3,}")
ITEM = "\u00a7"   # marks a sentence that is an exercise item

STOPWORDS = set("""a an the of is are was were be been to in on at by for with from and or that this
these those it its as what which who whom how why when where do does did can could should would
will shall may might me my i you your we our they their them he she his her about into than then
there here also not no yes explain tell give show mean means meaning please""".split())


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def _content(text: str) -> set[str]:
    return {w for w in _words(text) if len(w) > 2 and w not in STOPWORDS}


def _matches(query_word: str, sentence_words: set[str]) -> bool:
    stem = query_word[:5]
    return any(w == query_word or (len(w) >= 5 and len(stem) >= 5 and w.startswith(stem)) for w in sentence_words)


def is_exercise(text: str) -> bool:
    """A section that is mostly exercises or an answer key."""
    markers = len(EXERCISE_MARKERS.findall(text))
    items = len(ENUMERATED.findall(text))
    return markers >= 2 or items >= 3 or (markers >= 1 and items >= 2)


def _usable(sentence: str) -> bool:
    words = sentence.split()
    return (
        not sentence.startswith(ITEM)
        and 5 <= len(words) <= 60
        and not sentence.rstrip("\"”’ ").endswith("?")
        and not EXERCISE_MARKERS.search(sentence)
        and not INSTRUCTION.match(sentence)
    )


def split_sentences(text: str) -> list[str]:
    """
    Sentences, with figure labels removed. A numbered or lettered exercise item
    ("c. Prime numbers do not have any factors.") is kept but marked, so it is
    never shown as a fact.
    """
    text = BULLETS.sub("\n", " ".join(text.split()))
    text = LABEL_RUN.sub("", text)
    text = ENUMERATED.sub(lambda m: "\n" + ITEM, text)
    out = []
    for chunk in text.split("\n"):
        chunk = chunk.strip()
        item = chunk.startswith(ITEM)
        for n, sentence in enumerate(SENTENCE_END.split(chunk.lstrip(ITEM).strip())):
            sentence = sentence.strip()
            if sentence:
                out.append((ITEM if item and n == 0 else "") + sentence)
    return out


def _clip(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    cut = " ".join(words[:max_words])
    end = max(cut.rfind(". "), cut.rfind("! "))
    return cut[: end + 1] if end > len(cut) // 2 else cut + "…"


def focus(text: str, question: str | None, fallback: str | None = None, max_words: int = MAX_WORDS) -> str:
    """
    The two or three sentences of `text` that best answer `question`.

    When nothing in `text` is plain prose (an exercise block), `fallback` - the
    chapter summary - is shown instead, so exercise items are never quoted.
    """
    text = (text or "").strip()
    if not text:
        return (fallback or "").strip()
    sentences = split_sentences(text)
    usable = [i for i, s in enumerate(sentences) if _usable(s)]
    if not usable:
        return (fallback or "").strip() or _clip(text, max_words)

    wanted = _content(question or "")
    def score(i: int) -> int:
        words = set(_words(sentences[i]))
        return sum(1 for w in wanted if _matches(w, words))

    best = max(usable, key=lambda i: (score(i), -i)) if wanted else usable[0]
    if wanted and score(best) == 0:
        best = usable[0]

    # The best sentence and the ones straight after it, stopping at the first
    # sentence that is not plain prose (a question, an exercise item, a label).
    chosen = [sentences[best]]
    total = len(sentences[best].split())
    for i in range(best + 1, len(sentences)):
        if len(chosen) >= MAX_SENTENCES or i not in usable:
            break
        length = len(sentences[i].split())
        if total + length > max_words:
            break
        chosen.append(sentences[i])
        total += length
    return " ".join(chosen)
