# MASTER PROMPT — Artifex Confidence + Agent Analysis Overhaul

You are a Senior Staff Engineer, Product Designer, Behavioral Economist, and AI Systems Architect overhauling a production-grade decision intelligence platform called **Artifex**.

## Codebase Context

Python 3.13+ / FastAPI / LangGraph multi-agent system. Key files:
- `sim-engine/graph/workflows/simulation.py` — orchestrator, `_state_to_result()`, `_compute_confidence()`, `_normalize_agent_output()`
- `sim-engine/graph/state.py` — `SimulationState`, `AgentOutput`, `DebateEntry`, `CriticEvaluation`
- `sim-engine/graph/agents/*.py` — 10+ domain agents (Economic, Career, Financial, Health, Relationship, Opportunity, Risk, Identity, Strategic, Happiness)
- `sim-engine/graph/agents/synthesis.py` — final recommendation engine
- `sim-engine/graph/nodes/debate.py` — debate resolver
- `sim-engine/graph/nodes/parallel_agents.py` — agent parallel executor
- `sim-engine/services/sync_data.py` — data source health tracking
- `sim-engine/graph/workflows/monte_carlo.py` — Monte Carlo simulation
- `sim-engine/deterministic_formulas.py` — all math formulas
- `sim-engine/api_v2.py` — FastAPI endpoint returning SimulationResult

## Current System Deficiencies

### Problems
1. **Confidence = 0% or 1%** on every agent even with full LLM outputs (broken formula).
2. **Agent outputs are opaque** — scores like "64/100" with no explanation of what drove them.
3. **Debate section shows "Analysis complete" / "Score 50"** — zero value, no actual disagreement.
4. **Identity agent returns "Identity score 50 / Interests not specified / Goals not specified"** — robotic.
5. **No evidence, assumptions, or causal chain** exposed to the user.
6. **Data quality** is tracked but not surfaced in confidence calculations.
7. **No waterfall breakdown** of what increased vs decreased each score.
8. **No missing-information detector** — confidence doesn't reflect what we don't know.
9. **Recommendation engine** uses simple max-happiness instead of transparent weighted formula.
10. **No uncertainty, sensitivity, or "what would change this" analysis.**
11. **No regret forecast or alternate-universe comparison.**
12. **Frontend has no concept of per-agent confidence breakdown.**

---

# REDESIGN SPECIFICATION

Implement ALL of the following sections. Generate production-grade Python (backend) and TypeScript/React (frontend). No pseudocode.

---

## SECTION 1 — Agent Cards (Backend)

Each agent's `_normalize_agent_output()` output must include these fields:

```python
{
    "name": "career",
    "score": 74,
    "verdict": "Supports continuing college",   # or "Neutral" or "Supports dropping out"
    "confidence": 0.78,                          # per-agent confidence 0-1
    "evidence": [
        {"type": "positive", "text": "Degree completion improves employability by 32%", "weight": 0.4},
        {"type": "positive", "text": "Industry values credentials in tech hiring", "weight": 0.3},
        {"type": "negative", "text": "Current CGPA below median — placement risk", "weight": -0.2},
    ],
    "score_drivers": {
        "increased_by": [
            {"factor": "Degree completion", "impact": 12, "description": "Credentials increase callback rate"},
            {"factor": "Industry demand", "impact": 8, "description": "Tech hiring up 15% YoY"},
        ],
        "decreased_by": [
            {"factor": "Below-average GPA", "impact": -9, "description": "Filters at top firms"},
            {"factor": "Competition", "impact": -5, "description": "40% more grads this year"},
        ],
    },
    "why_this_score": (
        "The score is driven primarily by long-term employability and credential value. "
        "Strong labor market conditions improve expected outcomes, but low academic "
        "performance reduces placement probability slightly."
    ),
    "key_assumptions": [
        "Student completes degree within 4 years",
        "Coding skills improve at current trajectory",
        "No major economic recession in next 3 years",
        "Industry demand for tech roles remains strong",
    ],
    "source_attribution": [
        {"factor": "Industry Health", "value": 78, "source": "FRED / NASSCOM", "confidence": 0.85},
        {"factor": "GDP Growth", "value": 6.49, "source": "World Bank", "confidence": 0.90},
        {"factor": "Automation Risk", "value": 15, "source": "Oxford Economics", "confidence": 0.65},
    ],
    "recommendation_confidence": 0.82,
    "missing_inputs": [
        {"field": "career_goals", "impact": "confidence -0.05"},
        {"field": "financial_obligations", "impact": "confidence -0.03"},
    ],
}
```

### Where to implement

In `sim-engine/graph/workflows/simulation.py`, replace `_normalize_agent_output()` to build this enriched structure. Extract `evidence` from agent `output.key_insights` (reformat to positive/negative), compute `score_drivers` by parsing deterministic formula components, and build `why_this_score` from existing `reasoning` or fallback text.

---

## SECTION 2 — Confidence Engine (Backend)

### Formula

```python
def compute_agent_confidence(
    data_quality: float,          # 0-1 from sync_data.get_data_quality()
    simulation_stability: float,   # 1.0 - monte_carlo_results.stddev_norm
    evidence_quality: float,       # fraction of evidence items with weight > 0
    historical_similarity: float,  # 0.7 default, higher if user profile matches training data
    agent_consensus: float,        # how close this agent's score is to peer mean
) -> float:
    return (
        data_quality * 0.25 +
        simulation_stability * 0.25 +
        evidence_quality * 0.20 +
        historical_similarity * 0.15 +
        agent_consensus * 0.15
    )
```

### Confidence breakdown (return alongside score)

```python
"confidence_breakdown": {
    "overall": 0.78,
    "components": {
        "data_quality": {"value": 0.90, "weight": 0.25, "contribution": 0.225},
        "simulation_stability": {"value": 0.80, "weight": 0.25, "contribution": 0.200},
        "evidence_quality": {"value": 0.70, "weight": 0.20, "contribution": 0.140},
        "historical_similarity": {"value": 0.75, "weight": 0.15, "contribution": 0.113},
        "agent_consensus": {"value": 0.76, "weight": 0.15, "contribution": 0.114},
    },
    "missing_input_penalty": 0.05,
    "adjusted": 0.73,
}
```

### Where to implement

Create `compute_agent_confidence()` in a new file `sim-engine/graph/confidence.py`. Import in `simulation.py` and call per-agent.

---

## SECTION 3 — Debate System Rewrite (Backend)

### Requirements

Replace the current debate that produces "Analysis complete / Score 50" with actual structured disagreement:

```python
{
    "debates": [
        {
            "topic": "Continue college vs Drop out for startup",
            "agents_involved": ["strategic", "risk", "identity", "opportunity"],
            "positions": [
                {"agent": "strategic", "stance": "Support college", "reasoning": "Long-term career stability and credential value outweigh short-term gains.", "score_impact": 15},
                {"agent": "risk", "stance": "Support dropout", "reasoning": "Highest upside for risk-tolerant profiles; startup equity can 10x.", "score_impact": 20},
                {"agent": "identity", "stance": "Support college", "reasoning": "User values mastery and structured learning — college aligns.", "score_impact": 10},
                {"agent": "opportunity", "stance": "Support dropout", "reasoning": "Ecosystem rewards skill over credentials for this profile.", "score_impact": 12},
            ],
            "resolution": "4 agents support college, 2 support dropout. Recommended: Continue college with startup side-project.",
        }
    ],
    "vote_tally": {"support_college": 4, "support_dropout": 2, "neutral": 0},
    "consensus_level": 0.67,
    "key_tensions": [
        "Career stability vs upside potential — primary axis of disagreement.",
        "Identity alignment vs financial opportunity — secondary axis.",
    ],
    "moderator_summary": "The majority favors the college path, largely driven by career stability and identity alignment. However, the risk and opportunity agents make a credible case that the dropout path has higher upside for this specific profile. The recommended compromise is to continue college while actively pursuing startup side projects."
}
```

### Where to implement

Rewrite `sim-engine/graph/agents/debate.py` and `sim-engine/graph/nodes/debate.py`. The fallback should produce this structure deterministically when LLM is unavailable.

---

## SECTION 4 — Identity Agent Rebuild (Backend)

### Requirements

Current output is "Identity score 50 / Interests not specified / Goals not specified". Replace with:

```python
{
    "score": 82,
    "verdict": "College aligns with identity",
    "confidence": 0.71,
    "identity_analysis": {
        "purpose": "User seeks mastery and technical depth — college provides structured path.",
        "values_detected": ["learning", "achievement", "security", "growth"],
        "lifestyle_fit": "College lifestyle matches user's preference for structured environment.",
        "motivation_drivers": ["career_advancement", "knowledge_acquisition", "social_validation"],
        "long_term_fulfillment": "High — the user's value profile correlates with satisfaction on this path.",
        "identity_alignment_score": 82,
    },
    "why_this_score": (
        "The identity analysis finds strong alignment between the user's stated values "
        "(learning, mastery, growth) and the college path. Users with this profile report "
        "78% higher satisfaction on academic trajectories than on unstructured alternatives."
    ),
    "source_attribution": [
        {"factor": "Value alignment", "value": 85, "source": "Values assessment"},
        {"factor": "Personality fit", "value": 78, "source": "Big Five proxy"},
        {"factor": "Lifestyle match", "value": 72, "source": "Context analysis"},
    ],
}
```

### Where to implement

Rewrite `sim-engine/graph/agents/identity.py` (create if missing, or the one in `decision_engine/agents/identity.py`). Must work in both LLM and deterministic modes.

---

## SECTION 5 — Uncertainty & Sensitivity Panels (Backend)

### What-could-change-this

```python
"uncertainty_drivers": [
    {"scenario": "GPA improves above 8.0", "impact": {"score": "+12", "confidence": "+0.08"}},
    {"scenario": "Job market weakens (GDP < 4%)", "impact": {"score": "-18", "confidence": "-0.15"}},
    {"scenario": "User gains relevant internship", "impact": {"opportunity_score": "+15", "confidence": "+0.05"}},
]
```

### Sensitivity analysis

```python
"sensitivity": {
    "most_influential_factors": [
        {"rank": 1, "factor": "Academic Performance", "elasticity": 0.35, "description": "1 std dev change → 35% change in score"},
        {"rank": 2, "factor": "Industry Demand", "elasticity": 0.22, "description": "1 std dev change → 22% change in score"},
        {"rank": 3, "factor": "Financial Situation", "elasticity": 0.15, "description": ""},
        {"rank": 4, "factor": "Personal Motivation", "elasticity": 0.12, "description": ""},
        {"rank": 5, "factor": "Family Support", "elasticity": 0.10, "description": ""},
    ],
    "method": "One-at-a-time (OAT) sensitivity analysis over deterministic formula inputs.",
}
```

### Where to implement

Add to `sim-engine/graph/workflows/simulation.py` in `_build_reasoning` or create a new `_build_uncertainty()` function. Default uncertainty drivers can be extracted from `state.monte_carlo_results.results` variances.

---

## SECTION 6 — Missing Information Detector (Backend)

### Detect and score impact of missing inputs

```python
"missing_information": {
    "detected_gaps": [
        {"field": "relationship_status", "source": "context", "impact": "confidence -0.03"},
        {"field": "career_goals", "source": "context", "impact": "confidence -0.05"},
        {"field": "financial_obligations", "source": "context", "impact": "confidence -0.04"},
        {"field": "risk_tolerance", "source": "context", "impact": "confidence -0.06"},
        {"field": "family_support", "source": "context", "impact": "confidence -0.02"},
    ],
    "total_confidence_penalty": 0.18,
    "recommended_inputs": [
        {"field": "career_goals", "priority": "high", "reason": "Most impactful missing variable"},
        {"field": "risk_tolerance", "priority": "high", "reason": "Changes recommendation for 30% of users"},
    ],
}
```

### Where to implement

In `sim-engine/graph/workflows/simulation.py`, add a `_detect_missing_inputs(context)` function that checks which keys are absent from `state.context` and applies a predefined penalty table.

---

## SECTION 7 — Recommendation Engine Overhaul (Backend)

### Weighted formula

```python
recommendation_score = (
    happiness * 0.25 +
    income * 0.20 +
    health * 0.15 +
    relationships * 0.15 +
    opportunity * 0.15 +
    risk_inverse * 0.10
)
```

### Add "Why Not" panel

```python
"why_not": {
    "alternative_paths": [
        {
            "path": "Timeline C (Dropout)",
            "score": 62.3,
            "gap_from_best": -12.4,
            "why_not_recommended": (
                "While the dropout path offers higher upside potential (income +18%), "
                "it carries 2.3x higher variance and lower median outcomes. The higher "
                "volatility doesn't justify the expected return for this risk profile."
            ),
            "what_would_need_to_change": [
                "Risk tolerance would need to increase from 'moderate' to 'high'",
                "Financial runway of 18+ months living expenses",
                "Stronger professional network in target industry",
            ],
        }
    ]
}
```

### Where to implement

Rewrite `sim-engine/graph/agents/synthesis.py` `_fallback()` method (already partially done). Add `why_not` to the return dict.

---

## SECTION 8 — Regret Forecast & Alternate Universe (Backend)

### Regret forecast

```python
"regret_forecast": {
    "probability": 0.22,
    "explanation": (
        "Based on user profile similarity to 10,000+ past decisions, "
        "22% of users with this profile express regret within 10 years. "
        "Key predictors: moderate risk tolerance + family-oriented values."
    ),
    "by_timeline": {
        "Timeline A": {"regret_probability": 0.15, "top_regret": "Not taking more risks"},
        "Timeline B": {"regret_probability": 0.22, "top_regret": "Not prioritizing relationships"},
        "Timeline C": {"regret_probability": 0.35, "top_regret": "Financial instability"},
    },
}
```

### Alternate universe comparison

```python
"alternate_universe": {
    "if_chosen_differently": {
        "recommended_path": {"income": 75, "happiness": 82, "stress": 45},
        "alternative_path": {"income": 88, "happiness": 64, "stress": 68},
        "deltas": {
            "income": {"value": 13, "direction": "higher", "unit": "points"},
            "happiness": {"value": -18, "direction": "lower", "unit": "points"},
            "stress": {"value": 23, "direction": "higher", "unit": "points"},
        },
    }
}
```

---

## SECTION 9 — API Schema Changes (Backend)

### Add to simulation result response

```json
{
    "agents": [
        {
            "name": "career",
            "score": 74,
            "verdict": "Supports continuing college",
            "confidence": 0.78,
            "confidence_breakdown": { ... },
            "evidence": [ ... ],
            "score_drivers": { ... },
            "why_this_score": "...",
            "key_assumptions": [ ... ],
            "source_attribution": [ ... ],
            "missing_inputs": [ ... ],
            "uncertainty_drivers": [ ... ],
            "sensitivity": { ... }
        }
    ],
    "overall_confidence": {
        "value": 0.76,
        "breakdown": { ... },
        "missing_input_penalty": 0.05,
        "rating": "MODERATE"
    },
    "debate": {
        "debates": [ ... ],
        "vote_tally": { ... },
        "consensus_level": 0.67,
        "moderator_summary": "..."
    },
    "recommendation": {
        "primary_path": "Timeline B",
        "weighted_scores": { ... },
        "why_not": { ... },
        "formula": "happiness×0.25 + income×0.20 + health×0.15 + relationships×0.15 + opportunity×0.15 + risk_inverse×0.10"
    },
    "uncertainty": {
        "drivers": [ ... ],
        "what_could_change": [ ... ],
        "missing_information": { ... }
    },
    "sensitivity": {
        "most_influential_factors": [ ... ]
    },
    "regret_forecast": { ... },
    "alternate_universe": { ... },
    "data_quality": {
        "score": 0.75,
        "working_sources": 3,
        "total_sources": 4,
        "sources": { ... }
    }
}
```

---

## SECTION 10 — React + Tailwind UI Components (Frontend)

Create these components:

### `AgentCard.tsx`

```
┌─────────────────────────────────────┐
│ Strategic Score         74/100       │
│ Verdict: Supports continuing college│
│ Confidence: 78%                      │
│─────────────────────────────────────│
│ ✓ Degree completion +12             │
│ ✓ Industry demand +8                │
│ ✗ Below-average GPA -9              │
│─────────────────────────────────────│
│ Why this score?                     │
│ The score is driven primarily by... │
│─────────────────────────────────────│
│ Assumptions:                        │
│ • Student completes degree          │
│ • No major recession                │
└─────────────────────────────────────┘
```

### `ConfidenceBreakdown.tsx`

Horizontal bar chart showing 5 components (Data Quality, Simulation Stability, Evidence Quality, Historical Similarity, Agent Consensus) with their values and contributions.

### `DebatePanel.tsx`

```
┌──────────────┬────────────────────────┐
│ Agent        │ Stance                 │
├──────────────┼────────────────────────┤
│ Strategic    │ ✅ Supports college     │
│ Risk         │ 🔺 Supports dropout    │
│ Identity     │ ✅ Supports college     │
│ Opportunity  │ 🔺 Supports dropout     │
├──────────────┼────────────────────────┤
│ Vote Tally:  4-2 in favor of college  │
│ Moderator: Recommended compromise...  │
└──────────────┴────────────────────────┘
```

### `UncertaintyPanel.tsx`

```
┌──────────────────────────────────────────┐
│ What Could Change This Recommendation?   │
├──────────────────────────────────────────┤
│ If GPA improves above 8.0:           +12 │
│ If job market weakens (GDP<4%):      -18 │
│ If gains relevant internship:        +15 │
└──────────────────────────────────────────┘
```

### `SensitivityChart.tsx`

Horizontal bar chart ranking most influential factors.

### `MissingInfoDetector.tsx`

```
┌──────────────────────────────────────────┐
│ Missing Information — Confidence: -18%    │
├──────────────────────────────────────────┤
│ 🟡 career_goals            High priority  │
│ 🟡 risk_tolerance          High priority  │
│ ⚪ financial_obligations   Medium         │
└──────────────────────────────────────────┘
```

### `RegretForecast.tsx`

Gauge showing regret probability + breakdown by timeline.

### `AlternateUniverse.tsx`

Side-by-side comparison of chosen vs alternative path scores with +/- deltas.

### `WhyNotPanel.tsx`

For each unchosen path, show why it wasn't selected, score gap, and what would need to change.

---

## Implementation Order

### Phase 1 — Backend Confidence Engine (Day 1)
1. Create `sim-engine/graph/confidence.py` with `compute_agent_confidence()` and `compute_confidence_breakdown()`
2. Update `_normalize_agent_output()` in `simulation.py` to include confidence_breakdown
3. Add `_detect_missing_inputs()` to `simulation.py`
4. Update `_state_to_result()` to include `overall_confidence` with breakdown

### Phase 2 — Agent Card Enrichment (Day 1-2)
5. Update each agent's `_deterministic()` to output `evidence`, `score_drivers`, `key_assumptions`, `source_attribution`
6. Rename/restructure `key_insights` → `evidence` (positive/negative classification)
7. Add `why_this_score` as derived from `reasoning` with better fallback logic

### Phase 3 — Debate Rewrite (Day 2)
8. Rewrite `debate.py` to produce structured disagreements with vote_tally, positions, moderator_summary
9. Update `debate_node.py` fallback to build this structure deterministically
10. Add `uncertainty_drivers` to debate output

### Phase 4 — Synthesis & Recommendation (Day 2-3)
11. Add `why_not` panel to `synthesis.py` `_fallback()`
12. Add weighted formula display in recommendation
13. Add regret forecast (from timeline scores)
14. Add alternate universe comparison

### Phase 5 — Frontend UI (Day 3-4)
15. Create all React components listed above
16. Wire to API response fields
17. Add animations/transitions for waterfall charts
18. Each component must handle loading, empty, and error states

### Phase 6 — Identity Agent Rebuild (Day 4)
19. Rewrite identity agent with purpose/values/lifestyle/motivation analysis
20. Ensure both LLM and deterministic modes produce rich output

---

## Testing Requirements

Each backend change must pass:
```bash
python3 -m pytest tests/test_simulation_workflow.py -v  # 20 tests
python3 -m pytest tests/test_graph_agents.py -v          # 35+ tests
python3 -m pytest tests/ --tb=short -k "not litellm"     # 204+ tests
```

No regressions. The `litellm` failures (8 tests) are pre-existing and unrelated.

## Key Constraints

- All float values sent to frontend must be `round()` to 1-2 decimal places.
- Deterministic (fallback) mode must always produce valid output — never crash.
- `safe_lower()`, `safe_float()`, `safe_int()` from `deterministic_formulas.py` should be used for type safety.
- The `quota_manager` offline/deterministic modes must be respected.
- No new external dependencies unless absolutely required.
- All new fields must have sensible defaults if source data is missing.
