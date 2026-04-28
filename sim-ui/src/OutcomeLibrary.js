/**
 * OutcomeLibrary.js
 *
 * Public "What actually happened" page — anonymised, aggregated longitudinal outcomes.
 *
 * Props:
 *   onClose – fn()
 */
import axios from 'axios';
import React, { useEffect, useState } from 'react';

const LANE_COLORS = { 'Timeline A': '#00f2ff', 'Timeline B': '#ff2a7a', 'Timeline C': '#7b2fff' };

function OutcomeLibrary({ onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios
      .get('/outcomes?limit=30')
      .then((res) => setData(res.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div
      className="modal-overlay"
      onClick={onClose}
      onKeyDown={(e) => { if (e.key === 'Escape') onClose(); }}
      role="button"
      tabIndex={-1}
    >
      <div
        className="modal-content outcome-modal"
        onClick={(e) => e.stopPropagation()}
        role="presentation"
      >
        <h3>📚 OUTCOME LIBRARY</h3>
        <p className="compare-hint">
          Real anonymised outcomes from users who reported back. This is what actually happened.
        </p>

        {loading && <div className="loader" style={{ padding: '1rem' }}>Loading outcomes...</div>}

        {data && (
          <>
            {/* Aggregate stats */}
            {data.aggregate.total_followups > 0 && (
              <div className="outcome-aggregate">
                <span className="outcome-agg-total">
                  {data.aggregate.total_followups} follow-ups collected
                </span>
                <div className="outcome-agg-dist">
                  {Object.entries(data.aggregate.timeline_distribution).map(([tl, count]) => (
                    <span
                      key={tl}
                      className="outcome-agg-tag"
                      style={{ borderColor: LANE_COLORS[tl] || '#aaa', color: LANE_COLORS[tl] || '#aaa' }}
                    >
                      {tl}: {count}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {data.outcomes.length === 0 ? (
              <div className="peer-empty" style={{ marginTop: '1rem' }}>
                No outcomes yet. Run a simulation and report back in 6 months!
              </div>
            ) : (
              <div className="outcome-list">
                {data.outcomes.map((o) => (
                  <div key={o.decision_preview + o.months_after} className="outcome-card">
                    <div className="outcome-card-top">
                      <span className="outcome-decision">{o.decision_preview}</span>
                      {o.chosen_timeline && (
                        <span
                          className="outcome-tl-badge"
                          style={{
                            color: LANE_COLORS[o.chosen_timeline] || '#aaa',
                            borderColor: LANE_COLORS[o.chosen_timeline] || '#aaa',
                          }}
                        >
                          {o.chosen_timeline}
                        </span>
                      )}
                    </div>
                    <div className="outcome-card-meta">
                      {o.context.age && <span>Age {o.context.age}</span>}
                      {o.context.location && <span>· {o.context.location}</span>}
                      {o.months_after != null && <span>· {o.months_after}mo later</span>}
                    </div>
                    {o.feedback_preview && (
                      <p className="outcome-feedback">
                        &ldquo;
                        {o.feedback_preview}
                        &rdquo;
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        <div className="modal-buttons" style={{ marginTop: '1.5rem' }}>
          <button type="button" onClick={onClose}>CLOSE</button>
        </div>
      </div>
    </div>
  );
}

export default OutcomeLibrary;
