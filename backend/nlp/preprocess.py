"""
Week 6 - Text preprocessing for student queries.

Pipeline stages
---------------
raw query
  -> clean_text()        lowercase, strip noise, expand chat shorthand
  -> tokenize()          NLTK word_tokenize
  -> lemmatize()         spaCy lemmas + POS tags
  -> remove_stopwords()  NLTK stop-word list, minus a protected keep-list
  -> processed_text      space-joined lemma string

Two different outputs are produced on purpose:

* ``normalized_text`` - lightly cleaned, word order and function words intact.
  This is what gets fed to DistilBERT. Transformer models are pre-trained on
  natural sentences and lose accuracy if you hand them a bag of lemmas.
* ``processed_text``  - the fully reduced lemma string. This is what feeds
  keyword/TF-IDF style features, vocabulary statistics and the readable
  inspection output for the review.

Both are stored so Week 7 can choose per model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict, field
from functools import lru_cache
from typing import List

import nltk
import spacy
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

from .config import (
    CHAT_NORMALISATION,
    KEEP_WORDS,
    MIN_TOKEN_LENGTH,
    SPACY_MODEL,
)

# --- Regex patterns (compiled once) ----------------------------------------
URL_PATTERN = re.compile(r"https?://\S+|www\.\S+")
EMAIL_PATTERN = re.compile(r"\S+@\S+\.\S+")
# Keep letters, digits, whitespace and intra-word apostrophes/hyphens.
NOISE_PATTERN = re.compile(r"[^a-z0-9\s'\-]")
REPEATED_CHARS = re.compile(r"(.)\1{2,}")       # "helloooo" -> "helloo"
MULTI_SPACE = re.compile(r"\s+")

_REQUIRED_NLTK_PACKAGES = [
    ("corpora/stopwords", "stopwords"),
    ("tokenizers/punkt", "punkt"),
    ("tokenizers/punkt_tab", "punkt_tab"),
]


def ensure_nltk_data() -> None:
    """Download the NLTK corpora we need, only if they are missing."""
    for resource_path, package_name in _REQUIRED_NLTK_PACKAGES:
        try:
            nltk.data.find(resource_path)
        except LookupError:
            nltk.download(package_name, quiet=True)


@lru_cache(maxsize=1)
def get_spacy_model():
    """Load spaCy once and reuse it. Parser and NER are not needed for lemmas."""
    try:
        return spacy.load(SPACY_MODEL, disable=["parser", "ner"])
    except OSError as exc:  # pragma: no cover - environment setup issue
        raise OSError(
            f"spaCy model '{SPACY_MODEL}' is not installed. Run:\n"
            f"    python -m spacy download {SPACY_MODEL}"
        ) from exc


@lru_cache(maxsize=1)
def get_stopwords() -> frozenset:
    """NLTK English stop words, minus the words our intents depend on."""
    ensure_nltk_data()
    return frozenset(set(stopwords.words("english")) - KEEP_WORDS)


@dataclass
class ProcessedQuery:
    """Everything the pipeline produced for a single query."""

    raw_text: str
    normalized_text: str          # -> DistilBERT
    tokens: List[str] = field(default_factory=list)          # NLTK tokenization
    lemmas: List[str] = field(default_factory=list)          # spaCy lemmas
    pos_tags: List[str] = field(default_factory=list)        # spaCy POS
    filtered_tokens: List[str] = field(default_factory=list)  # after stop-word removal
    processed_text: str = ""      # -> TF-IDF / keyword features
    removed_stopwords: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class QueryPreprocessor:
    """Runs the Week 6 preprocessing stages over student query text."""

    def __init__(self) -> None:
        self.nlp = get_spacy_model()
        self.stop_words = get_stopwords()

    # -- Stage 1: cleaning --------------------------------------------------
    def clean_text(self, text: str) -> str:
        """Lowercase, remove noise, and expand common student chat shorthand."""
        if not text:
            return ""

        text = text.lower().strip()
        text = URL_PATTERN.sub(" ", text)
        text = EMAIL_PATTERN.sub(" ", text)
        text = REPEATED_CHARS.sub(r"\1\1", text)
        text = NOISE_PATTERN.sub(" ", text)
        text = MULTI_SPACE.sub(" ", text).strip()

        # Expand shorthand word-by-word so "plz" -> "please" but "plzz" is left
        # to the repeated-character rule above.
        expanded = [CHAT_NORMALISATION.get(word, word) for word in text.split()]
        return " ".join(expanded).strip()

    # -- Stage 2: tokenization ---------------------------------------------
    def tokenize(self, cleaned_text: str) -> List[str]:
        """NLTK word tokenization on the cleaned string."""
        if not cleaned_text:
            return []
        return word_tokenize(cleaned_text)

    # -- Stage 3 + 4: lemmatization and stop-word removal -------------------
    def lemmatize_and_filter(self, cleaned_text: str):
        """
        Run spaCy for lemmas/POS, then drop stop words and punctuation.

        Returns (lemmas, pos_tags, kept_tokens, removed_stopwords).
        """
        if not cleaned_text:
            return [], [], [], []

        doc = self.nlp(cleaned_text)

        lemmas: List[str] = []
        pos_tags: List[str] = []
        kept: List[str] = []
        removed: List[str] = []

        for token in doc:
            if token.is_space or token.is_punct:
                continue

            lemma = token.lemma_.lower().strip()
            if not lemma:
                continue

            lemmas.append(lemma)
            pos_tags.append(token.pos_)

            is_protected = lemma in KEEP_WORDS or token.text.lower() in KEEP_WORDS
            is_stop = lemma in self.stop_words or token.text.lower() in self.stop_words
            too_short = len(lemma) < MIN_TOKEN_LENGTH and not lemma.isdigit()

            if is_protected:
                kept.append(lemma)
            elif is_stop:
                removed.append(lemma)
            elif too_short:
                removed.append(lemma)
            else:
                kept.append(lemma)

        return lemmas, pos_tags, kept, removed

    # -- Full pipeline ------------------------------------------------------
    def process(self, text: str) -> ProcessedQuery:
        """Run every stage on a single query and return the full record."""
        cleaned = self.clean_text(text)
        tokens = self.tokenize(cleaned)
        lemmas, pos_tags, kept, removed = self.lemmatize_and_filter(cleaned)

        return ProcessedQuery(
            raw_text=text,
            normalized_text=cleaned,
            tokens=tokens,
            lemmas=lemmas,
            pos_tags=pos_tags,
            filtered_tokens=kept,
            processed_text=" ".join(kept),
            removed_stopwords=removed,
        )

    def process_batch(self, texts: List[str]) -> List[ProcessedQuery]:
        """Process many queries. Uses spaCy's pipe for speed on larger sets."""
        cleaned_texts = [self.clean_text(t) for t in texts]
        results: List[ProcessedQuery] = []

        for raw, cleaned, doc in zip(
            texts, cleaned_texts, self.nlp.pipe(cleaned_texts, batch_size=64)
        ):
            lemmas: List[str] = []
            pos_tags: List[str] = []
            kept: List[str] = []
            removed: List[str] = []

            for token in doc:
                if token.is_space or token.is_punct:
                    continue
                lemma = token.lemma_.lower().strip()
                if not lemma:
                    continue

                lemmas.append(lemma)
                pos_tags.append(token.pos_)

                is_protected = lemma in KEEP_WORDS or token.text.lower() in KEEP_WORDS
                is_stop = lemma in self.stop_words or token.text.lower() in self.stop_words
                too_short = len(lemma) < MIN_TOKEN_LENGTH and not lemma.isdigit()

                if is_protected:
                    kept.append(lemma)
                elif is_stop or too_short:
                    removed.append(lemma)
                else:
                    kept.append(lemma)

            results.append(
                ProcessedQuery(
                    raw_text=raw,
                    normalized_text=cleaned,
                    tokens=self.tokenize(cleaned),
                    lemmas=lemmas,
                    pos_tags=pos_tags,
                    filtered_tokens=kept,
                    processed_text=" ".join(kept),
                    removed_stopwords=removed,
                )
            )

        return results


@lru_cache(maxsize=1)
def get_preprocessor() -> QueryPreprocessor:
    """Shared singleton so the API doesn't reload spaCy on every request."""
    return QueryPreprocessor()


if __name__ == "__main__":
    pre = get_preprocessor()
    samples = [
        "Explain photosynthesis",
        "What is a numerator?",
        "plz help me with my hw!!!",
        "I don't understand this again",
        "Whats the formula for simple interest?",
    ]
    for sample in samples:
        result = pre.process(sample)
        print(f"raw        : {result.raw_text}")
        print(f"normalized : {result.normalized_text}")
        print(f"tokens     : {result.tokens}")
        print(f"processed  : {result.processed_text}")
        print(f"removed    : {result.removed_stopwords}")
        print("-" * 60)
