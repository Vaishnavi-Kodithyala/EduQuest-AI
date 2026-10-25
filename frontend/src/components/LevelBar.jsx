import React from 'react';

// Progress towards the next level, in marigold (the colour used for XP).
export default function LevelBar({ level, title, pct, xpIntoLevel, xpForNextLevel }) {
  const left = xpForNextLevel - xpIntoLevel;
  return (
    <div className="levelbar">
      <div className="levelbar-track" role="progressbar" aria-valuemin={0} aria-valuemax={xpForNextLevel}
           aria-valuenow={xpIntoLevel} aria-label={`Level ${level} progress`}>
        <div className="levelbar-fill" style={{ width: `${pct}%` }} />
      </div>
      <div className="levelbar-text">
        <span>Level {level}, {title}</span>
        <span>{left} XP to level {level + 1}</span>
      </div>
    </div>
  );
}
