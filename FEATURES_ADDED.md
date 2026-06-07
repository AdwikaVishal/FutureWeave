# FutureWeave — Decision Intelligence Platform

"The Operating System for Human Decisions."

---

## Core Architecture

### 12 Independent Decision Agents
Each agent independently scores every option, producing per-option scores, reasoning, evidence, and confidence:

| Agent | Focus | Analysis |
|-------|-------|----------|
| **Financial** | Wealth, cash flow, savings, investments, debt, ROI | Income potential, net worth trajectory, savings rate |
| **Risk** | Downside risk, uncertainty, volatility, failure probability | Risk exposure, downside scenarios, safety margins |
| **Opportunity** | Future upside, network effects, career leverage, optionality | Hidden opportunities, growth vectors, optionality |
| **Health** | Stress, burnout, sleep, physical health | Burnout risk, work-life balance, health trajectory |
| **Relationship** | Family impact, friendship impact, social support | Social connection, family stability, community support |
| **Time** | Opportunity cost, years invested, time lost | Time horizon, compounding effects, delay costs |
| **Happiness** | Life satisfaction, purpose, fulfillment | Well-being trajectory, satisfaction curves |
| **Identity** | Alignment with values, personal growth, meaning | Value congruence, growth alignment, authenticity |
| **Career** | Skill growth, employability, promotion timeline | Career acceleration, skill acquisition, seniority |
| **Strategic** | Long-term positioning, leverage, competitive advantage | Strategic position, bargaining power, market timing |
| **Lifestyle** | Daily experience, location freedom, work style | Location flexibility, work arrangement, daily satisfaction |
| **Economic** | Macro conditions, industry health, market trends | GDP, inflation, industry health, salary growth |

### Agent Debate System
- 6 debate topics covering safe vs ambitious, stability vs growth, income vs purpose, etc.
- Consensus Score (0-100)
- Disagreement Matrix (voting matrix between all agent pairs)
- Decision Tension Score
- Agent Alliances (agents that consistently agree)
- Primary Disagreement identification

### Monte Carlo Engine
- 10,000+ stochastic simulations
- Variables: economic cycles, job loss, startup success, market growth, inflation, health events, family events
- Outputs: Success Probability, Failure Probability, Expected Outcome, Regret Probability
- Best Case (P90), Expected Case (Mean), Worst Case (P10)

### Regret Engine
- 4 regret dimensions: Not Trying, Taking Risk, Delaying, Staying Comfortable
- Overall Regret Risk Score
- Regret Timeline (Year 1 → Year 20)
- Regret Letter from future self
- Per-option regret breakdown

### Life Dashboard
9 key metrics:
- Life Satisfaction Index
- Freedom Index
- Stress Index
- Purpose Index
- Wealth Index
- Relationship Index
- Growth Index
- Regret Risk
- Decision Confidence

### Confidence Engine
- 7-component confidence breakdown
- Agent agreement, data quality, simulation stability, economic certainty, historical similarity, data freshness, data completeness
- Tier: High / Medium / Low
- Uncertainty drivers identification

### Causal Graph
- 12 causal edges between life dimensions
- Positive and negative feedback loops identified
- Strength-weighted relationships

### Real Data Engine
- Live data from: World Bank (GDP, unemployment, CPI), AmbitionBox (salary scraping)
- 5 composite scores: Economic Strength, Employment, Industry Growth, Cost of Living, Salary Opportunity
- Data freshness tracking (live vs static)
- Confidence scoring per data source

---

## API Endpoints

### Frontend (Vite → Backend Proxy)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v2/simulate` | POST | Full simulation (agents, MC, regret, dashboard) |
| `/v2/pivot` | POST | What-if scenario simulation |
| `/v2/simulation/{id}` | GET | Retrieve saved simulation |
| `/v2/simulate-and-save` | POST | Simulate + persist to database |
| `/v2/health` | GET | API health check |

### Backend (api.py)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/simulate` | POST | Legacy simulation |
| `/simulate-v2` | POST | LangGraph version |
| `/score` | POST | Personalised scoring |
| `/peer-comparison` | GET | Anonymised peer data |
| `/compare-two` | POST | Side-by-side decision comparison |
| `/counsellor/students` | GET | Counsellor dashboard |
| `/job-market` | GET | Live job market data |
| `/economic-research` | POST | Economic research agent |
| `/future-chat` | POST | Future self conversation |
| `/monte-carlo` | POST | Standalone MC simulation |
| `/memory/query` | POST | Memory retrieval |
| `/outcomes` | GET | Outcome library |

---

## Frontend Tabs

| Tab | Component | Features |
|-----|-----------|----------|
| **Dashboard** | `Dashboard.tsx` | Overview cards, life dashboard, regret analysis, agent debate, data sources, economic indicators, path comparison, MC summary |
| **Paths** | `TimelineView.tsx` | Life trajectory charts, year-by-year detail, best/expected/worst case |
| **Agents** | `AgentsView.tsx` | 12 agent cards with scores, reasoning, evidence, tensions, option rankings |
| **Monte Carlo** | `MonteCarloView.tsx` | Distribution means, path comparison, risk metrics, case scenarios |
| **Confidence** | `ConfidenceView.tsx` | Overall gauge, component scores, per-aspect radar, per-agent confidence |
| **Explorer** | `Explorer.tsx` | Year-by-year path comparison across all dimensions |
| **Regret** | `RegretView.tsx` | Regret sources, timeline, per-option breakdown, regret letter |
| **Pivot** | `PivotView.tsx` | What-if simulator with side-by-side comparison and delta effects |
| **Future Chat** | `FutureChat.tsx` | Conversational interface with simulation context |

---

## Database Schema

- **users_v2** — User accounts
- **simulations_v2** — Simulation results with full JSON payloads
- **timelines_v2** — Per-path year-by-year scores and events
- **agent_outputs_v2** — Per-agent outputs, scores, reasoning
- **monte_carlo_runs_v2** — MC iteration results and distributions
- **pivot_events_v2** — What-if pivot history
- **simulations** — Legacy simulation storage
- **counsellor_notes** — Counsellor annotations
- **outcome_records** — Longitudinal follow-up tracking

---

## Tech Stack

**Backend:** Python, FastAPI, SQLAlchemy, Pydantic, Uvicorn
**AI/ML:** LangGraph (agent orchestration), 12 rule-based agents, Monte Carlo simulation
**Data:** World Bank API, AmbitionBox scraping, static datasets
**Frontend:** React 19, TypeScript, Vite, Zustand (state), Recharts (charts), Lucide (icons)
**Database:** SQLite (dev) / PostgreSQL (production)

---

## How to Run

```bash
# Start backend (port 8000)
cd sim-engine && uvicorn api:app --reload --port 8000

# Start frontend (port 5173, proxies /v2 to :8000)  
cd sim-ui && npm run dev

# Or use the combined launcher:
./run.sh
```

Open http://localhost:5173 in your browser.

---

## Verification Status

- [x] Frontend TypeScript build passes (0 errors)
- [x] Backend API starts and responds
- [x] `/v2/simulate` endpoint produces full simulation
- [x] All 12 agents execute in parallel
- [x] Monte Carlo simulation runs (50-10000 iterations)
- [x] Regret analysis generates scores and letters
- [x] Life dashboard computes 9 dimensions
- [x] Confidence engine evaluates uncertainty
- [x] Agent debate produces tension scores and alliances
- [x] Real data integration (World Bank, AmbitionBox)
- [x] Vite dev server proxies to backend
- [x] All 9 frontend tabs render simulation data
