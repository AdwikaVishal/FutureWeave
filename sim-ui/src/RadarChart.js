/**
 * RadarChart.js
 *
 * D3-powered radar chart for comparing causal node scores across timelines.
 * Renders one polygon per timeline, with neon glow matching the futuristic theme.
 *
 * Props:
 *   data        – { "Timeline A": {income:40, career_growth:20, ...}, ... }
 *   year        – number, used only for the title
 *   colors      – string[], one colour per timeline (index-matched to data keys)
 *   nodeLabels  – { income: "Income", career_growth: "Career Growth", ... }
 */
import * as d3 from 'd3';
import React, { useEffect, useRef, memo } from 'react';

// ── Constants ────────────────────────────────────────────────────────────────
const TICK_COUNT = 5; // number of concentric grid rings
const LABEL_PADDING = 18; // pixels beyond outer ring for axis labels
const MIN_SIZE = 280; // minimum chart diameter
const MAX_SIZE = 480; // maximum chart diameter

// ── Helper: convert polar (angle, radius) to Cartesian (x, y) ─────────────────
function polarToXY(angle, r) {
  // 0° points up (−π/2 offset)
  return {
    x: r * Math.cos(angle - Math.PI / 2),
    y: r * Math.sin(angle - Math.PI / 2),
  };
}

function pointsString(pts) {
  return pts.map((p) => `${p.x},${p.y}`).join(' ');
}

// ── Helper to compute text anchor based on x position ────────────────────────
function getTextAnchor(x) {
  if (x > 2) return 'start';
  if (x < -2) return 'end';
  return 'middle';
}

// ── Component ────────────────────────────────────────────────────────────────
function RadarChart({
  data, year, colors, nodeLabels,
}) {
  const svgRef = useRef(null);

  useEffect(() => {
    if (!svgRef.current || !data) return;

    const nodes = Object.keys(nodeLabels);
    const timelineNames = Object.keys(data);
    if (nodes.length === 0 || timelineNames.length === 0) return;

    // ── Sizing ──────────────────────────────────────────────────────────────
    const container = svgRef.current.parentElement;
    const size = Math.max(
      MIN_SIZE,
      Math.min(MAX_SIZE, container.clientWidth - 32),
    );
    const cx = size / 2;
    const cy = size / 2;
    const radius = (size / 2) - LABEL_PADDING - 24;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();
    svg.attr('width', size).attr('height', size);

    const g = svg.append('g').attr('transform', `translate(${cx},${cy})`);

    // ── Scales ───────────────────────────────────────────────────────────────
    const angleSlice = (2 * Math.PI) / nodes.length;
    const rScale = d3.scaleLinear().domain([0, 100]).range([0, radius]);

    // ── Grid rings ───────────────────────────────────────────────────────────
    const levels = d3.range(1, TICK_COUNT + 1);
    levels.forEach((level) => {
      const r = (radius / TICK_COUNT) * level;
      const ringPts = nodes.map((_, i) => {
        const { x, y } = polarToXY(i * angleSlice, r);
        return `${x},${y}`;
      });
      g.append('polygon')
        .attr('points', ringPts.join(' '))
        .attr('fill', 'none')
        .attr('stroke', 'rgba(0,242,255,0.12)')
        .attr('stroke-width', 1);

      // Tick label (20, 40, 60, 80, 100)
      g.append('text')
        .attr('x', 4)
        .attr('y', -r)
        .attr('fill', 'rgba(160,160,192,0.4)')
        .style('font-size', '9px')
        .style('font-family', "'JetBrains Mono', monospace")
        .text(level * (100 / TICK_COUNT));
    });

    // ── Axis spokes ──────────────────────────────────────────────────────────
    nodes.forEach((node, i) => {
      const angle = i * angleSlice;
      const outer = polarToXY(angle, radius);

      // Spoke line
      g.append('line')
        .attr('x1', 0).attr('y1', 0)
        .attr('x2', outer.x).attr('y2', outer.y)
        .attr('stroke', 'rgba(0,242,255,0.2)')
        .attr('stroke-width', 1);

      // Axis label
      const labelPos = polarToXY(angle, radius + LABEL_PADDING);
      const anchor = getTextAnchor(labelPos.x);

      g.append('text')
        .attr('x', labelPos.x)
        .attr('y', labelPos.y + 4)
        .attr('text-anchor', anchor)
        .attr('fill', 'rgba(160,160,192,0.75)')
        .style('font-size', '10px')
        .style('font-family', "'JetBrains Mono', monospace")
        .style('letter-spacing', '0.5px')
        .text((nodeLabels[node] || node).toUpperCase());
    });

    // ── Timeline polygons ────────────────────────────────────────────────────
    timelineNames.forEach((tlName, tlIdx) => {
      const scores = data[tlName];
      if (!scores) return;

      const color = colors[tlIdx] || '#00f2ff';

      const pts = nodes.map((node, i) => {
        const val = scores[node] ?? 0;
        return polarToXY(i * angleSlice, rScale(val));
      });

      // Glow fill
      g.append('polygon')
        .attr('points', pointsString(pts))
        .attr('fill', color)
        .attr('fill-opacity', 0.08)
        .attr('stroke', 'none');

      // Outer glow stroke
      g.append('polygon')
        .attr('points', pointsString(pts))
        .attr('fill', 'none')
        .attr('stroke', color)
        .attr('stroke-width', 4)
        .attr('stroke-opacity', 0.15)
        .style('filter', `drop-shadow(0 0 6px ${color})`);

      // Main stroke
      g.append('polygon')
        .attr('points', pointsString(pts))
        .attr('fill', 'none')
        .attr('stroke', color)
        .attr('stroke-width', 1.8)
        .style('filter', `drop-shadow(0 0 4px ${color})`);

      // Vertex dots
      pts.forEach((pt) => {
        g.append('circle')
          .attr('cx', pt.x)
          .attr('cy', pt.y)
          .attr('r', 3.5)
          .attr('fill', color)
          .attr('stroke', '#0a0a1a')
          .attr('stroke-width', 1.5)
          .style('filter', `drop-shadow(0 0 4px ${color})`);
      });
    });

    // ── Legend ───────────────────────────────────────────────────────────────
    const legendX = -size / 2 + 12;
    const legendY = size / 2 - 16 - (timelineNames.length - 1) * 18;
    const legend = svg.append('g').attr('transform', `translate(${legendX},${legendY})`);

    timelineNames.forEach((tlName, tlIdx) => {
      const color = colors[tlIdx] || '#00f2ff';
      const row = legend.append('g').attr('transform', `translate(0,${tlIdx * 18})`);
      row.append('rect')
        .attr('width', 10).attr('height', 10).attr('rx', 2)
        .attr('fill', color)
        .style('filter', `drop-shadow(0 0 3px ${color})`);
      row.append('text')
        .attr('x', 16).attr('y', 9)
        .attr('fill', 'rgba(160,160,192,0.8)')
        .style('font-size', '10px')
        .style('font-family', "'JetBrains Mono', monospace")
        .text(tlName);
    });

    // ── Title ────────────────────────────────────────────────────────────────
    svg.append('text')
      .attr('x', cx).attr('y', 16)
      .attr('text-anchor', 'middle')
      .attr('fill', 'rgba(160,160,192,0.6)')
      .style('font-size', '11px')
      .style('font-family', "'JetBrains Mono', monospace")
      .style('letter-spacing', '2px')
      .text(`TRADE-OFF MATRIX — YEAR ${year}`);
  }, [data, year, colors, nodeLabels]);

  return <svg ref={svgRef} />;
}

export default memo(RadarChart);
