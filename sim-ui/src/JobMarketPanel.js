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

  useEffect(() => {
    if (!role) return;
    API
      .get('/job-market', { params: { role, location, skills } })
      .then((res) => setData(res.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [role, location, skills]);

  if (loading) return <div className="job-market-loading">⟳ Loading job market data...</div>;
  if (!data) return null;

  return (
    <div className="job-market-panel">
      <div className="job-market-header">
        <span className="job-market-title">📈 LIVE JOB MARKET</span>
        <span className="job-market-meta">
          {data.role} · {data.location}
        </span>
      </div>

      <div className="job-market-stats">
        {data.salary_range_lpa && (
          <div className="jm-stat">
            <span className="jm-stat-label">Salary Range</span>
            <span className="jm-stat-value" style={{ color: 'var(--glow-cyan)' }}>
              ₹{data.salary_range_lpa[0]}–{data.salary_range_lpa[1]} LPA
            </span>
            <span className="jm-stat-source">📊 {data.data_sources.salary}</span>
          </div>
        )}
        {data.unemployment_pct != null && (
          <div className="jm-stat">
            <span className="jm-stat-label">Unemployment</span>
            <span className="jm-stat-value" style={{ color: 'var(--glow-pink)' }}>
              {data.unemployment_pct.toFixed(1)}%
            </span>
            <span className="jm-stat-source">🌐 {data.data_sources.macro}</span>
          </div>
        )}
        {data.gdp_growth_pct != null && (
          <div className="jm-stat">
            <span className="jm-stat-label">GDP Growth</span>
            <span className="jm-stat-value" style={{ color: '#00ff88' }}>
              {data.gdp_growth_pct.toFixed(1)}%
            </span>
            <span className="jm-stat-source">🌐 {data.data_sources.macro}</span>
          </div>
        )}
        {data.adzuna?.total_jobs && (
          <div className="jm-stat">
            <span className="jm-stat-label">Live Job Listings</span>
            <span className="jm-stat-value" style={{ color: '#ffaa00' }}>
              {data.adzuna.total_jobs.toLocaleString()}
            </span>
            <span className="jm-stat-source">🔍 Adzuna</span>
          </div>
        )}
      </div>

      {Object.keys(data.skill_demand || {}).length > 0 && (
        <div className="jm-skills">
          <div className="jm-skills-title">SKILL DEMAND</div>
          {Object.entries(data.skill_demand).map(([skill, info]) => (
            <div key={skill} className="jm-skill-row">
              <span className="jm-skill-name">{skill}</span>
              {info.growth_pct != null && (
                <span
                  className="jm-skill-growth"
                  style={{ color: TREND_COLOR[info.trend] || '#aaa' }}
                >
                  {TREND_ICON[info.trend]} {info.growth_pct}% YoY
                </span>
              )}
              {info.jobs_india && (
                <span className="jm-skill-jobs">{info.jobs_india.toLocaleString()} jobs</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default JobMarketPanel;
