# Week 7 — Intent Detection and Chatbot Core

Implements the Week 7 deliverables:

1. Train an intent detection and text classification model on the labelled
   query dataset and DistilBERT embeddings
2. Build the chatbot backend endpoint in FastAPI that receives a student query,
   runs it through the NLP engine, and returns an appropriate response
3. Test classifier accuracy on held-out samples and refine the intent
   categories as needed

---

## Request flow

```text
   "explain lines and angles"
            |
            v
   +--------------------------+
   | Week 6 preprocessing     |  clean, tokenize, lemmatize
   +--------------------------+
            |
            +---------------------------+
            |                           |
            v                           v
   +------------------+       +------------------------+
   | distilbert-base  |       | multi-qa-distilbert    |
   | -uncased         |       | -cos-v1                |
   | 768-d            |       | 768-d                  |
   +------------------+       +------------------------+
            |                           |
            v                           v
   +------------------+       +------------------------+
   | Linear classifier|       | Hybrid lesson search   |
   | 10 intents       |       | 75% semantic + 25% lex |
   +------------------+       +------------------------+
            |                           |
            +-------------+-------------+
                          v
                 +------------------+
                 | Rule-based       |
                 | responder        |
                 +------------------+
                          |
                          v
                  POST /api/chat
```

---

## The dataset had to be fixed first

Week 6's validation surfaced three problems that would have made any Week 7
training meaningless. All three are fixed in `backend/nlp/build_queries.py`,
which regenerates `student_queries.json` and `intents.json`.

**`intents.json` duplicated `student_queries.json` exactly.** All 50 example
phrases were the same 50 texts. It looked like a second dataset and was not.
It now holds intent descriptions rather than duplicate training data.

**`definition` and `concept_explanation` were not separable.** Both contained
"What is a X?" phrasings. The boundary is now explicit — `definition` asks what
a *term* means, `concept_explanation` asks how a *process* works — and the
queries are written consistently against it. Both intents scored 1.00 precision
and recall afterwards.

**The queries referenced a curriculum that does not exist.** The original 50
asked about photosynthesis, fractions and simple interest. The content bank
contains none of those; it holds NCERT chapters on patterns, lines and angles,
acids and bases, large numbers. Lesson retrieval therefore had nothing correct
to find. Every query now references a real chapter.

The set also grew from 5 to 15 examples per intent, and `out_of_scope` gained
several "Show me ..." phrasings — every "show" query previously belonged to
`progress_help`, so the classifier had learned that the verb itself meant
progress.

---

## Two models, because the two tasks want opposite things

This is the main design decision of Week 7, and it was driven by measurement
rather than assumption.

| Embedding model | Intent accuracy (5-fold CV) | Retrieval top-1 |
|---|---|---|
| `distilbert-base-uncased` | 92.7% | 50% |
| `multi-qa-distilbert-cos-v1` | 81.3% | 100% |

Running everything through the retrieval-tuned checkpoint fixed lesson search
and broke intent classification. The confusion matrix showed exactly why — the
new errors were `clarification` ↔ `concept_explanation`, `formula_help` →
`concept_explanation`, `quiz_help` → `formula_help`. Every pair shares a
**topic** but differs in what the student is **asking for**.

That is precisely what `multi-qa` is trained to do. It maps a question and its
answer into the same region of the space, which deliberately collapses "explain
the order of operations" and "I don't understand the order of operations".
Correct for search. Fatal for intent.

So each task uses the checkpoint suited to it. Both are DistilBERT, both use
mean pooling, both load lazily, and the retrieval model only loads when an
intent actually needs a lesson — greetings, progress questions and out-of-scope
queries never touch it.

---

## Intent classifier

A single linear layer over the frozen 768-dimensional embeddings. The
DistilBERT weights are not updated: Week 6 produces features, Week 7 learns a
decision boundary over them.

With 150 examples across 10 intents, a deeper network has more parameters than
there are training examples and would memorise rather than generalise. Linear
probing on good frozen features is the standard approach at this data size.

### Results

```text
5-fold cross-validation : 89.3%  (std 5.7%)
Held-out (20% split)    : 100.0% (30/30)
Random baseline         : 10.0%
Mean confidence         : 0.915
```

**Quote the 89.3%.** The held-out split is 30 samples, so a perfect score there
is partly luck. The cross-validation mean across five folds, with its spread,
is the honest estimate.

### Confidence threshold

The classifier always returns some intent, even for input it has never seen. It
also returns the softmax probability, and anything below
`CONFIDENCE_THRESHOLD` is treated as "not understood" rather than acted on.

The threshold sits at **0.65**, chosen from data. In an earlier run the only
held-out error sat at 0.63 confidence while everything above 0.70 was correct.
Declining a handful of borderline queries is cheaper than answering them wrongly.

---

## Lesson retrieval

Hybrid scoring: 75% semantic similarity, 25% lexical word overlap.

Semantic search alone ranked "Exploring Substances: Acidic, Basic, and Neutral"
*second* for the query "what is an acid". Adding a lexical component with
prefix matching catches acid/acidic, angle/angles and pattern/patterns — the
cases students actually type. Common words are stripped before matching, or
"what is an acid" matches any chapter whose summary opens with "What if ...".

### Results

```text
Correct top-1 on on-topic queries : 10/10
On-topic  top-1 score : min 0.4380  mean 0.5721  max 0.7080
Off-topic top-1 score : min 0.0870  mean 0.1661  max 0.2480
```

The two groups separate cleanly, so `RELEVANCE_THRESHOLD = 0.35` sits in the
gap. Off-topic controls ("book me a hotel room", "who won the cricket match")
score below 0.25 and correctly match nothing.

Note the absolute scores are *lower* than the base model produced. That is the
point: with `distilbert-base-uncased`, unrelated text scored 0.70 and nothing
could be rejected. Lower, better-spread scores are what a usable threshold
needs.

---

## Response generation

Rule-based, per intent. The action plan specifies this, and it is also the
right call here: every answer must trace back to the Week 2 content bank, and a
generative model would need heavy constraining to avoid inventing facts for
school children. The NLP does the hard part — understanding what was asked. The
responder decides what to do about it.

| Intent | Strategy |
|---|---|
| `greeting` | Template |
| `out_of_scope` | Polite decline |
| `progress_help` | Reads quiz attempts and XP from MongoDB |
| `quiz_help` | Lists real quizzes for the student's grade |
| `definition`, `concept_explanation`, `example_request`, `formula_help`, `homework_help`, `clarification` | Semantic lesson search, then answer from the matched chapter |

`homework_help` deliberately does not give the answer outright. It points the
student at the relevant worked example instead. On a learning platform that is
the correct behaviour, and it is a rule rather than a hope.

---

## Files added

```text
backend/nlp/
  build_queries.py        regenerates the query dataset with fixed labels
  classifier.py           linear intent classifier, save/load, confidence
  train_intent.py         training with CV, held-out eval, confusion matrix
  predict_intent.py       CLI for spot-checking predictions
  retriever.py            hybrid semantic + lexical lesson search
  build_lesson_index.py   embeds the content bank
  test_retrieval.py       retrieval diagnostic and threshold tuning

backend/chatbot/
  responder.py            per-intent response strategies

backend/models/chat.py    request/response schemas
backend/routes/chat.py    GET /api/chat/status, POST /api/chat

data/processed/
  intent_classifier.pt        trained weights
  intent_labels.json          label order
  lesson_embeddings.npy       (16, 768) content index
  lesson_index_meta.json
  week7_training_report.json
```

---

## How to run

From the project root:

```bash
python -m backend.nlp.setup_nlp          # downloads both checkpoints
python -m backend.nlp.build_queries      # regenerate the dataset
python -m backend.nlp.build_dataset      # query embeddings
python -m backend.nlp.train_intent       # train + evaluate
python -m backend.nlp.build_lesson_index # content index
python -m backend.nlp.test_retrieval     # retrieval diagnostic
```

Then `uvicorn backend.main:app --reload` and try `POST /api/chat` at
`/docs`:

```json
{ "message": "explain lines and angles", "grade": 6 }
```

---

## Carried into Week 8

**Still English only.** Both checkpoints are English models and all 150 queries
are English, while the plan calls for a regional language. Note that four
chapters (`g6-tel-1`, `g6-tel-2`, `g7-tel-1`, `g7-tel-2`) have Telugu titles
and summaries but are tagged `"language": "en"` in `lessons.json`. That looks
like a data error and is worth confirming with whoever owns the content bank.

**150 queries is still small.** 15 per intent is enough for a linear classifier
on frozen features, and the ±5.7% cross-validation spread reflects that. More
data would tighten it.

**No conversation memory.** Each request is independent, so `clarification`
cannot refer back to what was just explained. The endpoint is stateless by
design; the client would need to pass context, or the server would need a
session store.

**Retrieval is evaluated on 13 hand-written probes.** Enough to catch a broken
pipeline and to set a threshold, not enough to claim a general accuracy figure.
