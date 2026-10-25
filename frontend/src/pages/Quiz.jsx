import React, { useState } from 'react';
import Header from '../components/Header';
import Reward from '../components/Reward';
import { api } from '../services/api';

// What a teacher would write next to the mark.
function remark(score) {
  if (score === 100) return 'Excellent!';
  if (score >= 80) return 'Very good';
  if (score >= 60) return 'Good';
  if (score >= 40) return 'Keep trying';
  return 'Read it again';
}

export default function Quiz({ quiz, user, streak, onBack, onSubmitted }) {
  const [answers, setAnswers] = useState({});
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (!quiz) {
    return (
      <main className="container">
        <button className="back" onClick={onBack}>Back to chapters</button>
      </main>
    );
  }

  const total = quiz.questions.length;
  const answered = Object.keys(answers).length;
  const title = quiz.title.replace(/\s+[—-]\s+Chapter Quiz$/i, '');

  async function submit(e) {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      // One answer per question, in order; -1 marks a question left blank.
      const r = await api.submitQuiz({
        user_id: user.id,
        quiz_id: quiz.id,
        answers: quiz.questions.map((_, i) => (i in answers ? answers[i] : -1))
      });
      setResult(r);
      window.scrollTo(0, 0);
      if (onSubmitted) onSubmitted();
    } catch (err) {
      setError(err.message === 'Failed to fetch' ? 'Could not send your answers. Check that the server is running.' : err.message);
    } finally {
      setSubmitting(false);
    }
  }

  function retake() {
    setAnswers({});
    setResult(null);
    setError('');
    window.scrollTo(0, 0);
  }

  return (
    <>
      <Header user={user} streak={streak} />

      <main className="container quiz-sheet">
        <button className="back" onClick={onBack}>← All chapters</button>
        <div className="page-title">
          <h1>Quiz: {title}</h1>
          {!result && <p>{total} questions. Choose one answer for each, then check your answers.</p>}
        </div>

        {result ? (
          <>
            <section className="sheet result">
              <div className="score-mark" aria-label={`${result.correct} out of ${result.total}`}>
                <span>{result.correct}/{result.total}<small>{result.score}%</small></span>
              </div>
              <div>
                <span className="remark">{remark(result.score)}</span>
                <p className="muted result-line">
                  You answered {result.correct} of {result.total} questions correctly.
                  {result.score < 60 && ' You need 60% to pass this quiz.'}
                </p>
                <Reward result={result.gamification} />
                <div className="actions result-actions">
                  {result.score < 100 && <button className="btn" onClick={retake}>Try again</button>}
                  <button className={result.score < 100 ? 'btn-quiet' : 'btn'} onClick={onBack}>Back to chapters</button>
                </div>
              </div>
            </section>

            {result.review && (
              <section className="sheet review">
                <h2>Your answers</h2>
                <ol className="questions">
                  {result.review.map((item, i) => (
                    <li className="review-item" key={i}>
                      <span className="review-tick" aria-hidden="true">
                        {item.is_correct ? '✓' : item.chosen < 0 ? '–' : '✗'}
                      </span>
                      <div>
                        <h3><span className="q-no">{i + 1}.</span>{item.question}</h3>
                        <span className="sr-only">{item.is_correct ? 'Correct.' : item.chosen < 0 ? 'Not answered.' : 'Wrong.'}</span>
                        <ul className="review-options">
                          {item.options.map((option, j) => {
                            const isAnswer = j === item.correct;
                            const isWrong = j === item.chosen && !item.is_correct;
                            return (
                              <li key={j} className={isAnswer ? 'is-answer' : isWrong ? 'is-wrong' : ''}>
                                {option}
                                {isAnswer && <small>correct answer</small>}
                                {isWrong && <small>your answer</small>}
                              </li>
                            );
                          })}
                        </ul>
                        {item.explanation && <p className="review-explain">{item.explanation}</p>}
                        {item.concept && <p className="review-topic">Topic: {item.concept}</p>}
                      </div>
                    </li>
                  ))}
                </ol>
              </section>
            )}
          </>
        ) : (
          <form className="sheet" onSubmit={submit}>
            <ol className="questions">
              {quiz.questions.map((q, i) => (
                <li className="question" key={i}>
                  <fieldset>
                    <legend><span className="q-no">{i + 1}.</span>{q.text}</legend>
                    {q.options.map((o, j) => (
                      <label className={`option ${answers[i] === j ? 'selected' : ''}`} key={j}>
                        <input type="radio" name={`q${i}`} checked={answers[i] === j}
                               onChange={() => setAnswers({ ...answers, [i]: j })} required />
                        {o}
                      </label>
                    ))}
                  </fieldset>
                </li>
              ))}
            </ol>
            {error && <div className="error">{error}</div>}
            <div className="quiz-foot">
              <span className="quiz-count">{answered} of {total} answered</span>
              <button className="btn" disabled={submitting}>{submitting ? 'Checking…' : 'Check my answers'}</button>
            </div>
          </form>
        )}
      </main>
    </>
  );
}
