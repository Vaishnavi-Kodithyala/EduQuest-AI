# Week 8 — Chatbot Integration and Recommendation Engine

Implements the Week 8 deliverables:

1. Connect the chatbot interface in React to the backend NLP engine and
   validate the complete end-to-end query and response flow
2. Develop a rule-based recommendation engine in Python that uses quiz
   performance and NLP analysis to suggest relevant learning materials
3. Test the recommendation logic against sample student performance data

---

## What was built

```text
   React chat page                    Dashboard panel
   /pages/Chat.jsx                    "What to study next"
         |                                    |
         v                                    v
   POST /api/chat                    GET /api/recommendations/{user_id}
         |                                    |
         v                                    v
   +------------------+              +----------------------+
   | Week 7 NLP       |              | RecommendationEngine |
   | intent + retrieve|              | 5 rules, ranked      |
   +------------------+              +----------------------+
         |                                    ^
         v                                    |
   chat_history  ------------------------------
   (logged intents and matched lessons feed the NLP half
    of the recommender)
```

---

## The chat interface

`frontend/src/pages/Chat.jsx`, reachable from the header and the dashboard.

Each reply shows the detected intent and the confidence percentage. That is
deliberate: when the classifier is unsure the badge greys out and the reply
says so, rather than presenting a guess as fact. When an answer comes from a
chapter, a button opens it directly.

Suggestion chips cover the common intents so a new student is not staring at an
empty box wondering what the bot can do.

---

## Answering from chapter sections, not summaries

Week 7 indexed one entry per chapter — title plus summary, about 800
characters. The best such an index can do is say "open this chapter", which is
exactly what early replies did.

The index now holds **95 sections** instead of 16 chapters. Chapter content is
written as blocks with emoji headings, so it splits cleanly, and the retriever
returns the specific passage that addresses the question.

Asking "what is an acid" went from a chapter blurb to the actual sentence about
acidic, basic and neutral substances.

An ingestion pipeline (`backend/nlp/ingest_pdfs.py`) can extract passages from
chapter PDFs to deepen this further. It handles both per-chapter files and
whole textbooks with page ranges, strips page furniture, and splits on sentence
boundaries with overlap. It is written and tested but not yet run against real
textbooks.

---

## The grade filter was too strict

Retrieval originally filtered to the student's grade before ranking, so a
Grade 7 student asking "what is an angle" was told the topic did not exist —
even though the Grade 6 chapter covers it.

Knowledge does not respect grade boundaries. Retrieval now falls back to
searching every grade when nothing in the student's own grade matches, and the
reply says where the answer came from: *"from the Grade 6 chapter"*.

---

## Intent confidence and content relevance are independent

This was the most useful structural change of the week.

Originally a confidence below the threshold meant an outright refusal. But a
low-confidence query is not necessarily off-topic — it may just be phrased in a
way the training data did not cover. A fixed set of intents can never cover
everything a student might type.

So the two signals were separated. **Intent decides how to answer. Retrieval
decides whether there is anything to answer with.** Three outcomes:

| Intent confidence | Chapter matched | Result |
|---|---|---|
| Above threshold | — | Normal handling for that intent |
| Below threshold | Yes | Shows the content, states it was unsure |
| Below threshold | No | Lists what it can actually help with |

The middle row is the important one. A student typing "angle thing confusing
help" gets the angles chapter with an honest caveat, instead of being told to
rephrase. `understood` stays `false` in the response, so the interface does not
pretend otherwise.

---

## Four intents were added

Week 7 shipped 10 intents. Testing surfaced four categories of legitimate
question that none of them covered.

| Intent | Example | How it is answered |
|---|---|---|
| `browse_content` | "list the chapters" | Straight from the content bank. Nothing to retrieve — the student is asking what exists, not about a topic. Picks up a named subject or grade. |
| `study_advice` | "what should I study next" | Calls the recommendation engine, so the chatbot and the dashboard give identical advice for identical reasons. |

`progress_help` also gained per-subject answers ("what is my score in
English?") and honest handling of questions about data that is not recorded.

The final set is 12 intents, 180 queries, 15 each.

---

## Untracked data gets an honest answer

"How much time did I spend studying?" used to get "I did not understand that."
The truthful answer is that the app does not record time — it stores quiz
attempts and scores, nothing else.

Those are very different messages. One sends a student off rephrasing a
question that can never work; the other tells them what is actually available.
The responder now recognises time-related questions and says so.

The general principle, worth applying to any future gap: a failed question is
either a **logic gap** (the data exists, the handler does not) or a **data gap**
(nothing records it). The first is fixable in code. The second needs either new
tracking or an honest answer.

---

## The recommendation engine

`backend/recommender/engine.py`. Five rules, each producing candidates with a
priority. Highest priority wins per lesson, so a student is never told to study
the same chapter twice for different reasons.

| Priority | Rule | Fires when |
|---|---|---|
| 100 | `retry` | Latest attempt on a quiz is below 60% |
| 80 | `weak_subject` | Subject averages below 70% across at least 2 quizzes |
| 60 | `asked_about` | Chapter asked about in chat 2+ times, quiz not attempted |
| 40 | `next_chapter` | Chapter in the student's grade never attempted |
| 20 | `revision` | Fallback — lowest passing scores |

### Why rule-based

The action plan specifies it, and at this scale it is also the only honest
option. Collaborative filtering needs many students and many interactions; this
system has one student at a time and a 16-chapter content bank. Explicit rules
are transparent, debuggable, and every suggestion states exactly why it was
made — which matters when the person acting on it is a child.

### The NLP half

`asked_about` is the NLP-driven rule. Every chat message is logged with its
detected intent and matched chapter, so repeated questions about one chapter
signal a struggle that quiz scores alone do not capture — a student may be
confused about a topic they have not yet been tested on.

### Two bugs found by testing

The rules were tested against eight constructed student scenarios before being
wired up, which caught two problems that would have been hard to spot in
production.

**A student who improved was still flagged as weak.** Someone who scored 40%
then 90% on the same quiz had those averaged to 65%, which read as a weak
subject. Every rule now judges on the **latest attempt per quiz**, never the
average across attempts.

**A student who passed everything got an empty panel** — the one doing best saw
the least useful screen. Hence the `revision` fallback.

---

## Files added or changed

```text
backend/recommender/
  __init__.py
  engine.py                   five rules, ranked and deduplicated

backend/nlp/
  ingest_pdfs.py              chapter PDF -> passages (chapters or textbooks)
  build_lessons_from_pdfs.py  expand the content bank from full textbooks
  retriever.py                section splitting, grade fallback, hybrid scoring
  build_lesson_index.py       indexes sections and PDF passages
  build_queries.py            4 new intents, phrasing-collision linter
  train_intent.py             --seed and --repeat for variance measurement
  classifier.py               threshold 0.65 -> 0.60

backend/chatbot/responder.py  browse_content, study_advice, per-subject
                              progress, untracked-data answers, low-confidence
                              content fallback
backend/routes/chat.py        retrieval on low confidence, chat_history logging
backend/routes/recommend.py   GET /api/recommendations/{user_id}
backend/models/recommend.py

frontend/src/pages/Chat.jsx       the chat interface
frontend/src/pages/Dashboard.jsx  recommendations panel
frontend/src/services/api.js      chat() and recommendations()
frontend/src/components/Header.jsx
frontend/src/styles/app.css
```

---

## Measured results

### Intent classification, 12 intents, 180 queries

```text
5-fold cross-validation, averaged over 5 seeds : 89.1%
Range across seeds                             : 88.9% to 89.4%
Random baseline                                : 8.3%
```

The seed range is worth noting. Individual folds vary by several points
(standard deviation 4.7%), but the **average across folds barely moves between
seeds** — 0.5 percentage points across five. So 89.1% is a stable measurement,
not a lucky split. That distinction was only visible after adding `--repeat`,
and it changed the conclusion: earlier variation between runs had been assumed
to be noise, when it was actually caused by dataset edits.

### Remaining errors are genuine ambiguity

Four consistent misclassifications, none of which rewording fixed:

```text
'I still do not get it'      clarification -> homework_help
'How many points do I have?' progress_help -> browse_content
'Give me a study plan'       study_advice  -> quiz_help
```

A student who says "I still do not get it" is both confused and stuck — both
labels fit. "Give me a study plan" opens exactly like "Give me a quiz". These
are overlapping categories, not model failures. Fixing them would mean merging
intents or substantially more data per intent.

### One dataset bug worth recording

Adding `browse_content` silently dropped `progress_help` recall to 0.33.
`browse_content` contained "How many chapters do I have?" while `progress_help`
had "How many points do I have?" — the same template under two labels, so the
model learned the pattern belonged to the newer intent.

The confusion matrix is what exposed it: the errors were not scattered, they
all pointed at the intent that had just been added.

`build_queries.py` now runs a collision check at build time, comparing token
sets so a single swapped word is caught wherever it falls in the sentence. An
earlier version compared sentence prefixes and missed this exact case.

### Retrieval

```text
Correct top-1 on on-topic probes : 10/10
On-topic  score range            : 0.44 to 0.82
Off-topic score range            : 0.09 to 0.37
RELEVANCE_THRESHOLD              : 0.44
```

---

## Carried into Week 9

**Adaptive quizzing needs a bigger question pool.** The 16 quizzes hold 3–5
questions each, 62 in total, with no concept or difficulty tags. Selecting
questions by weakness requires a pool larger than the quiz being served, and
tags to select on. Quiz attempts already store the full answer array, so
per-question analysis is possible today — that data does not need retrofitting.

**The content bank is still 16 chapters.** The PDF ingestion and content
expansion tooling is written and tested, but the NCERT portal was unreachable
during Week 8. Running it is a three-command job once the source PDFs are
available.

**Still English only.** Both embedding checkpoints are English models. The four
Telugu chapters extract and index but retrieve poorly, because their text
tokenises almost entirely to unknown tokens.

**No conversation memory.** Each chat request is independent, so `clarification`
cannot refer back to what was just explained.

**Time is not tracked.** The app records quiz attempts and scores only. Any
question about study duration is answered honestly rather than guessed at.
