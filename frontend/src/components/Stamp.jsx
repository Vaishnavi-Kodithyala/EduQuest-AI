import React from 'react';

// A badge, drawn as the teacher's rubber stamp. Locked badges are a faint
// dashed outline with what is still needed.
export default function Stamp({ badge, showDetails = true }) {
  const earned = badge.earned;
  return (
    <div className="stamp-cell">
      <div className={`stamp ${earned ? '' : 'locked'}`} aria-hidden="true">{badge.label}</div>
      {showDetails && (
        <>
          <p>
            <span className="sr-only">{badge.label}: </span>
            {badge.description}
          </p>
          {!earned && <span className="progress">{badge.progress} of {badge.target}</span>}
          {earned && <span className="sr-only">Earned</span>}
        </>
      )}
    </div>
  );
}
