import React, { useContext } from 'react';
import { avatarForUser } from '../utils/gamify';
import { NavContext } from '../context/nav';

const PAGES = [
  { key: 'home', label: 'Home', match: ['dashboard'] },
  { key: 'lessons', label: 'Chapters', match: ['lessons', 'lesson', 'quiz'] },
  { key: 'leaderboard', label: 'Leaderboard', match: ['leaderboard'] },
  { key: 'chat', label: 'Ask a question', match: ['chat'] },
];

export default function Header({ user, streak }) {
  // Navigation comes from App, so every page's header behaves the same way.
  const nav = useContext(NavContext) || {};
  const xp = nav.game?.xp;

  return (
    <header className="topbar">
      <div className="topbar-inner">
        <button className="brand" onClick={nav.home}>EduQuest</button>

        <nav className="topbar-nav" aria-label="Main">
          {PAGES.map(p => (
            <button key={p.key} className={p.match.includes(nav.page) ? 'nav-active' : ''}
                    aria-current={p.match.includes(nav.page) ? 'page' : undefined}
                    onClick={nav[p.key]}>
              {p.label}
            </button>
          ))}
        </nav>

        <div className="topbar-right">
          {xp !== undefined && (
            <span className="topbar-xp" title="Your XP">
              {xp.toLocaleString('en-IN')} XP
              {streak > 0 && <small>{streak}-day streak</small>}
            </span>
          )}
          <button className="topbar-user" onClick={nav.settings} title="Avatar and language">
            <span className="avatar" aria-hidden="true">{avatarForUser(user)}</span>
            <span className="name">{user.username}</span>
          </button>
          <button className="topbar-logout" onClick={nav.logout}>Log out</button>
        </div>
      </div>
    </header>
  );
}
