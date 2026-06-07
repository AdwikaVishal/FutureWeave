import React from 'react';

const SCORE_COLOR = (v) => {
  if (v >= 70) return '#00ff88';
  if (v >= 40) return '#ffaa00';
  return '#ff2a7a';
};

export default function ConfidenceView({ simulationResult }) {
  if (!simulationResult) {
    return (
      <div className="empty-state">
        <p>Run a simulation to see confidence analysis.</p>
      </div>
    );
  }

  const { data_confidence, data_confidence_explanation, data_warnings, data_monitoring } = simulationResult;

  if (data_confidence == null) {
    return (
      <div className="empty-state">
        <p>Confidence data not available from this simulation.</p>
      </div>
    );
  }

  const monitoring = data_monitoring || {};
  const monitoringEntries = Object.entries(monitoring);

  return (
    <div className="confidence-view">
      <div className="confidence-header" style={{ display: 'flex', gap: '1.5rem', alignItems: 'flex-start', flexWrap: 'wrap', marginBottom: '1.5rem' }}>
        <div className="overall-gauge" style={{
          border: `2px solid ${SCORE_COLOR(data_confidence)}`,
          borderRadius: 16, padding: '1.5rem', textAlign: 'center', minWidth: 180, background: 'var(--bg-card)',
        }}>
          <div className="gauge-value" style={{ fontSize: '2.5rem', fontWeight: 700, color: SCORE_COLOR(data_confidence) }}>
            {data_confidence}%
          </div>
          <div className="gauge-label" style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: 4 }}>
            Overall Confidence
          </div>
          <div className="gauge-tier" style={{
            marginTop: 8, background: SCORE_COLOR(data_confidence), color: '#0a0a1a',
            padding: '2px 12px', borderRadius: 20, fontSize: '0.7rem', fontWeight: 700, fontFamily: 'var(--font-mono)', display: 'inline-block',
          }}>
            {data_confidence >= 70 ? 'HIGH' : data_confidence >= 40 ? 'MEDIUM' : 'LOW'}
          </div>
        </div>

        {data_confidence_explanation && (
          <div style={{ flex: 1, minWidth: 200, padding: '1rem', background: 'var(--bg-card)', borderRadius: 12, border: '1px solid var(--border-dim)' }}>
            <div style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--glow-cyan)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 1 }}>
              Explanation
            </div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
              {data_confidence_explanation}
            </div>
          </div>
        )}
      </div>

      {data_warnings && data_warnings.length > 0 && (
        <div className="data-panel" style={{ marginBottom: '1rem' }}>
          <div className="panel-header">
            <span>Data Warnings</span>
          </div>
          <div className="warnings-list">
            {data_warnings.map((w, i) => (
              <div key={i} className="warning-item">⚠ {w}</div>
            ))}
          </div>
        </div>
      )}

      {monitoringEntries.length > 0 && (
        <div className="data-panel">
          <div className="panel-header">
            <span>Data Monitoring</span>
          </div>
          <div className="composite-grid">
            {monitoringEntries.map(([key, val]) => (
              <div key={key} className="composite-item">
                <span className="composite-label">{key.replace(/_/g, ' ')}</span>
                <span className="composite-value" style={{ color: '#3b82f6', fontSize: '0.85rem' }}>
                  {typeof val === 'object' ? JSON.stringify(val).slice(0, 80) : String(val).slice(0, 80)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {simulationResult.data_sources && (
        <div className="data-panel" style={{ marginTop: '1rem' }}>
          <div className="panel-header">
            <span>Data Sources</span>
          </div>
          <div className="composite-grid" style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {Object.entries(simulationResult.data_sources).map(([key, val]) => (
              <div key={key} className="data-chip" style={{ borderColor: val === 'live' ? '#10b981' : '#6a6a9a' }}>
                <span className="data-key">{key.replace(/_/g, ' ')}</span>
                <span className="data-val" style={{ color: val === 'live' ? '#10b981' : '#6a6a9a' }}>
                  {val === 'live' ? '● Live' : '○ Static'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
