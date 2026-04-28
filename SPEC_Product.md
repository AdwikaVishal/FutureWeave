# Product Spec — Decision Simulator

> This document describes what the product does, what's built, and what's planned.
> It is not a technical reference — see [SPEC_Technical.md](SPEC_Technical.md) for that.

---

## What it is

Decision Simulator takes a real life decision and generates three divergent 10-year futures for it. Each future is grounded in real economic data (salaries, inflation, unemployment) and driven by causal rules — not vibes. The output is a structured comparison of timelines, a regret analysis for each, and a letter from your future self.

**This is a simulation, not a prediction.**

---

## Core user flow

1. User describes a decision and provides context (age, city, risk tolerance, savings, dependents, skills).
2. Engine generates three timelines (A: work-life balance, B: steady growth, C: aggressive income/career).
3. Each timeline runs through Years 1, 3, 5, and 10 with causal score updates and one chaos event.
4. A regret analysis and a letter from the future self are produced per timeline.
5. A cross-timeline comparison surfaces the hinge point — the single factor that most determines divergence.

---

## Feature status

### ✅ Implemented

- Three-timeline generation (A/B/C) via batched LLM call with deterministic fallback
- Causal variable scoring: income, career_growth, stress, health, relationships, happiness, opportunity
- Chaos Agent: structured random events per timeline personality (no LLM)
- Regret Agent: lost_opportunity, missed_identity, emotional_cost per timeline
- Letter from Future Self: LLM-generated (140–200 words) with template fallback
- Cross-timeline comparator: common patterns, key differences, hinge point
- Real economic grounding: World Bank CPI + unemployment, AmbitionBox salary data
- Two-tier LLM cache (memory + disk, 7-day TTL)
- Quota manager: auto-switches full → low → offline based on daily call count and rate-limit errors
- REST API: `POST /simulate`, `GET /health`, `POST /pivot`, `GET /simulation/{id}`, `POST /followup`
- SQLite persistence of simulation results
- React frontend: context form, timeline view, radar chart

### 🚧 In progress

- Frontend polish and mobile layout
- Pivot point UI (branch a timeline at a specific year)

### 📅 Phase 2

- Time scrubbing UI (drag a slider to move through years)
- Emotional temperature map (visual heatmap of wellbeing scores)
- Shared simulations (send a link to a friend)
- Side-by-side comparison view

### 📅 Phase 3

- Ground truth follow-up: email check-in at 6 months with actual outcome
- A/B prompt testing framework
- Multi-country support beyond India

---

## What this is not

- Not a financial advisor
- Not a career counsellor
- Not a prediction engine

Every output page will say: **"This is a simulation, not a prediction. The future bends."**
