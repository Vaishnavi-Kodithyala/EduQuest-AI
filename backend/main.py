import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import client, ensure_indexes
from .routes import auth, content, quiz, nlp, chat, recommend, gamification, teacher

app = FastAPI(title="EduQuest API", version="1.0.0")

origins=[x.strip() for x in os.getenv("CORS_ORIGINS","http://localhost:5173").split(",")]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

app.include_router(auth.router, prefix="/api")
app.include_router(content.router, prefix="/api")
app.include_router(quiz.router, prefix="/api")
app.include_router(nlp.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(recommend.router, prefix="/api")
app.include_router(gamification.router, prefix="/api")
app.include_router(teacher.router, prefix="/api")

@app.on_event("startup")
def startup():
    client.admin.command("ping")
    ensure_indexes()

@app.get("/api/health")
def health():
    client.admin.command("ping")
    return {"status":"ok","database":"MongoDB","service":"EduQuest API"}
