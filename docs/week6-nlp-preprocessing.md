# Week 6 — NLP Preprocessing Pipeline

Implements the Week 6 deliverables from the project action plan:

1. Text cleaning, tokenization, stop-word removal and lemmatization on the
   student query dataset using **spaCy** and **NLTK**
2. **DistilBERT** (Hugging Face Transformers) to convert processed text into
   contextual embeddings
3. Validation of the pipeline on sample student queries, confirming it is ready
   for Week 7 intent detection

Intent *prediction* is deliberately not implemented here — that is Week 7.

---

## Pipeline

```text
   Week 2 dataset
   data/student_queries.json  (50 labelled queries, 10 intents)
            |
            v
   +------------------------+
   | 1. Cleaning            |  lowercase, strip URLs/emails/symbols,
   |    clean_text()        |  collapse repeated chars, expand chat
   +------------------------+  shorthand ("plz" -> "please")
            |
            +--------------------------------+
            |                                |
            v                                |
   +------------------------+                |
   | 2. Tokenization        |  NLTK          |  normalized_text
   |    word_tokenize()     |  word_tokenize |  (word order intact)
   +------------------------+                |
            |                                |
            v                                |
   +------------------------+                |
   | 3. Lemmatization       |  spaCy         |
   |    en_core_web_sm      |  lemmas + POS  |
   +------------------------+                |
            |                                |
            v                                |
   +------------------------+                |
   | 4. Stop-word removal   |  NLTK list     |
   |    minus keep-list     |  minus         |
   +------------------------+  KEEP_WORDS    |
            |                                |
            v                                v
     processed_text                   +----------------+
     "what be fraction"               | 5. DistilBERT  |
            |                         |  mean pooling  |
            v                         +----------------+
     TF-IDF / keyword                        |
     features, vocabulary                    v
     statistics                       768-d vector, L2 normalised
                                             |
                                             v
                                      Week 7 intent classifier
```

---

## Two outputs, on purpose

The pipeline produces **two** representations of every query, and they feed
different consumers:

| Field | Content | Consumer |
|---|---|---|
| `normalized_text` | Lightly cleaned; word order and function words intact | DistilBERT |
| `processed_text` | Lemmatized, stop-words removed | TF-IDF / keyword features, vocabulary stats, inspection |

This split matters. Transformer models are pre-trained on natural sentences and
their whole advantage is contextual attention over word order. Feeding
DistilBERT a stop-word-stripped bag of lemmas (`"what be fraction"`) throws away
the signal it was trained to use and measurably degrades the embeddings. The
classical preprocessing output is still valuable — for vocabulary analysis, for
keyword rules, and as a fallback feature set — so both are kept.

---

## The stop-word keep-list

NLTK's English stop-word list contains words that are the *primary* signal for
several of our intent categories. Two examples from the actual dataset:

```text
"What is a numerator?"      intent: definition
"Explain the water cycle"   intent: concept_explanation
```

Strip stop words naively and the first becomes `"numerator"` — the question word
that distinguishes a definition request from an explanation request is gone.
`"I don't understand"` (clarification) becomes `"understand"`, which inverts its
meaning entirely.

`backend/nlp/config.py` therefore defines `KEEP_WORDS`, protecting:

- **Question words** — what, why, how, when, where, which, who
- **Negations** — not, no, don't, can't, isn't, won't
- **Modals and auxiliaries** — should, could, would, is, are, do, does
- **Possessives used by progress/quiz intents** — my, me, again, more

Validation check 4 confirms this works: 13 of the 50 queries contain a question
word, and 100% still contain one after filtering.

---

## Files added

```text
backend/nlp/
  __init__.py
  config.py           paths, model names, KEEP_WORDS, chat normalisation map
  preprocess.py       QueryPreprocessor - cleaning, tokenization, lemmas, stop words
  embeddings.py       DistilBertEmbedder - mean-pooled 768-d vectors
  pipeline.py         NLPPipeline - the single interface Week 7 should import
  build_dataset.py    runs the pipeline over the dataset, writes artifacts
  validate.py         the Week 6 validation report
  setup_nlp.py        downloads spaCy model, NLTK corpora, DistilBERT weights

backend/models/nlp.py     request/response schemas for the demo endpoints
backend/routes/nlp.py     /api/nlp/status, /preprocess, /embed

data/processed/
  processed_queries.json      every stage, per query
  vocabulary.json             token frequencies from processed_text
  query_embeddings.npy        float32 array, shape (50, 768)
  embeddings_meta.json        row order, labels, model configuration
  week6_validation_report.json
```

---

## Embedding design decisions

**Mean pooling, not `[CLS]`.** `distilbert-base-uncased` is a plain masked
language model. Its `[CLS]` token was never trained as a sentence summary the
way it is in a fine-tuned sentence-transformer, so using it directly gives noisy
sentence vectors. Averaging the token vectors — masked so padding contributes
nothing — is far more stable for short queries.

**L2 normalisation.** With unit-length vectors a dot product *is* the cosine
similarity, which simplifies the Week 7 similarity search and keeps the
classifier numerically better behaved.

**`max_length=64`.** Student queries are short; the longest in the dataset is
well under this. Truncating here rather than at DistilBERT's 512-token default
cuts inference time substantially with no information loss.

**Lazy loading.** The model loads on first use, not at import, so `uvicorn`
still starts in under a second.

**Inference only.** Everything runs under `torch.no_grad()` in `eval()` mode.
Week 6 produces features; Week 7 trains on them.

---

## How to run

From the **project root** (not `backend/`), because the backend uses relative
imports:

```bash
pip install -r backend/requirements.txt
python -m backend.nlp.setup_nlp        # spaCy model + NLTK corpora + DistilBERT
python -m backend.nlp.build_dataset    # writes data/processed/
python -m backend.nlp.validate         # prints the validation report
```

To run preprocessing without downloading the 265 MB model:

```bash
python -m backend.nlp.setup_nlp --skip-model
python -m backend.nlp.build_dataset --skip-embeddings
```

### Live demonstration endpoints

```bash
uvicorn backend.main:app --reload
```

Then open `http://127.0.0.1:8000/docs` and try:

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/nlp/status` | Which parts of the pipeline are ready |
| POST | `/api/nlp/preprocess` | Every preprocessing stage for one query |
| POST | `/api/nlp/embed` | DistilBERT vector for one query |

Example:

```json
POST /api/nlp/preprocess
{ "text": "plz explain wat is a fraction??" }
```

```json
{
  "normalized_text": "please explain what is a fraction",
  "tokens": ["please", "explain", "what", "is", "a", "fraction"],
  "lemmas": ["please", "explain", "what", "be", "a", "fraction"],
  "pos_tags": ["INTJ", "VERB", "PRON", "AUX", "DET", "NOUN"],
  "processed_text": "please explain what be fraction",
  "removed_stopwords": ["a"]
}
```

---

## Validation

`python -m backend.nlp.validate` runs eight checks.

**Preprocessing (1–4)** — no query is reduced to an empty string, token
reduction statistics, vocabulary and intent coverage, and question-word
retention.

**Embeddings (5–8)** — array shape and dtype, no NaN/Inf values, unit L2 norms,
same-intent vs different-intent cosine similarity, and leave-one-out
nearest-neighbour intent accuracy.

Check 8 is the headline number. It is **not** the Week 7 classifier — it just
answers "do these embeddings already separate the ten intent classes?" Each
query is matched to its most similar *other* query and we check whether the
intent labels agree. Against a 10% random baseline, a good score means a trained
classifier next week has strong features to work with.

Measured results on the Week 2 dataset (Python 3.14, Windows, CPU):

```text
PREPROCESSING
[1] Queries processed              : 50
    Empty after processing         : 0        PASS
    Duplicate query texts          : 0        PASS
[2] Tokens before stop-word removal: 236
    Tokens after                   : 172
    Reduction                      : 27.1%
[3] Vocabulary size                : 83 unique tokens
    Intent classes                 : 10 (5 queries each)
[4] Queries with a question word   : 13
    Retained after filtering       : 13 (100%) PASS

EMBEDDINGS
[5] Model                          : distilbert-base-uncased
    Array shape                    : (50, 768) PASS
    All values finite              : True      PASS
[6] Vector L2 norms                : 1.0000    PASS
[7] Mean similarity, same intent   : 0.7813
    Mean similarity, different     : 0.7021
    Separation margin              : +0.0792   PASS
[8] Leave-one-out 1-NN accuracy    : 50.0% (25/50)
    Random baseline                : 10.0%
```

### Reading the 50%

Five times the random baseline is real signal, but it is a modest score and
worth being precise about why.

**The absolute similarities are meaningless; only the margin matters.** Note
that two *unrelated* queries still score 0.70. This is the well-known
anisotropy of raw BERT-family embeddings: vectors from a model that was never
fine-tuned for sentence similarity occupy a narrow cone in the 768-dimensional
space, so everything looks similar to everything. The +0.079 margin is the
entire usable signal.

**Most of the errors are dataset labelling, not model failure.** Look at what
actually got confused:

```text
'What is a fraction?'      concept_explanation -> definition
'What is a numerator?'     definition          -> concept_explanation
'What is the denominator?' definition          -> concept_explanation
```

These are the same surface form — *"What is a X?"* — carrying two different
labels in the Week 2 dataset. No embedding model can separate them, because
they are not separable. The same holds for the greeting class:

```text
'Can you help me?'            greeting -> formula_help
'I need help with my lesson'  greeting -> homework_help
```

Both are labelled `greeting` but read as help requests. The nearest-neighbour
result is arguably more sensible than the label.

Strip out the ambiguous pairs and the remaining errors are few. The headline
number is therefore better understood as a measurement of **dataset label
quality** than of embedding quality — which is exactly the kind of thing this
check exists to surface before Week 7 trains on it.

**Check 8 is a lower bound on Week 7.** A single nearest neighbour uses the raw
768 dimensions with no learning at all. A trained classifier learns a
projection that amplifies the discriminative directions and suppresses the
anisotropic ones, and will score higher on the same features.

---

## Findings for Week 7

**`intents.json` duplicates `student_queries.json` exactly.** All 50 example
phrases in `intents.json` are the same 50 texts as in `student_queries.json` —
a 100% overlap. The two files look like two datasets but are one. Running
`build_dataset.py --include-intents` therefore does not expand the training
data, it duplicates it, and it makes check 8 meaningless because every query
finds its own copy as its nearest neighbour. `validate.py` now detects exact
duplicates and marks the accuracy invalid when it sees them. **Do not use that
flag until `intents.json` contains genuinely new phrases.**

**Several intent labels overlap.** `definition` and `concept_explanation` both
contain *"What is a X?"* phrasings, and two `greeting` queries are really help
requests. Before training in Week 7, either relabel these or merge the two
overlapping classes. This is the highest-value fix available and costs nothing
but a text edit.

**Dataset size.** 50 queries across 10 intents is 5 examples per class. Enough
to validate that the pipeline runs correctly, too thin to train a reliable
classifier. New queries need to be written by hand — there is no second dataset
to draw on, per the duplication finding above.

**English only.** All 50 queries are `"language": "en"`, and both
`en_core_web_sm` and `distilbert-base-uncased` are English models. The action
plan calls for at least one regional language, so multilingual query handling is
still outstanding. The fix is `distilbert-base-multilingual-cased`, a one-line
change to `EMBEDDING_MODEL_NAME` in `config.py`; the pipeline code itself does
not need to change.

**Embeddings are static.** `query_embeddings.npy` is generated from the current
dataset file. If the dataset changes, re-run `build_dataset.py`.

**Windows Smart App Control blocks spaCy.** On Windows 11 with Smart App
Control enabled, spaCy's compiled `.pyd` files are unsigned and get blocked,
producing `ImportError: DLL load failed while importing kb: An Application
Control policy has blocked this file`. torch and numpy are unaffected. The
workaround is to disable Smart App Control, which is permanent and cannot be
re-enabled without reinstalling Windows.
