// Avatars and display helpers.
//
// XP, levels, streaks and badges used to be computed here in the browser from
// three progress numbers, with the streak kept in localStorage. They now come
// from the server (GET /api/gamification/:id) so that the dashboard,
// leaderboard, chatbot and teacher dashboard all see the same figures, on any
// device. What remains here is purely presentational.

export const AVATARS = ['🦊', '🐼', '🐯', '🦁', '🐨', '🦉', '🐸', '🐧', '🦄', '🐙'];

// Shown before the first /gamification response arrives.
export const STARTING_LEVEL = {
  level: 1,
  title: 'Wayfarer',
  xpIntoLevel: 0,
  xpForNextLevel: 150,
  pct: 0
};

export function levelFromGame(game) {
  if (!game) return STARTING_LEVEL;
  const { level, title, xpIntoLevel, xpForNextLevel, pct } = game;
  return { level, title, xpIntoLevel, xpForNextLevel, pct };
}

export function avatarForUser(user) {
  if (!user) return AVATARS[0];
  if (user.avatar) return user.avatar;
  let stored = null;
  try {
    stored = localStorage.getItem(`eduquest_avatar_${user.id}`);
  } catch {
    stored = null;
  }
  if (stored) return stored;
  // Same formula as the server's default (gamification/engine.py) so the
  // leaderboard and header agree for students who never picked one.
  const idx = Math.abs(hash(user.username || 'x')) % AVATARS.length;
  return AVATARS[idx];
}

export function setAvatarForUser(user, avatar) {
  try {
    localStorage.setItem(`eduquest_avatar_${user.id}`, avatar);
  } catch {
    // storage unavailable - the server copy on the user record still applies
  }
}

function hash(str) {
  let h = 0;
  for (let i = 0; i < str.length; i++) {
    h = (h << 5) - h + str.charCodeAt(i);
    h |= 0;
  }
  return h;
}
