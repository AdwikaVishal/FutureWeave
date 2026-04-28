/**
 * CompareTwoModal.js
 *
 * Side-by-side comparison of two different decisions.
 * Runs two full simulations and overlays their radar charts + regret trade-offs.
 *
 * Props:
 *   context   – current user context
 *   onClose   – fn()
 */
import React, { useState } from 'react';
import API from './api';
import RadarChart from './RadarChart';

const RADAR_NODE_LABELS = {
  income: 'Income',
  career_growth: 'Career',
  stress: 'Stress',
  health: 'Health',
  relationships: 'Relations',
  happiness: 'Happiness',
  opportunity: 'Opportunity',
};

const COLORS_A = ['#00f2ff', '#ff2a7a', '#7b2fff'];
const COLORS_B = ['#00ff88', '#ffaa00', '#ff6600'];

function CompareTwoModal({ context, onClose }) {
  const [decisionA, setDecisionA] = useState('');
  const [decisionB, setDecisionB] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [year, setYear] = useState(1);

  const YEARS = [1, 3, 5, 10];

  const handleCompare = async () => {
    if (!decisionA.trim() || !decisionB.trim()) {
      setError('Enter both decisions.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await API.post('/compare-two', {
        decision_a: decisionA,
        decision_b: decisionB,
        context,
      });
      setResult(res.data);
      setYear(1);
    } catch (err) {
      setError(err.response?.data?.detail || 'Comparison failed.');
    }
    setLoading(false);
  };

  // Build radar data for a single decision result at selected year
  const buildRadarData = (simResult) => {
    if (!simResult?.causal_data) return {};
    const yrKey = `Year${year}`;
    const out = {};
    Object.keys(simResult.causal_data).forEach((tl) => {
      const scores = simResult.causal_data[tl]?.[yrKey];
      if (scores) out[tl] = scores;
    });
    return out;
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
        className="modal-content compare-two-modal"
        onClick={(e) => e.stopPropagation()}
        role="presentation"
      >
        <h3>⟁ COMPARE TWO DECISIONS</h3>
        <p className="compare-hint">Run two full simulations side-by-side to see which path suits you better.</p>

        {!result ? (
          <>
            <div className="compare-inputs">
              <div className="compare-input-group">
                <label htmlFor="decision-a" className="compare-label" style={{ color: '#00f2ff' }}>
                  DECISION A
                  <input
                    id="decision-a"
                    type="text"
                    className="pivot-input"
                    placeholder="e.g. Join BMSCE for CS"
                    value={decisionA}
                    onChange={(e) => setDecisionA(e.target.value)}
                  />
                </label>
              </div>
              <div className="compare-vs">VS</div>
              <div className="compare-input-group">
                <label htmlFor="decision-b" className="compare-label" style={{ color: '#ff2a7a' }}>
                  DECISION B
                  <input
                    id="decision-b"
                    type="text"
                    className="pivot-input"
                    placeholder="e.g. Join MAIT for CS"
                    value={decisionB}
                    onChange={(e) => setDecisionB(e.target.value)}
                  />
                </label>
              </div>
            </div>
            {error && <div className="values-error">⚠ {error}</div>}
            <div className="modal-buttons">
              <button type="button" onClick={handleCompare} disabled={loading}>
                {loading ? '◈ SIMULATING BOTH...' : '▶ COMPARE'}
              </button>
              <button type="button" onClick={onClose}>CANCEL</button>
            </div>
          </>
        ) : (
          <>
            {/* Year selector */}
            <div className="year-selector" style={{ marginBottom: '1.5rem' }}>
              {YEARS.map((yr) => (
                <button
                  key={yr}
                  type="button"
                  className={`year-button ${yr === year ? 'active' : ''}`}
                  onClick={() => setYear(yr)}
                >
                  YR {yr}
                </button>
              ))}
            </div>

            {/* Side-by-side radar charts */}
            <div className="compare-radars">
              <div className="compare-radar-side">
                <div className="compare-radar-label" style={{ color: '#00f2ff' }}>
                  A: {result.decision_a.decision.slice(0, 50)}
                </div>
                <RadarChart
                  data={buildRadarData(result.decision_a)}
                  year={year}
                  colors={COLORS_A}
                  nodeLabels={RADAR_NODE_LABELS}
                />
              </div>
              <div className="compare-radar-side">
                <div className="compare-radar-label" style={{ color: '#ff2a7a' }}>
                  B: {result.decision_b.decision.slice(0, 50)}
                </div>
                <RadarChart
                  data={buildRadarData(result.decision_b)}
                  year={year}
                  colors={COLORS_B}
                  nodeLabels={RADAR_NODE_LABELS}
                />
              </div>
            </div>

            {/* Regret trade-offs */}
            <div className="compare-regrets">
              {['decision_a', 'decision_b'].map((key, idx) => {
                const sim = result[key];
                const color = idx === 0 ? '#00f2ff' : '#ff2a7a';
                const label = idx === 0 ? 'A' : 'B';
                return (
                  <div key={key} className="compare-regret-col">
                    <div className="compare-regret-header" style={{ color }}>
                      REGRET TRADE-OFFS — {label}
                    </div>
                    {Object.entries(sim.regrets || {}).map(([tl, regret]) => (
                      <div key={tl} className="compare-regret-item">
                        <strong style={{ color }}>{tl}</strong>
                        <p>{regret.lost_opportunity}</p>
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>

            <div className="modal-buttons" style={{ marginTop: '1.5rem' }}>
              <button type="button" onClick={() => setResult(null)}>← NEW COMPARISON</button>
              <button type="button" onClick={onClose}>CLOSE</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default CompareTwoModal;
