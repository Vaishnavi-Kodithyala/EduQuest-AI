import React, { useState } from 'react';
import { api } from '../services/api';

export default function Login({ onRegister, onLoggedIn }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const r = await api.login({ username, password });
      onLoggedIn(r.user);
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
        <h1>Log in</h1>
        <p>Grade 6 chapters, quizzes and a question helper for English, Maths, Science and Telugu.</p>
        <label>
          Username
          <input value={username} onChange={e => setUsername(e.target.value)} autoComplete="username" required />
        </label>
        <label>
          Password
          <input type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" required />
        </label>
        {error && <div className="error">{error}</div>}
        <button className="btn" disabled={loading}>{loading ? 'Logging in…' : 'Log in'}</button>
        <p className="auth-switch">
          New here? <button type="button" className="link" onClick={onRegister}>Create an account</button>
        </p>
        <p className="auth-note">Teachers log in here too, with the account made for them.</p>
      </form>
    </main>
  );
}
