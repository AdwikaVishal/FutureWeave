/**
 * CounsellorDashboard.js
 *
 * Separate view for career counsellors to see all student simulations,
 * compare across cases, and add notes.
 *
 * Accessed via ?counsellor=email@example.com in the URL or via the
 * "Counsellor Login" button in the header.
 */
import axios from 'axios';
import React, { useState, useCallback } from 'react';

function CounsellorDashboard({ onClose }) {
  const [email, setEmail] = useState('');
  const [loggedIn, setLoggedIn] = useState(false);
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [noteInputs, setNoteInputs] = useState({});
  const [savingNote, setSavingNote] = useState(null);
  const [expanded, setExpanded] = useState(null);

  const fetchStudents = useCallback(async (counsellorEmail) => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get('/counsellor/students', {
        params: { counsellor_email: counsellorEmail },
      });
      setStudents(res.data.students || []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load students.');
    }
    setLoading(false);
  }, []);

  const handleLogin = (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    setLoggedIn(true);
    fetchStudents(email.trim());
  };

  const handleAddNote = async (simId) => {
    const note = noteInputs[simId]?.trim();
    if (!note) return;
    setSavingNote(simId);
    try {
      await axios.post('/counsellor/note', {
        simulation_id: simId,
        counsellor_email: email,
        note,
      });
      setNoteInputs((prev) => ({ ...prev, [simId]: '' }));
      fetchStudents(email);
    } catch (err) {
      // silent
    }
    setSavingNote(null);
  };

  return (
    <div
      className="modal-overlay"
      onClick={onClose}
      onKeyDown={(e) => { if (e.key === 'Escape') onClose(); }}
      role="button"
      tabIndex={-1}
    >
      <div
        className="modal-content counsellor-modal"
        onClick={(e) => e.stopPropagation()}
        role="presentation"
      >
        <h3>🎓 COUNSELLOR DASHBOARD</h3>

        {!loggedIn ? (
          <form onSubmit={handleLogin} className="counsellor-login">
            <p className="compare-hint">Enter your counsellor email to access student simulations.</p>
            <input
              type="email"
              className="pivot-input"
              placeholder="counsellor@school.edu"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <div className="modal-buttons">
              <button type="submit">▶ ACCESS DASHBOARD</button>
              <button type="button" onClick={onClose}>CANCEL</button>
            </div>
          </form>
        ) : (
          <>
            <div className="counsellor-meta">
              <span style={{ color: 'var(--glow-cyan)' }}>{email}</span>
              <span className="counsellor-count">{students.length} simulations</span>
              <button type="button" className="counsellor-refresh" onClick={() => fetchStudents(email)}>
                ↻ Refresh
              </button>
            </div>

            {loading && <div className="loader" style={{ padding: '1rem' }}>Loading...</div>}
            {error && <div className="values-error">⚠ {error}</div>}

            <div className="counsellor-list">
              {students.map((s) => (
                <div key={s.simulation_id} className="counsellor-card">
                  <div
                    className="counsellor-card-header"
                    onClick={() => setExpanded(
                      expanded === s.simulation_id ? null : s.simulation_id,
                    )}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        setExpanded(expanded === s.simulation_id ? null : s.simulation_id);
                      }
                    }}
                  >
                    <div className="counsellor-card-left">
                      <span className="counsellor-student-email">{s.user_email}</span>
                      <span className="counsellor-decision">{s.decision.slice(0, 80)}{s.decision.length > 80 ? '...' : ''}</span>
                    </div>
                    <div className="counsellor-card-right">
                      <span className="counsellor-date">
                        {s.created_at ? new Date(s.created_at).toLocaleDateString() : '—'}
                      </span>
                      <span className="counsellor-expand">{expanded === s.simulation_id ? '▲' : '▼'}</span>
                    </div>
                  </div>

                  {expanded === s.simulation_id && (
                    <div className="counsellor-card-body">
                      <div className="counsellor-context">
                        {Object.entries(s.context || {}).map(([k, v]) => (
                          <span key={k} className="counsellor-ctx-tag">
                            {k}
                            :
                            {' '}
                            {String(v)}
                          </span>
                        ))}
                      </div>

                      {s.notes.length > 0 && (
                        <div className="counsellor-notes">
                          {s.notes.map((n) => (
                            <div key={n.id} className="counsellor-note">
                              <span className="counsellor-note-date">
                                {n.created_at ? new Date(n.created_at).toLocaleDateString() : ''}
                              </span>
                              <span className="counsellor-note-text">{n.note}</span>
                            </div>
                          ))}
                        </div>
                      )}

                      <div className="counsellor-note-input-row">
                        <input
                          type="text"
                          className="pivot-input"
                          placeholder="Add a note..."
                          value={noteInputs[s.simulation_id] || ''}
                          onChange={(e) => setNoteInputs(
                            (prev) => ({ ...prev, [s.simulation_id]: e.target.value }),
                          )}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') handleAddNote(s.simulation_id);
                          }}
                        />
                        <button
                          type="button"
                          className="counsellor-note-btn"
                          onClick={() => handleAddNote(s.simulation_id)}
                          disabled={savingNote === s.simulation_id}
                        >
                          {savingNote === s.simulation_id ? '...' : '+ Note'}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>

            <div className="modal-buttons" style={{ marginTop: '1rem' }}>
              <button type="button" onClick={onClose}>CLOSE</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default CounsellorDashboard;
