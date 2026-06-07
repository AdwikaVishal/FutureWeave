import React, { useState } from 'react';
import { monteCarlo } from '../api';

function pct(v) {
  if (v == null) return 0;
  return v > 1 ? v : Math.round(v * 1000) / 10;
}

function dataQualityColor(pctVal) {
  if (pctVal >= 80) return '#00ff88';
  if (pctVal >= 50) return '#ffaa00';
  return '#ff2a7a';
}

function normalizeMC(data) {
  const n = { ...data };
  n.success_probability = pct(data.success_probability);
  n.failure_probability = pct(data.failure_probability);
  n.neutral_probability = pct(data.neutral_probability);
  n.regret_probability = pct(data.regret_probability);

  // Preserve source attribution from backend
  n.data_sources = data.data_sources || {};
  n.live_data = data.live_data || {};

  // Use node_distributions if already provided by backend
  if (data.node_distributions || !data.income_distribution) return n;

  // Legacy: build node_distributions from simple income/happiness distributions
  const ic = data.income_distribution || {};
  const hc = data.happiness_distribution || {};
  const nd = data.node_distributions || {};
  const pctiles = data.percentiles || {};

  n.node_distributions = {
    ...nd,
    income: { mean: ic.mean || 50, median: ic.median || 50, std: ic.std_dev || 10, min: ic.min || 0, max: ic.max || 100 },
    happiness: { mean: hc.mean || 50, median: hc.median || 50, std: hc.std_dev || 10, min: hc.lower || 0, max: hc.upper || 100 },
  };
  n.percentiles = {
    ...pctiles,
    income: { p5: ic.lower || 30, p25: 40, p50: ic.median || 50, p75: 60, p95: ic.upper || 80 },
    happiness: { p5: hc.lower || 30, p25: 40, p50: hc.median || 50, p75: 60, p95: hc.upper || 80 },
  };

  // Generic best/expected/worst based on available distributions
  const distKeys = Object.keys(n.node_distributions);
  const buildCase = (factor, defaultVal) => {
    const c = {};
    distKeys.forEach((k) => {
      const d = n.node_distributions[k] || {};
      const mean = d.mean || 50;
      const min = d.min != null ? d.min : 0;
      const max = d.max != null ? d.max : 100;
      c[k] = Math.max(min, Math.min(max, mean + (mean - 50) * factor + defaultVal[k] || 0));
    });
    return c;
  };

  n.best_case = n.best_case || buildCase(0.5, { income: 30, career_growth: 25, happiness: 30 });
  n.expected_case = n.expected_case || buildCase(0, {});
  n.worst_case = n.worst_case || buildCase(-0.5, { income: -30, career_growth: -25, happiness: -30 });

  n.risk_metrics = n.risk_metrics || {
    value_at_risk_95: (hc.mean || 50) - (hc.lower || 30),
    expected_shortfall: hc.lower || 30,
    coefficient_of_variation: (hc.std_dev || 10) / Math.max(hc.mean || 50, 1),
    regret_at_risk: n.regret_probability || 0,
    downside_deviation: 15,
  };

  return n;
}

function SourceAttribution({ sources }) {
  if (!sources || Object.keys(sources).length === 0) return null;
  const summary = sources._summary || {};
  return (
    <div className="data-panel">
      <div className="panel-header">
        <span>Data Sources</span>
        <span style={{ fontSize: '0.75rem', color: dataQualityColor(summary.data_quality_pct) }}>
          Quality: {summary.data_quality_pct || 0}%
        </span>
      </div>
      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
        {Object.entries(sources).filter(([k]) => k !== '_summary').map(([provider, info]) => {
          const ok = info && info.available;
          return (
            <div key={provider} className="composite-item" style={{ flex: '1 1 180px', opacity: ok ? 1 : 0.5 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ color: ok ? '#00ff88' : '#ff2a7a', fontSize: '1rem' }}>{ok ? '✓' : '✗'}</span>
                <span className="composite-label" style={{ textTransform: 'capitalize' }}>{provider}</span>
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                {ok ? info.url : (info.fallback || 'unavailable')}
              </div>
              {info.metrics && info.metrics.length > 0 && (
                <div style={{ fontSize: '0.7rem', color: '#7b9fff', marginTop: 4 }}>
                  {info.metrics.join(', ')}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function LiveDataPreview({ liveData }) {
  if (!liveData || Object.keys(liveData).length === 0) return null;
  const show = { ...liveData };
  delete show.sources;
  const entries = Object.entries(show).slice(0, 12);
  return (
    <div className="data-panel" style={{ borderColor: '#3b82f640' }}>
      <div className="panel-header">
        <span>Economic Parameters</span>
      </div>
      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
        {entries.map(([k, v]) => (
          <div key={k} className="composite-item" style={{ flex: '1 1 140px' }}>
            <span className="composite-label">{k.replace(/_/g, ' ')}</span>
            <span className="composite-value" style={{ color: '#3b82f6', fontFamily: 'var(--font-mono)' }}>
              {typeof v === 'number' ? v.toFixed(2) : Array.isArray(v) ? v.join(' - ') : String(v)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function MonteCarloAnalysis({ decision, context }) {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [iterations, setIterations] = useState(100);
  const [localDecision, setLocalDecision] = useState(decision || '');

  const handleRun = async () => {
    if (!localDecision.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await monteCarlo(localDecision, context, iterations);
      setResult(normalizeMC(data));
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  };

  const nodeNames = result?.node_distributions ? Object.keys(result.node_distributions) : [];

  return (
    <div className="mc-analysis">
      <div className="input-area" style={{ maxWidth: 600, margin: '0 auto 2rem' }}>
        <input
          className="decision-input"
          placeholder="Enter a decision for Monte Carlo analysis..."
          value={localDecision}
          onChange={(e) => setLocalDecision(e.target.value)}
        />
        <div className="mc-controls" style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <label style={{ color: 'var(--text-muted)', fontSize: '0.8rem', fontFamily: 'var(--font-mono)' }}>
            Iterations:
            <input
              type="number"
              min={10}
              max={10000}
              value={iterations}
              onChange={(e) => setIterations(Number(e.target.value))}
              style={{ width: 70, marginLeft: 8, background: 'rgba(0,0,0,0.4)', border: '1px solid var(--border-dim)', borderRadius: 6, padding: '0.3rem 0.5rem', color: 'var(--text-primary)' }}
            />
          </label>
          <button className="cf-submit-btn" style={{ flex: 1 }} onClick={handleRun} disabled={loading}>
            {loading ? 'RUNNING...' : '▶ RUN MONTE CARLO'}
          </button>
        </div>
        {error && <div className="error" style={{ marginTop: '0.75rem' }}>⚠ {error}</div>}
      </div>

      {result && (
        <div className="mc-results">
          <div className="mc-hero">
            <div className="mc-hero-stats">
              <div className="mc-stat-box" style={{ borderColor: '#00ff88' }}>
                <div className="mc-stat-value" style={{ color: '#00ff88' }}>{result.success_probability}%</div>
                <div className="mc-stat-label">Success</div>
              </div>
              <div className="mc-stat-box" style={{ borderColor: '#ffaa00' }}>
                <div className="mc-stat-value" style={{ color: '#ffaa00' }}>{result.neutral_probability}%</div>
                <div className="mc-stat-label">Neutral</div>
              </div>
              <div className="mc-stat-box" style={{ borderColor: '#ff2a7a' }}>
                <div className="mc-stat-value" style={{ color: '#ff2a7a' }}>{result.failure_probability}%</div>
                <div className="mc-stat-label">Failure</div>
              </div>
              <div className="mc-stat-box" style={{ borderColor: '#f97316' }}>
                <div className="mc-stat-value" style={{ color: '#f97316' }}>{result.regret_probability}%</div>
                <div className="mc-stat-label">Regret Risk</div>
              </div>
              <div className="mc-stat-box" style={{ borderColor: '#7b2fff' }}>
                <div className="mc-stat-value" style={{ color: '#7b2fff' }}>{(result.iterations || result.iterations_run || 0).toLocaleString()}</div>
                <div className="mc-stat-label">Simulations</div>
              </div>
            </div>
          </div>

          <SourceAttribution sources={result.data_sources} />
          <LiveDataPreview liveData={result.live_data} />

          {result.best_case && (
            <div className="data-panel">
              <div className="panel-header">
                <span>Best Case (P90)</span>
              </div>
              <div className="composite-grid" style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                {Object.entries(result.best_case).map(([k, v]) => (
                  <div key={k} className="composite-item" style={{ flex: '1 1 120px' }}>
                    <span className="composite-label">{k.replace(/_/g, ' ')}</span>
                    <span className="composite-value" style={{ color: '#00ff88', fontSize: '1.1rem' }}>{typeof v === 'number' ? v.toFixed(1) : v}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.expected_case && (
            <div className="data-panel">
              <div className="panel-header">
                <span>Expected Case (Mean)</span>
              </div>
              <div className="composite-grid" style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                {Object.entries(result.expected_case).map(([k, v]) => (
                  <div key={k} className="composite-item" style={{ flex: '1 1 120px' }}>
                    <span className="composite-label">{k.replace(/_/g, ' ')}</span>
                    <span className="composite-value" style={{ color: '#3b82f6', fontSize: '1.1rem' }}>{typeof v === 'number' ? v.toFixed(1) : v}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.worst_case && (
            <div className="data-panel">
              <div className="panel-header">
                <span>Worst Case (P10)</span>
              </div>
              <div className="composite-grid" style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                {Object.entries(result.worst_case).map(([k, v]) => (
                  <div key={k} className="composite-item" style={{ flex: '1 1 120px' }}>
                    <span className="composite-label">{k.replace(/_/g, ' ')}</span>
                    <span className="composite-value" style={{ color: '#ff2a7a', fontSize: '1.1rem' }}>{typeof v === 'number' ? v.toFixed(1) : v}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {nodeNames.length > 0 && (
            <div className="data-panel">
              <div className="panel-header">
                <span>Distribution by Dimension</span>
              </div>
              <div className="composite-grid">
                {nodeNames.map((node) => {
                  const dist = result.node_distributions[node];
                  const perc = result.percentiles?.[node] || {};
                  return (
                    <div key={node} className="composite-item">
                      <span className="composite-label">{node.replace(/_/g, ' ')}</span>
                      <div className="composite-bar-track">
                        <div className="composite-bar-fill" style={{ width: `${dist.mean || 50}%`, background: '#7b2fff' }} />
                      </div>
                      <div style={{ display: 'flex', gap: '0.5rem', fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                        <span>μ={dist.mean?.toFixed(1)}</span>
                        <span>σ={dist.std?.toFixed(1)}</span>
                        {perc.p5 != null && <span>P5={perc.p5.toFixed(0)}</span>}
                        {perc.p95 != null && <span>P95={perc.p95.toFixed(0)}</span>}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {result.risk_metrics && Object.keys(result.risk_metrics).length > 0 && (
            <div className="data-panel">
              <div className="panel-header">
                <span>Risk Metrics</span>
              </div>
              <div className="composite-grid" style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                {Object.entries(result.risk_metrics).map(([k, v]) => (
                  <div key={k} className="composite-item" style={{ flex: '1 1 150px' }}>
                    <span className="composite-label">{k.replace(/_/g, ' ')}</span>
                    <span className="composite-value" style={{ color: '#f97316' }}>{typeof v === 'number' ? v.toFixed(2) : v}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.timeline_comparison && Object.keys(result.timeline_comparison).length > 0 && (
            <div className="data-panel">
              <div className="panel-header">
                <span>Timeline Comparison</span>
              </div>
              <div className="composite-grid" style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                {Object.entries(result.timeline_comparison).map(([k, v]) => {
                  const mv = typeof v === 'object' ? (v.mean ?? v.happiness?.mean ?? 0) : v;
                  const sv = typeof v === 'object' ? (v.std ?? v.happiness?.std ?? 0) : 0;
                  return (
                    <div key={k} className="composite-item" style={{ flex: '1 1 150px' }}>
                      <span className="composite-label">{k}</span>
                      <span className="composite-value" style={{ color: '#3b82f6' }}>
                        μ={typeof mv === 'number' ? mv.toFixed(1) : mv}
                        {sv ? ` σ=${typeof sv === 'number' ? sv.toFixed(1) : sv}` : ''}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
