import React, { useEffect, useState } from 'react';
import Header from '../components/Header';
import Reward from '../components/Reward';
import { api } from '../services/api';
import { chapterNumber, plain, sentenceCase } from '../utils/text';

// Section headings in the chapter content start with an emoji.
const HEADING = /^\p{Extended_Pictographic}/u;

// Chapters taken from the textbook PDFs arrive as very long paragraphs.
// Break them every 60 words or so, at the end of a sentence.
function paragraphs(text) {
  if (text.split(/\s+/).length <= 90) return [text];
  const out = [];
  let current = [];
  let words = 0;
  for (const sentence of text.split(/(?<=[.!?]["”’]?)\s+(?=[A-Z“"‘])/)) {
    current.push(sentence);
    words += sentence.split(/\s+/).length;
    if (words >= 60) {
      out.push(current.join(' '));
      current = [];
      words = 0;
    }
  }
  if (current.length) out.push(current.join(' '));
  return out;
}

export default function LessonView({ lesson, user, streak, game, completedLessons = [], onBack, onQuiz, onCompleted }) {
  const [quiz, setQuiz] = useState(null);
  const [marking, setMarking] = useState(false);
  const [reward, setReward] = useState(null);
  const [error, setError] = useState('');

  const isRead = lesson ? completedLessons.includes(lesson.id) || reward !== null : false;
  const mark = lesson ? game?.quiz_marks?.[lesson.id] : null;

  async function markAsRead() {
    if (marking || !lesson) return;
    setMarking(true);
    setError('');
    try {
      const result = await api.completeLesson(lesson.id, user.id);
      setReward(result);
      if (onCompleted) onCompleted();
    } catch (err) {
      setError('Could not save. Check that the server is running.');
    } finally {
      setMarking(false);
    }
  }

  useEffect(() => {
    if (!lesson) return;
    window.scrollTo(0, 0);
    api.quiz(`q-${lesson.id}`).then(setQuiz).catch(() => setQuiz(null));
  }, [lesson]);

  if (!lesson) {
    return (
      <main className="container">
        <button className="back" onClick={onBack}>Back to chapters</button>
      </main>
    );
  }

  // Bullets in the PDF text come through as control characters; each starts a
  // new line.
  const lines = String(lesson.content || '').replace(/[\u0080-\u009f]/g, '\n')
    .split('\n').map(x => x.trim()).filter(Boolean);
  const summary = plain(lesson.summary);
  // For chapters from the PDFs the summary is a passage from the chapter itself.
  const showSummary = summary && !lines.join(' ').includes(summary.slice(0, 40));

  return (
    <>
      <Header user={user} streak={streak} />

      <main className="container">
        <button className="back" onClick={onBack}>← All chapters</button>

        <article className="reading">
          <span className="subject">{lesson.subject}, chapter {chapterNumber(lesson.id)}</span>
          <h1>{lesson.title}</h1>
          {showSummary && <p className="summary">{summary}</p>}

          <div className="reading-text">
            {lines.map((line, i) => (HEADING.test(line) && line.length < 80
              ? <h3 key={i}>{sentenceCase(line)}</h3>
              : paragraphs(line).map((text, j) => <p key={`${i}-${j}`}>{text}</p>)))}
          </div>

          <section className="chapter-end">
            {isRead ? (
              <>
                <div className="done-line"><span className="tick big">✓</span><h2>You have read this chapter</h2></div>
                {reward && !reward.already_completed
                  ? <Reward result={reward} />
                  : <p>Take the quiz below to check what you remember.</p>}
              </>
            ) : (
              <>
                <h2>Finished reading?</h2>
                <p>Mark the chapter as read to get 20 XP and keep your streak going.</p>
                <button className="btn" onClick={markAsRead} disabled={marking}>
                  {marking ? 'Saving…' : 'Mark as read'}
                </button>
                {error && <div className="error">{error}</div>}
              </>
            )}
          </section>

          {quiz && (
            <section className="chapter-end">
              <h2>Chapter quiz</h2>
              <p>
                {quiz.questions.length} questions. You get 10 XP for each correct answer.
                {mark && <> Your last score was <span className="quiz-mark">{mark.latest}%</span>.</>}
              </p>
              <button className={isRead ? 'btn' : 'btn-quiet'} onClick={() => onQuiz(quiz)}>
                {mark ? 'Take the quiz again' : 'Take the quiz'}
              </button>
            </section>
          )}
        </article>
      </main>
    </>
  );
}
