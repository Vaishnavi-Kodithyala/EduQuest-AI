import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../services/api';
import { Meter, ScoreTrend, SubjectBars, pct } from '../components/teacher/charts';
import StudentPanel from '../components/teacher/StudentPanel';
import { SHORT_SUBJECT, ago, clock, when } from '../components/teacher/format';
import '../styles/teacher.css';

/*
 * Week 9 - Teacher dashboard.
 *
 * One request (GET /api/teacher/class) returns every figure on the page; the
 * numbers are worked out by MongoDB aggregation on the server
 * (backend/teacher/analytics.py). Clicking a student loads their detail.
 */

function Delta({ now, before, unit = '', higherIsBetter = true }) {
  if (now === null || now === undefined || before === null || before === undefined) {
    return <span className="tile-delta">no data for last week</span>;
  }
  const change = now - before;
  if (change === 0) return <span className="tile-delta">same as last week</span>;
  const good = change > 0 === higherIsBetter;
  return (
    <span className={`tile-delta ${good ? 'up' : 'down'}`}>
      {change > 0 ? '▲' : '▼'} {Math.abs(change)}{unit} vs last week
    </span>
  );
}

function Tile({ label, value, children, onClick }) {
  const Tag = onClick ? 'button' : 'div';
  return (
    <Tag className={`card tile ${onClick ? 'tile-button' : ''}`} onClick={onClick}>
      <span className="tile-label">{label}</span>
      <b className="tile-value">{value}</b>
      {children}
    </Tag>
  );
}

function SortHeader({ label, k, sort, setSort, num = false, title }) {
  const active = sort.key === k;
  return (
    <th className={num ? 'num' : ''} title={title}
        aria-sort={active ? (sort.dir === 1 ? 'ascending' : 'descending') : 'none'}>
      <button className={`sort-btn ${active ? 'active' : ''}`}
              onClick={() => setSort({ key: k, dir: active ? -sort.dir : (num ? -1 : 1) })}>
        {label}{active ? (sort.dir === 1 ? ' ↑' : ' ↓') : ''}
      </button>
    </th>
  );
}

const STUDENT_VALUE = {
  username: (r) => r.username.toLowerCase(),
  xp: (r) => r.xp,
  streak: (r) => r.streak,
  chapters_read: (r) => r.chapters_read,
  quizzes_taken: (r) => r.quizzes_taken,
  average_score: (r) => r.average_score,
  last_active: (r) => (r.days_inactive === null ? null : -r.days_inactive),
};

function sortRows(rows, sort, valueOf) {
  const get = valueOf[sort.key] || ((r) => r[sort.key]);
  return rows.slice().sort((a, b) => {
    const va = get(a);
    const vb = get(b);
    // Empty values (no quizzes yet) always go last.
    if (va === null || va === undefined) return vb === null || vb === undefined ? 0 : 1;
    if (vb === null || vb === undefined) return -1;
    return va < vb ? -sort.dir : va > vb ? sort.dir : 0;
  });
}

function ScoreCell({ value, pass }) {
  if (value === null || value === undefined) return <td className="num muted">—</td>;
  return (
    <td className={`num ${value < pass ? 'score-low' : ''}`}>
      {value < pass && <span className="low-icon" aria-hidden="true">▼</span>}
      {value}%{value < pass && <span className="sr-only"> (below the pass mark)</span>}
    </td>
  );
}

export default function TeacherDashboard({ user, onLogout }) {
  const [report, setReport] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [subject, setSubject] = useState('All');
  const [studentFilter, setStudentFilter] = useState('all');
  const [studentSort, setStudentSort] = useState({ key: 'username', dir: 1 });
  const [chapterSort, setChapterSort] = useState({ key: 'average_score', dir: 1 });
  const [allChapters, setAllChapters] = useState(false);
  const [openStudent, setOpenStudent] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError('');
    api.teacherClass(user.id)
      .then(setReport)
      .catch((e) => setError(e.message || 'Could not load the class. Check that the server is running.'))
      .finally(() => setLoading(false));
  }, [user.id]);

  useEffect(() => { load(); }, [load]);

  const pass = report?.pass_score ?? 60;
  const subjects = report?.subjects.map((s) => s.subject) ?? [];

  const students = useMemo(() => {
    if (!report) return [];
    const rows = studentFilter === 'attention' ? report.students.filter((r) => r.flags.length) : report.students;
    return sortRows(rows, studentSort, STUDENT_VALUE);
  }, [report, studentFilter, studentSort]);

  const chapters = useMemo(() => {
    if (!report) return [];
    const rows = report.chapters.filter((c) => subject === 'All' || c.subject === subject);
    return sortRows(rows, chapterSort, { title: (c) => c.title.toLowerCase() });
  }, [report, subject, chapterSort]);

  const concepts = useMemo(
    () => (report?.weak_concepts ?? []).filter((c) => subject === 'All' || c.chapter?.subject === subject),
    [report, subject]
  );

  const closeStudent = useCallback(() => setOpenStudent(null), []);
  const showAttention = () => {
    setStudentFilter('attention');
    document.getElementById('students')?.scrollIntoView({ behavior: 'smooth' });
  };

  const o = report?.overview;
  const t = report?.trend;
  const visibleChapters = allChapters ? chapters : chapters.slice(0, 8);

  return (
    <div className="teacher">
      <header className="topbar">
        <div className="topbar-inner">
          <button className="brand" onClick={() => window.scrollTo(0, 0)}>EduQuest</button>
          <span className="role-pill">Teacher</span>
          <nav className="topbar-nav" aria-label="Sections">
            <a href="#overview">Overview</a>
            <a href="#struggling">Weak spots</a>
            <a href="#chatbot">Questions</a>
            <a href="#students">Students</a>
          </nav>
          <div className="topbar-right">
            <span className="teacher-name">{user.username}</span>
            <button className="topbar-logout" onClick={onLogout}>Log out</button>
          </div>
        </div>
      </header>

      <main className={`container ${loading && report ? 'refreshing' : ''}`}>
        <div className="page-title teacher-head" id="overview">
          <div>
            <h1>Grade {report?.grade ?? user.grade} class</h1>
            {report && (
              <p>
                {o.students} {o.students === 1 ? 'student' : 'students'}. Scores use each student's latest attempt at
                each quiz. Updated at {clock(report.generated_at)}.
              </p>
            )}
          </div>
          <button className="btn-quiet" onClick={load} disabled={loading}>{loading ? 'Refreshing…' : 'Refresh'}</button>
        </div>

        {error && <div className="error">{error}</div>}
        {!report && !error && <p className="muted">Loading the class…</p>}

        {report && o.demo_students > 0 && (
          <p className="demo-note">
            Includes {o.demo_students} sample students from the demo class. Remove them with
            <code>python -m backend.seed_demo_class --remove</code>
          </p>
        )}

        {report && o.students === 0 && (
          <section className="sheet">
            <h2>No students yet</h2>
            <p>Students appear here once they sign up for Grade {report.grade}. To try the dashboard with a sample class, run
              <code>python -m backend.seed_demo_class</code></p>
          </section>
        )}

        {report && o.students > 0 && (
          <>
            <section className="tiles">
              <Tile label="Students" value={o.students}>
                <span className="tile-delta">{o.active_this_week} active in the last 7 days</span>
              </Tile>
              <Tile label="Need attention" value={o.needs_attention} onClick={o.needs_attention ? showAttention : undefined}>
                <span className="tile-delta">{o.needs_attention ? 'inactive, not started or below 60%' : 'everyone is on track'}</span>
              </Tile>
              <Tile label="Quiz average, last 7 days" value={pct(t.this_week.average_score)}>
                <Delta now={t.this_week.average_score} before={t.last_week.average_score} unit=" pts" />
              </Tile>
              <Tile label="Quizzes taken, last 7 days" value={t.this_week.attempts}>
                <Delta now={t.this_week.attempts} before={t.last_week.attempts} />
              </Tile>
              <Tile label="Chapters read, last 7 days" value={o.chapters_read_this_week}>
                <span className="tile-delta">{o.chapters_read} in total</span>
              </Tile>
              <Tile label="Questions to the chatbot" value={report.chat.questions}>
                <span className="tile-delta">{report.chat.questions ? `${report.chat.answered_pct}% got an exact answer` : 'none yet'}</span>
              </Tile>
            </section>

            <section className="teacher-grid">
              <div className="card">
                <div className="card-head">
                  <h2>Quiz scores, last {t.days} days</h2>
                  <span className="card-sub">Average score of the quizzes taken each day. The grey line is the {pass}% pass mark.</span>
                </div>
                <ScoreTrend points={t.points} passScore={pass} />
              </div>
              <div className="card">
                <div className="card-head">
                  <h2>By subject</h2>
                  <span className="card-sub">Current quiz average. The grey line is the {pass}% pass mark.</span>
                </div>
                <SubjectBars subjects={report.subjects} passScore={pass} />
              </div>
            </section>

            <div className="section-title" id="struggling">
              <h2>What to go over again</h2>
            </div>
            <div className="tabs teacher-filter" role="tablist" aria-label="Subject">
              {[...subjects, 'All'].map((s) => (
                <button key={s} role="tab" aria-selected={subject === s} className={subject === s ? 'active' : ''} onClick={() => setSubject(s)}>
                  {s === 'All' ? 'All subjects' : s}
                </button>
              ))}
            </div>

            <section className="teacher-grid">
              <div className="card">
                <div className="card-head">
                  <h2>Weak concepts</h2>
                  <span className="card-sub">Concepts where fewer than 60% of answers were right, from at least 5 answers.</span>
                </div>
                {concepts.length === 0 ? (
                  <p className="muted">No weak concepts{subject !== 'All' ? ` in ${subject}` : ''} - the class answers every concept well.</p>
                ) : (
                  <div className="table-scroll">
                    <table className="data-table">
                      <thead><tr><th>Concept</th><th>Answered right</th><th>Struggling</th></tr></thead>
                      <tbody>
                        {concepts.map((c) => (
                          <tr key={`${c.chapter?.id}-${c.concept}`}>
                            <td>
                              <b>{c.concept}</b>
                              <span className="cell-sub">{c.chapter?.subject}, chapter {c.chapter?.number}: {c.chapter?.title}</span>
                            </td>
                            <td>
                              <Meter value={c.accuracy} />
                              <span className="cell-sub">{c.correct} of {c.answers} answers</span>
                            </td>
                            <td>
                              <b>{c.struggling} of {c.students} students</b>
                              <span className="cell-sub">{c.struggling_names.join(', ') || '—'}</span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              <div className="card">
                <div className="card-head">
                  <h2>Chapters</h2>
                  <span className="card-sub">Lowest quiz average first. Click a column heading to sort.</span>
                </div>
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <SortHeader label="Chapter" k="title" sort={chapterSort} setSort={setChapterSort} />
                        <SortHeader label="Read by" k="readers" sort={chapterSort} setSort={setChapterSort} num />
                        <SortHeader label="Quiz avg" k="average_score" sort={chapterSort} setSort={setChapterSort} num />
                        <SortHeader label="Asked" k="chat_questions" sort={chapterSort} setSort={setChapterSort} num title="Questions asked to the chatbot about this chapter" />
                      </tr>
                    </thead>
                    <tbody>
                      {visibleChapters.map((c) => (
                        <tr key={c.id}>
                          <td>
                            <b>{c.title}</b>
                            <span className="cell-sub">{c.subject}, chapter {c.number}{c.quiz_takers ? `. ${c.quiz_takers} took the quiz` : ''}</span>
                          </td>
                          <td className="num">{c.readers}<span className="of"> / {o.students}</span></td>
                          <ScoreCell value={c.average_score} pass={pass} />
                          <td className="num">{c.chat_questions}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {chapters.length > 8 && (
                  <button className="link" onClick={() => setAllChapters((v) => !v)}>
                    {allChapters ? 'Show fewer' : `Show all ${chapters.length} chapters`}
                  </button>
                )}
              </div>
            </section>

            <div className="section-title" id="chatbot">
              <h2>What students ask</h2>
              <p>
                {report.chat.questions} questions from {report.chat.students} students
                {report.chat.questions > 0 && `, ${report.chat.understood_pct}% matched to a chapter`}
              </p>
            </div>
            <section className="teacher-grid">
              <div className="card">
                <div className="card-head"><h2>Chapters asked about most</h2></div>
                {report.chat.top_chapters.length === 0 ? <p className="muted">No questions yet.</p> : (
                  <ol className="rank-list">
                    {report.chat.top_chapters.map((c) => (
                      <li key={c.id}>
                        <span><b>{c.title}</b><span className="cell-sub">{c.subject}, asked by {c.students} {c.students === 1 ? 'student' : 'students'}</span></span>
                        <span className="rank-count">{c.questions}</span>
                      </li>
                    ))}
                  </ol>
                )}
              </div>
              <div className="card">
                <div className="card-head">
                  <h2>Questions it could not answer</h2>
                  <span className="card-sub">Worth picking up in class</span>
                </div>
                {report.chat.unanswered.length === 0 ? <p className="muted">The chatbot matched every question to a chapter.</p> : (
                  <ul className="t-list">
                    {report.chat.unanswered.map((q) => (
                      <li key={q.message}>
                        <b>“{q.message}”</b>
                        <span>
                          {q.times > 1 ? `${q.times} times, by ${q.students.join(', ')}` : q.students[0]}
                          {', last on '}{when(q.last_asked)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </section>

            <div className="section-title" id="students">
              <h2>Students</h2>
            </div>
            <div className="tabs" role="tablist" aria-label="Which students">
              <button role="tab" aria-selected={studentFilter === 'all'} className={studentFilter === 'all' ? 'active' : ''} onClick={() => setStudentFilter('all')}>
                Everyone ({report.students.length})
              </button>
              <button role="tab" aria-selected={studentFilter === 'attention'} className={studentFilter === 'attention' ? 'active' : ''} onClick={() => setStudentFilter('attention')}>
                Need attention ({o.needs_attention})
              </button>
            </div>
            <section className="card">
              <div className="table-scroll">
                <table className="data-table students-table">
                  <thead>
                    <tr>
                      <SortHeader label="Student" k="username" sort={studentSort} setSort={setStudentSort} />
                      <SortHeader label="XP" k="xp" sort={studentSort} setSort={setStudentSort} num />
                      <SortHeader label="Streak" k="streak" sort={studentSort} setSort={setStudentSort} num />
                      <SortHeader label="Read" k="chapters_read" sort={studentSort} setSort={setStudentSort} num title="Chapters marked as read" />
                      <SortHeader label="Quizzes" k="quizzes_taken" sort={studentSort} setSort={setStudentSort} num />
                      {subjects.map((s) => <th key={s} className="num" title={`${s}: current quiz average`}>{SHORT_SUBJECT[s] || s}</th>)}
                      <SortHeader label="Average" k="average_score" sort={studentSort} setSort={setStudentSort} num />
                      <SortHeader label="Last active" k="last_active" sort={studentSort} setSort={setStudentSort} />
                      <th>Flags</th>
                    </tr>
                  </thead>
                  <tbody>
                    {students.map((r) => (
                      <tr key={r.user_id} className="clickable" tabIndex={0}
                          onClick={() => setOpenStudent(r.user_id)}
                          onKeyDown={(e) => { if (e.key === 'Enter') setOpenStudent(r.user_id); }}>
                        <td>
                          <span className="student-cell">
                            <span className="student-avatar">{r.avatar}</span>
                            <span><b>{r.username}</b>{r.demo && <span className="demo-tag">sample</span>}
                              <span className="cell-sub">Level {r.level}</span></span>
                          </span>
                        </td>
                        <td className="num">{r.xp}</td>
                        <td className="num">{r.streak}</td>
                        <td className="num">{r.chapters_read}</td>
                        <td className="num">{r.quizzes_taken}</td>
                        {subjects.map((s) => <ScoreCell key={s} value={r.subjects[s]?.average ?? null} pass={pass} />)}
                        <ScoreCell value={r.average_score} pass={pass} />
                        <td>{ago(r.days_inactive)}</td>
                        <td>
                          {r.flags.length === 0 ? <span className="muted">—</span> : (
                            <span className="flag-row">
                              {r.flags.map((f) => <span key={f.code} className={`flag flag-${f.code}`}>{f.label}</span>)}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="table-note">
                Subject columns and Average use each student's latest attempt at each quiz.
                <span className="score-low-key"><span aria-hidden="true">▼</span> 48%</span> is below the {pass}% pass mark. Click a student for details.
              </p>
            </section>
          </>
        )}
      </main>

      {openStudent && (
        <StudentPanel teacherId={user.id} studentId={openStudent} passScore={pass} onClose={closeStudent} />
      )}
    </div>
  );
}

