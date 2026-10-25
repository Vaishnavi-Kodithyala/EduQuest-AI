import React, { useEffect, useRef, useState } from 'react';

/*
 * Small hand-made charts for the teacher dashboard (no chart library, so
 * nothing new to install). Conventions, applied to every chart:
 *   - one series per chart, in ball-pen blue; text stays in the text colours
 *   - thin marks, hairline solid gridlines, 4px rounded bar ends
 *   - values are labelled directly or listed in a table, so hover is a
 *     convenience, never the only way to read a number
 *   - the score trend and the daily quiz count are two charts on one shared
 *     x-axis rather than one chart with two y-scales
 */

export const pct = (v) => (v === null || v === undefined ? '—' : `${v}%`);

export function useWidth() {
  const ref = useRef(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const update = () => setWidth(el.clientWidth);
    update();
    if (typeof ResizeObserver === 'undefined') return undefined;
    const observer = new ResizeObserver(update);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return [ref, width];
}

// Trend dates are calendar days in India ("2026-10-22"); read and print them
// as UTC so the browser's own time zone cannot shift them by a day.
const SHORT_DAY = new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', timeZone: 'UTC' });
const LONG_DAY = new Intl.DateTimeFormat('en-IN', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' });
const asDate = (iso) => new Date(`${iso}T00:00:00Z`);

function roundedTopBar(x, y, w, h, r) {
  const rr = Math.max(0, Math.min(r, w / 2, h));
  return `M${x},${y + h}V${y + rr}Q${x},${y} ${x + rr},${y}H${x + w - rr}Q${x + w},${y} ${x + w},${y + rr}V${y + h}Z`;
}

export function ScoreTrend({ points, passScore = 60 }) {
  const [ref, width] = useWidth();
  const [active, setActive] = useState(null);

  const n = points.length;
  const left = 38;
  const right = 46;
  const top = 10;
  const plotH = 170;
  const bottom = top + plotH;
  const colH = 64;
  const plotW = Math.max(0, width - left - right);
  const step = n ? plotW / n : 0;
  const x = (i) => left + step * (i + 0.5);
  const y = (v) => top + (1 - v / 100) * plotH;

  // The line breaks on days with no quizzes instead of drawing through them.
  let path = '';
  let pen = false;
  points.forEach((p, i) => {
    if (p.average_score === null) { pen = false; return; }
    path += `${pen ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.average_score).toFixed(1)}`;
    pen = true;
  });
  const lastIndex = points.map((p) => p.average_score !== null).lastIndexOf(true);
  // Keep the end value clear of the "pass" label when the two are close.
  let endY = lastIndex >= 0 ? y(points[lastIndex].average_score) - 9 : 0;
  if (lastIndex >= 0 && Math.abs(endY - (y(passScore) + 4)) < 13) {
    endY = y(points[lastIndex].average_score) + (points[lastIndex].average_score >= passScore ? -16 : 20);
  }
  const maxAttempts = Math.max(1, ...points.map((p) => p.attempts));
  const busiest = points.findIndex((p) => p.attempts === maxAttempts);
  const every = Math.max(1, Math.ceil(52 / Math.max(step, 1)));
  const barW = Math.max(2, Math.min(24, step - 2));

  function pick(clientX) {
    const box = ref.current.getBoundingClientRect();
    const i = Math.floor((clientX - box.left - left) / step);
    setActive(Math.max(0, Math.min(n - 1, i)));
  }
  function onKey(e) {
    if (e.key === 'ArrowLeft') { e.preventDefault(); setActive((a) => Math.max(0, (a ?? n) - 1)); }
    if (e.key === 'ArrowRight') { e.preventDefault(); setActive((a) => Math.min(n - 1, (a ?? -1) + 1)); }
    if (e.key === 'Escape') setActive(null);
  }

  const shown = active === null ? null : points[active];
  const tipLeft = active === null ? 0 : Math.max(70, Math.min(width - 70, x(active)));

  return (
    <div className="trend" ref={ref}>
      {width > 0 && n > 0 && (
        <div
          className="trend-plot"
          tabIndex={0}
          role="img"
          aria-label="Average quiz score per day. Use the left and right arrow keys to read each day."
          onPointerMove={(e) => pick(e.clientX)}
          onPointerLeave={() => setActive(null)}
          onFocus={() => setActive(lastIndex >= 0 ? lastIndex : n - 1)}
          onBlur={() => setActive(null)}
          onKeyDown={onKey}
        >
          <svg width={width} height={bottom + 24} className="chart-svg">
            {[0, 25, 50, 75, 100].map((t) => (
              <g key={t}>
                <line x1={left} x2={left + plotW} y1={y(t)} y2={y(t)} className="grid-line" />
                <text x={left - 8} y={y(t) + 4} textAnchor="end" className="axis-tick">{t}{t === 100 ? '%' : ''}</text>
              </g>
            ))}
            <line x1={left} x2={left + plotW} y1={y(passScore)} y2={y(passScore)} className="pass-line" />
            <text x={left + plotW + 6} y={y(passScore) + 4} className="axis-tick">pass</text>

            {active !== null && (
              <line x1={x(active)} x2={x(active)} y1={top} y2={bottom} className="crosshair" />
            )}
            <path d={path} className="series-line" />
            {points.map((p, i) => p.average_score !== null && (
              <circle key={p.date} cx={x(i)} cy={y(p.average_score)} r={i === active ? 5.5 : 4}
                      className="series-dot" />
            ))}
            {lastIndex >= 0 && (
              <text x={x(lastIndex) + 9} y={endY} className="end-label">
                {points[lastIndex].average_score}%
              </text>
            )}
            {points.map((p, i) => (n - 1 - i) % every === 0 && (
              <text key={p.date} x={x(i)} y={bottom + 18} textAnchor="middle" className="axis-tick">
                {SHORT_DAY.format(asDate(p.date))}
              </text>
            ))}
          </svg>

          <div className="trend-sub">Quizzes taken per day</div>
          <svg width={width} height={colH + 4} className="chart-svg">
            <line x1={left} x2={left + plotW} y1={colH} y2={colH} className="axis-line" />
            {points.map((p, i) => {
              if (!p.attempts) return null;
              const h = (p.attempts / maxAttempts) * (colH - 18);
              return (
                <path key={p.date} d={roundedTopBar(x(i) - barW / 2, colH - h, barW, h, 4)}
                      className={`series-col ${active !== null && active !== i ? 'dim' : ''}`} />
              );
            })}
            <text x={x(busiest)} y={colH - (colH - 18) - 5} textAnchor="middle" className="end-label small">
              {maxAttempts}
            </text>
          </svg>

          {shown && (
            <div className="chart-tip" style={{ left: tipLeft }}>
              <b>{shown.average_score === null ? 'No quizzes' : `${shown.average_score}% average`}</b>
              {shown.attempts > 0 && (
                <span>{shown.attempts} {shown.attempts === 1 ? 'quiz' : 'quizzes'} by {shown.students} {shown.students === 1 ? 'student' : 'students'}</span>
              )}
              <small>{LONG_DAY.format(asDate(shown.date))}</small>
            </div>
          )}
        </div>
      )}

      <details className="chart-table">
        <summary>Show as a table</summary>
        <div className="table-scroll">
          <table className="data-table">
            <thead><tr><th>Day</th><th className="num">Quizzes</th><th className="num">Students</th><th className="num">Average</th></tr></thead>
            <tbody>
              {points.slice().reverse().map((p) => (
                <tr key={p.date}>
                  <td>{LONG_DAY.format(asDate(p.date))}</td>
                  <td className="num">{p.attempts}</td>
                  <td className="num">{p.students}</td>
                  <td className="num">{pct(p.average_score)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}

/* Average score per subject, as horizontal bars on a 0-100 scale. */
export function SubjectBars({ subjects, passScore = 60, single = false }) {
  return (
    <ul className="subject-bars">
      {subjects.map((s) => (
        <li key={s.subject} className="subject-bar">
          <div className="subject-bar-name">{s.subject}</div>
          <div className="subject-bar-area" title={s.average_score === null ? `${s.subject}: no quizzes yet` : `${s.subject}: ${s.average_score}% average`}>
            <span className="subject-bar-pass" style={{ left: `${passScore}%` }} aria-hidden="true" />
            {s.average_score === null ? (
              <span className="subject-bar-empty">No quizzes yet</span>
            ) : (
              <>
                <span className="subject-bar-fill" style={{ width: `${s.average_score}%` }} />
                <span className="subject-bar-value" style={{ left: `${s.average_score}%` }}>
                  {s.average_score}%
                  {s.average_score < passScore && <LowMark />}
                </span>
              </>
            )}
          </div>
          <div className="subject-bar-meta">
            {s.quizzes_taken === 0
              ? 'No quizzes yet'
              : single
                ? `${s.quizzes_taken} ${s.quizzes_taken === 1 ? 'quiz' : 'quizzes'}, ${s.pass_rate}% passed`
                : `${s.pass_rate}% of quizzes passed by ${s.students_tested} ${s.students_tested === 1 ? 'student' : 'students'}`}
            {`. ${s.coverage}% of chapters read.`}
          </div>
        </li>
      ))}
    </ul>
  );
}

/* Status mark for "below the pass mark": an icon and text, never colour alone. */
export function LowMark({ label = 'below pass' }) {
  return <span className="low-mark"><span aria-hidden="true">▼</span> {label}</span>;
}

/* Share of answers that were right, as a meter whose fill carries severity. */
export function Meter({ value }) {
  const level = value < 40 ? 'critical' : 'serious';
  return (
    <span className={`meter meter-${level}`}>
      <span className="meter-track"><span className="meter-fill" style={{ width: `${Math.max(value, 3)}%` }} /></span>
      <span className="meter-value">{value}%</span>
    </span>
  );
}
