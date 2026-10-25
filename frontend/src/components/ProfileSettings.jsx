import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { AVATARS, avatarForUser, setAvatarForUser } from '../utils/gamify';

const LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'te', label: 'తెలుగు' },
  { code: 'hi', label: 'हिंदी' }
];

export default function ProfileSettings({ user, game, onUpdated, onClose }) {
  const currentAvatar = avatarForUser(user);
  const [language, setLanguage] = useState(user.language);
  const [avatar, setAvatar] = useState(currentAvatar);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  // Base avatars plus reward avatars; locked rewards show the level needed.
  const unlocked = new Set(game?.avatars || AVATARS);
  const rewards = game?.rewards || [];
  const changed = language !== user.language || avatar !== currentAvatar;

  useEffect(() => {
    const onKey = e => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  async function save() {
    if (!changed || saving) return;
    setSaving(true);
    setError('');
    try {
      const payload = {};
      if (language !== user.language) payload.language = language;
      if (avatar !== currentAvatar) payload.avatar = avatar;
      const res = await api.updateProfile(user.id, payload);
      if (payload.avatar) setAvatarForUser(res.user, payload.avatar);
      onUpdated(res.user);
      onClose();
    } catch (err) {
      setError(err.message && err.message !== 'Request failed' && err.message !== 'Failed to fetch'
        ? err.message
        : 'Could not save. Check that the server is running.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="overlay" onClick={onClose}>
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="settings-title" onClick={e => e.stopPropagation()}>
        <div className="dialog-head">
          <h2 id="settings-title">Your profile</h2>
          <button className="link" onClick={onClose}>Close</button>
        </div>
        <p className="muted">{user.username}, Grade {user.grade}</p>

        <div className="group">
          <b>Picture</b>
          <div className="avatar-picker">
            {AVATARS.map(a => (
              <button type="button" key={a} aria-pressed={avatar === a}
                      className={`avatar-option ${avatar === a ? 'selected' : ''}`} onClick={() => setAvatar(a)}>
                {a}
              </button>
            ))}
            {rewards.map(r => {
              const open = unlocked.has(r.avatar);
              return (
                <button type="button" key={r.avatar} aria-pressed={avatar === r.avatar}
                        className={`avatar-option ${avatar === r.avatar ? 'selected' : ''} ${open ? '' : 'locked'}`}
                        onClick={() => open && setAvatar(r.avatar)} disabled={!open}
                        title={open ? r.name : `Unlocks at level ${r.level}`}>
                  {open ? r.avatar : `L${r.level}`}
                </button>
              );
            })}
          </div>
          {rewards.some(r => !unlocked.has(r.avatar)) && <p className="hint">The pictures marked L2, L3 and so on unlock at that level.</p>}
        </div>

        <div className="group">
          <b>Language</b>
          <div className="choice-row">
            {LANGUAGES.map(l => (
              <button key={l.code} aria-pressed={language === l.code}
                      className={language === l.code ? 'chosen' : ''} onClick={() => setLanguage(l.code)}>
                {l.label}
              </button>
            ))}
          </div>
          {language !== 'en' && (
            <p className="hint">Chapters are not in this language yet, so you will see the English chapters with a note.</p>
          )}
        </div>

        {error && <div className="error">{error}</div>}

        <div className="actions">
          <button className="btn" onClick={save} disabled={!changed || saving}>{saving ? 'Saving…' : 'Save'}</button>
          <button className="btn-quiet" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </div>
  );
}
