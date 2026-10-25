"""
Week 7 - Semantic lesson retrieval.

Finds the lesson most relevant to a student's question by comparing DistilBERT
embeddings, rather than matching keywords.

Why semantic rather than keyword search
---------------------------------------
"Explain how plants make food" shares no useful keyword with a chapter titled
"Photosynthesis", so a keyword search returns nothing. Embedding both and
comparing them by cosine similarity finds it, because the two phrases sit close
together in the embedding space. This is the same pipeline Week 6 built, reused
on the content side.

The index is built once from data/lessons.json and cached to disk, so the
16 lessons are only embedded a single time rather than on every request.
"""

from __future__ import annotations

import json
from functools import lru_cache

import numpy as np

from .config import DATA_DIR, PROCESSED_DIR
from .excerpt import is_exercise

# Words stripped before lexical matching. The Week 6 preprocessing keeps
# question words on purpose - they carry intent - but here they are pure noise:
# without this filter "what is an acid" matches any chapter whose summary opens
# with "What if ...".
_LEXICAL_STOPWORDS = frozenset("""
what when where which whose whom that this these those there here
does did done doing have has had will would could should shall
about with from into onto over under between among during
explain tell show give help please make made take took
some more most much many other another such very just only
your yours mine ours their them they then than
""".split())

LESSON_INDEX_FILE = PROCESSED_DIR / "lesson_embeddings.npy"
LESSON_META_FILE = PROCESSED_DIR / "lesson_index_meta.json"
LESSONS_FILE = DATA_DIR / "lessons.json"

# Below this similarity, treat the best match as "nothing relevant found".
#
# This value depends entirely on which embedding model is configured.
#
# With the base `distilbert-base-uncased` checkpoint, unrelated text sat at
# ~0.70 similarity and nothing below 0.78 was meaningful. The retrieval-tuned
# checkpoint spreads scores out properly, so the useful cutoff is much lower.
#
# Always re-tune after changing EMBEDDING_MODEL_NAME:
#     python -m backend.nlp.test_retrieval
RELEVANCE_THRESHOLD = 0.49


def _is_heading(line: str) -> bool:
    """
    Heading lines open with an emoji and are short.

    The chapter content uses lines like "🔎 TESTING SUBSTANCES" as headings.
    Sometimes a blank line follows the heading, sometimes the body starts on
    the next line, so splitting on blank lines alone does not work - the
    heading has to be recognised directly.
    """
    line = line.strip()
    if not line or len(line) > 70:
        return False
    return ord(line[0]) > 0x2000  # emoji / symbol range, not a normal letter


def split_sections(lesson: dict) -> list[dict]:
    """
    Break a chapter into its sections.

    Indexing whole chapters means the best the chatbot can say is "open this
    chapter". Indexing sections means it can return the paragraph that actually
    answers the question.

    The summary is included as the first section so every chapter has at least
    one entry even when `content` is missing.
    """
    sections: list[dict] = []

    summary = (lesson.get("summary") or "").strip()
    if summary:
        sections.append({"heading": "Overview", "text": summary})

    heading = "Overview"
    body: list[str] = []

    def flush() -> None:
        text = " ".join(body).strip()
        if text:
            sections.append({"heading": heading, "text": text})

    for raw_line in (lesson.get("content") or "").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if _is_heading(line):
            flush()
            heading = line
            body = []
        else:
            body.append(line)
    flush()

    return sections


def section_index_text(lesson: dict, section: dict) -> str:
    """What gets embedded for one section."""
    return (
        f"{lesson['subject']}. {lesson['title']}. "
        f"{section['heading']}. {section['text']}"
    ).strip()


def lesson_index_text(lesson: dict) -> str:
    """
    The text used to represent a lesson in the index.

    Title plus summary, not the full chapter body: the body is long enough that
    it would be truncated at 64 tokens anyway, and its opening lines are often
    scene-setting rather than topical. Title and summary describe what the
    chapter is actually about.
    """
    return (
        f"{lesson['subject']}. {lesson['title']}. {lesson.get('summary', '')}"
    ).strip()


class LessonRetriever:
    """Cosine-similarity search over the lesson index."""

    def __init__(self) -> None:
        if not LESSON_INDEX_FILE.exists() or not LESSON_META_FILE.exists():
            raise FileNotFoundError(
                "Lesson index not found. Build it with:\n"
                "    python -m backend.nlp.build_lesson_index"
            )

        self.vectors = np.load(LESSON_INDEX_FILE)
        with open(LESSON_META_FILE, encoding="utf-8") as fh:
            self.meta = json.load(fh)
        self.lessons = self.meta["lessons"]

    @staticmethod
    def _lexical_overlap(query_text: str, lesson: dict) -> float:
        """
        Fraction of the query's words that appear in the lesson's indexed text.

        Semantic search alone misses obvious word matches: "what is an acid"
        should find a chapter with "Acidic" in the title, but the embeddings
        ranked it second. Prefix matching catches acid/acidic, angle/angles and
        pattern/patterns, which are exactly the cases students actually type.
        """
        query_words = {
            w.strip(".,:;!?\"'()").lower()
            for w in query_text.split()
        }
        query_words = {
            w for w in query_words if len(w) > 3 and w not in _LEXICAL_STOPWORDS
        }
        if not query_words:
            return 0.0

        lesson_words = {
            w.strip(".,:;!?\"'()").lower()
            for w in lesson.get("indexed_text", lesson.get("title", "")).split()
        }
        lesson_words = {
            w for w in lesson_words if len(w) > 3 and w not in _LEXICAL_STOPWORDS
        }

        hits = 0
        for qw in query_words:
            for lw in lesson_words:
                if (
                    qw == lw
                    or (len(lw) >= 4 and qw.startswith(lw[:4]))
                    or (len(qw) >= 4 and lw.startswith(qw[:4]))
                ):
                    hits += 1
                    break
        return hits / len(query_words)

    def search(
        self,
        query_vector: np.ndarray,
        grade: int | None = None,
        subject: str | None = None,
        top_k: int = 3,
        query_text: str | None = None,
        lexical_weight: float = 0.25,
    ) -> list[dict]:
        """
        Return the top_k most similar lessons, each with a `score`.

        Grade and subject filters are applied before ranking so a Grade 6
        student never gets pointed at a Grade 7 chapter.
        """
        candidates = [
            i
            for i, lesson in enumerate(self.lessons)
            if (grade is None or lesson["grade"] == grade)
            and (subject is None or lesson["subject"] == subject)
        ]
        if not candidates:
            return []

        query = query_vector / max(float(np.linalg.norm(query_vector)), 1e-9)
        subset = self.vectors[candidates]
        semantic = subset @ query

        # Blend in lexical overlap when the raw query text is available.
        if query_text:
            lexical = np.array(
                [
                    self._lexical_overlap(query_text, self.lessons[i])
                    for i in candidates
                ]
            )
            scores = (1 - lexical_weight) * semantic + lexical_weight * lexical
        else:
            lexical = np.zeros(len(candidates))
            scores = semantic

        order = np.argsort(scores)[::-1][:top_k]
        results = []
        for position in order:
            index = int(position)
            lesson = dict(self.lessons[candidates[index]])
            lesson["score"] = round(float(scores[index]), 4)
            lesson["semantic_score"] = round(float(semantic[index]), 4)
            lesson["lexical_score"] = round(float(lexical[index]), 4)
            results.append(lesson)
        return results

    def best_match(
        self,
        query_vector: np.ndarray,
        grade: int | None = None,
        query_text: str | None = None,
        allow_other_grades: bool = True,
    ) -> dict | None:
        """
        Single best section, or None if nothing clears the relevance bar.

        If nothing in the student's own grade is relevant, this falls back to
        searching every grade. Knowledge does not respect grade boundaries: a
        Grade 7 student asking "what is an angle" should be pointed at the
        Grade 6 chapter that covers it, not told the topic does not exist. The
        result is marked so the reply can say which grade it came from.
        """
        results = self.search(
            query_vector, grade=grade, top_k=SECTIONS_TO_CONSIDER, query_text=query_text
        )
        if results and results[0]["score"] >= RELEVANCE_THRESHOLD:
            best = _prefer_prose(results)
            best["from_other_grade"] = False
            return best

        if not allow_other_grades or grade is None:
            return None

        wider = self.search(query_vector, grade=None, top_k=SECTIONS_TO_CONSIDER, query_text=query_text)
        if wider and wider[0]["score"] >= RELEVANCE_THRESHOLD:
            best = _prefer_prose(wider)
            best["from_other_grade"] = best["grade"] != grade
            return best

        return None


# Week 10: when the best section is an exercise block, a section of the same
# chapter scoring almost as well is shown instead. The chapter never changes.
SECTIONS_TO_CONSIDER = 8
PROSE_MARGIN = 0.05


def _prefer_prose(results: list[dict]) -> dict:
    top = results[0]
    if not is_exercise(top.get("text", "")):
        return top
    for other in results[1:]:
        if (other["id"] == top["id"]
                and other["score"] >= max(top["score"] - PROSE_MARGIN, RELEVANCE_THRESHOLD)
                and not is_exercise(other.get("text", ""))):
            return other
    return top


@lru_cache(maxsize=1)
def get_retriever() -> LessonRetriever:
    return LessonRetriever()
