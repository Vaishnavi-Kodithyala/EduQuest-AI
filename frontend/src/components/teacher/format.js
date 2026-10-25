// Times are shown in India Standard Time whatever the browser's setting.
const WHEN = new Intl.DateTimeFormat('en-IN', {
  day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit', timeZone: 'Asia/Kolkata'
});
const CLOCK = new Intl.DateTimeFormat('en-IN', { hour: 'numeric', minute: '2-digit', timeZone: 'Asia/Kolkata' });

export const when = (iso) => (iso ? WHEN.format(new Date(iso)) : '');
export const clock = (iso) => (iso ? CLOCK.format(new Date(iso)) : '');

export function ago(days) {
  if (days === null || days === undefined) return 'never';
  if (days <= 0) return 'today';
  if (days === 1) return 'yesterday';
  return `${days} days ago`;
}

export const SHORT_SUBJECT = { English: 'Eng', Mathematics: 'Maths', Science: 'Sci', Telugu: 'Tel' };
