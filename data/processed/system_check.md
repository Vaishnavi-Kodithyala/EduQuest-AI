# System check

Run on 22 Oct 2026, 17:36 IST with `python -m backend.check_system`: the real MongoDB and the
real models, driven through the API the way a student and a teacher use the app.

**32 of 32 checks passed.**

| Step | Check | Result | Time |
|---|---|---|---|
| 1. Setup | MongoDB is reachable | PASS | |
| 1. Setup | 40 chapters and 40 quizzes are seeded | PASS | |
| 1. Setup | trained model files are present | PASS | |
| 2. Student | register | PASS | |
| 2. Student | log in | PASS | |
| 2. Student | chapter list (40, textbook order) | PASS | |
| 2. Student | open a chapter | PASS | |
| 2. Student | mark it as read: +30 XP (20 + daily 10) | PASS | |
| 2. Student | quiz arrives without its answers | PASS | |
| 2. Student | first attempt scored 40% with a review | PASS | |
| 3. Gamification | 40% earns +20 XP (2 correct answers, no pass bonus) | PASS | |
| 3. Gamification | retake at 100%: +80 XP (3 new correct, pass, perfect) | PASS | |
| 3. Gamification | badges: perfect score and comeback | PASS | |
| 3. Gamification | total 130 XP, level 1, 20 XP to level 2 | PASS | |
| 3. Gamification | streak started today | PASS | |
| 3. Gamification | on the leaderboard with the same XP | PASS | |
| 4. Next steps | after the failed quiz: 'try again' comes first | PASS | |
| 4. Next steps | after passing: no retry, unread chapters suggested | PASS | |
| 5. Chatbot (the first question loads the models) | classifier and lesson index ready | PASS | |
| 5. Chatbot (the first question loads the models) | textbook fact: exact answer 'metre' | PASS | 10.0s |
| 5. Chatbot (the first question loads the models) | calculation: 1/2 with working | PASS | |
| 5. Chatbot (the first question loads the models) | Telugu: answered from అభినందన | PASS | |
| 5. Chatbot (the first question loads the models) | explanation: points to Lines and Angles | PASS | 0.2s |
| 5. Chatbot (the first question loads the models) | off-topic: politely declined | PASS | 0.2s |
| 5. Chatbot (the first question loads the models) | progress: quotes the student's XP | PASS | |
| 6. Teacher | teacher logs in as a teacher | PASS | |
| 6. Teacher | students cannot open the class dashboard | PASS | |
| 6. Teacher | class dashboard loads and lists the student | PASS | 0.1s |
| 6. Teacher | same numbers: 1 chapter, 1 quiz, 2 attempts, 100% (latest), 130 XP | PASS | |
| 6. Teacher | chatbot questions counted (6) | PASS | |
| 6. Teacher | student detail opens | PASS | |
| 7. Clean-up | temporary accounts and their data deleted | PASS | |

## Chatbot replies

**Q:** What is the SI unit of length?  
intent `formula_help` (51%), answer **metre**, 10.0s  
> Metre.  “The SI unit of length is metre.”  That is from "Measurement of Length and Motion" in Science. Open the chapter to read more.

**Q:** what is 1/3 + 1/6  
intent `calculation` (100%), answer **1/3 + 1/6 = 1/2**, 0.0s  
> 1/3 + 1/6 = 1/2  Use a common denominator: the LCM of 3 and 6 is 6. 1/3 = 2/6 and 1/6 = 1/6 2/6 + 1/6 = 3/6 Simplify: 3/6 = 1/2  This is from "Fractions" in Mathematics - open it to practise the method.

**Q:** రైతు ఏమి చేస్తాడు?  
intent `telugu_question` (28%), answer **రైతు పొలంలో శ్రమించి పంటను పండిస్తాడు.**, 0.0s  
> రైతు పొలంలో శ్రమించి పంటను పండిస్తాడు.  — ‘అభినందన’ పాఠం నుండి.

**Q:** explain lines and angles  
intent `concept_explanation` (80%), 0.2s  
> Lines and line segments connect points, while rays extend in one direction.  Read the rest in "Lines and Angles", Mathematics, for the full walkthrough.

**Q:** who won the cricket match  
intent `out_of_scope` (99%), 0.2s  
> I can only help with your lessons and quizzes. Try asking me about a chapter, a formula, or your progress.

**Q:** how many points do I have  
intent `progress_help` (95%), 0.0s  
> You have completed 2 quizzes, averaging 70%, with a best score of 100%. You have 130 XP (level 1) and 4 badges.

