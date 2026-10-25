import React, { useEffect, useState } from 'react';
import { api } from '../../services/api';
import { LowMark, SubjectBars, pct } from './charts';
import { SHORT_SUBJECT, ago, when } from './format';

export default function StudentPanel({ teacherId, studentId, passScore, onClose }) {
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let live = true;
    setDetail(null);
    setError('');
    api.teacherStudent(teacherId, studentId)
      .then((d) => { if (live) setDetail(d); })
      .catch((e) => { if (live) setError(e.message); });
    return () => { live = false; };
  }, [teacherId, studentId]);

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const d = detail;
  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-label="Student details"
             onClick={(e) => e.stopPropagation()}>
        <button className="drawer-close" onClick={onClose} aria-label="Close">✕</button>

        {error && <div className="error">{error}</div>}
        {!d && !error && <p className="muted">Loading…</p>}

        {d && (
          <>
            <header className="drawer-head">
              <span className="drawer-avatar">{d.avatar}</span>
              <div>
                <h2>{d.username}{d.demo && <span className="demo-tag">sample</span>}</h2>
                <p>Level {d.level}, {d.xp} XP, {d.badges} {d.badges === 1 ? 'badge' : 'badges'}</p>
                <p>
                  {d.streak > 0 ? `${d.streak}-day streak (best ${d.streak_best}). ` : `Best streak ${d.streak_best} days. `}
                  Last active {ago(d.days_inactive)}.
                </p>
              </div>
            </header>

            {d.flags.length > 0 && (
              <div className="flag-row">
                {d.flags.map((f) => <span key={f.code} className={`flag flag-${f.code}`}>{f.label}</span>)}
              </div>
            )}

            <div className="mini-stats">
              <div><b>{d.chapters_read}</b><span>chapters read</span></div>
              <div><b>{d.quizzes_taken}</b><span>quizzes ({d.quiz_attempts} attempts)</span></div>
              <div><b>{pct(d.average_score)}</b><span>current average</span></div>
              <div><b>{d.chat_questions}</b><span>chatbot questions</span></div>
            </div>

            <section className="drawer-section">
              <h3>By subject</h3>
              <SubjectBars subjects={d.subject_performance} passScore={passScore} single />
            </section>

            <section className="drawer-section">
              <h3>Concepts missed on the latest attempts</h3>
              {d.weak_concepts.length === 0 ? (
                <p className="muted">No concept below 60% on the latest attempts.</p>
              ) : (
                <ul className="t-list">
                  {d.weak_concepts.map((c) => (
                    <li key={`${c.chapter?.id}-${c.concept}`}>
                      <b>{c.concept}</b>
                      <span>{c.chapter?.title}: {c.correct} of {c.answers} right</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="drawer-section">
              <h3>Recent quiz attempts</h3>
              {d.recent_attempts.length === 0 ? (
                <p className="muted">No quizzes yet.</p>
              ) : (
                <ul className="t-list">
                  {d.recent_attempts.map((a, i) => (
                    <li key={`${a.quiz_id}-${i}`} className="attempt-row">
                      <span className="attempt-score">
                        {a.score}%{a.score < passScore && <LowMark label="" />}
                      </span>
                      <span>
                        <b>{a.chapter?.title}</b>
                        <span>{a.chapter?.subject}, {a.correct} of {a.total} right, {when(a.submitted_at)}</span>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="drawer-section">
              <h3>Recent questions to the chatbot</h3>
              {d.recent_questions.length === 0 ? (
                <p className="muted">No questions asked yet.</p>
              ) : (
                <ul className="t-list">
                  {d.recent_questions.map((q, i) => (
                    <li key={i}>
                      <b>“{q.message}”</b>
                      <span>
                        {q.chapter ? q.chapter.title : 'no chapter matched'}
                        {', '}
                        {!q.understood ? 'not answered' : q.answered ? 'exact answer given' : 'pointed to the chapter'}
                        {', '}{when(q.asked_at)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="drawer-section">
              <h3>Chapters read ({d.chapters.length})</h3>
              {d.chapters.length === 0 ? (
                <p className="muted">No chapters marked as read yet.</p>
              ) : (
                <div className="chip-wrap">
                  {d.chapters.map((c) => (
                    <span key={c.id} className="chapter-chip" title={`Read ${when(c.completed_at)}`}>
                      {SHORT_SUBJECT[c.subject] || c.subject} {c.number}: {c.title}
                    </span>
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </aside>
    </div>
  );
}
