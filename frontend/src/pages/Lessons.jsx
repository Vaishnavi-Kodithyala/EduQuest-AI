import React, { useEffect, useState } from 'react';
import Header from '../components/Header';
import { api } from '../services/api';
import { SUBJECTS, chapterNumber, plain } from '../utils/text';

const LANGUAGE_NAMES = { en: 'English', te: 'Telugu', hi: 'Hindi' };

function ChapterRow({ lesson, read, mark, onOpenLesson, onOpenQuiz }) {
  return (
    <li>
      <span className="chapter-no" aria-hidden="true">{chapterNumber(lesson.id)}</span>
      <div className="chapter-body">
        <h3>
          <button onClick={() => onOpenLesson(lesson)}>
            <span className="sr-only">Chapter {chapterNumber(lesson.id)}: </span>{lesson.title}
          </button>
        </h3>
        <p>{plain(lesson.summary)}</p>
      </div>
      <div className="chapter-side">
        {read && <span className="tick">✓ read</span>}
        {mark ? (
          <button className="mark-btn" onClick={() => onOpenQuiz(lesson.id)} title="Take the quiz again">
            <span className={`quiz-mark ${mark.latest < 60 ? 'low' : ''}`}>quiz {mark.latest}%</span>
          </button>
        ) : (
          <button className="btn-quiet" onClick={() => onOpenQuiz(lesson.id)}>Take the quiz</button>
        )}
      </div>
    </li>
  );
}

export default function Lessons({ user, streak, game, completedLessons = [], onOpenLesson, onOpenQuiz }) {
  const [lessons, setLessons] = useState(null);
  const [subject, setSubject] = useState('');
  const [usingFallback, setUsingFallback] = useState(false);

  useEffect(() => {
    // Only the latest request may update the page. Without this, clicking
    // Science while the slower "All subjects" list is still loading let that
    // list arrive last and overwrite the Science chapters.
    let current = true;
    const params = { grade: user.grade, subject };

    // If nothing exists in the student's language, fall back to English rather
    // than showing an empty page.
    api.lessons({ ...params, language: user.language })
      .then(data => {
        if (data.length === 0 && user.language !== 'en') {
          return api.lessons({ ...params, language: 'en' })
            .then(englishData => ({ list: englishData, fallback: englishData.length > 0 }));
        }
        return { list: data, fallback: false };
      })
      .then(({ list, fallback }) => {
        if (!current) return;
        setUsingFallback(fallback);
        setLessons(list);
      })
      .catch(() => { if (current) { setUsingFallback(false); setLessons([]); } });

    return () => { current = false; };
  }, [user.grade, user.language, subject]);

  const marks = game?.quiz_marks || {};
  const readSet = new Set(completedLessons);
  const tabs = [...SUBJECTS, ''];   // "All subjects" last
  const groups = subject ? [subject] : SUBJECTS;
  const row = lesson => (
    <ChapterRow key={lesson.id} lesson={lesson} read={readSet.has(lesson.id)} mark={marks[lesson.id]}
                onOpenLesson={onOpenLesson} onOpenQuiz={onOpenQuiz} />
  );

  return (
    <>
      <Header user={user} streak={streak} />

      <main className="container">
        <div className="page-title">
          <h1>Chapters</h1>
          <p>Every Grade {user.grade} chapter from your textbooks. Read a chapter, then take its quiz to check what you remember.</p>
        </div>

        <div className="tabs" role="tablist" aria-label="Subject">
          {tabs.map(s => (
            <button key={s || 'all'} role="tab" aria-selected={subject === s}
                    className={subject === s ? 'active' : ''} onClick={() => setSubject(s)}>
              {s || 'All subjects'}
            </button>
          ))}
        </div>

        {usingFallback && (
          <p className="notice">
            These chapters are not available in {LANGUAGE_NAMES[user.language] || user.language} yet, so they are shown in English.
          </p>
        )}

        {lessons === null ? (
          <p className="empty">Loading chapters…</p>
        ) : lessons.length === 0 ? (
          <p className="empty">No chapters found. Check that the server is running and the content is loaded (python -m backend.seed).</p>
        ) : (
          groups.map(g => {
            const list = lessons.filter(l => l.subject === g);
            if (list.length === 0) return null;
            const done = list.filter(l => readSet.has(l.id)).length;
            return (
              <section className="subject-group" key={g}>
                {!subject && (
                  <div className="section-title" style={{ marginTop: 0, marginBottom: 10 }}>
                    <h2>{g}</h2>
                    <p>{done} of {list.length} read</p>
                  </div>
                )}
                {subject && <p className="chapter-count">{done} of {list.length} chapters read</p>}
                <ul className="chapters">{list.map(row)}</ul>
              </section>
            );
          })
        )}
      </main>
    </>
  );
}
