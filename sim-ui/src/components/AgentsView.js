import React from 'react';

const AGENT_COLORS = {
  financial: '#10b981', risk: '#ef4444', opportunity: '#06b6d4',
  health: '#f59e0b', relationship: '#ec4899', time: '#84cc16',
  happiness: '#a855f7', identity: '#6366f1', career: '#3b82f6',
  strategic: '#14b8a6', lifestyle: '#eab308', economic: '#8b5cf6',
};

export default function AgentsView({ agents }) {
  if (!agents || agents.length === 0) {
    return (
      <div className="agents-view">
        <div className="empty-state">
          <p>No agent analysis available for this simulation.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="agents-view">
      <div className="agents-header" style={{ marginBottom: '1.5rem', textAlign: 'center' }}>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
          Multi-agent analysis evaluated your decision from {agents.length} expert perspectives.
        </p>
      </div>

      <div className="agents-grid">
        {agents.sort((a, b) => b.score - a.score).map((agent) => {
          const color = AGENT_COLORS[agent.name] || '#6a6a9a';
          return (
            <div key={agent.name} className="agent-card" style={{ borderLeftColor: color, marginBottom: 12 }}>
              <div className="agent-header">
                <div className="agent-name-section">
                  <div className="agent-name" style={{ color }}>{agent.name}</div>
                  {agent.verdict && <div className="agent-verdict" style={{ fontSize: 11, color: '#888' }}>{agent.verdict}</div>}
                </div>
                <div className="agent-scores">
                  <div className="agent-score" style={{ color }}>{agent.score.toFixed(0)}</div>
                  <div className="agent-confidence">{agent.confidence.toFixed(0)}% confident</div>
                </div>
              </div>

              {agent.reasoning && (
                <div className="agent-reasoning">{agent.reasoning}</div>
              )}

              <div className="agent-details" style={{ display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 12 }}>
                {agent.evidence?.length > 0 && (
                  <div className="agent-section" style={{ flex: '1 1 200px' }}>
                    <div className="section-title">Evidence</div>
                    {agent.evidence.slice(0, 4).map((e, i) => (
                      <div key={i} style={{ marginBottom: 2, color: '#6a6a9a' }}>• {e}</div>
                    ))}
                  </div>
                )}
                {agent.impact_factors?.length > 0 && (
                  <div className="agent-section" style={{ flex: '1 1 200px' }}>
                    <div className="section-title">Impact Factors</div>
                    {agent.impact_factors.map((f, i) => (
                      <div key={i} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                        <span>{f.factor}</span>
                        <span style={{ color: f.delta >= 0 ? '#10b981' : '#ef4444' }}>
                          {f.delta >= 0 ? '+' : ''}{f.delta?.toFixed(0)} pts
                        </span>
                      </div>
                    ))}
                  </div>
                )}
                {agent.option_rankings?.length > 0 && (
                  <div className="agent-section" style={{ flex: '1 1 200px' }}>
                    <div className="section-title">Option Rankings</div>
                    {agent.option_rankings.slice(0, 5).map((opt, i) => (
                      <div key={i} style={{ marginBottom: 2 }}>
                        {i + 1}. {opt} {agent.per_option_scores?.[opt] !== undefined ? `(${agent.per_option_scores[opt].toFixed(0)})` : ''}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="agent-footer" style={{ marginTop: 8, display: 'flex', gap: 8, alignItems: 'center', fontSize: 12 }}>
                <span className="tag" style={{
                  background: agent.impact === 'positive' ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)',
                  color: agent.impact === 'positive' ? '#10b981' : '#ef4444',
                  padding: '2px 8px', borderRadius: 4,
                }}>
                  {agent.impact}
                </span>
                <span style={{ color: '#6a6a9a' }}>Score: {agent.score.toFixed(0)}/100</span>
                <span style={{ color: '#6a6a9a' }}>| Conf: {agent.confidence.toFixed(0)}%</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
