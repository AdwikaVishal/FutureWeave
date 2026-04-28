/**
 * ValuesSlider.js
 *
 * Lets the user set priority weights across causal nodes (income, happiness, etc.)
 * Weights are normalised to sum to 100% and sent to POST /score.
 *
 * Props:
 *   simulationId  – int
 *   onScore       – fn({ scores, ranked, recommendation, weights_used })
 */
import axios from 'axios';
import React, { useState, useCallback, useEffect } from 'react';

const NODES = [
  { key: 'income', label: 'Income', color: '#00f2ff' },
  { key: 'happiness', label: 'Happiness', color: '#ffffff' },
  { key: 'career_growth', label: 'Career Growth', color: '#7b2fff' },
  { key: 'health', label: 'Health', color: '#00ff88' },
  { key: 'relationships', label: 'Relationships', color: '#ffaa00' },
  { key: 'opportunity', label: 'Opportunity', color: '#ff6600' },
  { key: 'stress', label: 'Low Stress', color: '#ff2a7a' },
];

const DEFAULT_WEIGHTS = Object.fromEntries(
  NODES.map((n) => [n.key, Math.round(100 / NODES.length)]),
);

function ValuesSlider({ simulationId, onScore }) {
  const [weights, setWeights] = useState(DEFAULT_WEIGHTS);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const total = Object.values(weights).reduce((a, b) => a + b, 0);

  // When any slider changes, redistribute rounding error onto 'income'
  // so the total always reads exactly 100 in the UI hint.
  useEffect(() => {
    const sum = Object.values(weights).reduce((a, b) => a + b, 0);
    if (sum === 0 || Math.abs(sum - 100) <= 0.5) return;
    const factor = 100 / sum;
    const normalised = Object.fromEntries(
      Object.entries(weights).map(([k, v]) => [k, Math.round(v * factor)]),
    );
    // Fix rounding drift on the first key
    const normSum = Object.values(normalised).reduce((a, b) => a + b, 0);
    if (normSum !== 100) {
      const firstKey = Object.keys(normalised)[0];
      normalised[firstKey] += 100 - normSum;
    }
    setWeights(normalised);
  }, [weights]);

  const handleChange = useCallback((key, val) => {
    setWeights((prev) => ({ ...prev, [key]: Number(val) }));
  }, []);

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);
    try {
      // Normalise to fractions
      const normWeights = Object.fromEntries(
        Object.entries(weights).map(([k, v]) => [k, v / total]),
      );
      const res = await axios.post('/score', {
        simulation_id: simulationId,
        weights: normWeights,
      });
      onScore(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Score calculation failed.');
    }
    setLoading(false);
  };

  return (
    <div className="values-slider-panel">
      <div className="values-slider-header">
        <span className="values-slider-title">⟁ WHAT MATTERS TO YOU?</span>
        <span className="values-total" style={{ color: total === 100 ? 'var(--glow-cyan)' : 'var(--glow-pink)' }}>
          {total}% allocated
        </span>
      </div>
      <p className="values-slider-hint">
        Drag the sliders to weight your priorities. We&apos;ll score each timeline for you.
      </p>
      <div className="values-sliders">
        {NODES.map(({ key, label, color }) => (
          <div key={key} className="values-slider-row">
            <span className="values-slider-label" style={{ color }}>{label}</span>
            <input
              type="range"
              min={0}
              max={100}
              value={weights[key]}
              onChange={(e) => handleChange(key, e.target.value)}
              className="values-range"
              style={{ '--slider-color': color }}
            />
            <span className="values-slider-pct" style={{ color }}>{weights[key]}%</span>
          </div>
        ))}
      </div>
      {error && <div className="values-error">⚠ {error}</div>}
      <button
        type="button"
        className="values-score-btn"
        onClick={handleSubmit}
        disabled={loading || total === 0}
      >
        {loading ? 'SCORING...' : '▶ SCORE MY TIMELINES'}
      </button>
    </div>
  );
}

export default ValuesSlider;
