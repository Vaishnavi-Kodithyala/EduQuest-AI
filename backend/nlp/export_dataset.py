"""
Export the intent classifier's training data in a readable form.

The project holds three different kinds of data, and only the first is training
data in the strict sense:

1. **Training data** - data/student_queries.json. 180 questions, each labelled
   with the intent it belongs to. This is what the classifier learns from.

2. **Knowledge base** - data/lessons.json and data/chapter_passages.json. The
   chapters the chatbot answers *from*. Nothing is trained on these; they are
   searched at query time.

3. **Pre-trained model weights** - DistilBERT, downloaded from Hugging Face.
   Trained by others on a large text corpus. This project does not train it;
   it only trains a small classifier layer on top of its output.

This script writes the first of those as a report and a spreadsheet.

Run from the project root:

    python -m backend.nlp.export_dataset
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime

from .config import DATA_DIR, PROCESSED_DIR

QUERIES_FILE = DATA_DIR / "student_queries.json"
INTENTS_FILE = DATA_DIR / "intents.json"
LESSONS_FILE = DATA_DIR / "lessons.json"
PASSAGES_FILE = DATA_DIR / "chapter_passages.json"

REPORT_FILE = PROCESSED_DIR / "training_data.md"
CSV_FILE = PROCESSED_DIR / "training_data.csv"


def load(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return default


def main() -> None:
    queries = load(QUERIES_FILE)
    if queries is None:
        raise SystemExit(
            f"{QUERIES_FILE.name} not found. Generate it with:\n"
            "    python -m backend.nlp.build_queries"
        )

    intents_meta = {i["intent"]: i for i in (load(INTENTS_FILE) or [])}
    lessons = load(LESSONS_FILE, [])
    passages = load(PASSAGES_FILE, [])

    by_intent = defaultdict(list)
    for row in queries:
        by_intent[row["intent"]].append(row)

    counts = {intent: len(rows) for intent, rows in sorted(by_intent.items())}
    vocabulary = Counter(
        word.lower().strip("?.,!") for row in queries for word in row["query"].split()
    )
    languages = Counter(row.get("language", "en") for row in queries)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # --- CSV, for anyone who wants it in a spreadsheet ---
    with open(CSV_FILE, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["id", "query", "intent", "language"])
        for row in queries:
            writer.writerow(
                [row.get("id", ""), row["query"], row["intent"], row.get("language", "en")]
            )

    # --- Markdown report ---
    out = [
        "# EduQuest AI &mdash; intent classifier training data",
        "",
        f"Exported {datetime.now().strftime('%d %B %Y')}.",
        "",
        "## What this is",
        "",
        "Each row is a question a student might type, labelled with the kind of",
        "request it represents. The classifier learns from these labels to",
        "recognise the intent behind a question it has never seen.",
        "",
        "The project contains three distinct kinds of data, and only this file is",
        "training data:",
        "",
        "| Data | Role | Size |",
        "|---|---|---|",
        f"| `student_queries.json` | **Training data.** The classifier learns from these labelled examples. | {len(queries)} questions |",
        f"| `lessons.json`, `chapter_passages.json` | **Knowledge base.** Searched at query time to answer from; nothing is trained on them. | {len(lessons)} chapters, {len(passages)} passages |",
        "| DistilBERT weights | **Pre-trained by others** on a large text corpus. This project trains only a small classifier layer on top of its output. | 66 million parameters |",
        "",
        "## Summary",
        "",
        f"- **{len(queries)} labelled questions** across **{len(counts)} intents**",
        (
            f"- **{min(counts.values())} examples per intent**, balanced"
            if len(set(counts.values())) == 1
            else f"- **{min(counts.values())} to {max(counts.values())} examples per intent**"
        ),
        f"- **{len(vocabulary)} distinct words** in the question text",
        f"- Languages: {', '.join(f'{k} ({v})' for k, v in languages.items())}",
        "",
        "Classes are kept balanced deliberately. An intent with more examples than",
        "the others would be predicted more often simply because it appears more",
        "often, which inflates accuracy without improving the system.",
        "",
        "## The intents",
        "",
        "| Intent | What the student wants | Examples |",
        "|---|---|---|",
    ]

    for intent in sorted(by_intent):
        description = intents_meta.get(intent, {}).get("description", "&mdash;")
        out.append(f"| `{intent}` | {description} | {counts[intent]} |")

    out += [
        "",
        "## Every question, by intent",
        "",
        "These are the complete contents of the training set.",
        "",
    ]

    for intent in sorted(by_intent):
        description = intents_meta.get(intent, {}).get("description", "")
        out += [f"### {intent}", ""]
        if description:
            out += [f"*{description}*", ""]
        for row in by_intent[intent]:
            out.append(f"{row.get('id', '')} &mdash; {row['query']}")
            out.append("")

    out += [
        "## Notes on how this set was built",
        "",
        "**The original Week 2 dataset had three problems**, all found by the",
        "Week 6 validation checks before any training took place:",
        "",
        "1. The two data files contained the same 50 texts, so using both would",
        "   have duplicated every question and produced a meaningless accuracy.",
        "2. `definition` and `concept_explanation` both contained \u201cWhat is a X?\u201d",
        "   phrasings, which no classifier can separate.",
        "3. Questions referenced topics absent from the content bank, so chapter",
        "   search had nothing correct to find.",
        "",
        "**The build script checks for near-duplicate phrasings across intents**",
        "every time the dataset is regenerated. Adding \u201cHow many chapters do I",
        "have?\u201d to one intent once dropped another intent's recall to 0.33,",
        "because \u201cHow many points do I have?\u201d was already in it. The check now",
        "catches a single swapped word anywhere in a sentence.",
        "",
        "**Regenerate this dataset with** `python -m backend.nlp.build_queries`.",
        "The questions live in that script rather than being edited by hand, so",
        "the validation runs automatically on every change.",
        "",
    ]

    with open(REPORT_FILE, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))

    print("=" * 68)
    print("TRAINING DATA EXPORT")
    print("=" * 68)
    print(f"\n  {len(queries)} labelled questions across {len(counts)} intents")
    print(f"  {len(vocabulary)} distinct words")
    print(f"  Balanced: {'yes' if len(set(counts.values())) == 1 else 'no'}"
          f"  ({min(counts.values())}-{max(counts.values())} per intent)")
    print("\n  Per intent:")
    for intent, count in counts.items():
        print(f"    {intent:<22} {count}")
    print(f"\n  Also in the project, but not training data:")
    print(f"    knowledge base        {len(lessons)} chapters, {len(passages)} passages")
    print(f"\n  Written:")
    print(f"    {REPORT_FILE}")
    print(f"    {CSV_FILE}")
    print()


if __name__ == "__main__":
    main()
