// Chapter text comes from the textbook PDFs and the content bank, where
// summaries and section headings start with an emoji ("🔎 TESTING SUBSTANCES").
// The interface shows them as plain text.

const LEADING_SYMBOLS = /^[\p{Extended_Pictographic}\p{Emoji_Presentation}️‍\s]+/u;

export function plain(text) {
  return String(text || '').replace(/[\u0080-\u009f]/g, ' ').replace(LEADING_SYMBOLS, '').trim();
}

// "TESTING SUBSTANCES" -> "Testing substances"; mixed-case text is left alone.
export function sentenceCase(text) {
  const t = plain(text);
  if (t && t === t.toUpperCase() && /[A-Z]/.test(t)) {
    return t.charAt(0) + t.slice(1).toLowerCase();
  }
  return t;
}

export const SUBJECTS = ['English', 'Mathematics', 'Science', 'Telugu'];

export function chapterNumber(id) {
  const m = String(id || '').match(/(\d+)$/);
  return m ? Number(m[1]) : null;
}

// Usernames are typed in lower case; greetings use a capital letter.
export const displayName = name => (name ? name.charAt(0).toUpperCase() + name.slice(1) : '');
