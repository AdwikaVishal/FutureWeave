/**
 * ScoreResult.js
 *
 * Displays the personalised timeline scores returned by POST /score.
 *
 * Props:
 *   data – { scores, ranked, recommendation, weights_used }
 */
import React from 'react';

const LANE_COLORS = ['#00f2ff', '#ff2a7a', '#7b2fff'];

function ScoreResult({ data }) {
  if (!data) return null;
  const { ranked, recommendation } = data;

  const maxScore = ranked[0]?.score || 1;

  return (
    <div className="score-result">
      <div className="score-result-header">
        <span className="score-result-title">⟁ YOUR PERSONALISED RANKING</span>
        {recommendation && (
          <span className="score-recommendation">
            Best fit: <strong style={{ color: 'var(--glow-cyan)' }}>{recommendation}</strong>
          </span>
        )}
      </div>
      <div className="score-bars">
        {ranked.map(({ timeline, score }, i) => (
          <div key={timeline} className="score-bar-row">
            <span className="score-bar-label" style={{ color: LANE_COLORS[i] || '#00f2ff' }}>
              {timeline}
            </span>
            <div className="score-bar-track">
              <div
                className="score-bar-fill"
                style={{
                  width: `${(score / maxScore) * 100}%`,
                  background: LANE_COLORS[i] || '#00f2ff',
                  boxShadow: `0 0 8px ${LANE_COLORS[i] || '#00f2ff'}`,
                }}
              />
            </div>
            <span className="score-bar-value" style={{ color: LANE_COLORS[i] || '#00f2ff' }}>
              {score.toFixed(1)}
            </span>
            {i === 0 && <span className="score-badge">★ BEST FIT</span>}
          </div>
        ))}
      </div>
    </div>
  );
}

export default ScoreResult;
