import React, { useState, useRef, useEffect } from 'react';
import { futureChat as apiFutureChat } from '../api';

const SUGGESTIONS = [
  'How did my career progress?',
  'What was your biggest regret?',
  'Was taking that risk worth it?',
  'What would you change?',
  'How are my relationships?',
  'Are you happy?',
];

export default function FutureChat({ simulationResult, decision: _decision }) {
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [selectedTimeline, setSelectedTimeline] = useState('');
  const chatEnd = useRef(null);

  const timelines = simulationResult?.timelines || {};
  const timelineKeys = Object.keys(timelines);
  const activeKey = selectedTimeline || timelineKeys[0] || '';

  useEffect(() => {
    setMessages([]);
  }, [activeKey]);

  useEffect(() => {
    chatEnd.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!question.trim() || !activeKey) return;
    const userMsg = { role: 'user', content: question };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);
    setQuestion('');

    const activeTimeline = timelines[activeKey] || {};
    const persona = {
      name: activeKey,
      archetype: activeKey,
      summary: activeTimeline.Year10 || '',
    };

    try {
      const data = await apiFutureChat(activeKey, question, persona, activeTimeline, messages);
      setMessages((prev) => [...prev, { role: 'assistant', content: data.response || '...' }]);
    } catch {
      const fallback = `Looking back from Year 10 on the ${activeKey} path, I can tell you that every choice shaped who I became. ${question.toLowerCase().includes('regret') ? 'There are always trade-offs, but I made peace with my decisions.' : 'The journey was not always easy, but it was worth it.'}`;
      setMessages((prev) => [...prev, { role: 'assistant', content: fallback }]);
    }
    setLoading(false);
  };

  if (!simulationResult) {
    return (
      <div className="empty-state">
        <p>Run a simulation first to chat with your future selves.</p>
      </div>
    );
  }

  return (
    <div className="future-chat">
      {timelineKeys.length > 0 && (
        <div className="chat-timeline-selector" style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
          {timelineKeys.map((key, i) => (
            <button
              key={key}
              className={`chat-tl-btn ${activeKey === key ? 'active' : ''}`}
              onClick={() => setSelectedTimeline(key)}
              style={{
                borderColor: activeKey === key ? ['#00f2ff', '#ff2a7a', '#7b2fff'][i % 3] : 'var(--border-dim)',
                color: activeKey === key ? ['#00f2ff', '#ff2a7a', '#7b2fff'][i % 3] : 'var(--text-muted)',
              }}
            >
              {key}
            </button>
          ))}
        </div>
      )}

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-welcome">
            <p>Ask your future self on the <strong>{activeKey || 'selected'}</strong> path anything about how life turned out.</p>
            <div className="suggestions" style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', justifyContent: 'center', marginTop: '1rem' }}>
              {SUGGESTIONS.map((s) => (
                <button key={s} className="suggestion-chip" onClick={() => { setQuestion(s); }}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <div className="msg-bubble">{m.content}</div>
          </div>
        ))}
        {loading && <div className="msg assistant"><div className="msg-bubble loading">Thinking...</div></div>}
        <div ref={chatEnd} />
      </div>

      <div className="chat-input-area" style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem' }}>
        <input
          className="chat-input"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Ask your future self..."
          style={{ flex: 1 }}
        />
        <button className="chat-send" onClick={handleSend} disabled={loading || !question.trim()}>
          Send
        </button>
      </div>
    </div>
  );
}
