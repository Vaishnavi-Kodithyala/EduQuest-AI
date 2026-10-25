import React, { useEffect, useState } from 'react';
import Header from '../components/Header';
import LevelBar from '../components/LevelBar';
import Stamp from '../components/Stamp';
import { api } from '../services/api';
import { chapterNumber, displayName } from '../utils/text';

const DAY = new Intl.DateTimeFormat('en-IN', { weekday: 'short', timeZone: 'UTC' });

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

// The first recommendation, with the button that does what it suggests.
function ContinueCard({ rec, onOpenLesson, onOpenQuiz, onLessons }) {
  if (!rec) {
    return (
      <section className="sheet ruled continue">
        <h2>Pick a chapter to start</h2>
        <p className="why">Read a chapter, then take its quiz to earn XP.</p>
        <button className="btn" onClick={onLessons}>See all chapters</button>
      </section>
    );
  }
  const quizFirst = rec.kind === 'take_quiz' || rec.kind === 'retry';
  return (
    <section className="sheet ruled continue">
      <span className="where">{rec.subject}, chapter {chapterNumber(rec.lesson_id)}</span>
      <h2>{rec.title}</h2>
      <p className="why">{rec.reason}</p>
      <div className="actions">
        {quizFirst ? (
          <>
            <button className="btn" onClick={() => onOpenQuiz(rec.lesson_id)}>
              {rec.kind === 'retry' ? 'Try the quiz again' : 'Take the quiz'}
            </button>
            <button className="btn-quiet" onClick={() => onOpenLesson(rec)}>Open the chapter</button>
          </>
        ) : (
          <button className="btn" onClick={() => onOpenLesson(rec)}>Open the chapter</button>
        )}
      </div>
    </section>
  );
}

export default function Dashboard({ user, game, level, streak, onLessons, onLeaderboard, onOpenLesson, onOpenQuiz }) {
  const [recs, setRecs] = useState(null);

  useEffect(() => {
    api.recommendations(user.id, { grade: user.grade, limit: 5 })
      .then(r => setRecs(r.recommendations || []))
      .catch(() => setRecs([]));
  }, [user.id, user.grade, game?.xp]);

  const badges = game?.badges || [];
  const earned = badges.filter(b => b.earned).length;
  const rewards = game?.rewards || [];
  const nextReward = game?.next_reward;
  const recent = game?.recent_xp || [];
  const week = game?.week || [];
  const report = game?.subjects || [];
  const read = game?.stats?.lessons_completed ?? 0;
  const total = report.reduce((n, s) => n + s.chapters, 0) || 40;
  const best = game?.streak?.best ?? 0;

  return (
    <>
      <Header user={user} streak={streak} />

      <main className="container">
        <div className="home-head">
          <div>
            <h1>{greeting()}, {displayName(user.username)}.</h1>
            <p>You have read {read} of {total} chapters in Grade {user.grade}.</p>
          </div>
          <LevelBar {...level} />
        </div>

        <div className="home-grid">
          <div>
            <ContinueCard rec={recs?.[0]} onOpenLesson={onOpenLesson} onOpenQuiz={onOpenQuiz} onLessons={onLessons} />

            {recs && recs.length > 1 && (
              <>
                <div className="section-title"><h2>Up next</h2></div>
                <ul className="next-list">
                  {recs.slice(1).map(r => (
                    <li key={r.lesson_id}>
                      <button onClick={() => onOpenLesson(r)}>
                        <b>{r.title}</b>
                        <span>{r.reason}</span>
                        <em>{r.subject}</em>
                      </button>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>

          <div className="home-side">
            <section className="sheet">
              <h2>This week</h2>
              <table className="register">
                <thead>
                  <tr>{week.map(d => <th key={d.date} scope="col">{DAY.format(new Date(`${d.date}T00:00:00Z`))}</th>)}</tr>
                </thead>
                <tbody>
                  <tr>
                    {week.map((d, i) => (
                      <td key={d.date} className={`${i === week.length - 1 ? 'today' : ''} ${d.active ? '' : 'absent'}`}>
                        {d.active ? 'P' : ''}
                        <span className="sr-only">{d.active ? 'studied' : 'no study'}</span>
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
              <p className="streak-line">
                {streak > 0
                  ? <><b>{streak} {streak === 1 ? 'day' : 'days'} in a row.</b> Your best is {best}.</>
                  : 'Read a chapter or take a quiz today to start a streak.'}
              </p>
            </section>

            <section className="sheet">
              <h2>Progress report</h2>
              <table className="report">
                <thead>
                  <tr><th scope="col">Subject</th><th scope="col" className="num">Read</th><th scope="col" className="num">Quiz average</th></tr>
                </thead>
                <tbody>
                  {report.map(s => (
                    <tr key={s.subject}>
                      <td>{s.subject}</td>
                      <td className="num">{s.read} of {s.chapters}</td>
                      <td className="num">{s.average === null ? <span className="muted">no quiz yet</span> : <span className="mark">{s.average}%</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          </div>
        </div>

        <div className="section-title">
          <h2>Badges</h2>
          <p>{earned} of {badges.length} earned</p>
        </div>
        <section className="sheet">
          <div className="stamps">
            {badges.map(b => <Stamp key={b.id} badge={b} />)}
          </div>
        </section>

        <div className="two-col">
          <section className="sheet">
            <h2>Avatars you can unlock</h2>
            <div className="unlock-row">
              {rewards.map(r => (
                <div className={`unlock ${r.unlocked ? '' : 'closed'}`} key={r.avatar} title={r.name}>
                  <span className="avatar">{r.unlocked ? r.avatar : `L${r.level}`}</span>
                  <span>{r.unlocked ? r.name : `Level ${r.level}`}</span>
                </div>
              ))}
            </div>
            <p className="muted">
              {nextReward
                ? `Reach level ${nextReward.level} to unlock the ${nextReward.name.toLowerCase()}.`
                : 'You have unlocked every avatar.'}
              {' '}Change yours by clicking your name at the top.
            </p>
          </section>

          <section className="sheet">
            <h2>Where your XP came from</h2>
            {recent.length === 0 ? (
              <p className="muted" style={{ marginTop: 8 }}>Reading a chapter gives 20 XP, and each correct quiz answer gives 10.</p>
            ) : (
              <ul className="plain-list" style={{ marginTop: 6 }}>
                {recent.slice(0, 5).map((entry, i) => (
                  <li key={i}><span>{entry.reason.replace(/\s+[—-]\s+Chapter Quiz/g, '')}</span><span className="xp-plus">+{entry.xp}</span></li>
                ))}
              </ul>
            )}
            <p className="xp-more"><button className="link" onClick={onLeaderboard}>See the class leaderboard</button></p>
          </section>
        </div>
      </main>
    </>
  );
}
