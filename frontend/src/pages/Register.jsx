import React, { useState } from 'react';
import { api } from '../services/api';
import { AVATARS, setAvatarForUser } from '../utils/gamify';

export default function Register({ onLogin, onRegistered }) {
  const [form, setForm] = useState({ username: '', password: '', grade: 6, language: 'en' });
  const [avatar, setAvatar] = useState(AVATARS[0]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const change = (k, v) => setForm({ ...form, [k]: v });

  async function submit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const r = await api.register({ ...form, avatar });
      setAvatarForUser(r.user, avatar);
      onRegistered(r.user);
    } catch (err) {
      setError(err.message === 'Failed to fetch'
        ? 'Cannot reach the server. Check that the backend is running.'
        : err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-page">
      <form className="auth-card ruled" onSubmit={submit}>
        <div className="auth-brand">EduQuest</div>
        <h1>Create your account</h1>
        <p>For Grade 6 students.</p>

        <p className="field-label">Choose a picture for your profile</p>
        <div className="avatar-picker" role="radiogroup" aria-label="Profile picture">
          {AVATARS.map(a => (
            <button type="button" key={a} role="radio" aria-checked={avatar === a}
                    className={`avatar-option ${avatar === a ? 'selected' : ''}`} onClick={() => setAvatar(a)}>
              {a}
            </button>
          ))}
        </div>

        <label>Username
          <input value={form.username} onChange={e => change('username', e.target.value)} minLength="3" autoComplete="username" required />
        </label>
        <label>Password (at least 6 characters)
          <input type="password" value={form.password} onChange={e => change('password', e.target.value)} minLength="6" autoComplete="new-password" required />
        </label>
        <label>Language you prefer
          <select value={form.language} onChange={e => change('language', e.target.value)}>
            <option value="en">English</option>
            <option value="te">తెలుగు (Telugu)</option>
            <option value="hi">हिंदी (Hindi)</option>
          </select>
        </label>
        {error && <div className="error">{error}</div>}
        <button className="btn" disabled={loading}>{loading ? 'Creating your account…' : 'Create account'}</button>
        <p className="auth-switch">
          Already have an account? <button type="button" className="link" onClick={onLogin}>Log in</button>
        </p>
      </form>
    </main>
  );
}
