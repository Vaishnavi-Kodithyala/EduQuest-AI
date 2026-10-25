"""
Week 6 - Central configuration for the NLP preprocessing pipeline.

Keeping every path, model name and tunable constant in one file means the
Week 7 intent-detection work can import these values instead of hard-coding
them again.
"""

from pathlib import Path

# --- Paths -----------------------------------------------------------------
# This file lives at <project_root>/backend/nlp/config.py
BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"

# Week 2 inputs
STUDENT_QUERIES_FILE = DATA_DIR / "student_queries.json"
INTENTS_FILE = DATA_DIR / "intents.json"

# Week 6 outputs
PROCESSED_QUERIES_FILE = PROCESSED_DIR / "processed_queries.json"
EMBEDDINGS_FILE = PROCESSED_DIR / "query_embeddings.npy"
EMBEDDINGS_META_FILE = PROCESSED_DIR / "embeddings_meta.json"
VOCABULARY_FILE = PROCESSED_DIR / "vocabulary.json"
VALIDATION_REPORT_FILE = PROCESSED_DIR / "week6_validation_report.json"

# --- Models ----------------------------------------------------------------
SPACY_MODEL = "en_core_web_sm"

# Two DistilBERT checkpoints, because intent classification and lesson
# retrieval want opposite things from an embedding.
#
# Measured on this project's data:
#
#                                    intent acc.   retrieval top-1
#   distilbert-base-uncased              92.7%           50%
#   multi-qa-distilbert-cos-v1           81.3%          100%
#
# `multi-qa` is trained so that a question and its answer land in the same
# region of the space. That is exactly right for finding the chapter a student
# is asking about, and exactly wrong for telling "explain the order of
# operations" apart from "I don't understand the order of operations" - same
# topic, different intent. The base masked language model keeps that
# distinction but has no useful notion of topical similarity.
#
# So each model does the job it is good at. Both are DistilBERT, both use mean
# pooling, both are loaded lazily.

# Intent classification (Week 7 classifier, Week 6 query embeddings)
EMBEDDING_MODEL_NAME = "distilbert-base-uncased"

# Lesson retrieval (Week 7 semantic search over the content bank)
RETRIEVAL_MODEL_NAME = "sentence-transformers/multi-qa-distilbert-cos-v1"

# Answer extraction (Week 10): DistilBERT fine-tuned on SQuAD question
# answering. Reads a retrieved passage and points at the words that answer the
# question. See backend/nlp/answerer.py.
QA_MODEL_NAME = "distilbert-base-cased-distilled-squad"

EMBEDDING_DIM = 768          # DistilBERT hidden size
MAX_SEQ_LENGTH = 64          # student queries are short; 64 tokens is plenty
EMBEDDING_BATCH_SIZE = 16

# --- Stop-word handling ----------------------------------------------------
# NLTK's stop-word list contains words that are *essential* signals for our
# intent categories. "what is a fraction" (definition) and "explain fractions"
# (concept_explanation) both collapse to "fraction" if question words are
# stripped, which would make the two intents indistinguishable in Week 7.
# These words are therefore protected from stop-word removal.
KEEP_WORDS = {
    # question words - separate definition / concept_explanation / clarification
    "what", "why", "how", "when", "where", "which", "who", "whom", "whose",
    # negation - flips meaning entirely
    "not", "no", "nor", "don", "don't", "didn", "didn't", "doesn", "doesn't",
    "can", "cannot", "couldn", "couldn't", "won", "won't", "isn", "isn't",
    # modal / request markers - separate example_request and homework_help
    "should", "could", "would", "will", "do", "does", "did", "is", "are",
    # progress / quiz intents lean on these
    "my", "me", "again", "more", "very", "too",
}

# Informal spellings that appear in student chat input. Normalising them before
# tokenisation keeps the vocabulary tight and stops "plz"/"pls" from becoming
# separate unknown tokens.
CHAT_NORMALISATION = {
    "plz": "please",
    "pls": "please",
    "u": "you",
    "ur": "your",
    "r": "are",
    "n": "and",
    "y": "why",
    "wat": "what",
    "wht": "what",
    "hw": "homework",
    "ans": "answer",
    "qn": "question",
    "ques": "question",
    "eg": "example",
    "exp": "explain",
    "maths": "math",
    "thx": "thanks",
    "tq": "thanks",
    "ty": "thanks",
    "gm": "good morning",
    "idk": "i do not know",
    "im": "i am",
    "dont": "do not",
    "cant": "cannot",
    "whats": "what is",
    "hows": "how is",
}

# Tokens shorter than this are dropped after lemmatisation, unless protected.
MIN_TOKEN_LENGTH = 2
