import React, { useEffect, useState } from 'react';
import Header from '../components/Header';
import { api } from '../services/api';

function Row({ row }) {
  return (
    <tr className={row.is_you ? 'you' : ''}>
      <td className="rank">{row.rank}</td>
      <td>
        <span className="who">
          <span className="avatar" aria-hidden="true">{row.avatar}</span>
          <span>{row.username}{row.is_you ? ' (you)' : ''}<small>Level {row.level}, {row.title}</small></span>
        </span>
      </td>
      <td className="num">{row.streak > 0 ? `${row.streak} ${row.streak === 1 ? 'day' : 'days'}` : '–'}</td>
      <td className="num">{row.badges}</td>
      <td className="num xp">{row.xp.toLocaleString('en-IN')}</td>
    </tr>
  );
}

export default function Leaderboard({ user, streak }) {
  const [board, setBoard] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api.leaderboard({ grade: user.grade, user_id: user.id, limit: 15 })
      .then(setBoard)
      .catch(() => setError('Could not load the leaderboard. Check that the server is running.'));
  }, [user.id, user.grade]);

  const youInTop = board?.top?.some(r => r.is_you);

  return (
    <>
      <Header user={user} streak={streak} />

      <main className="container">
        <div className="page-title">
          <h1>Class leaderboard</h1>
          <p>Grade {user.grade}, ranked by XP. You earn XP by reading chapters, answering quiz questions correctly and studying every day.</p>
        </div>

        {error && <div className="error">{error}</div>}

        {board && (
          <section className="sheet">
            {board.top.length === 0 ? (
              <p className="empty">No one has earned XP yet. Read a chapter to be the first.</p>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table className="board">
                  <thead>
                    <tr>
                      <th scope="col">Rank</th>
                      <th scope="col">Student</th>
                      <th scope="col" className="num">Streak</th>
                      <th scope="col" className="num">Badges</th>
                      <th scope="col" className="num">XP</th>
                    </tr>
                  </thead>
                  <tbody>
                    {board.top.map(row => <Row row={row} key={row.user_id} />)}
                    {board.you && !youInTop && (
                      <>
                        <tr className="board-gap"><td colSpan={5}>…</td></tr>
                        <Row row={board.you} />
                      </>
                    )}
                  </tbody>
                </table>
              </div>
            )}
            <p className="board-note">
              {board.students} {board.students === 1 ? 'student' : 'students'} in Grade {user.grade}. Students with the same XP share a rank.
            </p>
          </section>
        )}
      </main>
    </>
  );
}
