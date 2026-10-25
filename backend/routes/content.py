from fastapi import APIRouter, HTTPException
from ..content_order import sort_textbook
from ..database import lessons, quizzes

router = APIRouter(tags=["Learning Content"])

@router.get("/lessons")
def get_lessons(grade:int|None=None, subject:str|None=None, language:str|None=None):
    query={}
    if grade is not None: query["grade"]=grade
    if subject: query["subject"]=subject
    if language: query["language"]=language
    return sort_textbook(list(lessons.find(query, {"_id":0})))

@router.get("/lessons/{lesson_id}")
def get_lesson(lesson_id:str):
    doc=lessons.find_one({"id":lesson_id},{"_id":0})
    if not doc: raise HTTPException(404,"Lesson not found")
    return doc

# Answers and explanations stay on the server until the quiz is submitted.
# Sent with the questions, anyone could read the answers in the browser's
# network tab; POST /quiz-attempts returns them as a review instead.
HIDDEN_FIELDS = {"questions.correct": 0, "questions.explanation": 0}

@router.get("/quizzes")
def get_quizzes(grade:int|None=None, subject:str|None=None):
    query={}
    if grade is not None: query["grade"]=grade
    if subject: query["subject"]=subject
    return sort_textbook(list(quizzes.find(query, {"_id":0, **HIDDEN_FIELDS})))

@router.get("/quizzes/{quiz_id}")
def get_quiz(quiz_id:str):
    doc=quizzes.find_one({"id":quiz_id},{"_id":0, **HIDDEN_FIELDS})
    if not doc: raise HTTPException(404,"Quiz not found")
    return doc
