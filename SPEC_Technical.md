# Technical Spec — Decision Simulator

> How it actually works. Data models, agent logic, causal rules, prompt templates, API reference.

---

## 1. Input schema

```json
{
  "decision": "string — the decision being simulated (e.g. 'Should I drop out to start a company?')",
  "context": {
    "age":             "integer, 16–100",
    "location":        "string — city name (e.g. 'Bangalore')",
    "risk_tolerance":  "integer, 1–10",
    "months_savings":  "integer, 0–120",
    "dependents":      "integer, 0–20",
    "top_skills":      ["string"],
    "financial_condition": "string — e.g. 'lower middle class', 'comfortable'",
    "interests":       ["string"],
    "optional_context": "string — free text, max 500 chars"
  },
  "user_email": "string | null — optional, for follow-up"
}
```

**Validation rules:**
- `age` must be 16–100; reject outside range
- `risk_tolerance` must be 1–10; clamp if outside
- `dependents` must be 0–20; cap at 20
- `top_skills` must have at least 1 entry; use `["general"]` as fallback
- `decision` must be non-empty string, max 500 chars

---

## 2. Timeline generation

### 2.1 Three fixed timelines (MVP)

| Key        | Primary orientation     | Income growth/yr | Stress bias |
|------------|-------------------------|------------------|-------------|
| Timeline A | Work-life balance       | 3–5%             | Low         |
| Timeline B | Steady growth           | 6–9%             | Medium      |
| Timeline C | Aggressive income/career| 10–15%           | High        |

### 2.2 Fixed year intervals

Years simulated: **1, 3, 5, 10**. No interpolation between years.

### 2.3 Causal variable definitions

| Variable       | Range  | Unit              | Derivation |
|----------------|--------|-------------------|------------|
| income         | 0–100  | LPA score (₹)     | Base salary + annual growth rate per timeline |
| career_growth  | 0–100  | index             | Promotion speed + skill acquisition rate |
| stress         | 0–100  | index             | `(weekly_hours / 10) + (dependents × 3) - (risk_tolerance × 2)`, clamped 0–100 |
| health         | 0–100  | index             | Starts at 70; decays by 5–10 if stress > 70 for 2+ consecutive years |
| relationships  | 0–100  | index             | Decays when work hours > 50/week; boosted by low stress |
| happiness      | 0–100  | index             | `(health × 0.3) + (relationships × 0.3) + (income_relative × 0.2) + (career_growth × 0.2)` |
| opportunity    | 0–100  | %                 | Probability of next role change within 2 years |

`income_relative` = income score relative to local median (grounded via World Bank + AmbitionBox data).

### 2.4 Disposable income calculation

```
monthly_gross     = (salary_lpa × 100_000) / 12
monthly_after_tax = monthly_gross × 0.75          # rough 25% effective tax
living_cost       = base_city_cost × (1 + dependents × 0.3)
disposable_income = monthly_after_tax - living_cost
```

---

## 3. Agent descriptions

### 3.1 Timeline Agent (`agents/timeline.py`)

**One LLM call** per simulation (batched — all 3 timelines × 4 years in a single prompt).

- Loads `prompts/batch_timeline_prompt.txt`
- Substitutes: `{decision}`, `{context_json}`, `{grounding_data}`
- Returns: `{TimelineA: {Year1: {node: score}, ...}, TimelineB: ..., TimelineC: ...}`
- Cache key: SHA-256 of `(decision + context + salary_entry_lpa + location)`
- Fallback: `_deterministic_all_years()` — rule-based score transitions, no LLM

### 3.2 Chaos Agent (`agents/chaos.py`)

**Zero LLM calls.** Fully deterministic.

- Exactly **1 event per timeline** from a personality-keyed event library (A/B/C)
- 40% chance of a second shared event (family emergency, market crash)
- Events fire at Year 3, 5, or 10 — never Year 1
- Each event modifies 1–3 variables by ±5–20 points
- Event pool per personality:
  - A (conservative): Steady Promotion, Health Scare, Stable Milestone
  - B (balanced): Economic Slowdown, Unexpected Mentor, Industry Disruption
  - C (aggressive): High-Stakes Bet, Burnout Episode, Lucky Break
- Shared pool: Family Emergency, Market Crash

### 3.3 Synthesis Agent (`agents/synthesis.py`)

**One LLM call** per simulation (batched — regrets + letters + comparison in a single prompt).

- Loads `prompts/batch_synthesis_prompt.txt`
- Substitutes: `{decision}`, `{age}`, `{timelines_json}`
- Returns: `{regrets: {...}, letters: {...}, comparison: {...}}`
- Cache key: SHA-256 of `(synthesis + decision + context + timeline_keys)`
- Fallback: `_build_fallback_store()` — template-based outputs, no LLM

### 3.4 Regret Agent (`agents/regret.py`)

Thin wrapper. Reads from the synthesis store populated by `batch_synthesis()`.

**Output schema:**
```json
{
  "lost_opportunity": "string — specific thing sacrificed (e.g. 'startup equity at Series A')",
  "missed_identity":  "string — who you didn't become (e.g. 'a founder')",
  "emotional_cost":   "string — how it shows up day-to-day (e.g. 'low-grade anxiety on Sunday evenings')"
}
```

Regret items must be **specific to the user's context**. If `dependents > 0`, regret should reference time with family. If `risk_tolerance > 7`, regret should reference the safer path not taken.

### 3.5 Letter Agent (`agents/letter.py`)

Thin wrapper. Reads from the synthesis store.

**Letter constraints:**
- Length: 140–200 words
- Structure: Gratitude → Hard truth → Concrete advice → Regret note
- Tone: calibrated by Year 10 happiness score
  - happiness > 70: proud, warm
  - happiness 40–70: wistful, honest
  - happiness < 40: exhausted, cautionary
- Must include **one concrete sensory or situational memory** (e.g. "the 2am Slack message that changed everything", "chai with your team before the pivot")

### 3.6 Comparator Agent (`agents/comparator.py`)

Thin wrapper. Reads from the synthesis store.

**Output schema:**
```json
{
  "common_patterns": "string — what all three timelines share",
  "key_differences": "string — where they diverge most",
  "hinge_point":     "string — the single factor that most determines outcome divergence"
}
```

---

## 4. Real-world data grounding

### 4.1 CPI (inflation)

Source: **World Bank Open Data** — `FP.CPI.TOTL.ZG` indicator for India.

```
GET https://api.worldbank.org/v2/country/IN/indicator/FP.CPI.TOTL.ZG?format=json
```

Fallback: `5.5%` (static default) if API unavailable.

CPI interpretation applied in `prompts/analysis_prompt.txt`:
- CPI > 6%: high cost pressure, reduced disposable income, increased stress
- CPI 3–6%: stable conditions
- CPI < 3%: lower cost pressure, improved savings potential

### 4.2 Salary data

Priority chain: **AmbitionBox** (scrape) → **Indeed Scraper API** (key required) → **OpenWeb Ninja** (key required) → static `SALARY_DATABASE` in `data_grounding.py`.

### 4.3 Macro indicators

Source: **World Bank Open Data**
- Unemployment: `SL.UEM.TOTL.ZS`
- GDP growth: `NY.GDP.MKTP.KD.ZG`

All live data cached in-memory for 24 hours.

---

## 5. LLM configuration

### 5.1 Model

Default: `groq/llama3-8b-8192` (via litellm). Set `GROQ_API_KEY` in `.env`.

To use a different model, pass `model=` to `call_llm()` or set `LLM_MODE_OVERRIDE`.

### 5.2 Call budget per simulation

| Call | Agent | Prompt file |
|------|-------|-------------|
| 1 | Timeline Agent | `batch_timeline_prompt.txt` |
| 2 | Synthesis Agent | `batch_synthesis_prompt.txt` |
| — | Analysis (optional) | `analysis_prompt.txt` |

**Total: 2 LLM calls per simulation** (down from 12 in the original design).

### 5.3 Quota manager

State persisted in `quota_state.json`.

| Condition | Mode switch |
|-----------|-------------|
| `calls_today > 15` | `full` → `low` (synthesis skipped) |
| `rate_limit_hits >= 2` | any → `offline` (all LLM calls blocked) |
| Daily reset | resets `calls_today` and `rate_limit_hits` |

In `low` mode: timeline LLM call still runs; synthesis uses deterministic fallback.
In `offline` mode: all agents use deterministic fallbacks; simulation still completes.

### 5.4 Cache

Two-tier: in-memory → disk (`.llm_cache/`). TTL: 7 days (configurable via `LLM_CACHE_TTL_DAYS`).
Cache key: SHA-256 of `(model + prompt)`.

---

## 6. Error handling and edge cases

| Input | Handling |
|-------|----------|
| `dependents > 20` | Cap at 20 |
| `risk_tolerance` outside 1–10 | Clamp to range |
| `skills` empty | Use `["general"]` |
| LLM returns invalid JSON | `json.loads` fails → deterministic fallback |
| LLM rate limit (429) | `rate_limit_hits += 1`; after 2 hits → offline mode |
| Non-rate-limit LLM error | Logged, fallback used; quota not penalised |
| World Bank API down | CPI fallback: `5.5%`, source: `"fallback"` |
| AmbitionBox scrape fails | Falls through to next salary source |
| All salary sources fail | Uses static `SALARY_DATABASE` |
| `disposable_income < 0` | Displayed as negative; not clamped — it's a real signal |

---

## 7. API reference

Base URL: `http://localhost:8000`

### `POST /simulate`

Run a full simulation.

**Request:**
```json
{
  "decision": "string",
  "context": { ... },
  "user_email": "string | null"
}
```

**Response:** `SimulateResponse` — timelines, causal_data, interpretations, grounding, computed, analysis, regrets, letters, comparison, simulation_id.

### `GET /health`

```json
{
  "status": "ok",
  "llm_mode": "full | low | offline",
  "calls_today": 3,
  "cache_enabled": true,
  "quota": { "mode": "...", "calls_today": 3, "rate_limit_hits": 0 }
}
```

### `POST /pivot`

Branch a timeline from a specific year with an alternative outcome.

**Request:** `original_timeline`, `event_year`, `alternative_outcome`, `decision`, `context`

### `GET /simulation/{id}`

Retrieve a saved simulation by ID.

### `POST /followup`

Submit a follow-up response (actual outcome after the decision).

---

## 8. Evaluation criteria

A simulation output is considered good if:

1. **Plausible numbers** — income doesn't jump more than 15% in a single year (except chaos events)
2. **Specific regret** — regret items reference the user's actual context (dependents, skills, location), not generic phrases
3. **Concrete letter** — letter contains at least one specific situational memory, not just abstract advice
4. **Causal consistency** — if stress > 70 for 2+ years, health must have decreased
5. **Timeline differentiation** — Year 10 happiness and income scores must differ meaningfully across A/B/C (not within 5 points of each other)
6. **Chaos diversity** — no two timelines should have the same chaos event

To A/B test prompts: run 5 simulations with identical input, check variance in regret specificity and letter concreteness.

---

## 9. Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | — | Required for LLM calls |
| `LLM_SESSION_BUDGET` | 50 | Max calls before quota kicks in |
| `LLM_BUDGET_FULL` | 10 | Remaining calls threshold for low mode |
| `LLM_BUDGET_LOW` | 3 | Remaining calls threshold for offline mode |
| `LLM_CACHE_TTL_DAYS` | 7 | Cache TTL in days |
| `LLM_MODE_OVERRIDE` | — | Force `full`, `low`, or `offline` |
| `INDEED_API_KEY` | — | Optional, for Indeed salary data |
| `RAPIDAPI_KEY` | — | Optional, for OpenWeb Ninja salary data |
