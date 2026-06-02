/**
 * JobMarketPanel.js
 *
 * Shows live job market demand for the user's role/location and skills.
 *
 * Props:
 *   role     – string (detected from simulation grounding)
 *   location – string
 *   skills   – string (comma-separated from context form)
 */
import React, { useEffect, useState } from 'react';
import API from './api';

const TREND_COLOR = { rising: '#00ff88', stable: '#ffaa00', unknown: '#6a6a9a' };
const TREND_ICON = { rising: '↑', stable: '→', unknown: '?' };

function JobMarketPanel({ role, location, skills }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!role) {
      console.log('[JobMarketPanel] No role provided, skipping fetch');
      setLoading(false);
      return;
    }

    console.log('[JobMarketPanel] Fetching job market data for:', { role, location, skills });
    setLoading(true);
    setError(null);

    API
      .get('/job-market', { params: { role, location, skills } })
      .then((res) => {
        console.log('[JobMarketPanel] API response:', res.data);
        setData(res.data);
      })
      .catch((err) => {
        console.error('[JobMarketPanel] API error:', err.response?.data || err.message);
        setData(null);
        setError(err.response?.data?.detail || err.message || 'Failed to load job market data');
      })
      .finally(() => setLoading(false));
  }, [role, location, skills]);

  if (loading) {
    return <div className="job-market-loading">⟳ Loading job market data...</div>;
  }

  if (error) {
    return (
      <div className="job-market-panel">
        <div className="job-market-header">
          <span className="job-market-title">📈 JOB MARKET</span>
        </div>
        <div className="job-market-error" style={{ padding: '1rem', color: 'var(--glow-pink)' }}>
          ⚠ {error}
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="job-market-panel">
        <div className="job-market-header">
          <span className="job-market-title">📈 JOB MARKET</span>
        </div>
        <div className="job-market-error" style={{ padding: '1rem', color: 'var(--text-muted)' }}>
          No job market data available.
        </div>
      </div>
    );
  }

  const ds = data.data_sources || {};
  const salaryRange = Array.isArray(data.salary_range_lpa) ? data.salary_range_lpa : null;
  const skillDemand = data.skill_demand || {};

  return (
    <div className="job-market-panel">
      <div className="job-market-header">
        <span className="job-market-title">📈 LIVE JOB MARKET</span>
        <span className="job-market-meta">
          {data.role || 'Unknown role'} · {data.location || 'Unknown location'}
        </span>
      </div>

      <div className="job-market-stats">
        {salaryRange && (
          <div className="jm-stat">
            <span className="jm-stat-label">Salary Range</span>
            <span className="jm-stat-value" style={{ color: 'var(--glow-cyan)' }}>
              ₹{salaryRange[0]}–{salaryRange[1]} LPA
            </span>
            <span className="jm-stat-source">📊 {ds.salary || 'Unknown source'}</span>
          </div>
        )}
        {data.unemployment_pct != null && (
          <div className="jm-stat">
            <span className="jm-stat-label">Unemployment</span>
            <span className="jm-stat-value" style={{ color: 'var(--glow-pink)' }}>
              {Number(data.unemployment_pct).toFixed(1)}%
            </span>
            <span className="jm-stat-source">🌐 {ds.macro || 'World Bank'}</span>
          </div>
        )}
        {data.gdp_growth_pct != null && (
          <div className="jm-stat">
            <span className="jm-stat-label">GDP Growth</span>
            <span className="jm-stat-value" style={{ color: '#00ff88' }}>
              {Number(data.gdp_growth_pct).toFixed(1)}%
            </span>
            <span className="jm-stat-source">🌐 {ds.macro || 'World Bank'}</span>
          </div>
        )}
        {data.adzuna?.total_jobs ? (
          <div className="jm-stat">
            <span className="jm-stat-label">Live Job Listings</span>
            <span className="jm-stat-value" style={{ color: '#ffaa00' }}>
              {Number(data.adzuna.total_jobs).toLocaleString()}
            </span>
            <span className="jm-stat-source">🔍 Adzuna</span>
          </div>
        ) : null}
      </div>

      {Object.keys(skillDemand).length > 0 && (
        <div className="jm-skills">
          <div className="jm-skills-title">SKILL DEMAND</div>
          {Object.entries(skillDemand).map(([skill, info]) => (
            <div key={skill} className="jm-skill-row">
              <span className="jm-skill-name">{skill}</span>
              {info && info.growth_pct != null && (
                <span
                  className="jm-skill-growth"
                  style={{ color: TREND_COLOR[info.trend] || '#aaa' }}
                >
                  {TREND_ICON[info.trend] || '?'} {info.growth_pct}% YoY
                </span>
              )}
              {info?.jobs_india ? (
                <span className="jm-skill-jobs">{Number(info.jobs_india).toLocaleString()} jobs</span>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default JobMarketPanel;
