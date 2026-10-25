import React, { useEffect, useRef, useState } from 'react';
import Header from '../components/Header';
import { api } from '../services/api';
import { displayName } from '../utils/text';

// Questions the chatbot answers well (see docs/week10-testing.md).
const SUGGESTIONS = [
  'What is the SI unit of length?',
  'What is 1/3 + 1/6?',
  'Is 91 a prime number?',
  'How do camels survive in the desert?',
  'రైతు ఏమి చేస్తాడు?',
  'How many points do I have?'
];

const ANSWER_LABELS = {
  textbook: 'Answer from your textbook',
  math: 'Answer'
};

const INTENT_LABELS = {
  greeting: 'Greeting',
  definition: 'Definition',
  concept_explanation: 'Explanation',
  example_request: 'Example',
  formula_help: 'Method',
  homework_help: 'Homework',
  clarification: 'Clarification',
  quiz_help: 'Quiz',
  progress_help: 'Progress',
  out_of_scope: 'Off topic',
  browse_content: 'Chapters',
  study_advice: 'Study plan',
  calculation: 'Calculation',
  factual_question: 'Fact',
  telugu_question: 'Telugu'
};

// When the bot found an exact answer, the reply starts with it; it is shown in
// the highlighted box instead, so the bubble does not say it twice.
function splitAnswer(m) {
  if (!m.answer || !ANSWER_LABELS[m.answer.source]) return { box: null, body: m.text };
  const parts = m.text.split('\n\n');
  return { box: m.answer, body: parts.slice(1).join('\n\n') };
}

export default function Chat({ user, streak, onOpenLesson }) {
  const [messages, setMessages] = useState([
    {
      from: 'bot',
      text: `Hello ${displayName(user.username)}. Ask me about anything in your chapters, a maths sum, or your progress. You can ask in English or Telugu.`
    }
  ]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, sending]);

  async function send(text) {
    const message = (text ?? input).trim();
    if (!message || sending) return;

    setMessages(m => [...m, { from: 'student', text: message }]);
    setInput('');
    setSending(true);

    try {
      const res = await api.chat({
        message,
        user_id: user.id,
        grade: user.grade,
        language: user.language
      });

      setMessages(m => [
        ...m,
        {
          from: 'bot',
          text: res.reply,
          intent: res.intent,
          confidence: res.confidence,
          understood: res.understood,
          lesson: res.lesson,
          answer: res.answer
        }
      ]);
    } catch (err) {
      setMessages(m => [
        ...m,
        {
          from: 'bot',
          text: 'I could not reach the server. Check that the backend is running, then try again.',
          error: true
        }
      ]);
    } finally {
      setSending(false);
    }
  }

  return (
    <>
      <Header user={user} streak={streak} />

      <main className="container">
        <div className="page-title">
          <h1>Ask a question</h1>
          <p>Questions are answered from your Grade {user.grade} textbooks. Maths sums are worked out step by step.</p>
        </div>

        <section className="sheet chat">
          <div className="chat-log" aria-live="polite">
            {messages.map((m, i) => {
              const { box, body } = splitAnswer(m);
              return (
                <div key={i} className={`chat-row ${m.from}`}>
                  <div className={`chat-bubble ${m.from}${m.error ? ' chat-error' : ''}`}>
                    {box && (
                      <div className="chat-answer">
                        <span>{ANSWER_LABELS[box.source]}</span>
                        <b>{box.text}</b>
                      </div>
                    )}
                    {body && <p>{body}</p>}

                    {m.lesson && (
                      <div className="chat-open">
                        <button className="link" onClick={() => onOpenLesson(m.lesson)}>
                          Open “{m.lesson.title}”
                        </button>
                      </div>
                    )}

                    {m.from === 'bot' && m.intent && (
                      <div className="chat-meta">
                        {m.understood
                          ? <span>Understood as: {INTENT_LABELS[m.intent] || m.intent}</span>
                          : <span className="unsure">Not sure what you meant</span>}
                        {box?.source === 'textbook'
                          ? <span>, answer {Math.round(box.score * 100)}% likely</span>
                          : m.intent !== 'calculation' && <span>, {Math.round(m.confidence * 100)}% sure</span>}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {sending && (
              <div className="chat-row bot">
                <div className="chat-bubble bot" aria-label="Writing an answer">
                  <span className="typing"><i /><i /><i /></span>
                </div>
              </div>
            )}

            <div ref={endRef} />
          </div>

          <div className="try">
            <span>Try:</span>
            {SUGGESTIONS.map(s => (
              <button key={s} onClick={() => send(s)} disabled={sending}>{s}</button>
            ))}
          </div>

          <form className="chat-input" onSubmit={e => { e.preventDefault(); send(); }}>
            <label className="sr-only" htmlFor="question">Your question</label>
            <input id="question" value={input} onChange={e => setInput(e.target.value)}
                   placeholder="Type your question" disabled={sending} autoComplete="off" />
            <button className="btn" disabled={sending || !input.trim()}>Ask</button>
          </form>
        </section>

        <p className="chat-note">The first answer can take a few seconds while the language models start.</p>
      </main>
    </>
  );
}
