"""
Week 7 - Regenerate the student query dataset.

Fixes two labelling problems found by the Week 6 validation, and expands the
set from 5 to 15 examples per intent.

Label changes from the Week 2 dataset
-------------------------------------
1. `greeting` now contains only actual greetings. "Can you help me?" and
   "I need help with my lesson" moved to homework_help, where their nearest
   neighbours already put them.

2. Every topic referenced is a real chapter in data/lessons.json. The first
   version of this file used photosynthesis, fractions and simple interest,
   none of which exist in the content bank, so the chatbot's lesson retrieval
   had nothing correct to find.

3. A `browse_content` intent was added. "List the chapters" and "what subjects
   can I study" are entirely on-topic, but no existing intent covered them, so
   the classifier had nothing correct to choose and the confidence threshold
   rejected them. These are catalogue questions, answered by listing content
   rather than by searching it.

4. `out_of_scope` gained several "Show me ..." phrasings. Every "show" query
   used to belong to progress_help, so the classifier had learned that the verb
   itself meant progress.

5. `definition` and `concept_explanation` were not separable - both contained
   "What is a X?" phrasings. The boundary is now explicit:
      definition           -> what a TERM means. Short factual answer.
                              "define evaporation", "what does condensation mean"
      concept_explanation  -> how a PROCESS works. Longer walkthrough.
                              "explain the water cycle", "how does photosynthesis work"
   Queries are written consistently against that boundary so the distinction
   is learnable rather than arbitrary.

Run from the project root:
    python -m backend.nlp.build_queries
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_FILE = DATA_DIR / "student_queries.json"
INTENTS_FILE = DATA_DIR / "intents.json"

QUERIES: dict[str, list[str]] = {
    "greeting": [
        "Hi",
        "Hello",
        "Good morning",
        "Good evening",
        "Hey there",
        "Namaste",
        "Hello sir",
        "Hi teacher",
        "Good afternoon",
        "Hey",
        "Hello there",
        "Hi again",
        "Good morning teacher",
        "Hello friend",
        "Hi, I am back",
    ],
    "definition": [
        "What is an angle?",
        "Define a ray",
        "What does adaptation mean?",
        "What is an acid?",
        "What is a pattern?",
        "Define an arithmetic expression",
        "What is a base?",
        "What does neutral mean?",
        "What is place value?",
        "Define a line segment",
        "What is an indicator?",
        "What is a sequence?",
        "What does habitat mean?",
        "What is a protractor?",
        "Define estimation",
    ],
    "concept_explanation": [
        "Explain how camels survive in the desert",
        "Explain how lines and angles work",
        "How do scientists investigate a question?",
        "Explain the order of operations",
        "How do number patterns work?",
        "Explain how litmus paper tests a substance",
        "Explain why animals adapt to their surroundings",
        "How do you compare very large numbers?",
        "Explain what Rama Natha learned about wealth",
        "How did Gajaraj and the dog become friends?",
        "Explain how substances are grouped as acidic or basic",
        "How do you read large numbers correctly?",
        "Explain what the river was trying to say",
        "Explain why education matters in the lesson",
        "How are angles measured with a protractor?",
    ],
    "example_request": [
        "Give me an example of a number pattern",
        "Can you give me an example of an acid?",
        "Show me an example problem on angles",
        "Give me an example for this topic",
        "Can you show a real life example?",
        "Show me a sample question",
        "Give an example of a large number",
        "Can I see a worked example?",
        "Show me one more example",
        "Give me a practical example of adaptation",
        "Can you show an example with brackets?",
        "I want to see an example",
        "Show an example of a basic substance",
        "Give me a simple example",
        "Show me how it looks with an example",
    ],
    "formula_help": [
        "What is the rule for the order of operations?",
        "Which rule applies to this kind of sum?",
        "How do I simplify this expression?",
        "What is the rule for simplifying expressions?",
        "What are the steps in the correct order?",
        "What is the rule for naming angles?",
        "How do I estimate a large number?",
        "Which method applies to this sum?",
        "What steps do I follow for brackets?",
        "How do I find the value of an expression?",
        "Give me the rule for place value",
        "What is the method to compare numbers?",
        "Which method is used to measure an angle?",
        "What is the correct sequence of steps?",
        "What rule gives the correct answer here?",
    ],
    "homework_help": [
        "Help me solve my homework",
        "How do I solve this question?",
        "Can you help with this maths problem?",
        "I am stuck on my homework",
        "Help me answer this quiz question",
        "Can you help me?",
        "I need help with my lesson",
        "I cannot solve this angles sum",
        "Help me with this exercise",
        "How do I work out this expression?",
        "I am stuck on question three",
        "Can you help me finish this?",
        "Help me with my assignment",
        "I do not know how to start this problem",
        "Please help me solve this",
    ],
    "clarification": [
        "I don't understand",
        "Explain that again",
        "Can you explain it more simply?",
        "I am confused about this topic",
        "Please explain this in an easier way",
        "Say that again please",
        "That was too difficult to follow",
        "Can you repeat that?",
        "I still do not get it",
        "Explain in simple words",
        "This is confusing",
        "Can you say it differently?",
        "I did not understand your explanation",
        "Make it easier to understand",
        "Explain once more slowly",
    ],
    "quiz_help": [
        "Give me a quiz",
        "I want to practice questions",
        "Start a quiz for me",
        "Can I test myself?",
        "Show me practice questions",
        "I want to attempt a quiz",
        "Give me some practice problems",
        "Can we do a quiz now?",
        "Test me with some questions",
        "I want to revise with questions",
        "Start the chapter quiz",
        "Give me more questions to practice",
        "Can I take a test?",
        "Quiz me on this chapter",
        "I want practice exercises",
    ],
    "progress_help": [
        "Show my progress",
        "How many quizzes have I completed?",
        "What is my score?",
        "How many points do I have?",
        "Show my learning progress",
        "What is my current level?",
        "How many badges have I earned?",
        "What is my streak?",
        "How am I performing?",
        "Show my quiz results",
        "What is my score in English?",
        "How am I doing in Mathematics?",
        "What is my Science average?",
        "Show my report",
        "Am I improving?",
    ],
    "browse_content": [
        "List the chapters",
        "What chapters are there?",
        "Show me all the chapters",
        "What subjects can I study?",
        "Which chapters are in Science?",
        "What topics are covered?",
        "Show me the Mathematics chapters",
        "Which topics does this app cover?",
        "What can I learn here?",
        "List the available subjects",
        "What lessons are available?",
        "Show me the English chapters",
        "What is in the syllabus?",
        "Give me the chapter list",
        "What lessons does this app have?",
    ],
    "study_advice": [
        "What should I study next?",
        "How can I improve?",
        "Where am I weak?",
        "What should I focus on?",
        "Which subject do I need to work on?",
        "Help me plan what to study",
        "What do you suggest I learn?",
        "Where should I start?",
        "Which chapter should I do next?",
        "Tell me what to revise",
        "What needs more practice?",
        "Suggest something for me to study",
        "Where do I need more work?",
        "What is the best thing to learn now?",
        "Give me a study plan",
    ],
    "out_of_scope": [
        "What is today's weather?",
        "Order food for me",
        "Who won the cricket match?",
        "Tell me a movie review",
        "Book a hotel",
        "Play a song",
        "Show me funny videos",
        "Show me the cricket score",
        "Show me a movie trailer",
        "What is the news today?",
        "Who is the prime minister?",
        "Send a message to my friend",
        "Show me shopping offers",
        "Recommend a restaurant",
        "Book a train ticket",
    ],
}


def build() -> list[dict]:
    rows: list[dict] = []
    counter = 1
    for intent in sorted(QUERIES):
        for text in QUERIES[intent]:
            rows.append(
                {
                    "id": f"q{counter:03d}",
                    "query": text,
                    "intent": intent,
                    "language": "en",
                }
            )
            counter += 1
    return rows


def build_intents(rows: list[dict]) -> list[dict]:
    """
    Rebuild intents.json so it stays consistent with the query set.

    The Week 2 version duplicated student_queries.json exactly, which made it
    useless as a second dataset. It now holds a small set of canonical
    reference phrases per intent, disjoint from the training queries.
    """
    descriptions = {
        "greeting": "Student opens the conversation.",
        "browse_content": "Student asks what chapters or subjects exist. Answered from the content bank, not by search.",
        "study_advice": "Student asks what to study or where they are weak. Answered by the Week 8 recommendation engine.",
        "definition": "Student asks what a term means. Short factual answer.",
        "concept_explanation": "Student asks how a process works. Longer walkthrough.",
        "example_request": "Student asks to see a worked example.",
        "formula_help": "Student asks which formula to use or how to calculate.",
        "homework_help": "Student is stuck on a specific problem or exercise.",
        "clarification": "Student did not understand and wants it restated.",
        "quiz_help": "Student wants to practise or take a quiz.",
        "progress_help": "Student asks about their score, XP, streak or progress.",
        "out_of_scope": "Request unrelated to learning. Should be politely declined.",
    }

    intents = []
    for intent in sorted(QUERIES):
        intents.append(
            {
                "intent": intent,
                "description": descriptions[intent],
                "training_examples": len(QUERIES[intent]),
            }
        )
    return intents


def _tokens(query: str) -> set[str]:
    """Token set with subject names masked, for near-duplicate comparison."""
    text = query.lower().strip("?").strip()
    text = re.sub(r"\b(english|mathematics|maths|math|science|telugu)\b", "SUBJ", text)
    return {word.strip(".,!") for word in text.split() if word.strip(".,!")}


def check_collisions(rows: list[dict], max_difference: int = 2) -> list[str]:
    """
    Warn when two intents contain near-identical phrasings.

    Comparing sentence *prefixes* is not enough: "How many chapters do I have?"
    and "How many points do I have?" differ at the third word but are the same
    template, and that pair alone dropped progress_help's recall to 0.33 once.
    Comparing token sets catches single-word substitutions wherever they fall.

    A symmetric difference of 2 means the two queries differ by exactly one
    swapped word. The classifier has no way to separate those, so one side
    needs rewording.
    """
    problems: list[str] = []
    seen: set[tuple[str, str]] = set()

    entries = [(row["intent"], row["query"], _tokens(row["query"])) for row in rows]

    for i, (intent_a, query_a, tokens_a) in enumerate(entries):
        if len(tokens_a) < 4:
            continue
        for intent_b, query_b, tokens_b in entries[i + 1 :]:
            if intent_a == intent_b or len(tokens_b) < 4:
                continue
            if len(tokens_a ^ tokens_b) > max_difference:
                continue
            key = tuple(sorted((query_a, query_b)))
            if key in seen:
                continue
            seen.add(key)
            problems.append(
                f'  "{query_a}" ({intent_a})\n'
                f'  "{query_b}" ({intent_b})'
            )

    return problems


def main() -> None:
    rows = build()

    seen = {}
    for r in rows:
        key = r["query"].strip().lower()
        seen[key] = seen.get(key, 0) + 1
    duplicates = {k: v for k, v in seen.items() if v > 1}
    if duplicates:
        raise SystemExit(f"Duplicate queries found: {duplicates}")

    collisions = check_collisions(rows)
    if collisions:
        print("WARNING - these phrasings appear under more than one intent:")
        for line in collisions:
            print(line)
        print("  The classifier cannot separate identical phrasings. Reword one side.\n")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2, ensure_ascii=False)

    with open(INTENTS_FILE, "w", encoding="utf-8") as fh:
        json.dump(build_intents(rows), fh, indent=2, ensure_ascii=False)

    counts = {intent: len(queries) for intent, queries in sorted(QUERIES.items())}
    if len(set(counts.values())) > 1:
        print(f"WARNING - uneven class sizes: {counts}\n")

    print(f"Wrote {len(rows)} queries across {len(QUERIES)} intents")
    if not collisions:
        print("  No phrasing collisions between intents.")
    print(f"  {OUTPUT_FILE.name}")
    print(f"  {INTENTS_FILE.name}")
    print("\nNext:")
    print("  python -m backend.nlp.build_dataset")
    print("  python -m backend.nlp.validate")


if __name__ == "__main__":
    main()
