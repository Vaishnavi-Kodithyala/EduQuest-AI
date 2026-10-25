# EduQuest AI &mdash; intent classifier training data

Exported 07 October 2026.

## What this is

Each row is a question a student might type, labelled with the kind of
request it represents. The classifier learns from these labels to
recognise the intent behind a question it has never seen.

The project contains three distinct kinds of data, and only this file is
training data:

| Data | Role | Size |
|---|---|---|
| `student_queries.json` | **Training data.** The classifier learns from these labelled examples. | 180 questions |
| `lessons.json`, `chapter_passages.json` | **Knowledge base.** Searched at query time to answer from; nothing is trained on them. | 48 chapters, 3579 passages |
| DistilBERT weights | **Pre-trained by others** on a large text corpus. This project trains only a small classifier layer on top of its output. | 66 million parameters |

## Summary

- **180 labelled questions** across **12 intents**
- **15 examples per intent**, balanced
- **275 distinct words** in the question text
- Languages: en (180)

Classes are kept balanced deliberately. An intent with more examples than
the others would be predicted more often simply because it appears more
often, which inflates accuracy without improving the system.

## The intents

| Intent | What the student wants | Examples |
|---|---|---|
| `browse_content` | Student asks what chapters or subjects exist. Answered from the content bank, not by search. | 15 |
| `clarification` | Student did not understand and wants it restated. | 15 |
| `concept_explanation` | Student asks how a process works. Longer walkthrough. | 15 |
| `definition` | Student asks what a term means. Short factual answer. | 15 |
| `example_request` | Student asks to see a worked example. | 15 |
| `formula_help` | Student asks which formula to use or how to calculate. | 15 |
| `greeting` | Student opens the conversation. | 15 |
| `homework_help` | Student is stuck on a specific problem or exercise. | 15 |
| `out_of_scope` | Request unrelated to learning. Should be politely declined. | 15 |
| `progress_help` | Student asks about their score, XP, streak or progress. | 15 |
| `quiz_help` | Student wants to practise or take a quiz. | 15 |
| `study_advice` | Student asks what to study or where they are weak. Answered by the Week 8 recommendation engine. | 15 |

## Every question, by intent

These are the complete contents of the training set.

### browse_content

*Student asks what chapters or subjects exist. Answered from the content bank, not by search.*

q001 &mdash; List the chapters

q002 &mdash; What chapters are there?

q003 &mdash; Show me all the chapters

q004 &mdash; What subjects can I study?

q005 &mdash; Which chapters are in Science?

q006 &mdash; What topics are covered?

q007 &mdash; Show me the Mathematics chapters

q008 &mdash; Which topics does this app cover?

q009 &mdash; What can I learn here?

q010 &mdash; List the available subjects

q011 &mdash; What lessons are available?

q012 &mdash; Show me the English chapters

q013 &mdash; What is in the syllabus?

q014 &mdash; Give me the chapter list

q015 &mdash; What lessons does this app have?

### clarification

*Student did not understand and wants it restated.*

q016 &mdash; I don't understand

q017 &mdash; Explain that again

q018 &mdash; Can you explain it more simply?

q019 &mdash; I am confused about this topic

q020 &mdash; Please explain this in an easier way

q021 &mdash; Say that again please

q022 &mdash; That was too difficult to follow

q023 &mdash; Can you repeat that?

q024 &mdash; I still do not get it

q025 &mdash; Explain in simple words

q026 &mdash; This is confusing

q027 &mdash; Can you say it differently?

q028 &mdash; I did not understand your explanation

q029 &mdash; Make it easier to understand

q030 &mdash; Explain once more slowly

### concept_explanation

*Student asks how a process works. Longer walkthrough.*

q031 &mdash; Explain how camels survive in the desert

q032 &mdash; Explain how lines and angles work

q033 &mdash; How do scientists investigate a question?

q034 &mdash; Explain the order of operations

q035 &mdash; How do number patterns work?

q036 &mdash; Explain how litmus paper tests a substance

q037 &mdash; Explain why animals adapt to their surroundings

q038 &mdash; How do you compare very large numbers?

q039 &mdash; Explain what Rama Natha learned about wealth

q040 &mdash; How did Gajaraj and the dog become friends?

q041 &mdash; Explain how substances are grouped as acidic or basic

q042 &mdash; How do you read large numbers correctly?

q043 &mdash; Explain what the river was trying to say

q044 &mdash; Explain why education matters in the lesson

q045 &mdash; How are angles measured with a protractor?

### definition

*Student asks what a term means. Short factual answer.*

q046 &mdash; What is an angle?

q047 &mdash; Define a ray

q048 &mdash; What does adaptation mean?

q049 &mdash; What is an acid?

q050 &mdash; What is a pattern?

q051 &mdash; Define an arithmetic expression

q052 &mdash; What is a base?

q053 &mdash; What does neutral mean?

q054 &mdash; What is place value?

q055 &mdash; Define a line segment

q056 &mdash; What is an indicator?

q057 &mdash; What is a sequence?

q058 &mdash; What does habitat mean?

q059 &mdash; What is a protractor?

q060 &mdash; Define estimation

### example_request

*Student asks to see a worked example.*

q061 &mdash; Give me an example of a number pattern

q062 &mdash; Can you give me an example of an acid?

q063 &mdash; Show me an example problem on angles

q064 &mdash; Give me an example for this topic

q065 &mdash; Can you show a real life example?

q066 &mdash; Show me a sample question

q067 &mdash; Give an example of a large number

q068 &mdash; Can I see a worked example?

q069 &mdash; Show me one more example

q070 &mdash; Give me a practical example of adaptation

q071 &mdash; Can you show an example with brackets?

q072 &mdash; I want to see an example

q073 &mdash; Show an example of a basic substance

q074 &mdash; Give me a simple example

q075 &mdash; Show me how it looks with an example

### formula_help

*Student asks which formula to use or how to calculate.*

q076 &mdash; What is the rule for the order of operations?

q077 &mdash; Which rule applies to this kind of sum?

q078 &mdash; How do I simplify this expression?

q079 &mdash; What is the rule for simplifying expressions?

q080 &mdash; What are the steps in the correct order?

q081 &mdash; What is the rule for naming angles?

q082 &mdash; How do I estimate a large number?

q083 &mdash; Which method applies to this sum?

q084 &mdash; What steps do I follow for brackets?

q085 &mdash; How do I find the value of an expression?

q086 &mdash; Give me the rule for place value

q087 &mdash; What is the method to compare numbers?

q088 &mdash; Which method is used to measure an angle?

q089 &mdash; What is the correct sequence of steps?

q090 &mdash; What rule gives the correct answer here?

### greeting

*Student opens the conversation.*

q091 &mdash; Hi

q092 &mdash; Hello

q093 &mdash; Good morning

q094 &mdash; Good evening

q095 &mdash; Hey there

q096 &mdash; Namaste

q097 &mdash; Hello sir

q098 &mdash; Hi teacher

q099 &mdash; Good afternoon

q100 &mdash; Hey

q101 &mdash; Hello there

q102 &mdash; Hi again

q103 &mdash; Good morning teacher

q104 &mdash; Hello friend

q105 &mdash; Hi, I am back

### homework_help

*Student is stuck on a specific problem or exercise.*

q106 &mdash; Help me solve my homework

q107 &mdash; How do I solve this question?

q108 &mdash; Can you help with this maths problem?

q109 &mdash; I am stuck on my homework

q110 &mdash; Help me answer this quiz question

q111 &mdash; Can you help me?

q112 &mdash; I need help with my lesson

q113 &mdash; I cannot solve this angles sum

q114 &mdash; Help me with this exercise

q115 &mdash; How do I work out this expression?

q116 &mdash; I am stuck on question three

q117 &mdash; Can you help me finish this?

q118 &mdash; Help me with my assignment

q119 &mdash; I do not know how to start this problem

q120 &mdash; Please help me solve this

### out_of_scope

*Request unrelated to learning. Should be politely declined.*

q121 &mdash; What is today's weather?

q122 &mdash; Order food for me

q123 &mdash; Who won the cricket match?

q124 &mdash; Tell me a movie review

q125 &mdash; Book a hotel

q126 &mdash; Play a song

q127 &mdash; Show me funny videos

q128 &mdash; Show me the cricket score

q129 &mdash; Show me a movie trailer

q130 &mdash; What is the news today?

q131 &mdash; Who is the prime minister?

q132 &mdash; Send a message to my friend

q133 &mdash; Show me shopping offers

q134 &mdash; Recommend a restaurant

q135 &mdash; Book a train ticket

### progress_help

*Student asks about their score, XP, streak or progress.*

q136 &mdash; Show my progress

q137 &mdash; How many quizzes have I completed?

q138 &mdash; What is my score?

q139 &mdash; How many points do I have?

q140 &mdash; Show my learning progress

q141 &mdash; What is my current level?

q142 &mdash; How many badges have I earned?

q143 &mdash; What is my streak?

q144 &mdash; How am I performing?

q145 &mdash; Show my quiz results

q146 &mdash; What is my score in English?

q147 &mdash; How am I doing in Mathematics?

q148 &mdash; What is my Science average?

q149 &mdash; Show my report

q150 &mdash; Am I improving?

### quiz_help

*Student wants to practise or take a quiz.*

q151 &mdash; Give me a quiz

q152 &mdash; I want to practice questions

q153 &mdash; Start a quiz for me

q154 &mdash; Can I test myself?

q155 &mdash; Show me practice questions

q156 &mdash; I want to attempt a quiz

q157 &mdash; Give me some practice problems

q158 &mdash; Can we do a quiz now?

q159 &mdash; Test me with some questions

q160 &mdash; I want to revise with questions

q161 &mdash; Start the chapter quiz

q162 &mdash; Give me more questions to practice

q163 &mdash; Can I take a test?

q164 &mdash; Quiz me on this chapter

q165 &mdash; I want practice exercises

### study_advice

*Student asks what to study or where they are weak. Answered by the Week 8 recommendation engine.*

q166 &mdash; What should I study next?

q167 &mdash; How can I improve?

q168 &mdash; Where am I weak?

q169 &mdash; What should I focus on?

q170 &mdash; Which subject do I need to work on?

q171 &mdash; Help me plan what to study

q172 &mdash; What do you suggest I learn?

q173 &mdash; Where should I start?

q174 &mdash; Which chapter should I do next?

q175 &mdash; Tell me what to revise

q176 &mdash; What needs more practice?

q177 &mdash; Suggest something for me to study

q178 &mdash; Where do I need more work?

q179 &mdash; What is the best thing to learn now?

q180 &mdash; Give me a study plan

## Notes on how this set was built

**The original Week 2 dataset had three problems**, all found by the
Week 6 validation checks before any training took place:

1. The two data files contained the same 50 texts, so using both would
   have duplicated every question and produced a meaningless accuracy.
2. `definition` and `concept_explanation` both contained “What is a X?”
   phrasings, which no classifier can separate.
3. Questions referenced topics absent from the content bank, so chapter
   search had nothing correct to find.

**The build script checks for near-duplicate phrasings across intents**
every time the dataset is regenerated. Adding “How many chapters do I
have?” to one intent once dropped another intent's recall to 0.33,
because “How many points do I have?” was already in it. The check now
catches a single swapped word anywhere in a sentence.

**Regenerate this dataset with** `python -m backend.nlp.build_queries`.
The questions live in that script rather than being edited by hand, so
the validation runs automatically on every change.
