import * as d3 from 'd3';
import React, {
  useState, useEffect, useRef, useMemo, useCallback,
} from 'react';
import API from './api';

import RadarChart from './RadarChart';
import ValuesSlider from './ValuesSlider';
import ScoreResult from './ScoreResult';
import PeerComparison from './PeerComparison';
import JobMarketPanel from './JobMarketPanel';
import DataSourceBadge from './DataSourceBadge';

// ── Emotion keyword → wellbeing score ──────────────────────────────────────
const emotionScoreMap = {
  desperate: 2,
  anxious: 3,
  uncertain: 4,
  disappointed: 3,
  hopeful: 6,
  relieved: 7,
  grateful: 8,
  confident: 9,
  successful: 8,
  comfortable: 7,
  struggling: 2,
  modest: 5,
  minimalist: 4,
  frugal: 4,
  affluent: 9,
  excited: 8,
  lonely: 3,
};

const parseEmotion = (text) => {
  if (!text) return 5;
  const lower = text.toLowerCase();
  for (const [word, score] of Object.entries(emotionScoreMap)) {
    if (lower.includes(word)) return score;
  }
  return 5;
};

// ── Lane colors per timeline index ─────────────────────────────────────────
const LANE_COLORS = ['#00f2ff', '#ff2a7a', '#7b2fff'];

// ── SVG Arrow connector ─────────────────────────────────────────────────────
function NodeArrow({ color }) {
  const safeId = color.replace('#', '');
  return (
    <div className="node-arrow">
      <svg
        width="28"
        height="20"
        viewBox="0 0 28 20"
      >
        <defs>
          <marker
            id={`arrowhead-${safeId}`}
            markerWidth="6"
            markerHeight="6"
            refX="3"
            refY="3"
            orient="auto"
          >
            <path d="M0,0 L0,6 L6,3 z" fill={color} />
          </marker>
        </defs>
        <line
          x1="2"
          y1="10"
          x2="22"
          y2="10"
          stroke={color}
          strokeWidth="1.5"
          markerEnd={`url(#arrowhead-${safeId})`}
          style={{ filter: `drop-shadow(0 0 3px ${color})` }}
        />
      </svg>
    </div>
  );
}

// ── Helper to build a fallback label if interpretations missing ─────────────
function getFallbackLabel(node, score, groundingData) {
  if (node === 'income' && groundingData?.salary_entry_lpa) {
    const [entryMin] = groundingData.salary_entry_lpa;
    const [, seniorMax] = groundingData.salary_senior_lpa;
    const approx = entryMin + (score / 100) * (seniorMax - entryMin);
    return `~${Math.round(approx)} LPA`;
  }
  if (node === 'opportunity' && groundingData?.employment_rate) {
    return `base ${Math.round(groundingData.employment_rate * 100)}% employment`;
  }
  // For all other nodes return ONLY the contextual label, not the raw score
  // (the raw score is rendered separately in the JSX)
  return null;
}

// ── Main component ──────────────────────────────────────────────────────────
function TimelineView({ data, decision }) {
  const {
    simulation_id: simulationId,
    timelines = {},
    regrets = {},
    letters = {},
    comparison = {},
    causal_data: causalData = {},
    interpretations = {},
    grounding = {},
    decision_type: rawDecisionType,
    archetype_labels: archLabels,
    domain: responseDomain,
    main_page_insights: mainPageInsights,
  } = data || {};

  const decisionType = rawDecisionType || (decision || '').toLowerCase();
  const domain = responseDomain || decisionType;

  // Domain-aware: hide career-specific panels for non-career domains
  const isCareerDomain = domain === 'career' || domain === 'general';

  const timelineLabels = archLabels || {
    'Timeline A': 'Path A',
    'Timeline B': 'Path B',
    'Timeline C': 'Path C',
  };

  console.log('[TimelineView] Mounted with data:', {
    hasTimelines: Object.keys(timelines).length > 0,
    hasRegrets: Object.keys(regrets).length > 0,
    hasLetters: Object.keys(letters).length > 0,
    hasCausalData: Object.keys(causalData).length > 0,
    hasInterpretations: Object.keys(interpretations).length > 0,
    hasGrounding: Object.keys(grounding).length > 0,
    decisionType,
    domain,
    timelineLabels,
  });

  // Derive role/location from first timeline's grounding for job market panel
  const firstGrounding = Object.values(grounding)[0] || {};
  const groundedRole = isCareerDomain ? (firstGrounding.role || null) : null;
  const groundedLocation = firstGrounding.location || 'India';

  const availableYears = useMemo(() => {
    const first = Object.values(timelines)[0] || {};
    return Object.keys(first)
      .map((k) => parseInt(k.replace('Year', ''), 10))
      .filter((n) => !Number.isNaN(n))
      .sort((a, b) => a - b);
  }, [timelines]);

  const [year, setYear] = useState(availableYears[0] || 1);
  const [isPlaying, setIsPlaying] = useState(false);
  const chartRef = useRef(null);
  const causalChartRef = useRef(null);
  const playRef = useRef(null);

  useEffect(() => { setYear(availableYears[0] || 1); }, [availableYears]);

  // Auto-play
  useEffect(() => {
    if (!isPlaying) {
      clearInterval(playRef.current);
      return undefined;
    }
    playRef.current = setInterval(() => {
      setYear((prev) => {
        const idx = availableYears.indexOf(prev);
        const next = (idx + 1) % availableYears.length;
        if (next === 0) setIsPlaying(false);
        return availableYears[next];
      });
    }, 2200);
    return () => clearInterval(playRef.current);
  }, [isPlaying, availableYears]);

  // ── Emotional data — use real causal scores if available ────────────────
  const NODE_COLORS = useMemo(() => ({
    income: '#00f2ff',
    career_growth: '#7b2fff',
    stress: '#ff2a7a',
    health: '#00ff88',
    relationships: '#ffaa00',
    happiness: '#ffffff',
    opportunity: '#ff6600',
  }), []);

  const CAUSAL_NODES = Object.keys(NODE_COLORS);

  const emotionalData = useMemo(
    () => Object.entries(timelines).map(([name, timeline], i) => {
      const causal = causalData?.[name] || {};
      return {
        name,
        color: LANE_COLORS[i] || '#00f2ff',
        scores: availableYears.map((yr) => {
          const yrKey = `Year${yr}`;
          const score = causal[yrKey]?.happiness ?? parseEmotion(timeline?.[yrKey] || '');
          return { year: yr, score };
        }),
      };
    }),
    [timelines, causalData, availableYears],
  );

  // ── Selected timeline for causal node chart ──────────────────────────────
  const [selectedTimeline, setSelectedTimeline] = useState(
    Object.keys(timelines)[0] || 'Timeline A',
  );

  // ── Radar chart data — all timelines × all nodes for selected year ────────
  // Domain-aware metric labels — derive from available causal data keys
  const RADAR_NODE_LABELS = useMemo(() => {
    const labels = {
      income: 'Income', career_growth: 'Career', stress: 'Stress',
      health: 'Health', relationships: 'Relations', happiness: 'Happiness',
      opportunity: 'Opportunity',
      fulfillment: 'Fulfillment', work_life_balance: 'W/L Balance',
      personal_growth: 'Growth', social_connection: 'Social',
      financial_freedom: 'Freedom',
      emotional_health: 'Emotional', compatibility: 'Compat.',
      communication: 'Comm.', future_alignment: 'Future',
      placement_potential: 'Placement', admission_probability: 'Admission',
      college_quality: 'College', learning_curve: 'Learning',
      wealth_creation: 'Wealth', wealth_growth: 'Invest.',
      financial_health: 'Fin. Health', quality_of_life: 'QoL',
      treatment_efficacy: 'Efficacy', recovery_rate: 'Recovery',
      treatment_success: 'Success', recovery_progress: 'Progress',
      risk_level: 'Risk',
    };
    // Dynamically construct from first timeline's Year10 keys
    const firstTL = Object.values(causalData)[0] || {};
    const firstYr = firstTL?.Year10 || firstTL?.Year1 || {};
    const nodeKeys = Object.keys(firstYr).filter((k) => k !== '_causal');
    if (nodeKeys.length > 0) {
      const dyn = {};
      nodeKeys.forEach((k) => { dyn[k] = labels[k] || k.replace(/_/g, ' '); });
      return dyn;
    }
    return labels;
  }, [causalData]);

  const radarData = useMemo(() => {
    const yrKey = `Year${year}`;
    const result = {};
    Object.keys(timelines).forEach((tlName) => {
      const scores = causalData?.[tlName]?.[yrKey];
      if (scores) result[tlName] = scores;
    });
    return result;
  }, [causalData, timelines, year]);

  // ── D3 Glowing Waveform ──────────────────────────────────────────────────
  useEffect(() => {
    if (!chartRef.current || availableYears.length === 0) return;

    const container = chartRef.current.parentElement;
    const W = Math.min(container.clientWidth - 48, 900);
    const H = 220;
    const margin = {
      top: 30, right: 20, bottom: 40, left: 44,
    };
    const innerW = W - margin.left - margin.right;
    const innerH = H - margin.top - margin.bottom;

    const svg = d3.select(chartRef.current);
    svg.selectAll('*').remove();
    svg.attr('width', W).attr('height', H);

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    const x = d3.scaleLinear().domain(d3.extent(availableYears)).range([0, innerW]);
    const y = d3.scaleLinear().domain([0, 10]).range([innerH, 0]);

    // Grid lines
    g.append('g')
      .call(d3.axisLeft(y).ticks(5).tickSize(-innerW).tickFormat(''))
      .selectAll('line')
      .attr('stroke', 'rgba(0,242,255,0.06)')
      .attr('stroke-dasharray', '3,3');
    g.select('.domain').remove();

    // Axes
    g.append('g')
      .attr('transform', `translate(0,${innerH})`)
      .call(
        d3.axisBottom(x)
          .tickValues(availableYears)
          .tickFormat((d) => `Yr ${d}`),
      )
      .selectAll('text')
      .attr('fill', 'rgba(160,160,192,0.7)')
      .style('font-size', '11px')
      .style('font-family', "'JetBrains Mono', monospace");

    g.append('g')
      .call(d3.axisLeft(y).ticks(5))
      .selectAll('text')
      .attr('fill', 'rgba(160,160,192,0.7)')
      .style('font-size', '11px');

    // Chart title
    svg.append('text')
      .attr('x', W / 2)
      .attr('y', 18)
      .attr('text-anchor', 'middle')
      .attr('fill', 'rgba(160,160,192,0.7)')
      .style('font-size', '12px')
      .style('font-family', "'JetBrains Mono', monospace")
      .style('letter-spacing', '2px')
      .text('EMOTIONAL TEMPERATURE MAP');

    const lineGen = d3.line()
      .x((d) => x(d.year))
      .y((d) => y(d.score))
      .curve(d3.curveMonotoneX);

    emotionalData.forEach(({ name, color, scores }) => {
      const id = `grad-${name.replace(/\s/g, '')}`;

      const area = d3.area()
        .x((d) => x(d.year))
        .y0(innerH)
        .y1((d) => y(d.score))
        .curve(d3.curveMonotoneX);

      const defs = svg.append('defs');
      const grad = defs.append('linearGradient')
        .attr('id', id)
        .attr('x1', '0')
        .attr('y1', '0')
        .attr('x2', '0')
        .attr('y2', '1');
      grad.append('stop').attr('offset', '0%').attr('stop-color', color).attr('stop-opacity', 0.25);
      grad.append('stop').attr('offset', '100%').attr('stop-color', color).attr('stop-opacity', 0);

      g.append('path').datum(scores).attr('fill', `url(#${id})`).attr('d', area);

      // Outer glow
      g.append('path')
        .datum(scores)
        .attr('fill', 'none')
        .attr('stroke', color)
        .attr('stroke-width', 6)
        .attr('stroke-opacity', 0.15)
        .attr('d', lineGen);

      // Main line
      g.append('path')
        .datum(scores)
        .attr('fill', 'none')
        .attr('stroke', color)
        .attr('stroke-width', 2)
        .attr('d', lineGen)
        .style('filter', `drop-shadow(0 0 4px ${color})`);

      // Dots
      g.selectAll(`.dot-${id}`)
        .data(scores)
        .enter()
        .append('circle')
        .attr('cx', (d) => x(d.year))
        .attr('cy', (d) => y(d.score))
        .attr('r', 5)
        .attr('fill', color)
        .attr('stroke', '#0a0a1a')
        .attr('stroke-width', 2)
        .style('filter', `drop-shadow(0 0 5px ${color})`);
    });

    // Legend
    const legend = g.append('g').attr('transform', `translate(${innerW - 120}, 0)`);
    emotionalData.forEach(({ name, color }, i) => {
      const row = legend.append('g').attr('transform', `translate(0, ${i * 18})`);
      row.append('rect').attr('width', 10).attr('height', 10).attr('rx', 2)
        .attr('fill', color)
        .style('filter', `drop-shadow(0 0 3px ${color})`);
      row.append('text')
        .attr('x', 16)
        .attr('y', 9)
        .attr('fill', 'rgba(160,160,192,0.8)')
        .style('font-size', '10px')
        .style('font-family', "'JetBrains Mono', monospace")
        .text(name);
    });
  }, [emotionalData, availableYears]);

  // ── Causal multi-node chart for selected timeline ────────────────────────
  useEffect(() => {
    if (!causalChartRef.current || availableYears.length === 0) return;
    const causal = causalData?.[selectedTimeline];
    if (!causal) return;

    const container = causalChartRef.current.parentElement;
    const W = Math.min(container.clientWidth - 48, 900);
    const H = 260;
    const margin = {
      top: 30, right: 140, bottom: 40, left: 44,
    };
    const innerW = W - margin.left - margin.right;
    const innerH = H - margin.top - margin.bottom;

    const svg = d3.select(causalChartRef.current);
    svg.selectAll('*').remove();
    svg.attr('width', W).attr('height', H);

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    const x = d3.scaleLinear().domain(d3.extent(availableYears)).range([0, innerW]);
    const y = d3.scaleLinear().domain([0, 100]).range([innerH, 0]);

    // Grid
    g.append('g')
      .call(d3.axisLeft(y).ticks(5).tickSize(-innerW).tickFormat(''))
      .selectAll('line')
      .attr('stroke', 'rgba(0,242,255,0.05)')
      .attr('stroke-dasharray', '3,3');
    g.select('.domain').remove();

    g.append('g')
      .attr('transform', `translate(0,${innerH})`)
      .call(d3.axisBottom(x).tickValues(availableYears).tickFormat((d) => `Yr ${d}`))
      .selectAll('text')
      .attr('fill', 'rgba(160,160,192,0.7)')
      .style('font-size', '11px')
      .style('font-family', "'JetBrains Mono', monospace");

    g.append('g').call(d3.axisLeft(y).ticks(5))
      .selectAll('text')
      .attr('fill', 'rgba(160,160,192,0.7)')
      .style('font-size', '11px');

    svg.append('text')
      .attr('x', W / 2).attr('y', 18)
      .attr('text-anchor', 'middle')
      .attr('fill', 'rgba(160,160,192,0.7)')
      .style('font-size', '12px')
      .style('font-family', "'JetBrains Mono', monospace")
      .style('letter-spacing', '2px')
      .text(`CAUSAL NODE PROGRESSION — ${selectedTimeline.toUpperCase()}`);

    const lineGen = d3.line()
      .x((d) => x(d.year))
      .y((d) => y(d.value))
      .curve(d3.curveMonotoneX);

    CAUSAL_NODES.forEach((node) => {
      const color = NODE_COLORS[node];
      const series = availableYears.map((yr) => ({
        year: yr,
        value: causal[`Year${yr}`]?.[node] ?? 50,
      }));

      // Glow line
      g.append('path').datum(series)
        .attr('fill', 'none')
        .attr('stroke', color)
        .attr('stroke-width', 5)
        .attr('stroke-opacity', 0.12)
        .attr('d', lineGen);

      g.append('path').datum(series)
        .attr('fill', 'none')
        .attr('stroke', color)
        .attr('stroke-width', 1.8)
        .attr('d', lineGen)
        .style('filter', `drop-shadow(0 0 3px ${color})`);

      // Dots
      g.selectAll(null).data(series).enter().append('circle')
        .attr('cx', (d) => x(d.year))
        .attr('cy', (d) => y(d.value))
        .attr('r', 4)
        .attr('fill', color)
        .attr('stroke', '#0a0a1a')
        .attr('stroke-width', 1.5)
        .style('filter', `drop-shadow(0 0 4px ${color})`);
    });

    // Legend
    const legend = g.append('g').attr('transform', `translate(${innerW + 12}, 0)`);
    CAUSAL_NODES.forEach((node, i) => {
      const color = NODE_COLORS[node];
      const row = legend.append('g').attr('transform', `translate(0, ${i * 20})`);
      row.append('rect').attr('width', 10).attr('height', 10).attr('rx', 2)
        .attr('fill', color).style('filter', `drop-shadow(0 0 3px ${color})`);
      row.append('text').attr('x', 16).attr('y', 9)
        .attr('fill', 'rgba(160,160,192,0.8)')
        .style('font-size', '10px')
        .style('font-family', "'JetBrains Mono', monospace")
        .text(node.replace('_', ' '));
    });
  }, [causalData, selectedTimeline, availableYears, NODE_COLORS, CAUSAL_NODES]);

  // ── Pivot modal ──────────────────────────────────────────────────────────
  const [showPivot, setShowPivot] = useState(false);
  const [pivotData, setPivotData] = useState(null);
  const [pivotResult, setPivotResult] = useState(null);
  const [pivotLoading, setPivotLoading] = useState(false);
  const pivotInputRef = useRef(null);

  // ── Personalised score state ─────────────────────────────────────────────
  const [scoreResult, setScoreResult] = useState(null);
  const [showScorePanel, setShowScorePanel] = useState(false);

  const handlePivotClick = useCallback((name, description) => {
    if (!name || !timelines?.[name]) {
      console.warn('[TimelineView] Pivot attempted on missing timeline:', name);
      return;
    }
    setPivotData({
      name,
      year,
      description,
      originalTimeline: timelines[name],
    });
    setPivotResult(null);
    setShowPivot(true);
  }, [year, timelines]);

  const submitPivot = async (alternative) => {
    if (!pivotData || !alternative) return;
    setPivotLoading(true);
    try {
      const res = await API.post('/pivot', {
        original_timeline: pivotData.originalTimeline,
        event_year: pivotData.year,
        alternative_outcome: alternative,
        decision: 'What if this went differently?',
        context: { note: 'Pivot from user interaction' },
      });
      setPivotResult(res.data);
    } catch (err) {
      console.error(err);
    }
    setPivotLoading(false);
  };

  // ── Render ───────────────────────────────────────────────────────────────
  const timelineEntries = Object.entries(timelines);

  if (timelineEntries.length === 0) {
    return (
      <div className="timeline-container" style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
        <p>No timeline data available.</p>
      </div>
    );
  }

  return (
    <div className="timeline-container">

      {/* ── Agent Insights (top 4 agents) ── */}
      {mainPageInsights && mainPageInsights.length > 0 && (
        <div className="data-panel" style={{ marginBottom: '1.5rem' }}>
          <div className="panel-header">
            <span>🧠 WHY THIS PATH WON</span>
          </div>
          <div className="insights-grid" style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
            {mainPageInsights.map((agent) => {
              const color = {
                financial: '#10b981', risk: '#ef4444', opportunity: '#06b6d4',
                health: '#f59e0b', relationship: '#ec4899', time: '#84cc16',
                happiness: '#a855f7', identity: '#6366f1', career: '#3b82f6',
                strategic: '#14b8a6', lifestyle: '#eab308', economic: '#8b5cf6',
              }[agent.name] || '#6a6a9a';
              return (
                <div key={agent.name} className="agent-insight-card" style={{
                  flex: '1 1 180px', background: 'rgba(255,255,255,0.03)',
                  border: '1px solid rgba(255,255,255,0.06)', borderRadius: 8,
                  padding: '0.75rem 1rem',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                    <span style={{ color, fontWeight: 600, fontSize: '0.8rem', textTransform: 'capitalize' }}>
                      {agent.name}
                    </span>
                    <span style={{ color, fontWeight: 700, fontSize: '1.1rem' }}>
                      {typeof agent.score === 'number' ? agent.score.toFixed(0) : agent.score}/100
                    </span>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
                    {agent.reasoning?.slice(0, 120)}
                    {(agent.reasoning?.length || 0) > 120 ? '...' : ''}
                  </div>
                </div>
              );
            })}
          </div>
          {mainPageInsights.length >= 2 && (
            <div style={{ marginTop: '0.75rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              {mainPageInsights.length}/{mainPageInsights.length} expert agents agree
              {' · '}Confidence: {Math.round((mainPageInsights.reduce((s, a) => s + (a.confidence || 0), 0) / mainPageInsights.length) * 100)}%
            </div>
          )}
        </div>
      )}

      {/* Year selector bar */}
      <div className="year-selector">
        {availableYears.map((yr, idx) => (
          <React.Fragment key={yr}>
            <button
              type="button"
              className={`year-button ${yr === year ? 'active' : ''}`}
              onClick={() => setYear(yr)}
            >
              YR {yr}
            </button>
            {idx < availableYears.length - 1 && (
              <span className="year-arrow">›</span>
            )}
          </React.Fragment>
        ))}
        <button
          type="button"
          className="play-btn"
          onClick={() => setIsPlaying((p) => !p)}
        >
          {isPlaying ? '⏸ PAUSE' : '▶ PLAY'}
        </button>
      </div>

      {/* Glowing D3 waveform — happiness across timelines */}
      <div className="chart-container">
        <svg ref={chartRef} />
      </div>

      {/* ── Radar: trade-off matrix for selected year ── */}
      {Object.keys(radarData).length > 0 && (
        <div className="chart-container radar-container">
          <RadarChart
            data={radarData}
            year={year}
            colors={LANE_COLORS}
            nodeLabels={RADAR_NODE_LABELS}
          />
        </div>
      )}

      {/* Causal node progression chart — all nodes for selected timeline */}
      <div className="chart-container" style={{ marginTop: '1rem' }}>
        <div className="causal-chart-tabs">
          {Object.keys(timelines).map((name, i) => (
            <button
              key={name}
              type="button"
              className={`causal-tab ${selectedTimeline === name ? 'active' : ''}`}
              style={{ '--tab-color': LANE_COLORS[i] }}
              onClick={() => setSelectedTimeline(name)}
            >
              {name}
            </button>
          ))}
        </div>
        <svg ref={causalChartRef} />
      </div>

      {/* Timeline lanes */}
      <div className="timelines-grid">
        {timelineEntries.map(([name, timeline], laneIdx) => {
          const regret = regrets?.[name];
          const letter = letters?.[name];
          const color = LANE_COLORS[laneIdx] || '#00f2ff';
          const activeDesc = timeline[`Year${year}`] || 'No data for this year.';
          const activeCausal = causalData?.[name]?.[`Year${year}`] || null;
          const activeInterp = interpretations?.[name]?.[`Year${year}`] || null;
          const tlGrounding = grounding?.[name] || null;

          // Bar colors per node type
          const nodeColors = {
            income: '#00f2ff',
            career_growth: '#7b2fff',
            stress: '#ff2a7a',
            health: '#00ff88',
            relationships: '#ffaa00',
            happiness: '#ffffff',
            opportunity: '#ff6600',
          };

          return (
            <div key={name} className="timeline-lane">

              <div className="timeline-header">
                <span className="timeline-name">{name}</span>
                <span className="timeline-tag">⟶ YEAR {year} PROJECTION</span>
              </div>

              {/* Year nodes with SVG arrows */}
              <div className="year-progress">
                {availableYears.map((yr, idx) => {
                  const desc = timeline[`Year${yr}`] || 'No data';
                  const isActive = yr === year;
                  return (
                    <React.Fragment key={yr}>
                      <div
                        className={`year-node ${isActive ? 'active' : ''}`}
                        onClick={() => setYear(yr)}
                        onKeyDown={(e) => { if (e.key === 'Enter') setYear(yr); }}
                        role="button"
                        tabIndex={0}
                      >
                        <div className="year-node-label">Year {yr}</div>
                        <div className="year-node-desc">{desc}</div>
                      </div>
                      {idx < availableYears.length - 1 && (
                        <NodeArrow color={color} />
                      )}
                    </React.Fragment>
                  );
                })}
              </div>

              {/* Causal node bars for active year – with grounded labels and tooltips */}
              {activeCausal && (
                <div className="causal-bars">
                  {Object.entries(activeCausal).map(([node, val]) => {
                    const interp = activeInterp?.[node];
                    // interpretations.label already contains the full label (e.g. "~5.2 LPA")
                    // getFallbackLabel returns null for generic nodes to avoid duplication
                    const realLabel = interp?.label || getFallbackLabel(node, val, tlGrounding);
                    const source = interp?.source
                      || (node === 'income' ? 'India salary data 2024' : 'Psychographic baseline');

                    return (
                      <div
                        key={node}
                        className="causal-bar-item"
                        title={`${source}`}
                      >
                        <span className="causal-bar-label">
                          {node.replace('_', ' ')}
                        </span>
                        <div className="causal-bar-track">
                          <div
                            className="causal-bar-fill"
                            style={{
                              width: `${val}%`,
                              background: nodeColors[node] || '#00f2ff',
                              boxShadow: `0 0 4px ${nodeColors[node] || '#00f2ff'}`,
                            }}
                          />
                        </div>
                        <div className="causal-bar-value-row">
                          <span
                            className="causal-bar-value"
                            style={{ color: nodeColors[node] || 'var(--text-muted)' }}
                          >
                            {val}/100
                          </span>
                          {realLabel && (
                            <span className="causal-bar-real">{realLabel}</span>
                          )}
                          <DataSourceBadge node={node} />
                        </div>
                      </div>
                    );
                  })}
                  {tlGrounding?.role && tlGrounding.role !== 'default' && (
                    <div className="grounding-badge">
                      <span>
                        📊 {tlGrounding.role} · {tlGrounding.location}
                      </span>
                    </div>
                  )}
                </div>
              )}

              {/* Active year description — click to pivot */}
              <div
                className="active-year-desc"
                onClick={() => handlePivotClick(name, activeDesc)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    handlePivotClick(name, activeDesc);
                  }
                }}
                role="button"
                tabIndex={0}
                style={{ borderLeftColor: color }}
              >
                <span
                  className="active-year-label"
                  style={{ color }}
                >
                  YEAR {year} — CLICK TO PIVOT ↗
                </span>
                {activeDesc}
              </div>

              <details className="lane-details">
                <summary>💔 Regret Analysis</summary>
                <div className="lane-details-body">
                  <p><strong>Lost opportunity:</strong> {regret?.lost_opportunity}</p>
                  <p><strong>Missed identity:</strong> {regret?.missed_identity}</p>
                  <p><strong>Emotional cost:</strong> {regret?.emotional_cost}</p>
                </div>
              </details>

              <details className="lane-details" style={{ marginTop: '0.5rem' }}>
                <summary>📫 Letter from Future Self</summary>
                <div className="lane-details-body">
                  <div className="letter-text">{letter}</div>
                </div>
              </details>

            </div>
          );
        })}
      </div>

      {/* Comparison */}
      <div className="comparison">
        <h3>⟁ CROSS-TIMELINE ANALYSIS</h3>
        <div className="comparison-grid">
          <div className="comparison-item">
            <strong>Common Patterns</strong>
            <span>{comparison?.common_patterns}</span>
          </div>
          <div className="comparison-item">
            <strong>Key Differences</strong>
            <span>{comparison?.key_differences}</span>
          </div>
          <div className="comparison-item">
            <strong>The Hinge Point</strong>
            <span>{comparison?.hinge_point}</span>
          </div>
        </div>
      </div>

      {/* ── Personalised Score Panel ── */}
      <div className="feature-section">
        <button
          type="button"
          className="feature-toggle-btn"
          onClick={() => setShowScorePanel((p) => !p)}
        >
          {showScorePanel ? '▲' : '▼'} ⟁ PERSONALISED CAREER SCORE
        </button>
        {showScorePanel && simulationId && (
          <div className="feature-panel">
            <ValuesSlider simulationId={simulationId} onScore={setScoreResult} />
            {scoreResult && <ScoreResult data={scoreResult} />}
          </div>
        )}
      </div>

      {/* ── Peer Comparison ── */}
      <div className="feature-section">
        <PeerComparison decision={decision} />
      </div>

      {/* ── Live Job Market ── */}
      {isCareerDomain && (
        <div className="feature-section">
          <JobMarketPanel
            role={groundedRole}
            location={groundedLocation}
            skills={Object.values(grounding || {})[0]?.skills || ''}
          />
        </div>
      )}

      {/* Pivot Modal */}
      {showPivot && (
        <div
          className="modal-overlay"
          onClick={() => setShowPivot(false)}
          onKeyDown={(e) => { if (e.key === 'Escape') setShowPivot(false); }}
          role="button"
          tabIndex={-1}
        >
          <div
            className="modal-content"
            onClick={(e) => e.stopPropagation()}
            role="presentation"
          >
            <h3>⟁ PIVOT SIMULATION</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              What if Year {pivotData?.year} in{' '}
              <strong style={{ color: 'var(--glow-cyan)' }}>
                {pivotData?.name}
              </strong>{' '}
              went differently?
            </p>
            <div className="pivot-description">{pivotData?.description}</div>

            {!pivotResult ? (
              <>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem', marginBottom: '0.5rem' }}>
                  Describe the alternative outcome:
                </p>
                <input
                  ref={pivotInputRef}
                  type="text"
                  className="pivot-input"
                  placeholder="e.g. I got promoted instead of quitting"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') submitPivot(pivotInputRef.current?.value);
                  }}
                />
                <div className="modal-buttons">
                  <button
                    type="button"
                    onClick={() => submitPivot(pivotInputRef.current?.value)}
                    disabled={pivotLoading}
                  >
                    {pivotLoading ? 'SIMULATING...' : '▶ EXPLORE ALTERNATIVE'}
                  </button>
                  <button type="button" onClick={() => setShowPivot(false)}>
                    CANCEL
                  </button>
                </div>
              </>
            ) : (
              <div className="pivot-result">
                <h4>New Timeline Branch</h4>
                <div className="new-timeline">
                  {Object.entries(pivotResult.new_timeline || {}).map(([yr, desc]) => (
                    <p key={yr}><strong>{yr}:</strong> {desc}</p>
                  ))}
                </div>
                <details className="lane-details" style={{ marginTop: '1rem' }}>
                  <summary>💔 Regret in new path</summary>
                  <div className="lane-details-body">
                    <p><strong>Lost:</strong> {pivotResult.regret?.lost_opportunity}</p>
                    <p><strong>Identity:</strong> {pivotResult.regret?.missed_identity}</p>
                    <p><strong>Cost:</strong> {pivotResult.regret?.emotional_cost}</p>
                  </div>
                </details>
                <details className="lane-details" style={{ marginTop: '0.5rem' }}>
                  <summary>📫 Letter from future self</summary>
                  <div className="lane-details-body">
                    <div className="letter-text">{pivotResult.letter}</div>
                  </div>
                </details>
                <div className="modal-buttons" style={{ marginTop: '1.5rem' }}>
                  <button
                    type="button"
                    onClick={() => { setPivotResult(null); setShowPivot(false); }}
                  >
                    CLOSE
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default TimelineView;
