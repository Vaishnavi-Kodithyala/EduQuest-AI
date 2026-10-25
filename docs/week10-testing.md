# Week 10 - Integration and testing

The team decided not to host EduQuest online for now, so Week 10 makes sure
the app works end to end on the project laptop and can be demonstrated
reliably. Testing is done at four levels, from fastest to slowest:

| Level | Command (from the project root) | What it covers | Needs |
|---|---|---|---|
| 1. Automated tests | `python -m pytest` | 96 tests of the backend rules and API | nothing running |
| 2. System check | `python -m backend.check_system` | the whole app end to end, 32 checks | MongoDB, trained models |
| 3. Model accuracy | `python -m backend.nlp.test_retrieval`, `python -m backend.nlp.test_answers` | chapter search and exact answers | MongoDB, models |
| 4. Screens | `npm run build`, then the demo run-through below | every page at desktop and phone width | everything running |

Install the test tools once, into the same virtual environment:

    pip install -r backend/requirements-dev.txt

## 1. Automated tests (`backend/tests/`)

They run against an in-memory MongoDB (mongomock) and need no models, so the
whole suite takes about ten seconds and can be run after every change.

| File | Tests | What is checked |
|---|---|---|
| `test_auth_and_content.py` | 13 | registration rules (Grade 6 only, duplicates, short passwords, sign-up cannot create a teacher), salted password hashes, login, language change; 40 chapters in textbook order, subject filter, every chapter has a quiz, quiz answers never sent to the browser, answers spread across A-D |
| `test_quiz_and_gamification.py` | 17 | server-side scoring and review, blank answers, per-question results stored; every XP rule, no XP farming on retakes, badges (first chapter, perfect score, comeback, streaks), levels, streaks counted in Indian time (23:50 and 00:10 IST are two days), leaderboard ties and teacher exclusion, reward avatars locked by level |
| `test_recommendations.py` | 6 | new student starts at chapter 1 of each subject, read-but-untested suggests the quiz, a failed quiz comes first, a passed retake clears it, repeated chatbot questions suggest that chapter, no duplicates |
| `test_teacher.py` | 15 | only teachers can open the dashboard; scores use the latest attempt; flags (low average, inactive, not started); weak concepts name the struggling students and need 5+ answers; a fixed concept stops being weak; trend days in Indian time; week-on-week; old Grade 7 attempts ignored; unanswered chatbot questions grouped; the demo class adds up and removes cleanly; `create_teacher` |
| `test_chatbot_rules.py` | 45 | maths solver (fractions, primes, HCF/LCM, area/perimeter, integers, order of operations, division by zero, never runs code); when to give a short answer or an explanation; answer support scoring; exercise blanks never answers; Telugu detection and answers; the chat route for calculations and Telugu; a clear message when models are missing; readable passages |

## 2. System check (`backend/check_system.py`)

Runs the real app - the project's MongoDB, the trained intent classifier, the
lesson index and the answer model - through what a student and a teacher do,
using FastAPI's test client (the server does not need to be running):

1. **Setup** - MongoDB reachable, 40 chapters and 40 quizzes seeded, model files present.
2. **Student** - a temporary student registers, logs in, opens a chapter, marks it read, fails its quiz (40%).
3. **Gamification** - exact XP for each step (30, 20, then 80 for the 100% retake = 130), the perfect-score and comeback badges, streak, leaderboard.
4. **Next steps** - "try again" is recommended after the failed quiz and disappears after the pass.
5. **Chatbot** - a textbook fact (exact answer "metre"), a calculation, a Telugu question, an explanation, an off-topic question and "how many points do I have" (must quote the right XP). The time for each reply is recorded; the first one includes loading the models.
6. **Teacher** - a temporary teacher logs in, a student is refused the dashboard, and the class dashboard shows the student with the same numbers (1 chapter, 1 quiz, 2 attempts, 100% latest, 130 XP, 6 chatbot questions).
7. **Clean-up** - both temporary accounts and everything they created are deleted.

The results are written to `data/processed/system_check.md`.

**Result on the project laptop (22 Oct 2026): 32 of 32 checks passed.** The first
chatbot reply took 10 seconds because it loads the models; every later reply took
under 0.3 seconds, and the class dashboard loaded in 0.1 seconds.

## 3. Model accuracy

Unchanged from Weeks 7-10 and re-run before the demo:
`test_retrieval` (10 on-topic and 3 off-topic probes, all must find the right
chapter) and `test_answers` (38 questions across the four subjects;
DistilBERT-SQuAD gets 33/38 right, see `docs/week-status.md`).

## 4. Screens

Checked in a real browser at 1320 px and at phone width (390 px): student
dashboard, Quest Map with subject filters, chapter page and "mark as read",
quiz with review and rewards, leaderboard, chat, settings, the teacher
dashboard (tiles, trend chart with hover, subject bars, weak concepts,
chapters, chatbot questions, students table and the student panel). No page
scrolls sideways on a phone. `npm run build` must finish without errors.

## Problems found and fixed in Week 10

| Found by | Problem | Fix |
|---|---|---|
| tests | "what is 2 + 3 * 4" gave the answer with no working, so the order of operations was not taught | each step is shown with the rule ("Multiply and divide before you add and subtract") |
| tests | "what is 10 divided by 0" fell through to the textbook search and returned an unrelated passage | answered directly: division by zero has no answer, and why |
| tests | "12 - 4 - 3" was given a tip about negative numbers | the tip is only shown when negative numbers are involved |
| sample report | explanations sometimes quoted exercise items, figure labels or glossary notes - "prime number what mean" quoted a true-or-false exercise whose statements are false | replies now show the 2-3 sentences that best match the question, skip questions, instructions, numbered items and figure labels, prefer a prose section of the same chapter over an exercise block, and fall back to the chapter summary (`backend/nlp/excerpt.py`); the chapter matched never changes |
| refreshed sample report | a bulleted summary list came through as one long "sentence" (the PDF bullets are control characters), and "powers of 2. Sometimes" was cut at "2." as if it were an exercise number | bullets break sentences; an item number only counts after the end of a sentence |
| screenshots (Week 9) | the teacher page scrolled sideways on phones | screen-reader text is kept inside its scrolling table |

## Demo run-through (about 10 minutes)

**Before the presentation**

1. Start MongoDB, then in three Command Prompt windows:
   - backend: `cd C:\projects\EduQuest-AI`, `backend\.venv\Scripts\activate`, `uvicorn backend.main:app --reload`
   - frontend: `cd C:\projects\EduQuest-AI\frontend`, `npm run dev`
   - working window: `cd C:\projects\EduQuest-AI`, `backend\.venv\Scripts\activate`
2. In the working window: `python -m backend.seed_demo_class` (a fresh demo class with activity up to today) and `python -m backend.check_system` - every check should pass.
3. Open http://localhost:5173 and ask the chatbot one question, so the models are already loaded when you present.

**Student (log in as `asha` / `student123`)**

1. Dashboard: level, XP bar, streak, badges, "What to study next".
2. Quest Map: switch subjects; open a chapter you have not read and press **Mark as read** (+XP).
3. Take that chapter's quiz: answers are only revealed after submitting; show the review with explanations and the XP/badge pop-up.
4. Leaderboard: where asha ranks in the class.
5. Ask AI - one question of each kind:
   - `What is the SI unit of length?` - exact answer quoted from the textbook
   - `what is 1/3 + 1/6` - answer with the working
   - `రైతు ఏమి చేస్తాడు?` - answered in Telugu
   - `how do camels survive in the desert` - explanation from the chapter
   - `who won the cricket match` - politely declined
   - `how many points do I have` - the student's own XP

**Teacher (log out, log in as `teacher` / `teacher123`)**

1. Overview tiles and the 21-day score trend (hover a day).
2. **Need attention**: suresh (low scores), meena and venkat (inactive), raju (never started).
3. Where they struggle: filter by Mathematics; weak concepts with the students who need help.
4. What students ask the chatbot, including the questions it could not answer.
5. Click **kiran**: weak in Mathematics, the concepts missed, recent attempts and questions.

**After the presentation** (optional): `python -m backend.seed_demo_class --remove`.

## Known limitations

- Not hosted online (team decision); it runs on the project laptop.
- Requests identify the user by id rather than a signed login token, so the
  teacher check trusts the id the browser sends. A token issued at login (for
  example a JWT) is needed before real deployment.
- The chatbot's exact answers are right for 33 of 38 test questions; when it is
  unsure it shows the relevant passage and says so instead of guessing.
- Telugu covers the two Telugu chapters; the other chapters are in English.
- Study time is not recorded.
