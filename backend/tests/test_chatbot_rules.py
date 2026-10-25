"""
Chatbot parts that need no AI model: the maths solver, the answer rules, the
Telugu matcher, and the chat route for calculations and Telugu questions.
(Accuracy with the real models: python -m backend.nlp.test_answers.)
"""

import pytest

from backend.chatbot.service import ChatService
from backend.nlp.answerer import is_junk, is_question, support, wants_short_answer
from backend.nlp.math_solver import solve
from backend.nlp.telugu import get_telugu_answerer, is_telugu


# --- maths solver -----------------------------------------------------------------

@pytest.mark.parametrize("question,expected,lesson", [
    ("what is 1/3 + 1/6", "= 1/2", "g6-math-7"),
    ("simplify 12/18", "2/3", "g6-math-7"),
    ("which is bigger 2/3 or 3/4", "3/4 is greater", "g6-math-7"),
    ("3/4 of 20", "= 15", "g6-math-7"),
    ("is 91 a prime number", "not prime", "g6-math-5"),
    ("is 2 a prime number", "Yes", "g6-math-5"),
    ("is 1 a prime number", "not prime", "g6-math-5"),
    ("HCF of 12 and 18", "is 6", "g6-math-5"),
    ("LCM of 4 and 6", "is 12", "g6-math-5"),
    ("prime factors of 60", "2 × 2 × 3 × 5", "g6-math-5"),
    ("are 8 and 15 co-prime", "Yes", "g6-math-5"),
    ("area of a rectangle 5 m by 4 m", "20 sq m", "g6-math-6"),
    ("perimeter of a square of side 7 cm", "28 cm", "g6-math-6"),
    ("what is -5 + 3", "= -2", "g6-math-10"),
    ("what is 2 + 3 * 4", "= 14", "g6-math-3"),
])
def test_maths_solver(question, expected, lesson):
    result = solve(question)
    assert result is not None, question
    assert expected in result.answer
    assert result.lesson_id == lesson
    assert result.working                       # it shows the method, not only the answer


@pytest.mark.parametrize("question", [
    "what is a prime number",          # a definition: answered from the chapter
    "explain fractions",
    "who is the raven",
    "how many chapters are there",
    "chapter 5 quiz",
])
def test_maths_solver_leaves_other_questions_alone(question):
    assert solve(question) is None


def test_mixed_operations_show_the_order():
    result = solve("what is 2 + 3 * 4")
    assert result.working == ["Multiply and divide before you add and subtract.", "3 × 4 = 12", "2 + 12 = 14"]
    assert solve("what is (2 + 3) * 4").working[1:] == ["2 + 3 = 5", "5 × 4 = 20"]


def test_division_by_zero_is_explained():
    result = solve("what is 10 divided by 0")
    assert result is not None and "cannot divide by zero" in result.answer


def test_maths_solver_never_runs_code():
    assert solve("what is __import__('os').system('dir')") is None


# --- when to give a short exact answer ------------------------------------------------

@pytest.mark.parametrize("text,short", [
    ("What is the SI unit of length?", True),
    ("Who was Gajaraj?", True),
    ("How many legs does an insect have?", True),
    ("When was the National War Memorial established?", True),
    ("what is a prime number", False),            # asks for an explanation
    ("why do we sweat", False),
    ("how do camels survive in the desert", False),
    ("What did Rama Natha learn about wealth?", False),
])
def test_short_answer_or_explanation(text, short):
    assert wants_short_answer(text) is short


def test_is_question():
    assert is_question("What is the SI unit of length?")
    assert is_question("name the planets")
    assert not is_question("thank you")


def test_support_rewards_the_question_words_in_order():
    question = "What is the process of separating grains from stalks called?"
    right = "This process of separating grains from the stalks is known as threshing."
    unrelated = "Winnowing is used to separate husk from grain."
    assert support(question, right) > support(question, unrelated)
    assert support("Is iron magnetic?", "Iron is not magnetic.") < support("Is iron magnetic?", "Iron is magnetic.")


def test_exercise_blanks_are_never_answers():
    assert is_junk("Ans")
    assert is_junk("________")
    assert not is_junk("threshing")


# --- Telugu ---------------------------------------------------------------------------

def test_telugu_detection():
    assert is_telugu("రైతు ఏమి చేస్తాడు?")
    assert not is_telugu("What does a farmer do?")


def test_telugu_question_is_answered_from_the_telugu_chapter():
    reply = get_telugu_answerer().reply("రైతు ఏమి చేస్తాడు?")
    assert reply["intent"] == "telugu_question"
    assert "పంట" in reply["answer"]["text"]
    assert reply["lesson"]["id"] == "g6-tel-1"


# --- the chat route for questions that need no model ------------------------------------

def test_calculation_through_the_chat_route_is_logged(client, register, db):
    user = register("asha")
    body = client.post("/api/chat", json={"message": "what is 1/3 + 1/6", "user_id": user["id"], "grade": 6}).json()
    assert body["intent"] == "calculation"
    assert body["answer"]["text"].endswith("= 1/2") and body["answer"]["source"] == "math"
    assert body["lesson"]["id"] == "g6-math-7"
    logged = db.chat_history.find_one({"user_id": user["id"]})
    assert (logged["intent"], logged["answered"], logged["lesson_id"]) == ("calculation", True, "g6-math-7")


def test_telugu_through_the_chat_service():
    result = ChatService().reply("నిజమైన స్నేహం అంటే ఏమిటి?")
    assert result["intent"] == "telugu_question"
    assert result["lesson"]["id"] == "g6-tel-2"


def test_missing_models_give_a_clear_message(client, monkeypatch):
    class NoModels:
        def __init__(self, *args, **kwargs):
            pass

        def reply(self, *args, **kwargs):
            raise FileNotFoundError("intent_classifier.pt")

    monkeypatch.setattr("backend.routes.chat.ChatService", NoModels)
    response = client.post("/api/chat", json={"message": "what is a magnet"})
    assert response.status_code == 503
    assert "train_intent" in response.json()["detail"]


# --- readable passages (Week 10) --------------------------------------------------------

import json  # noqa: E402

from backend.nlp.excerpt import focus, is_exercise  # noqa: E402
from backend.nlp.retriever import _prefer_prose  # noqa: E402
from testkit import DATA_DIR  # noqa: E402

with open(DATA_DIR / "processed" / "lesson_index_meta.json", encoding="utf-8") as _f:
    SECTIONS = json.load(_f)["lessons"]


def section(lesson_id, words):
    return next(s for s in SECTIONS if s["id"] == lesson_id and words in s["text"])


def test_reply_keeps_the_sentence_that_answers():
    text = section("g6-math-9", "refers to a part")["text"]
    assert "A symmetry refers to a part or parts of a figure" in focus(text, "what is symmetry")


def test_false_exercise_statements_are_never_quoted():
    exercise = section("g6-math-5", "A product of primes can also be prime")
    assert is_exercise(exercise["text"])
    shown = focus(exercise["text"], "prime number what mean", fallback=exercise["summary"])
    assert "do not have any factors" not in shown
    assert shown == exercise["summary"].strip()


def test_figure_labels_and_instructions_are_dropped():
    text = section("g6-math-2", "Name the different angles")["text"]
    shown = focus(text, "angle thing confusing help")
    assert "170 70 120" not in shown and not shown.startswith("Name the")


def test_a_prose_section_of_the_same_chapter_is_preferred():
    exercise = {**section("g6-math-5", "A product of primes can also be prime"), "score": 0.70}
    prose = {**section("g6-math-5", "only two factors"), "score": 0.67}
    elsewhere = {**section("g6-math-9", "refers to a part"), "score": 0.69}
    assert _prefer_prose([exercise, elsewhere, prose]) is prose
    far = {**prose, "score": 0.50}
    assert _prefer_prose([exercise, far]) is exercise        # too far below: keep the best match


def test_bulleted_summaries_split_into_sentences():
    text = next(s["text"] for s in SECTIONS if s["id"] == "g6-sci-2" and "\x8b The special features" in s["text"]
                and "The place where plants and animals live" in s["text"])
    shown = focus(text, "how do plants and animals suit where they live")
    # The list items become separate sentences (before, the whole list was one
    # 70-word "sentence" and the summary was shown instead).
    assert shown.startswith("The place where plants and animals live is their habitat.")
    assert "\x8b" not in shown and len(shown.split()) <= 70


def test_a_number_ending_a_sentence_is_not_an_exercise_item():
    text = section("g6-math-1", "Virahānka numbers, and powers of 2")["text"]
    assert "powers of 2." in focus(text, "give me an example of a number pattern")
