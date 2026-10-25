# EduQuest — Weeks 2–10

This is the implementation of all ten weeks of the EduQuest project (Grade 6).

The original `eduquest.html` was treated as a prototype/reference. The final application is rebuilt with:

- React.js frontend
- Python FastAPI backend
- MongoDB database
- Week 2 structured datasets
- Week 3 requirements/design/API documentation
- Week 4 basic UI/backend/database setup
- Week 5 learning content + quiz submission/storage
- Week 6 NLP preprocessing pipeline (spaCy + NLTK) and DistilBERT embeddings
- Week 7 intent detection (12 intents, 89.1% CV) and the chatbot endpoint
- Week 8 React chat interface and rule-based recommendation engine
- Week 9 concept-tagged quizzes, gamification (XP, levels, streaks, badges, leaderboard) and the teacher dashboard
- Week 10 integration and testing: automated tests, an end-to-end system check and a demo run-through

## Run

### 1. MongoDB
Install/start MongoDB locally, or use MongoDB Atlas.

### 2. Backend
Open a terminal in `backend/`:

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env
python seed.py
uvicorn main:app --reload
```

If Python's package execution complains about relative imports, run the backend from the project root with:

```bash
uvicorn backend.main:app --reload
```

For the seed command from project root:

```bash
python -m backend.seed
```

### 3. Frontend
Open a second terminal in `frontend/`:

```bash
npm install      # run again after pulling: the fonts are npm packages
npm run dev
```

Open the Vite URL shown in the terminal (normally `http://localhost:5173`).

### 4. Week 6 NLP pipeline
Run these from the **project root**, not from `backend/`:

```bash
python -m backend.nlp.setup_nlp        # spaCy model + NLTK corpora + DistilBERT weights
python -m backend.nlp.build_dataset    # writes data/processed/
python -m backend.nlp.validate         # prints the validation report
```

To skip the 265 MB DistilBERT download and run preprocessing only:

```bash
python -m backend.nlp.setup_nlp --skip-model
python -m backend.nlp.build_dataset --skip-embeddings
```

The pipeline is also exposed for live demonstration at `/api/nlp/status`, `/api/nlp/preprocess` and `/api/nlp/embed`. See `docs/week6-nlp-preprocessing.md` for the full design notes and validation report.

### 5. Week 7–8 chatbot and recommendations

```bash
python -m backend.nlp.build_queries        # 180 queries, 12 intents
python -m backend.nlp.build_dataset        # query embeddings
python -m backend.nlp.train_intent         # train + evaluate the classifier
python -m backend.nlp.build_lesson_index   # semantic index over chapter sections
python -m backend.nlp.test_retrieval       # retrieval diagnostic
```

Then start the app and use **Ask AI** in the header. The dashboard shows a
"What to study next" panel driven by the recommendation engine.

Optional — deepen the content the chatbot can quote from, using chapter PDFs:

```bash
pip install pypdf
python -m backend.nlp.ingest_pdfs --list   # expected filenames
python -m backend.nlp.ingest_pdfs
python -m backend.nlp.build_lesson_index
```

### 6. Week 9 teacher dashboard
Teachers use the normal login page. Create a teacher account from the project root:

```bash
python -m backend.create_teacher <username>
```

To see the dashboard with a sample class (12 students, three weeks of activity,
teacher login `teacher` / `teacher123`, student password `student123`):

```bash
python -m backend.seed_demo_class           # create (re-running re-creates it)
python -m backend.seed_demo_class --remove  # delete it again
```

See `docs/week-status.md` for what each panel shows and how it is computed.

### 7. Week 10 testing
From the project root, with the virtual environment active:

```bash
pip install -r backend/requirements-dev.txt   # once: pytest, mongomock, httpx
python -m pytest                              # 96 automated tests, ~10 seconds, no database needed
python -m backend.check_system                # the whole app end to end on your MongoDB and models
```

`docs/week10-testing.md` lists what each test covers, the problems testing
found, and a step-by-step demo run-through for the presentation.

## Important
All ten weeks are implemented. The app is not hosted online (team decision);
it runs locally as described above.
