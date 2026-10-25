"""
Produce a report of sample questions and the system's answers.

Runs a set of questions through the complete pipeline - preprocessing, intent
classification, chapter retrieval and response generation - and writes a
readable report. Intended for demonstrations and progress reviews, where a
printed set of real inputs and outputs is more convincing than a description.

Run from the project root:

    python -m backend.nlp.demo_samples
    python -m backend.nlp.demo_samples --ask "what is a fraction"

The report is written to data/processed/sample_outputs.md as well as printed.
"""

from __future__ import annotations

import argparse
from datetime import datetime

from .classifier import CONFIDENCE_THRESHOLD, get_classifier
from .config import PROCESSED_DIR

REPORT_FILE = PROCESSED_DIR / "sample_outputs.md"

# Grouped so the report shows the system handling distinct kinds of question,
# not just many variations of one.
SAMPLE_GROUPS = [
    (
        "Questions about a topic",
        "Answered by finding the passage in the chapter that addresses them.",
        [
            "what is a prime number",
            "how do camels survive in the desert",
            "explain lines and angles",
            "what is symmetry",
            "give me an example of a number pattern",
        ],
    ),
    (
        "Questions where the wording does not match the chapter",
        "No shared keyword with the chapter title, so these test understanding "
        "of meaning rather than word matching.",
        [
            "how do plants and animals suit where they live",
            "what did Rama Natha learn about wealth",
            "the story about the elephant and the dog",
        ],
    ),
    (
        "Specific questions with exact answers",
        "DistilBERT fine-tuned for question answering reads the matching "
        "textbook passages and points at the words that answer the question.",
        [
            "What is the SI unit of length?",
            "What is the process of separating grains from stalks called?",
            "What is the name of the fox in the poem?",
            "When was the National War Memorial established?",
            "What are numbers with only two factors called?",
        ],
    ),
    (
        "Maths calculations",
        "No passage contains the answer to a calculation, so these are solved "
        "exactly, with the working the chapter teaches.",
        [
            "what is 1/3 + 1/6",
            "is 91 a prime number",
            "HCF of 12 and 18",
            "area of a rectangle 5 m by 4 m",
        ],
    ),
    (
        "Questions in Telugu",
        "Matched against the Telugu chapters with character n-grams, and "
        "answered in Telugu.",
        [
            "రైతు ఏమి చేస్తాడు?",
            "నిజమైన స్నేహం అంటే ఏమిటి?",
        ],
    ),
    (
        "Questions about the catalogue",
        "Answered from the content bank directly; there is nothing to search "
        "for, because the student is asking what exists.",
        [
            "list the chapters",
            "show me the science chapters",
            "what subjects can I study",
        ],
    ),
    (
        "Questions the system should decline",
        "Outside the curriculum, or about data the app does not record.",
        [
            "book me a hotel",
            "who won the cricket match",
            "how much time did I spend studying",
        ],
    ),
    (
        "Badly phrased questions",
        "The classifier is unsure, but a relevant chapter is still found and "
        "shown with an honest caveat.",
        [
            "angle thing confusing help",
            "prime number what mean",
            "asdfgh qwerty",
        ],
    ),
]

DIRECT_INTENTS = {"calculation", "telugu_question"}


def answer(question: str, grade: int | None, service) -> dict:
    """Run one question through the full pipeline (the same code the app uses)."""
    result = service.reply(question, grade=grade)
    confident = result["intent"] in DIRECT_INTENTS or result["confidence"] >= CONFIDENCE_THRESHOLD
    return {
        "question": question,
        "cleaned": result.get("cleaned", question),
        "processed": result.get("processed", question),
        "intent": result["intent"],
        "confidence": result["confidence"],
        "confident": confident,
        "top_intents": result.get("top_intents", []),
        "understood": result["understood"],
        "lesson": result["lesson"],
        "reply": result["reply"],
        "answer": result.get("answer"),
    }


def render(entry: dict) -> str:
    """One question and answer, as markdown."""
    lines = [f"### \u201c{entry['question']}\u201d", ""]

    verdict = entry["intent"] if entry["confident"] else f"{entry['intent']} (below threshold)"
    lines.append(f"**Detected as:** {verdict} &mdash; {entry['confidence'] * 100:.1f}% confident")

    if entry["lesson"]:
        lesson = entry["lesson"]
        lines.append(
            f"**Chapter found:** {lesson['title']} "
            f"({lesson['subject']}, Grade {lesson['grade']})"
        )
    else:
        lines.append("**Chapter found:** none")
    if entry.get("answer"):
        a = entry["answer"]
        lines.append(f"**Exact answer:** {a['text']} *(from {a['source']}, score {a['score']:.2f})*")

    # Blockquote line by line; a blank line inside a quote is ">" on its own,
    # and doing this with chained replaces double-prefixes the second line.
    quoted = "\n".join(
        ("> " + line) if line.strip() else ">"
        for line in entry["reply"].split("\n")
    )
    lines += ["", "**Reply:**", "", quoted, ""]

    runners_up = ", ".join(
        f"{name} {prob * 100:.0f}%" for name, prob in entry["top_intents"][1:]
    )
    lines.append(f"*Cleaned to:* `{entry['cleaned']}`  ")
    if runners_up:
        lines.append(f"*Next closest categories:* {runners_up}")
    lines.append("")
    return "\n".join(lines)


def print_entry(entry: dict) -> None:
    """One question and answer, for the terminal."""
    print(f"\n  Q: {entry['question']}")
    state = "" if entry["confident"] else "  [below confidence threshold]"
    print(f"     intent    : {entry['intent']} ({entry['confidence'] * 100:.1f}%){state}")
    if entry["lesson"]:
        print(f"     chapter   : {entry['lesson']['title']} ({entry['lesson']['subject']})")
    else:
        print("     chapter   : none")
    if entry.get("answer"):
        print(f"     answer    : {entry['answer']['text']}  ({entry['answer']['source']}, {entry['answer']['score']:.2f})")
    reply = entry["reply"].replace("\n\n", " ").replace("\n", " ")
    if len(reply) > 240:
        reply = reply[:240].rsplit(" ", 1)[0] + "..."
    print(f"     reply     : {reply}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sample outputs for a demonstration")
    parser.add_argument("--grade", type=int, default=6, help="student grade to answer as")
    parser.add_argument("--ask", metavar="QUESTION", help="run one question instead")
    args = parser.parse_args()

    try:
        get_classifier()
    except FileNotFoundError:
        raise SystemExit(
            "The classifier has not been trained. Run:\n"
            "    python -m backend.nlp.build_dataset\n"
            "    python -m backend.nlp.train_intent"
        )

    # The database is only needed for catalogue and progress questions; without
    # it the rest of the report still runs.
    try:
        from ..database import db

        db["lessons"].find_one({})
        database = db
    except Exception:
        print("WARNING: MongoDB not reachable. Catalogue questions will be limited.\n")
        database = None

    from ..chatbot.service import ChatService

    service = ChatService(database=database)

    if args.ask:
        entry = answer(args.ask, args.grade, service)
        print_entry(entry)
        print()
        return

    print("=" * 72)
    print(f"SAMPLE OUTPUTS  (answering as a Grade {args.grade} student)")
    print("=" * 72)

    report = [
        f"# EduQuest AI &mdash; sample questions and answers",
        "",
        f"Generated {datetime.now().strftime('%d %B %Y')} for a Grade {args.grade} "
        "student, by running each question through the same pipeline the app "
        "uses: Telugu detection, the maths solver, preprocessing, intent "
        "classification, chapter retrieval, answer extraction and response "
        "generation.",
        "",
        f"Confidence threshold: {CONFIDENCE_THRESHOLD}. Below it the system "
        "reports that it is unsure rather than presenting a guess as fact.",
        "",
        "These are demonstrations. Measured accuracy on the 38-question answer "
        "test (`python -m backend.nlp.test_answers`) is 33/38 (86%): Mathematics "
        "10/10, Telugu 4/4, explanation questions 3/3, off-topic 3/3, Science "
        "8/10, English 5/8. The misses are questions that need the model to follow "
        "a pronoun or description across sentences (\"who taught Ila Sachani\", "
        "\"who gave the neem tree its name\", \"who was Gajaraj\").",
        "",
    ]

    for title, note, questions in SAMPLE_GROUPS:
        print(f"\n{'-' * 72}\n{title.upper()}\n{'-' * 72}")
        print(f"  {note}")

        report += [f"## {title}", "", note, ""]

        for question in questions:
            entry = answer(question, args.grade, service)
            print_entry(entry)
            report.append(render(entry))

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_FILE, "w", encoding="utf-8") as fh:
        fh.write("\n".join(report))

    print(f"\n{'=' * 72}")
    print(f"  Written to {REPORT_FILE}")
    print(f"{'=' * 72}\n")


if __name__ == "__main__":
    main()
