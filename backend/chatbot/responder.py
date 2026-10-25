"""
Week 7 - Chatbot response generation.

Turns a classified intent into an answer. Each intent has its own strategy:
some look up lesson content, some query the student's progress from MongoDB,
some are pure templates.

Deliberately rule-based
-----------------------
The action plan specifies a rule-based approach, and for this project it is
also the right call. A generative model would need to be constrained heavily to
avoid inventing facts for school children, and every answer here must trace
back to the Week 2 content bank. Retrieval plus templates means the student
never sees anything that is not in the curriculum.

The NLP does the hard part - understanding what was asked. The response layer
then decides what to do about it.
"""

from __future__ import annotations

import random
import re

from ..content_order import sort_textbook
from ..gamification.engine import GamificationEngine
from ..nlp.classifier import CONFIDENCE_THRESHOLD
from ..nlp.excerpt import focus

# Used only when the query matches no content either. If a chapter matched,
# the student gets that instead - see `respond`.
FALLBACK_RESPONSES = [
    "I am not sure I understood that. I can explain a chapter, give you an "
    "example, set you a quiz, list your chapters, or tell you how you are "
    "doing. Which would help?",
    "Sorry, I did not follow that one. Try naming the chapter or topic, or ask "
    "me to list your chapters.",
    "I did not quite get that. You could ask me to explain a topic, show an "
    "example, start a quiz, or check your progress.",
]

# When intent confidence is low but a chapter matched strongly, the reply leads
# with the content and is honest that the question was not fully understood.
UNSURE_BUT_RELEVANT = (
    "I am not certain what you were asking, but this looks relevant:"
)

GREETINGS = [
    "Hello! I am your EduQuest study buddy. Ask me about any chapter, or say 'give me a quiz' to practise.",
    "Hi there! Ready to learn? You can ask me to explain a topic, show an example, or start a quiz.",
    "Namaste! Ask me anything about your lessons, or check your progress by asking 'what is my score'.",
]

OUT_OF_SCOPE = (
    "I can only help with your lessons and quizzes. "
    "Try asking me about a chapter, a formula, or your progress."
)


def _lesson_link(lesson: dict | None) -> dict | None:
    if not lesson:
        return None
    return {
        "id": lesson["id"],
        "title": lesson["title"],
        "subject": lesson["subject"],
        "grade": lesson["grade"],
    }


def _grade_note(lesson: dict) -> str:
    """Say so when the answer comes from a different grade's chapter."""
    if lesson.get("from_other_grade"):
        return f" (from the Grade {lesson['grade']} chapter)"
    return ""


def _passage(lesson: dict) -> str:
    """The matched section text, falling back to the chapter summary."""
    return (lesson.get("text") or lesson.get("summary") or "").strip()


def _focused(lesson: dict | None, query_text: str | None) -> dict | None:
    """
    Trim the matched section to the sentences that answer the question (Week 10).

    Sections from the PDFs mix explanation with exercises and figure labels;
    see backend/nlp/excerpt.py.
    """
    if not lesson:
        return lesson
    text = focus(lesson.get("text") or "", query_text, fallback=lesson.get("summary"))
    return {**lesson, "text": text}


def _no_lesson_found(topic_word: str = "that topic") -> str:
    return (
        f"I could not find a chapter about {topic_word} for your grade. "
        "Try naming the chapter, or pick a subject from the Lessons page."
    )


def answer_reply(answer) -> str:
    """Reply for an exact answer extracted from the textbook (Week 10)."""
    lesson = answer.passage
    text = answer.text[:1].upper() + answer.text[1:]
    reply = text if text.endswith((".", "!", "?")) else f"{text}."
    sentence = answer.sentence.strip()
    if sentence and sentence.lower().strip(" .") != answer.text.lower().strip(" ."):
        reply += f"\n\n\u201c{sentence}\u201d"
    reply += (
        f"\n\nThat is from \"{lesson['title']}\" in {lesson['subject']}"
        f"{_grade_note(lesson)}. Open the chapter to read more."
    )
    return reply


def math_reply(solution, lesson: dict | None) -> str:
    """Reply for a calculation solved by the maths solver (Week 10)."""
    lines = [solution.answer]
    if solution.working:
        lines.append("")
        lines.extend(solution.working)
    if lesson:
        lines.append("")
        lines.append(f"This is from \"{lesson['title']}\" in Mathematics - open it to practise the method.")
    return "\n".join(lines)


class ChatResponder:
    """Builds a reply for a classified query."""

    def __init__(self, retriever=None, database=None) -> None:
        self._retriever = retriever
        self._db = database

    # -- helpers ------------------------------------------------------------
    def _find_lesson(self, query_vector, grade: int | None, query_text: str | None = None):
        if self._retriever is None:
            return None
        return self._retriever.best_match(
            query_vector, grade=grade, query_text=query_text
        )

    # Things students reasonably ask about that this system does not record.
    # Saying "I do not track that" is more useful than "I did not understand" -
    # one tells them to rephrase, the other tells them to stop trying.
    UNTRACKED_PATTERNS = (
        "how much time", "how long", "time spent", "time did i", "hours",
        "minutes", "time in each", "time i spent", "duration",
    )

    def _progress_by_subject(self, user_id: str, subject: str) -> dict | None:
        """Average and best score for one subject."""
        if self._db is None:
            return None

        quizzes = {
            q["id"]: q
            for q in self._db["quizzes"].find({}, {"_id": 0, "id": 1, "subject": 1})
        }
        scores = [
            a["score"]
            for a in self._db["quiz_attempts"].find(
                {"user_id": user_id}, {"_id": 0, "quiz_id": 1, "score": 1}
            )
            if quizzes.get(a["quiz_id"], {}).get("subject") == subject
        ]
        if not scores:
            return None
        return {
            "attempts": len(scores),
            "average": round(sum(scores) / len(scores)),
            "best": max(scores),
        }

    def _progress_for(self, user_id: str | None) -> dict | None:
        """Read the student's quiz history straight from MongoDB."""
        if not user_id or self._db is None:
            return None

        attempts = list(
            self._db["quiz_attempts"].find({"user_id": user_id}, {"_id": 0, "score": 1})
        )
        # XP, level and streak come from the same engine as the dashboard, so
        # the chatbot never quotes a different number from the one on screen.
        try:
            game = GamificationEngine(self._db).profile(user_id)
        except Exception:
            game = None

        scores = [a["score"] for a in attempts]
        return {
            "attempts": len(scores),
            "average": round(sum(scores) / len(scores)) if scores else 0,
            "best": max(scores) if scores else 0,
            "points": game["xp"] if game else 0,
            "level": game["level"] if game else 1,
            "streak": game["streak"]["current"] if game else 0,
            "badges": game["badges_earned"] if game else 0,
        }

    def _lessons_for(self, grade: int | None, subject: str | None = None) -> list[dict]:
        if self._db is None:
            return []
        query: dict = {}
        if grade is not None:
            query["grade"] = grade
        if subject:
            query["subject"] = subject
        return sort_textbook(
            list(
                self._db["lessons"].find(
                    query, {"_id": 0, "id": 1, "title": 1, "subject": 1, "grade": 1}
                )
            )
        )

    def _available_grades(self) -> list[int]:
        if self._db is None:
            return []
        return sorted(self._db["lessons"].distinct("grade"))

    def _quizzes_for(self, grade: int | None) -> list[dict]:
        if self._db is None:
            return []
        query = {"grade": grade} if grade is not None else {}
        return list(
            self._db["quizzes"].find(query, {"_id": 0, "id": 1, "title": 1, "subject": 1}).limit(5)
        )

    @staticmethod
    def _grade_in(text: str | None) -> int | None:
        """
        Pick out a grade if the student named one.

        An explicit request beats the profile default. When the student names
        a grade the content bank does not cover, _browse_content says so
        instead of returning an empty list.
        """
        if not text:
            return None
        match = re.search(r"\b(?:grade|class|std)\s*(\d{1,2})\b", text.lower())
        if match:
            grade = int(match.group(1))
            if 1 <= grade <= 12:
                return grade
        return None

    @staticmethod
    def _subject_in(text: str | None) -> str | None:
        """Pick out a subject name if the student mentioned one."""
        if not text:
            return None
        lowered = text.lower()
        for subject, aliases in {
            "Mathematics": ("math", "maths", "mathematics"),
            "Science": ("science",),
            "English": ("english",),
            "Telugu": ("telugu",),
        }.items():
            if any(alias in lowered for alias in aliases):
                return subject
        return None

    # -- intent handlers ----------------------------------------------------
    def _definition(self, lesson):
        if not lesson:
            return _no_lesson_found("that term"), None
        return (
            f"{_passage(lesson)}\n\n"
            f"That is from \"{lesson['title']}\" in {lesson['subject']}"
            f"{_grade_note(lesson)}."
        ), lesson

    def _concept_explanation(self, lesson):
        if not lesson:
            return _no_lesson_found(), None
        return (
            f"{_passage(lesson)}\n\n"
            f"Read the rest in \"{lesson['title']}\", {lesson['subject']}"
            f"{_grade_note(lesson)}, for the full walkthrough."
        ), lesson

    def _example_request(self, lesson):
        if not lesson:
            return (
                "Tell me which topic you want an example for and I will point you "
                "to the right chapter."
            ), None
        return (
            f"{_passage(lesson)}\n\n"
            f"There are more examples in \"{lesson['title']}\""
            f"{_grade_note(lesson)}, and its quiz gives you real questions to try."
        ), lesson

    def _formula_help(self, lesson):
        if not lesson:
            return (
                "Which topic is the formula for? Name the chapter or the concept "
                "and I will find it."
            ), None
        return (
            f"{_passage(lesson)}\n\n"
            f"That is covered in \"{lesson['title']}\"{_grade_note(lesson)}. "
            "Look for the worked example - it shows each step with the numbers "
            "filled in."
        ), lesson

    def _homework_help(self, lesson):
        base = (
            "I will not give you the answer outright, because working it through "
            "is how it sticks. "
        )
        if not lesson:
            return base + "Tell me which chapter it is from and I will point you to the right notes.", None
        return (
            base
            + f"This looks like it is from \"{lesson['title']}\""
            f"{_grade_note(lesson)}. Here is the part that should help:\n\n"
            f"{_passage(lesson)}\n\n"
            "Try your problem the same way."
        ), lesson

    def _clarification(self, lesson):
        if not lesson:
            return (
                "Happy to go over it again. Which part was confusing - "
                "the idea itself, or how to use it in a question?"
            ), None
        return (
            "Let me put it another way.\n\n"
            f"{_passage(lesson)}\n\n"
            f"That is from \"{lesson['title']}\"{_grade_note(lesson)}. Ask me "
            "about the specific part that is still unclear."
        ), lesson

    def _browse_content(self, grade, query_text):
        """
        List what is available, rather than searching it.

        Catalogue questions are answered from the content bank directly. There
        is nothing to retrieve semantically - the student is asking what exists,
        not about a topic.
        """
        subject = self._subject_in(query_text)
        asked_grade = self._grade_in(query_text)
        target_grade = asked_grade if asked_grade is not None else grade

        # "show me grade 7 chapters" when only Grade 6 exists: say what is
        # covered and list that, rather than "I could not find any chapters".
        intro = ""
        available = self._available_grades()
        if asked_grade is not None and available and asked_grade not in available:
            covered = ", ".join(f"Grade {g}" for g in available)
            intro = f"EduQuest covers {covered} only, not Grade {asked_grade}. "
            target_grade = grade if grade in available else available[0]

        lessons = self._lessons_for(target_grade, subject)

        if not lessons:
            where = (
                f"Grade {target_grade}" if target_grade is not None else "your grade"
            )
            if subject:
                return f"I could not find any {subject} chapters for {where}.", None
            return f"I could not find any chapters for {where} yet.", None

        by_subject: dict[str, list[str]] = {}
        for lesson in lessons:
            by_subject.setdefault(lesson["subject"], []).append(lesson["title"])

        grade_label = (
            f"Grade {target_grade}" if target_grade is not None else "your grade"
        )
        lines = [f"{intro}Here is what you can study in {grade_label}:"]
        for subject_name in sorted(by_subject):
            titles = ", ".join(by_subject[subject_name])
            lines.append(f"\n{subject_name}: {titles}")

        lines.append(
            "\nAsk me about any of these, or say 'give me a quiz' to practise."
        )
        return "".join(lines), None

    def _study_advice(self, user_id, grade):
        """
        Answer "what should I study" with the Week 8 recommendation engine.

        There is no chapter to retrieve for this question - the answer depends
        on the student's own history, not on the content of any one chapter.
        Reusing the recommender means the chatbot and the dashboard give the
        same advice for the same reasons, rather than two systems disagreeing.
        """
        if not user_id or self._db is None:
            return "Log in and I can suggest what to study next.", None

        from ..recommender.engine import RecommendationEngine

        result = RecommendationEngine(self._db).recommend(user_id, grade=grade, limit=3)
        picks = result["recommendations"]
        basis = result["based_on"]

        if not picks:
            return (
                "I do not have enough to go on yet. Finish a chapter and try "
                "its quiz, then ask me again."
            ), None

        if basis["quiz_attempts"] == 0:
            opening = "You have not taken a quiz yet, so here is a good place to start:"
        else:
            opening = (
                f"Based on your {basis['quiz_attempts']} "
                f"{'quiz' if basis['quiz_attempts'] == 1 else 'quizzes'} "
                f"(average {basis['average_score']}%), here is what I suggest:"
            )

        lines = [opening]
        for i, pick in enumerate(picks, start=1):
            lines.append(f"\n{i}. {pick['title']} ({pick['subject']}) - {pick['reason']}")

        return "".join(lines), None

    def _quiz_help(self, grade):
        available = self._quizzes_for(grade)
        if not available:
            return "I could not find a quiz for your grade yet. Check the Lessons page.", None
        titles = ", ".join(q["title"] for q in available[:3])
        return (
            f"Here is what you can practise right now: {titles}. "
            "Open the Lessons page and pick one to start."
        ), None

    UNTRACKED_REPLY = (
        "I do not track how long you spend studying - the app only "
        "records quiz attempts and scores. I can tell you your scores, "
        "your XP, or how many quizzes you have completed."
    )

    def _asks_untracked(self, query_text: str | None) -> bool:
        lowered = (query_text or "").lower()
        return any(pattern in lowered for pattern in self.UNTRACKED_PATTERNS)

    def _progress_help(self, user_id, query_text=None):
        if self._asks_untracked(query_text):
            return self.UNTRACKED_REPLY, None

        subject = self._subject_in(query_text)
        if subject and user_id:
            stats = self._progress_by_subject(user_id, subject)
            if stats is None:
                return (
                    f"You have not attempted any {subject} quizzes yet. "
                    f"Try one and I can track how you are doing."
                ), None
            return (
                f"In {subject} you have completed {stats['attempts']} "
                f"{'quiz' if stats['attempts'] == 1 else 'quizzes'}, "
                f"averaging {stats['average']}%, with a best of {stats['best']}%."
            ), None

        stats = self._progress_for(user_id)
        if stats is None:
            return "Log in and I can show you your progress.", None
        if stats["attempts"] == 0:
            return (
                "You have not attempted a quiz yet. Finish a chapter and try its "
                "quiz - that is how you start earning XP."
            ), None
        return (
            f"You have completed {stats['attempts']} "
            f"{'quiz' if stats['attempts'] == 1 else 'quizzes'}, "
            f"averaging {stats['average']}%, with a best score of {stats['best']}%. "
            f"You have {stats['points']} XP (level {stats['level']}) and "
            f"{stats['badges']} {'badge' if stats['badges'] == 1 else 'badges'}"
            + (f", with a {stats['streak']}-day streak." if stats['streak'] > 1 else ".")
        ), None

    # -- entry point --------------------------------------------------------
    def respond(
        self,
        intent: str,
        confidence: float,
        query_vector=None,
        grade: int | None = None,
        user_id: str | None = None,
        query_text: str | None = None,
    ) -> dict:
        """
        Build the reply.

        Intent confidence and content relevance are treated as two independent
        signals. Intent decides *how* to answer; retrieval decides *whether
        there is anything to answer with*.

        A fixed set of intents can never cover everything a student might type.
        When the classifier is unsure, the question is not necessarily
        off-topic - it may just be phrased in a way the training data did not
        cover. So before giving up, we check whether the query matches a
        chapter anyway. If it does, showing that content is far more useful
        than refusing.
        """
        if confidence < CONFIDENCE_THRESHOLD:
            # An unsure classifier's best guess still carries information.
            # "how much time did I spend studying" lands on progress_help with
            # low confidence because no training query asks about time, yet
            # the honest answer is known: the app does not record it. Requiring
            # the progress_help guess keeps "how long is a line segment" out.
            if intent == "progress_help" and self._asks_untracked(query_text):
                return {"reply": self.UNTRACKED_REPLY, "understood": True, "lesson": None}

            lesson = _focused(
                self._find_lesson(query_vector, grade, query_text)
                if query_vector is not None
                else None,
                query_text,
            )
            if lesson:
                return {
                    "reply": (
                        f"{UNSURE_BUT_RELEVANT}\n\n"
                        f"{_passage(lesson)}\n\n"
                        f"That is from \"{lesson['title']}\" in "
                        f"{lesson['subject']}{_grade_note(lesson)}. "
                        "If that is not what you meant, try rephrasing."
                    ),
                    "understood": False,
                    "lesson": _lesson_link(lesson),
                }
            return {
                "reply": random.choice(FALLBACK_RESPONSES),
                "understood": False,
                "lesson": None,
            }

        if intent == "greeting":
            return {"reply": random.choice(GREETINGS), "understood": True, "lesson": None}

        if intent == "out_of_scope":
            return {"reply": OUT_OF_SCOPE, "understood": True, "lesson": None}

        if intent == "progress_help":
            reply, lesson = self._progress_help(user_id, query_text)
            return {"reply": reply, "understood": True, "lesson": _lesson_link(lesson)}

        if intent == "quiz_help":
            reply, lesson = self._quiz_help(grade)
            return {"reply": reply, "understood": True, "lesson": _lesson_link(lesson)}

        if intent == "study_advice":
            reply, lesson = self._study_advice(user_id, grade)
            return {"reply": reply, "understood": True, "lesson": _lesson_link(lesson)}

        if intent == "browse_content":
            reply, lesson = self._browse_content(grade, query_text)
            return {"reply": reply, "understood": True, "lesson": _lesson_link(lesson)}

        # The remaining intents all benefit from finding a relevant chapter.
        lesson = _focused(
            self._find_lesson(query_vector, grade, query_text)
            if query_vector is not None
            else None,
            query_text,
        )

        handlers = {
            "definition": self._definition,
            "concept_explanation": self._concept_explanation,
            "example_request": self._example_request,
            "formula_help": self._formula_help,
            "homework_help": self._homework_help,
            "clarification": self._clarification,
        }
        handler = handlers.get(intent)
        if handler is None:
            return {
                "reply": random.choice(FALLBACK_RESPONSES),
                "understood": False,
                "lesson": None,
            }

        reply, matched = handler(lesson)
        return {"reply": reply, "understood": True, "lesson": _lesson_link(matched)}
