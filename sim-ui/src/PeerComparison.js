/**
 * PeerComparison.js
 *
 * Shows anonymised peer outcome stats: "X% of similar users ended up in Timeline B."
 *
 * Props:
 *   decision – string (used for keyword matching)
 */
import React, { useEffect, useState } from 'react';
import API from './api';

const LANE_COLORS = { 'Timeline A': '#00f2ff', 'Timeline B': '#ff2a7a', 'Timeline C': '#7b2fff' };

function PeerComparison({ decision }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!decision) return;
    const keywords = decision.split(' ').slice(0, 5).join(',');
    API
      .get(`/peer-comparison?decision_keywords=${encodeURIComponent(keywords)}`)
      .then((res) => setData(res.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [decision]);

  if (loading) return null;
  if (!data || data.total === 0) {
    return (
      <div className="peer-comparison">
        <span className="peer-title">👥 PEER COMPARISON</span>
        <p className="peer-empty">No follow-up data yet — be the first to report back!</p>
      </div>
    );
  }

  return (
    <div className="peer-comparison">
      <span className="peer-title">👥 PEER COMPARISON</span>
      <p className="peer-subtitle">{data.message}</p>
      <div className="peer-bars">
        {Object.entries(data.stats).map(([tl, { pct, count }]) => (
          <div key={tl} className="peer-bar-row">
            <span className="peer-bar-label" style={{ color: LANE_COLORS[tl] || '#aaa' }}>{tl}</span>
            <div className="peer-bar-track">
              <div
                className="peer-bar-fill"
                style={{
                  width: `${pct}%`,
                  background: LANE_COLORS[tl] || '#aaa',
                  boxShadow: `0 0 6px ${LANE_COLORS[tl] || '#aaa'}`,
                }}
              />
            </div>
            <span className="peer-bar-pct">{pct}%</span>
            <span className="peer-bar-count">({count})</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default PeerComparison;
