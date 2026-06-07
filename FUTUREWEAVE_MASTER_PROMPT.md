# FUTUREWEAVE STABILIZATION + REAL-TIME DATA + AGENT SYSTEM MASTER PROMPT

You are a senior Staff Engineer auditing and repairing a production-grade AI decision simulation platform called FutureWeave.

The project currently has:

* React frontend
* FastAPI backend
* Multi-agent simulation engine
* Timeline generation
* Monte Carlo simulations
* Real-time data providers
* Gemini + Groq LLM integration
* Dashboard, Timelines, Agents, Confidence, Future Chat, Monte Carlo tabs

The application runs but has major architectural issues.

Your mission is to make the system production-ready.

---

## PRIMARY GOALS

### Goal 1

Fix ALL backend crashes.

Current logs show:

```python
'str' object has no attribute 'get'
```

Find every occurrence where:

```python
variable.get(...)
```

is called without type validation.

Replace with:

```python
if isinstance(variable, dict):
    value = variable.get(...)
else:
    logger.error(...)
```

No agent should ever crash due to malformed data.

---

### Goal 2

Fix Opportunity Agent.

Current log:

```python
Opportunity Agent failed:
'str' object has no attribute 'get'
```

Trace the entire execution path.

Find:

* request input
* agent input
* transformed payload
* output schema

Ensure:

```python
OpportunityAgent
```

always receives validated dictionaries.

Add Pydantic models.

Never allow raw strings where objects are expected.

---

### Goal 3

Fix Economic Agent.

Current error:

```python
compute_gdp_forecast()
takes 1 positional argument
but 4 were given
```

Audit:

```python
compute_gdp_forecast()
```

Find:

* function definition
* all callers

Unify signatures.

Add type hints.

Add tests.

---

### Goal 4

No Agent Failures

Every agent must return:

```python
{
   "status":"success",
   "data":...
}
```

or

```python
{
   "status":"fallback",
   "data":...
}
```

Never:

```python
None
```

Never:

```python
Exception
```

Never blank output.

---

## REAL-TIME DATA REQUIREMENTS

FutureWeave should not be a fake simulation.

It must use live data wherever possible.

---

### Career Decisions

Use:

* LinkedIn Jobs
* RapidAPI Jobs
* Adzuna
* JSearch
* World Bank
* Government labour data

Fetch:

```python
job_growth
market_demand
average_salary
hiring_trend
industry_growth
```

in real time.

---

### Education Decisions

Examples:

```text
CSE vs AIML
MBA vs Work
Study Abroad vs India
```

Use:

* QS rankings
* Times Higher Education
* NIRF
* placement datasets
* salary datasets

Generate live comparisons.

---

### Startup Decisions

Examples:

```text
quit job
start company
raise funding
join startup
```

Use:

* Crunchbase
* YCombinator data
* funding trends
* startup failure statistics

Generate live probabilities.

---

### Finance Decisions

Examples:

```text
buy house
invest
loan
savings
```

Use:

* RBI
* World Bank
* inflation APIs
* market APIs

---

### Relocation Decisions

Examples:

```text
move to Bangalore
move abroad
switch cities
```

Use:

* cost of living
* housing
* salaries
* taxes
* quality of life

from live APIs.

---

### General Life Decisions

FutureWeave must support:

```text
career
education
startup
job
relationships
marriage
relocation
business
investments
higher studies
freelancing
content creation
career switch
```

The system should dynamically classify decisions.

Do NOT hardcode only:

```text
job
college
```

---

## AGENT SYSTEM IMPROVEMENTS

Current agents:

```text
Economic
Career
Financial
Health
Relationship
Opportunity
```

Expand to:

```text
Career Agent
Economic Agent
Financial Agent
Education Agent
Startup Agent
Relocation Agent
Opportunity Agent
Relationship Agent
Health Agent
Risk Agent
Market Agent
Future Self Agent
```

All run in parallel.

---

## LLM SYSTEM IMPROVEMENTS

Current logs show:

```python
429 RESOURCE_EXHAUSTED
```

for Gemini.

and

```python
Rate limit exceeded
```

for Groq.

Implement:

```python
ProviderRouter
```

Priority:

```python
OpenAI
Gemini
Groq
OpenRouter
Anthropic
```

Automatic failover.

---

### Add caching

Cache identical prompts.

Example:

```python
decision + context hash
```

Store:

```python
Redis
```

or local cache.

TTL:

```python
1 hour
```

---

### Reduce token usage

Current system is making:

```text
6 agents
3 timelines
3 future selves
1 synthesis
```

per simulation.

Optimize.

Only run expensive LLM calls when needed.

Use deterministic engines whenever possible.

---

## TIMELINE ENGINE

Current timeline panels frequently appear blank.

Requirements:

Generate:

```python
Timeline A
Optimistic

Timeline B
Expected

Timeline C
Worst Case
```

For each:

```python
Year 1
Year 2
Year 3
Year 5
Year 10
```

Always populate.

Never return empty values.

---

## MONTE CARLO

Current Monte Carlo often displays:

```text
0%
0%
0%
```

Fix simulation logic.

Requirements:

Return:

```python
success_probability
failure_probability
regret_probability
confidence_interval
```

Use:

```python
1000+
iterations
```

based on actual decision factors.

---

## FRONTEND REQUIREMENTS

DO NOT redesign UI.

KEEP EXISTING CYBERPUNK UI.

KEEP:

* colors
* layout
* typography
* animations

ONLY FIX BROKEN DATA FLOWS.

---

### Agents Tab

Display:

```text
Career Agent
Economic Agent
Financial Agent
Education Agent
Startup Agent
Risk Agent
```

with:

```text
Status
Confidence
Reasoning
Key Insights
```

---

### Timeline Tab

Display:

```text
Timeline A
Timeline B
Timeline C
```

with actual generated content.

---

### Monte Carlo Tab

Display:

```text
Success %
Failure %
Regret %
Distribution Graph
```

using real backend data.

---

### Confidence Tab

Display:

```text
Decision Confidence
Data Quality Score
Simulation Reliability
```

---

### Future Chat

Allow user to chat with:

```text
Future Self
Timeline A Self
Timeline B Self
Timeline C Self
```

---

## OBSERVABILITY

Add structured logging everywhere.

Log:

```python
agent start
agent finish
api latency
llm latency
provider used
fallback used
```

No silent failures.

---

## TESTING

Create tests for:

```python
simulate endpoint
timeline generation
monte carlo
agent execution
real-time data providers
llm fallbacks
```

Target:

```python
90%+ coverage
```

---

## FINAL DELIVERABLE

Produce:

1. Fixed backend
2. Fixed agent system
3. Working real-time data integration
4. Stable Monte Carlo
5. Working timelines
6. Working confidence engine
7. Working future chat
8. Provider failover
9. Zero agent crashes
10. Frontend fully connected to all backend endpoints
11. No blank tabs
12. No hardcoded job-only logic
13. Production-ready architecture
14. Detailed explanation of every change made
15. Exact files modified and why

Do not stop after identifying issues. Implement all fixes and provide complete code changes.
