/**
 * ContextForm.js — redesigned input form
 *
 * Layout: 3 collapsible sections
 *   1. About You        (age, location)
 *   2. Financial Runway (savings, dependents)
 *   3. Preferences      (risk tolerance slider, skills)
 *   + optional email at the bottom
 *
 * The decision text field lives in App.js above this form.
 */
import React, { useState } from 'react';

// ── Tooltip component ────────────────────────────────────────────────────────
function Tooltip({ text }) {
  const [visible, setVisible] = useState(false);
  return (
    <span className="cf-tooltip-wrap">
      <button
        type="button"
        className="cf-info-btn"
        onMouseEnter={() => setVisible(true)}
        onMouseLeave={() => setVisible(false)}
        onFocus={() => setVisible(true)}
        onBlur={() => setVisible(false)}
        aria-label="More information"
      >
        ?
      </button>
      {visible && <span className="cf-tooltip" role="tooltip">{text}</span>}
    </span>
  );
}

// ── Section wrapper ──────────────────────────────────────────────────────────
function Section({ icon, title, children }) {
  return (
    <div className="cf-section">
      <div className="cf-section-header">
        <span className="cf-section-icon">{icon}</span>
        <span className="cf-section-title">{title}</span>
      </div>
      <div className="cf-section-body">{children}</div>
    </div>
  );
}

// ── Field wrapper ────────────────────────────────────────────────────────────
function Field({
  id, label, helper, tooltip, required, children,
}) {
  return (
    <div className="cf-field">
      <div className="cf-label-row">
        <label className="cf-label" htmlFor={id}>
          {label}
          {required && <span className="cf-required">*</span>}
        </label>
        {tooltip && <Tooltip text={tooltip} />}
      </div>
      {children}
      {helper && <span className="cf-helper">{helper}</span>}
    </div>
  );
}

const riskColor = (val) => {
  if (val <= 3) return '#00f2ff';
  if (val <= 6) return '#ffaa00';
  return '#ff2a7a';
};
const RISK_LABELS = [
  '', // 0 unused
  'Very cautious — prefer stability over growth',
  'Cautious — small calculated risks only',
  'Careful — avoid big unknowns',
  'Moderate — some risk is fine',
  'Balanced — comfort with uncertainty',
  'Open — willing to bet on yourself',
  'Adventurous — high risk, high reward',
  'Bold — startup / career-leap territory',
  'Very bold — all-in on a big bet',
  'Maximum risk — nothing to lose mindset',
];

// ── Risk slider labels ───────────────────────────────────────────────────────
function ContextForm({ onSubmit }) {
  const [values, setValues] = useState({
    age: '',
    location: '',
    risk_tolerance: 5,
    financial_runway_months: '',
    dependents_count: '',
    current_skills: '',
    user_email: '',
  });

  const set = (key, val) => setValues((prev) => ({ ...prev, [key]: val }));

  const handleSubmit = (e) => {
    e.preventDefault();
    const out = { ...values };
    ['age', 'financial_runway_months', 'dependents_count'].forEach((k) => {
      if (out[k] !== '') out[k] = Number(out[k]);
    });
    out.risk_tolerance = Number(out.risk_tolerance);
    onSubmit(out);
  };

  const riskVal = Number(values.risk_tolerance);

  return (
    <form onSubmit={handleSubmit} className="context-form-v2" noValidate>

      {/* ── Section 1: About You ── */}
      <Section icon="👤" title="About You">
        <div className="cf-row-2">
          <Field
            id="age"
            label="Age"
            required
            tooltip="Your age helps calibrate salary expectations and career stage."
          >
            <input
              id="age"
              type="number"
              className="cf-input"
              placeholder="e.g. 21"
              min={15}
              max={70}
              value={values.age}
              onChange={(e) => set('age', e.target.value)}
              required
            />
          </Field>

          <Field
            id="location"
            label="City"
            required
            tooltip="Used to ground salary data — e.g. Bangalore salaries differ from Delhi."
          >
            <input
              id="location"
              type="text"
              className="cf-input"
              placeholder="e.g. Bangalore, India"
              value={values.location}
              onChange={(e) => set('location', e.target.value)}
              required
            />
          </Field>
        </div>
      </Section>

      {/* ── Section 2: Financial Runway ── */}
      <Section icon="💰" title="Financial Context">
        <div className="cf-row-2">
          <Field
            id="financial_runway_months"
            label="Months of savings"
            required
            helper="How long you can survive without income"
            tooltip="This is your financial runway — the number of months you could cover expenses if you had zero income today. 3 months = tight, 12+ months = comfortable to take risks."
          >
            <input
              id="financial_runway_months"
              type="number"
              className="cf-input"
              placeholder="e.g. 6"
              min={0}
              max={120}
              value={values.financial_runway_months}
              onChange={(e) => set('financial_runway_months', e.target.value)}
              required
            />
          </Field>

          <Field
            id="dependents_count"
            label="Dependents"
            required
            helper="People who rely on your income"
            tooltip="Count anyone financially dependent on you — parents, siblings, children. Count yourself as 0 here (we already know you exist). A student supporting parents = 2."
          >
            <input
              id="dependents_count"
              type="number"
              className="cf-input"
              placeholder="e.g. 2"
              min={0}
              max={20}
              value={values.dependents_count}
              onChange={(e) => set('dependents_count', e.target.value)}
              required
            />
          </Field>
        </div>
      </Section>

      {/* ── Section 3: Preferences ── */}
      <Section icon="🎯" title="Your Preferences">

        {/* Risk tolerance slider */}
        <Field
          id="risk_tolerance"
          label="Risk tolerance"
          required
          tooltip="How comfortable are you with uncertainty? 1 = you need a guaranteed outcome. 10 = you're willing to bet everything on a long shot."
        >
          <div className="cf-risk-wrap">
            <div className="cf-risk-track">
              <span className="cf-risk-end-label">Cautious</span>
              <input
                id="risk_tolerance"
                type="range"
                className="cf-risk-slider"
                min={1}
                max={10}
                step={1}
                value={riskVal}
                onChange={(e) => set('risk_tolerance', e.target.value)}
              />
              <span className="cf-risk-end-label">Adventurous</span>
            </div>
            <div className="cf-risk-readout">
              <span
                className="cf-risk-number"
                style={{ color: riskColor(riskVal) }}
              >
                {riskVal}
                /10
              </span>
              <span className="cf-risk-label">{RISK_LABELS[riskVal]}</span>
            </div>
          </div>
        </Field>

        {/* Skills */}
        <Field
          id="current_skills"
          label="Your top skills"
          helper="Separate with commas — used to personalise career paths"
          tooltip="List 3–5 skills you're confident in. These help ground your simulation in realistic career trajectories. Examples: Python, Public Speaking, Project Management, CAD, Data Analysis, Sales."
        >
          <input
            id="current_skills"
            type="text"
            className="cf-input"
            placeholder="e.g. Python, Communication, Problem Solving"
            value={values.current_skills}
            onChange={(e) => set('current_skills', e.target.value)}
          />
        </Field>
      </Section>

      {/* ── Optional email ── */}
      <div className="cf-email-row">
        <div className="cf-email-icon">📬</div>
        <div className="cf-email-body">
          <label className="cf-label" htmlFor="user_email">
            Get a 6-month follow-up
            <input
              id="user_email"
              type="email"
              className="cf-input cf-email-input"
              placeholder="your@email.com (optional)"
              value={values.user_email}
              onChange={(e) => set('user_email', e.target.value)}
            />
          </label>
          <span className="cf-helper">
            We&apos;ll email you in 6 months to see which path you actually took.
            No spam — one email only.
          </span>
        </div>
      </div>

      {/* ── Submit ── */}
      <button type="submit" className="cf-submit-btn">
        <span className="cf-submit-icon">⟁</span>
        Explore My Possible Futures
      </button>

    </form>
  );
}

export default ContextForm;
