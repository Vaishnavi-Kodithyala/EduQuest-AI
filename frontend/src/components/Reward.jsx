import React from 'react';
import Stamp from './Stamp';

// What an action earned: XP, a level-up, new badges and newly unlocked
// avatars. `result` is the `gamification` object the server returns after a
// quiz is submitted or a chapter is marked as read.
export default function Reward({ result }) {
  if (!result) return null;
  const { xp_gained: gained, level_up: levelUp, level, new_badges: badges = [], new_rewards: rewards = [], streak } = result;

  return (
    <div className="reward-box">
      {gained > 0 ? (
        <p className="xp-gained">+{gained} XP{levelUp ? `, and you reached level ${level}` : ''}</p>
      ) : (
        <p>No new XP this time. You get 10 XP for each question you answer correctly for the first time.</p>
      )}
      {streak > 1 && <p>You have learned something {streak} days in a row.</p>}
      {badges.length > 0 && (
        <>
          <p>New {badges.length > 1 ? 'badges' : 'badge'}:</p>
          <div className="new-stamps">
            {badges.map(b => <Stamp key={b.id} badge={b} showDetails={false} />)}
          </div>
        </>
      )}
      {rewards.length > 0 && (
        <p>
          New avatar unlocked: {rewards.map(r => `${r.avatar} ${r.name}`).join(', ')}. You can switch to it in Settings.
        </p>
      )}
    </div>
  );
}
