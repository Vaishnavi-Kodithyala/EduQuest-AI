# EduQuest AI &mdash; sample questions and answers

Generated 22 October 2026 for a Grade 6 student, by running each question through the same pipeline the app uses: Telugu detection, the maths solver, preprocessing, intent classification, chapter retrieval, answer extraction and response generation.

Confidence threshold: 0.6. Below it the system reports that it is unsure rather than presenting a guess as fact.

These are demonstrations. Measured accuracy on the 38-question answer test (`python -m backend.nlp.test_answers`) is 33/38 (86%): Mathematics 10/10, Telugu 4/4, explanation questions 3/3, off-topic 3/3, Science 8/10, English 5/8. The misses are questions that need the model to follow a pronoun or description across sentences ("who taught Ila Sachani", "who gave the neem tree its name", "who was Gajaraj").

## Questions about a topic

Answered by finding the passage in the chapter that addresses them.

### “what is a prime number”

**Detected as:** definition &mdash; 90.5% confident
**Chapter found:** Prime Time (Mathematics, Grade 6)

**Reply:**

> Prime numbers are numbers like 2, 3, 5, 7, 11, … that have only two factors, namely 1 and themselves. Composite numbers are numbers like 4, 6, 8, 9, … that have more than 2 factors, i.e., at least one factor other than 1 and themselves. For example, 8 has the factor 4 and 9 has the factor 3, so 8 and 9 are both composite.
>
> That is from "Prime Time" in Mathematics.

*Cleaned to:* `what is a prime number`  
*Next closest categories:* formula_help 6%, concept_explanation 1%

### “how do camels survive in the desert”

**Detected as:** concept_explanation &mdash; 96.7% confident
**Chapter found:** Diversity in the Living World (Science, Grade 6)

**Reply:**

> As camels do not lose much water from their bodies, they can survive for many days without drinking water.
>
> Read the rest in "Diversity in the Living World", Science, for the full walkthrough.

*Cleaned to:* `how do camels survive in the desert`  
*Next closest categories:* out_of_scope 3%, study_advice 0%

### “explain lines and angles”

**Detected as:** concept_explanation &mdash; 80.3% confident
**Chapter found:** Lines and Angles (Mathematics, Grade 6)

**Reply:**

> Lines and line segments connect points, while rays extend in one direction.
>
> Read the rest in "Lines and Angles", Mathematics, for the full walkthrough.

*Cleaned to:* `explain lines and angles`  
*Next closest categories:* definition 13%, browse_content 3%

### “what is symmetry”

**Detected as:** definition &mdash; 97.4% confident
**Chapter found:** Symmetry (Mathematics, Grade 6)

**Reply:**

> A symmetry refers to a part or parts of a figure that are repeated in some definite pattern.
>
> That is from "Symmetry" in Mathematics.

*Cleaned to:* `what is symmetry`  
*Next closest categories:* progress_help 1%, clarification 0%

### “give me an example of a number pattern”

**Detected as:** example_request &mdash; 99.1% confident
**Chapter found:** Patterns in Mathematics (Mathematics, Grade 6)

**Reply:**

> Some important examples of number sequences include the counting numbers, odd numbers, even numbers, square numbers, triangular numbers, cube numbers, Virahānka numbers, and powers of 2. Sometimes number sequences can be related to each other in beautiful and remarkable ways. For example, adding up the sequence of odd numbers starting with 1 gives square numbers.
>
> There are more examples in "Patterns in Mathematics", and its quiz gives you real questions to try.

*Cleaned to:* `give me an example of a number pattern`  
*Next closest categories:* formula_help 1%, homework_help 0%

## Questions where the wording does not match the chapter

No shared keyword with the chapter title, so these test understanding of meaning rather than word matching.

### “how do plants and animals suit where they live”

**Detected as:** concept_explanation &mdash; 98.5% confident
**Chapter found:** Diversity in the Living World (Science, Grade 6)

**Reply:**

> The place where plants and animals live is their habitat. Based on their habitats, animals and plants can be grouped as terrestrial and aquatic. Due to damage of their habitats, plants and animals lose their homes, food and other resources resulting in the loss of biodiversity.
>
> Read the rest in "Diversity in the Living World", Science, for the full walkthrough.

*Cleaned to:* `how do plants and animals suit where they live`  
*Next closest categories:* study_advice 1%, out_of_scope 1%

### “what did Rama Natha learn about wealth”

**Detected as:** concept_explanation &mdash; 95.0% confident
**Chapter found:** A Bottle of Dew (English, Grade 6)

**Reply:**

> 🪙 What if a few drops of dew could make you rich? Rama Natha is determined to find a magical shortcut—but his search leads to a surprising discovery about where real wealth comes from.
>
> Read the rest in "A Bottle of Dew", English, for the full walkthrough.

*Cleaned to:* `what did rama natha learn about wealth`  
*Next closest categories:* browse_content 2%, study_advice 1%

### “the story about the elephant and the dog”

**Detected as:** concept_explanation (below threshold) &mdash; 58.1% confident
**Chapter found:** The Unlikely Best Friends (English, Grade 6)

**Reply:**

> I am not certain what you were asking, but this looks relevant:
>
> The story, ‘The Elephant and the Dog’ is found in the Jataka tales. These stories are ancient Buddhist stories of life values and wisdom. These stories have been told from one generation to the next for over two thousand years.
>
> That is from "The Unlikely Best Friends" in English. If that is not what you meant, try rephrasing.

*Cleaned to:* `the story about the elephant and the dog`  
*Next closest categories:* out_of_scope 38%, browse_content 1%

## Specific questions with exact answers

DistilBERT fine-tuned for question answering reads the matching textbook passages and points at the words that answer the question.

### “What is the SI unit of length?”

**Detected as:** formula_help (below threshold) &mdash; 51.1% confident
**Chapter found:** Measurement of Length and Motion (Science, Grade 6)
**Exact answer:** metre *(from textbook, score 0.96)*

**Reply:**

> Metre.
>
> “The SI unit of length is metre.”
>
> That is from "Measurement of Length and Motion" in Science. Open the chapter to read more.

*Cleaned to:* `what is the si unit of length`  
*Next closest categories:* definition 37%, concept_explanation 6%

### “What is the process of separating grains from stalks called?”

**Detected as:** concept_explanation &mdash; 69.3% confident
**Chapter found:** Methods of Separation in Everyday Life (Science, Grade 6)
**Exact answer:** threshing *(from textbook, score 0.98)*

**Reply:**

> Threshing.
>
> “This process of separating grains from the stalks is known as threshing.”
>
> That is from "Methods of Separation in Everyday Life" in Science. Open the chapter to read more.

*Cleaned to:* `what is the process of separating grains from stalks called`  
*Next closest categories:* formula_help 18%, definition 5%

### “What is the name of the fox in the poem?”

**Detected as:** concept_explanation (below threshold) &mdash; 44.2% confident
**Chapter found:** The Raven and the Fox (English, Grade 6)
**Exact answer:** Reynard *(from textbook, score 0.89)*

**Reply:**

> Reynard.
>
> “Y ou may begin like this: This is a story about a clever fox named Reynard and Mr Raven.”
>
> That is from "The Raven and the Fox" in English. Open the chapter to read more.

*Cleaned to:* `what is the name of the fox in the poem`  
*Next closest categories:* out_of_scope 34%, formula_help 6%

### “When was the National War Memorial established?”

**Detected as:** factual_question &mdash; 81.2% confident
**Chapter found:** National War Memorial (English, Grade 6)
**Exact answer:** F ebruary 2019 *(from textbook, score 0.87)*

**Reply:**

> F ebruary 2019.
>
> “National War Memorial, New Delhi ¼jk"Vªh; lej Lekjd] ubZ fnYyh½ was established in F ebruary 2019.”
>
> That is from "National War Memorial" in English. Open the chapter to read more.

*Cleaned to:* `when was the national war memorial established`  
*Next closest categories:* study_advice 9%, concept_explanation 4%

### “What are numbers with only two factors called?”

**Detected as:** formula_help (below threshold) &mdash; 48.2% confident
**Chapter found:** Prime Time (Mathematics, Grade 6)
**Exact answer:** Prime numbers *(from textbook, score 0.85)*

**Reply:**

> Prime numbers.
>
> “Prime numbers are numbers like 2, 3, 5, 7, 11, … that have only two factors, namely 1 and themselves.”
>
> That is from "Prime Time" in Mathematics. Open the chapter to read more.

*Cleaned to:* `what are numbers with only two factors called`  
*Next closest categories:* concept_explanation 28%, definition 21%

## Maths calculations

No passage contains the answer to a calculation, so these are solved exactly, with the working the chapter teaches.

### “what is 1/3 + 1/6”

**Detected as:** calculation &mdash; 100.0% confident
**Chapter found:** Fractions (Mathematics, Grade 6)
**Exact answer:** 1/3 + 1/6 = 1/2 *(from math, score 1.00)*

**Reply:**

> 1/3 + 1/6 = 1/2
>
> Use a common denominator: the LCM of 3 and 6 is 6.
> 1/3 = 2/6 and 1/6 = 1/6
> 2/6 + 1/6 = 3/6
> Simplify: 3/6 = 1/2
>
> This is from "Fractions" in Mathematics - open it to practise the method.

*Cleaned to:* `what is 1/3 + 1/6`  

### “is 91 a prime number”

**Detected as:** calculation &mdash; 100.0% confident
**Chapter found:** Prime Time (Mathematics, Grade 6)
**Exact answer:** No, 91 is not prime - it is composite. *(from math, score 1.00)*

**Reply:**

> No, 91 is not prime - it is composite.
>
> Factors of 91: 1, 7, 13, 91.
> For example, 91 = 7 × 13.
>
> This is from "Prime Time" in Mathematics - open it to practise the method.

*Cleaned to:* `is 91 a prime number`  

### “HCF of 12 and 18”

**Detected as:** calculation &mdash; 100.0% confident
**Chapter found:** Prime Time (Mathematics, Grade 6)
**Exact answer:** The highest common factor of 12 and 18 is 6. *(from math, score 1.00)*

**Reply:**

> The highest common factor of 12 and 18 is 6.
>
> Factors of 12: 1, 2, 3, 4, 6, 12
> Factors of 18: 1, 2, 3, 6, 9, 18
> Common factors: 1, 2, 3, 6
>
> This is from "Prime Time" in Mathematics - open it to practise the method.

*Cleaned to:* `HCF of 12 and 18`  

### “area of a rectangle 5 m by 4 m”

**Detected as:** calculation &mdash; 100.0% confident
**Chapter found:** Perimeter and Area (Mathematics, Grade 6)
**Exact answer:** Area = 20 sq m *(from math, score 1.00)*

**Reply:**

> Area = 20 sq m
>
> Area of a rectangle = length x breadth
> = 5 × 4 = 20 sq m
>
> This is from "Perimeter and Area" in Mathematics - open it to practise the method.

*Cleaned to:* `area of a rectangle 5 m by 4 m`  

## Questions in Telugu

Matched against the Telugu chapters with character n-grams, and answered in Telugu.

### “రైతు ఏమి చేస్తాడు?”

**Detected as:** telugu_question &mdash; 27.6% confident
**Chapter found:** అభినందన (Telugu, Grade 6)
**Exact answer:** రైతు పొలంలో శ్రమించి పంటను పండిస్తాడు. *(from telugu, score 0.28)*

**Reply:**

> రైతు పొలంలో శ్రమించి పంటను పండిస్తాడు.
>
> — ‘అభినందన’ పాఠం నుండి.

*Cleaned to:* `రైతు ఏమి చేస్తాడు?`  

### “నిజమైన స్నేహం అంటే ఏమిటి?”

**Detected as:** telugu_question &mdash; 45.2% confident
**Chapter found:** స్నేహబంధం (Telugu, Grade 6)
**Exact answer:** నిజమైన స్నేహం అంటే కష్టసమయంలో తోడుగా నిలబడటం, నమ్మకం ఉంచడం. *(from telugu, score 0.45)*

**Reply:**

> నిజమైన స్నేహం అంటే కష్టసమయంలో తోడుగా నిలబడటం, నమ్మకం ఉంచడం.
>
> — ‘స్నేహబంధం’ పాఠం నుండి.

*Cleaned to:* `నిజమైన స్నేహం అంటే ఏమిటి?`  

## Questions about the catalogue

Answered from the content bank directly; there is nothing to search for, because the student is asking what exists.

### “list the chapters”

**Detected as:** browse_content &mdash; 99.1% confident
**Chapter found:** none

**Reply:**

> Here is what you can study in Grade 6:
> English: A Bottle of Dew, The Unlikely Best Friends, The Raven and the Fox, Rama to the Rescue, A Friend’s Prayer, The Chair, Neem Baba, What a Bird Thought, Spices that Heal Us, Change of Heart, The Winner, Yoga—A Way of Life, Hamara Bharat—Incredible India!, The Kites, Ila Sachani: Embroidering Dreams with her Feet, National War Memorial
> Mathematics: Patterns in Mathematics, Lines and Angles, Number Play, Data Handling and Presentation, Prime Time, Perimeter and Area, Fractions, Playing with Constructions, Symmetry, The Other Side of Zero
> Science: The Wonderful World of Science, Diversity in the Living World, Mindful Eating: A Path to a Healthy Body, Exploring Magnets, Measurement of Length and Motion, Materials Around Us, Temperature and its Measurement, A Journey through States of Water, Methods of Separation in Everyday Life, Living Creatures: Exploring their Characteristics, Nature’s Treasures, Beyond Earth
> Telugu: అభినందన, స్నేహబంధం
> Ask me about any of these, or say 'give me a quiz' to practise.

*Cleaned to:* `list the chapters`  
*Next closest categories:* out_of_scope 0%, clarification 0%

### “show me the science chapters”

**Detected as:** browse_content &mdash; 94.3% confident
**Chapter found:** none

**Reply:**

> Here is what you can study in Grade 6:
> Science: The Wonderful World of Science, Diversity in the Living World, Mindful Eating: A Path to a Healthy Body, Exploring Magnets, Measurement of Length and Motion, Materials Around Us, Temperature and its Measurement, A Journey through States of Water, Methods of Separation in Everyday Life, Living Creatures: Exploring their Characteristics, Nature’s Treasures, Beyond Earth
> Ask me about any of these, or say 'give me a quiz' to practise.

*Cleaned to:* `show me the science chapters`  
*Next closest categories:* quiz_help 2%, out_of_scope 2%

### “what subjects can I study”

**Detected as:** browse_content &mdash; 94.4% confident
**Chapter found:** none

**Reply:**

> Here is what you can study in Grade 6:
> English: A Bottle of Dew, The Unlikely Best Friends, The Raven and the Fox, Rama to the Rescue, A Friend’s Prayer, The Chair, Neem Baba, What a Bird Thought, Spices that Heal Us, Change of Heart, The Winner, Yoga—A Way of Life, Hamara Bharat—Incredible India!, The Kites, Ila Sachani: Embroidering Dreams with her Feet, National War Memorial
> Mathematics: Patterns in Mathematics, Lines and Angles, Number Play, Data Handling and Presentation, Prime Time, Perimeter and Area, Fractions, Playing with Constructions, Symmetry, The Other Side of Zero
> Science: The Wonderful World of Science, Diversity in the Living World, Mindful Eating: A Path to a Healthy Body, Exploring Magnets, Measurement of Length and Motion, Materials Around Us, Temperature and its Measurement, A Journey through States of Water, Methods of Separation in Everyday Life, Living Creatures: Exploring their Characteristics, Nature’s Treasures, Beyond Earth
> Telugu: అభినందన, స్నేహబంధం
> Ask me about any of these, or say 'give me a quiz' to practise.

*Cleaned to:* `what subjects can i study`  
*Next closest categories:* study_advice 2%, progress_help 2%

## Questions the system should decline

Outside the curriculum, or about data the app does not record.

### “book me a hotel”

**Detected as:** out_of_scope &mdash; 96.6% confident
**Chapter found:** none

**Reply:**

> I can only help with your lessons and quizzes. Try asking me about a chapter, a formula, or your progress.

*Cleaned to:* `book me a hotel`  
*Next closest categories:* quiz_help 1%, study_advice 1%

### “who won the cricket match”

**Detected as:** out_of_scope &mdash; 99.0% confident
**Chapter found:** none

**Reply:**

> I can only help with your lessons and quizzes. Try asking me about a chapter, a formula, or your progress.

*Cleaned to:* `who won the cricket match`  
*Next closest categories:* concept_explanation 0%, progress_help 0%

### “how much time did I spend studying”

**Detected as:** progress_help (below threshold) &mdash; 34.8% confident
**Chapter found:** none

**Reply:**

> I do not track how long you spend studying - the app only records quiz attempts and scores. I can tell you your scores, your XP, or how many quizzes you have completed.

*Cleaned to:* `how much time did i spend studying`  
*Next closest categories:* study_advice 26%, browse_content 14%

## Badly phrased questions

The classifier is unsure, but a relevant chapter is still found and shown with an honest caveat.

### “angle thing confusing help”

**Detected as:** concept_explanation (below threshold) &mdash; 21.9% confident
**Chapter found:** Lines and Angles (Mathematics, Grade 6)

**Reply:**

> I am not certain what you were asking, but this looks relevant:
>
> 📐 Grab your imaginary ruler and protractor! Learn how lines, rays and angles behave, then use diagrams to name and understand them.
>
> That is from "Lines and Angles" in Mathematics. If that is not what you meant, try rephrasing.

*Cleaned to:* `angle thing confusing help`  
*Next closest categories:* greeting 18%, browse_content 15%

### “prime number what mean”

**Detected as:** definition &mdash; 66.3% confident
**Chapter found:** Prime Time (Mathematics, Grade 6)

**Reply:**

> Prime numbers are numbers like 2, 3, 5, 7, 11, … that have only two factors, namely 1 and themselves. Composite numbers are numbers like 4, 6, 8, 9, … that have more than 2 factors, i.e., at least one factor other than 1 and themselves. For example, 8 has the factor 4 and 9 has the factor 3, so 8 and 9 are both composite.
>
> That is from "Prime Time" in Mathematics.

*Cleaned to:* `prime number what mean`  
*Next closest categories:* formula_help 21%, progress_help 5%

### “asdfgh qwerty”

**Detected as:** browse_content (below threshold) &mdash; 21.4% confident
**Chapter found:** none

**Reply:**

> Sorry, I did not follow that one. Try naming the chapter or topic, or ask me to list your chapters.

*Cleaned to:* `asdfgh qwerty`  
*Next closest categories:* out_of_scope 21%, greeting 17%
