"""
Week 9 - Teacher dashboard endpoints.

    GET /api/teacher/class?teacher_id=...&days=21
        Everything on the class dashboard in one response: overview figures,
        daily score trend, subject and chapter performance, weak concepts,
        chatbot questions and the student table.

    GET /api/teacher/students/{student_id}?teacher_id=...
        One student in detail: quiz results per chapter, recent attempts, weak
        concepts, chapters read and recent chatbot questions.

Teacher accounts cannot be created from the sign-up page - otherwise any
student could register as a teacher and read the whole class's results. They
are created from the command line:

    python -m backend.create_teacher <username>

Like the rest of the app, requests identify the user by id rather than a login
token; adding tokens is listed under future work in docs/week-status.md.
"""

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query

from ..database import db, users
from ..teacher.analytics import DEFAULT_TREND_DAYS, TeacherAnalytics

router = APIRouter(prefix="/teacher", tags=["Teacher dashboard (Week 9)"])


def require_teacher(teacher_id: str) -> dict:
    try:
        object_id = ObjectId(teacher_id)
    except Exception:
        raise HTTPException(400, "Invalid teacher id")
    teacher = users.find_one({"_id": object_id}, {"username": 1, "role": 1, "grade": 1})
    if teacher is None:
        raise HTTPException(404, "User not found")
    if teacher.get("role") != "teacher":
        raise HTTPException(403, "Only teachers can see the class dashboard")
    return teacher


@router.get("/class")
def class_report(
    teacher_id: str = Query(..., description="The signed-in teacher's user id"),
    grade: int | None = Query(None, description="Defaults to the teacher's grade"),
    days: int = Query(DEFAULT_TREND_DAYS, ge=7, le=90, description="Days in the score trend"),
):
    teacher = require_teacher(teacher_id)
    return TeacherAnalytics(db).class_report(grade=grade or teacher.get("grade", 6), days=days)


@router.get("/students/{student_id}")
def student_detail(student_id: str, teacher_id: str = Query(...)):
    require_teacher(teacher_id)
    detail = TeacherAnalytics(db).student_detail(student_id)
    if detail is None:
        raise HTTPException(404, "Student not found")
    return detail
