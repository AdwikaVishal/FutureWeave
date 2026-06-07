import React from 'react';

const SCORE_COLOR = (v) => {
  if (v >= 70) return '#00ff88';
  if (v >= 40) return '#ffaa00';
  return '#ff2a7a';
};

export default function Dashboard({ data, decision }) {
  if (!data) return null;

  const { timelines = {}, comparison = {}, causal_data = {}, archetype_labels } = data;

  const timelineEntries = Object.entries(timelines);
  const causalValues = Object.values(causal_data);
  const firstCausal = causalValues[0] || {};
  const y10Scores = firstCausal.Year10 || {};
  const y1Scores = firstCausal.Year1 || {};

  // Derive metric nodes from available causal data (domain-aware)
  const nodeKeys = y10Scores ? Object.keys(y10Scores).filter((k) => k !== '_causal') : [];
  const hasMetric = (k) => nodeKeys.includes(k);

  const metricLabels = {
    income: 'Income', career_growth: 'Career Growth', stress: 'Stress',
    health: 'Health', relationships: 'Relationships', happiness: 'Happiness',
    opportunity: 'Opportunity', fulfillment: 'Fulfillment',
    work_life_balance: 'Work-Life Balance', personal_growth: 'Personal Growth',
    social_connection: 'Social Connection', financial_freedom: 'Financial Freedom',
    emotional_health: 'Emotional Health', compatibility: 'Compatibility',
    communication: 'Communication', future_alignment: 'Future Alignment',
    placement_potential: 'Placement Potential', admission_probability: 'Admission Prob.',
    college_quality: 'College Quality', learning_curve: 'Learning Curve',
    wealth_creation: 'Wealth Creation', wealth_growth: 'Wealth Growth',
    financial_health: 'Financial Health', quality_of_life: 'Quality of Life',
    treatment_efficacy: 'Treatment Efficacy', recovery_rate: 'Recovery Rate',
    treatment_success: 'Treatment Success', recovery_progress: 'Recovery Progress',
    risk_level: 'Risk Level',
  };

  const avgScore = (metric) => {
    const vals = timelineEntries.map((_e, i) => {
      const cv = causalValues[i];
      return (cv && cv.Year10 && cv.Year10[metric]) || null;
    }).filter((v) => v !== null);
    return vals.length > 0 ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
  };

  let primaryMetric = 'happiness';
  if (hasMetric('happiness')) {
    primaryMetric = 'happiness';
  } else if (hasMetric('quality_of_life')) {
    primaryMetric = 'quality_of_life';
  } else if (hasMetric('emotional_health')) {
    primaryMetric = 'emotional_health';
  } else if (hasMetric('fulfillment')) {
    primaryMetric = 'fulfillment';
  } else if (hasMetric('wealth_creation')) {
    primaryMetric = 'wealth_creation';
  } else if (nodeKeys.length > 0) {
    [primaryMetric] = nodeKeys;
  }

  const bestTimeline = timelineEntries
    .map(([name], i) => ({
      name,
      score: (causalValues[i] && causalValues[i].Year10 && causalValues[i].Year10[primaryMetric]) || 0,
    }))
    .sort((a, b) => b.score - a.score)
    .map((o) => o.name)[0] || '';

  const overviewCards = [
    { label: 'Decision', value: (decision || '').slice(0, 40) + ((decision || '').length > 40 ? '…' : ''), sub: `${timelineEntries.length} timelines analyzed`, color: '#00f2ff' },
    { label: 'Recommended Path', value: (archetype_labels && archetype_labels[bestTimeline]) || bestTimeline || 'N/A', sub: `Based on ${(metricLabels[primaryMetric] || primaryMetric)} projection`, color: '#00ff88' },
    hasMetric('income') && { label: 'Income (Y10)', value: `Rs. ${avgScore('income')?.toFixed(0) || 50}/100`, sub: 'vs baseline', color: '#7b2fff' },
    hasMetric(primaryMetric) && { label: `${metricLabels[primaryMetric] || primaryMetric} (Y10)`, value: `${y10Scores[primaryMetric] || 50}/100`, sub: `Started at ${y1Scores[primaryMetric] || 50}`, color: '#ffaa00' },
    hasMetric('health') && { label: 'Health (Y10)', value: `${y10Scores.health || 50}/100`, sub: `Stress: ${y10Scores.stress || 50}/100`, color: '#00ff88' },
    hasMetric('relationships') && { label: 'Relationships (Y10)', value: `${y10Scores.relationships || 50}/100`, sub: `Growth: ${y10Scores.career_growth || 50}/100`, color: '#ff2a7a' },
    hasMetric('work_life_balance') && { label: 'Work-Life Balance (Y10)', value: `${y10Scores.work_life_balance || 50}/100`, sub: `Stress: ${y10Scores.stress || 50}/100`, color: '#00ff88' },
    hasMetric('compatibility') && { label: 'Compatibility (Y10)', value: `${y10Scores.compatibility || 50}/100`, sub: `Emotional: ${y10Scores.emotional_health || 50}/100`, color: '#ff2a7a' },
    hasMetric('quality_of_life') && { label: 'Quality of Life (Y10)', value: `${y10Scores.quality_of_life || 50}/100`, sub: `Recovery: ${y10Scores.recovery_progress || 50}/100`, color: '#00ff88' },
  ].filter(Boolean);

  return (
    <div className="dashboard-view">
      <div className="overview-grid">
        {overviewCards.map((c) => (
          <div key={c.label} className="overview-card" style={{ borderTopColor: c.color }}>
            <div className="card-label">{c.label}</div>
            <div className="card-value" style={{ color: c.color }}>{c.value}</div>
            <div className="card-sub">{c.sub}</div>
          </div>
        ))}
      </div>

      {timelineEntries.length > 0 && (
        <div className="data-panel">
          <div className="panel-header">
            <span>Path Comparison</span>
          </div>
          <div className="composite-grid">
            {timelineEntries.map(([name], i) => {
              const causal = Object.values(causal_data)[i] || {};
              const y10 = causal.Year10 || {};
              const domainNodes = Object.keys(y10).filter((k) => k !== '_causal');
              const domainItemKeys = domainNodes.length > 0 ? domainNodes.slice(0, 6) : ['income', 'career_growth', 'health', 'happiness', 'relationships', 'stress'];
              const colors = ['#00f2ff', '#7b2fff', '#00ff88', '#ffffff', '#ffaa00', '#ff2a7a'];
              const items = domainItemKeys.map((k, idx) => ({
                label: metricLabels[k] || k.replace(/_/g, ' '),
                value: y10[k] || 50,
                color: colors[idx % colors.length],
              }));
              return (
                <div key={name} className="path-card" style={{ borderLeftColor: ['#00f2ff', '#ff2a7a', '#7b2fff'][i % 3] }}>
                  <div className="path-name">{name}</div>
                  {items.map((it) => (
                    <div key={it.label} className="composite-item">
                      <span className="composite-label">{it.label}</span>
                      <div className="composite-bar-track">
                        <div className="composite-bar-fill" style={{ width: `${it.value}%`, background: it.color }} />
                      </div>
                      <span className="composite-value" style={{ color: it.color }}>{it.value.toFixed(0)}</span>
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {comparison && Object.keys(comparison).length > 0 && (
        <div className="data-panel">
          <div className="panel-header">
            <span>Cross-Timeline Analysis</span>
          </div>
          <div className="comparison-grid">
            {comparison.common_patterns && (
              <div className="comparison-item">
                <strong>Common Patterns</strong>
                <span>{comparison.common_patterns}</span>
              </div>
            )}
            {comparison.key_differences && (
              <div className="comparison-item">
                <strong>Key Differences</strong>
                <span>{comparison.key_differences}</span>
              </div>
            )}
            {comparison.hinge_point && (
              <div className="comparison-item">
                <strong>Hinge Point</strong>
                <span>{comparison.hinge_point}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {data.data_confidence != null && (
        <div className="data-panel">
          <div className="panel-header">
            <span>Data Confidence</span>
            <span className="badge" style={{ background: SCORE_COLOR(data.data_confidence) }}>
              {data.data_confidence}%
            </span>
          </div>
          {data.data_confidence_explanation && (
            <div className="confidence-explanation">{data.data_confidence_explanation}</div>
          )}
          {data.data_warnings && data.data_warnings.length > 0 && (
            <div className="warnings-list">
              {data.data_warnings.map((w, i) => (
                <div key={i} className="warning-item">⚠ {w}</div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
