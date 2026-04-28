/**
 * DataSourceBadge.js
 *
 * Renders a small inline badge showing the data source for a grounded number.
 * Clicking opens a tooltip with full source details.
 *
 * Props:
 *   node    – causal node key (e.g. "income", "stress")
 *   sources – array from GET /data-sources
 */
import React, { useState } from 'react';

// Static badge map (loaded once at module level, no API call needed)
export const NODE_BADGES = {
  income: { badge: '📊 AmbitionBox + World Bank', url: 'https://www.ambitionbox.com' },
  opportunity: { badge: '🌐 World Bank', url: 'https://data.worldbank.org' },
  stress: { badge: '📋 Deloitte 2023 + World Bank', url: 'https://www2.deloitte.com/in' },
  health: { badge: '🏥 WHO 2022', url: 'https://www.who.int/india' },
  relationships: { badge: '🤝 IHR 2023', url: 'https://www.happinessstudies.academy' },
  happiness: { badge: '😊 WHR 2023', url: 'https://worldhappiness.report' },
  career_growth: { badge: '📊 AmbitionBox', url: 'https://www.ambitionbox.com' },
};

function DataSourceBadge({ node }) {
  const [open, setOpen] = useState(false);
  const info = NODE_BADGES[node];
  if (!info) return null;

  return (
    <span className="ds-badge-wrapper">
      <button
        type="button"
        className="ds-badge"
        onClick={() => setOpen((o) => !o)}
        title={`Data source: ${info.badge}`}
      >
        {info.badge}
      </button>
      {open && (
        <span className="ds-badge-tooltip">
          Source:{' '}
          <a href={info.url} target="_blank" rel="noopener noreferrer">
            {info.badge}
          </a>
          <button type="button" className="ds-badge-close" onClick={() => setOpen(false)}>✕</button>
        </span>
      )}
    </span>
  );
}

export default DataSourceBadge;
