import React, { useState } from 'react';
import API from './api';

import ContextForm from './ContextForm';
import TimelineView from './TimelineView';
import CompareTwoModal from './CompareTwoModal';
import CounsellorDashboard from './CounsellorDashboard';
import OutcomeLibrary from './OutcomeLibrary';
import './App.css';

const EXAMPLE_DECISIONS = [
  'CSE or AIML at VIT in 2026?',
  'Should I quit my job to start a company?',
  'MBA now or work for 2 more years first?',
  'Move to Bangalore for a startup or stay in a stable MNC?',
];

function App() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [decision, setDecision] = useState('');
  const [context, setContext] = useState({});
  const [error, setError] = useState(null);
  const [showCompare, setShowCompare] = useState(false);
  const [showCounsellor, setShowCounsellor] = useState(false);
  const [showOutcomes, setShowOutcomes] = useState(false);

  const runSimulation = async (ctx) => {
    if (!decision.trim()) {
      setError('Enter a decision first.');
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    const { user_email, ...simContext } = ctx;
    setContext(simContext);
    try {
      const response = await API.post('/simulate', {
        decision,
        context: simContext,
        user_email: user_email || undefined,
      });
      setResult(response.data);
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || err.message || 'Simulation failed.');
    }
    setLoading(false);
  };

  const handleReset = () => {
    setResult(null);
    setDecision('');
    setError(null);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="app">
      <header>
        <h1>⟁ FutureWeave</h1>
        <p>Map your possible futures before you choose</p>
        <div className="header-actions">
          <button type="button" className="header-action-btn" onClick={() => setShowCompare(true)}>
            ⇄ Compare Two Decisions
          </button>
          <button type="button" className="header-action-btn" onClick={() => setShowCounsellor(true)}>
            🎓 Counsellor Login
          </button>
          <button type="button" className="header-action-btn" onClick={() => setShowOutcomes(true)}>
            📚 Outcome Library
          </button>
        </div>
      </header>

      <main>
        {/* ── Input area — hidden once results are shown ── */}
        {!result && !loading && (
          <div className="input-area">

            {/* Step 1: Decision */}
            <div className="decision-step">
              <div className="step-label">
                <span className="step-num">1</span>
                What decision are you facing?
              </div>
              <input
                type="text"
                className="decision-input"
                placeholder='e.g. "Should I quit my job to start a company?"'
                value={decision}
                onChange={(e) => setDecision(e.target.value)}
              />
              {/* Example chips */}
              <div className="decision-chips">
                <span className="chips-label">Try an example:</span>
                {EXAMPLE_DECISIONS.map((ex) => (
                  <button
                    key={ex}
                    type="button"
                    className="decision-chip"
                    onClick={() => setDecision(ex)}
                  >
                    {ex}
                  </button>
                ))}
              </div>
            </div>

            {/* Step 2: Context form */}
            <div className="step-label" style={{ marginBottom: '0.75rem' }}>
              <span className="step-num">2</span>
              Tell us about yourself
            </div>
            <ContextForm onSubmit={runSimulation} />

            {error && <div className="error">⚠ {error}</div>}
          </div>
        )}

        {/* ── Loading state ── */}
        {loading && (
          <div className="loading-screen">
            <div className="loading-orb" />
            <div className="loader">◈ SIMULATING YOUR FUTURES...</div>
            <p className="loading-sub">
              Grounding in real salary data · Modelling causal outcomes · Writing your futures
            </p>
          </div>
        )}

        {/* ── Results ── */}
        {result && (
          <>
            <div className="results-header">
              <div className="results-decision-tag">
                <span className="results-decision-label">Your decision:</span>
                <span className="results-decision-text">{decision}</span>
              </div>
              <button type="button" className="new-sim-btn" onClick={handleReset}>
                ← New Simulation
              </button>
            </div>
            <TimelineView data={result} decision={decision} />
          </>
        )}
      </main>

      {showCompare && (
        <CompareTwoModal context={context} onClose={() => setShowCompare(false)} />
      )}
      {showCounsellor && (
        <CounsellorDashboard onClose={() => setShowCounsellor(false)} />
      )}
      {showOutcomes && (
        <OutcomeLibrary onClose={() => setShowOutcomes(false)} />
      )}
    </div>
  );
}

export default App;
