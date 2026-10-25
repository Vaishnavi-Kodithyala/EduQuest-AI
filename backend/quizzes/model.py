from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Q:
    """
    One multiple-choice question.

    concept      what the question tests; the teacher dashboard groups wrong
                 answers by this, so questions on the same idea share a name
    text         the question
    answer       the correct option, always written first here for readability
    wrong        three plausible wrong options
    explanation  one or two sentences shown to the student after submitting
    """

    concept: str
    text: str
    answer: str
    wrong: tuple[str, str, str]
    explanation: str
