from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


SIMULATION_YEARS = ["Year1", "Year3", "Year5", "Year10", "Year20"]
DASHBOARD_METRICS = [
    "life_satisfaction", "freedom", "stress_index", "purpose",
    "wealth", "relationships", "growth", "regret_risk", "decision_confidence",
]


@dataclass
class UserProfile:
    age: int = 25
    location: str = "Bangalore"
    risk_tolerance: float = 0.5
    savings: float = 0.0
    dependents: int = 0
    skills: List[str] = field(default_factory=list)
    industry: str = "technology"
    role: str = "software_engineer"

    relationship_status: str = "single"
    has_children: bool = False
    children_count: int = 0
    health_condition: str = "good"
    debt_amount: float = 0.0
    monthly_expenses: float = 0.0
    current_salary: float = 0.0
    education_level: str = "bachelors"
    years_experience: int = 2
    side_income: float = 0.0
    monthly_savings: float = 0.0
    investments: float = 0.0
    owns_home: bool = False
    city: str = ""
    country: str = "India"


@dataclass
class EconomicData:
    gdp_growth: Optional[float] = None
    inflation_cpi: Optional[float] = None
    unemployment_rate: Optional[float] = None
    salary_growth_pct: Optional[float] = None
    cost_of_living_index: Optional[float] = None
    industry_health: Optional[float] = None
    automation_risk: Optional[float] = None
    interest_rate: Optional[float] = None
    housing_index: float = 1.0
    education_index: float = 1.0
    healthcare_index: float = 1.0
    startup_funding: Optional[float] = None
    immigration_policy_score: Optional[float] = None

    data_sources: Dict[str, str] = field(default_factory=dict)
    data_confidence: float = 0.0
    data_freshness: Dict[str, str] = field(default_factory=dict)
    data_completeness: float = 0.0
    data_errors: Dict[str, str] = field(default_factory=dict)
    data_available: bool = False

    economic_score: float = 50.0
    employment_score: float = 50.0
    industry_score: float = 50.0
    cost_of_living_score: float = 50.0
    salary_score: float = 50.0


@dataclass
class DecisionOption:
    title: str
    description: str = ""
    risk_level: str = "moderate"
    time_horizon: str = "medium"
    upside_potential: str = "moderate"
    downside_risk: str = "moderate"
    liquidity: str = "medium"
    commitment_level: str = "medium"


@dataclass
class YearScores:
    income: float = 50.0
    career_growth: float = 50.0
    stress: float = 50.0
    health: float = 50.0
    relationships: float = 50.0
    happiness: float = 50.0
    opportunity: float = 50.0
    savings: float = 0.0
    net_worth: float = 0.0
    risk_exposure: float = 50.0
    purpose: float = 50.0
    freedom: float = 50.0
    regret: float = 50.0
    burnout_risk: float = 50.0
    learning_growth: float = 50.0
    social_support: float = 50.0


@dataclass
class FuturePath:
    option_key: str
    label: str
    archetype: str
    years: Dict[str, YearScores] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    final_score: float = 50.0
    regret_letter: str = ""
    best_case: Dict[str, float] = field(default_factory=dict)
    expected_case: Dict[str, float] = field(default_factory=dict)
    worst_case: Dict[str, float] = field(default_factory=dict)
    summary: str = ""


@dataclass
class AgentOutput:
    agent_name: str
    score: float
    confidence: float
    reasoning: str
    evidence: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    opportunities: List[str] = field(default_factory=list)
    recommendation: str = ""
    impact: str = ""
    year_scores: Dict[str, float] = field(default_factory=dict)
    score_changes: Dict[str, Any] = field(default_factory=dict)
    data_used: List[str] = field(default_factory=list)
    impact_factors: List[Dict[str, Any]] = field(default_factory=list)
    per_option_scores: Dict[str, float] = field(default_factory=dict)
    option_rankings: List[str] = field(default_factory=list)
    tension_with: List[str] = field(default_factory=list)
    verdict: str = ""


@dataclass
class DebateEntry:
    topic: str
    agents_involved: List[str]
    positions: Dict[str, float]
    consensus_score: float
    disagreement_score: float
    tension_score: float
    resolution: str
    key_tension_pair: tuple = ("", "")
    root_cause: str = ""


@dataclass
class DebateResult:
    entries: List[DebateEntry] = field(default_factory=list)
    voting_matrix: Dict[str, Dict[str, float]] = field(default_factory=dict)
    consensus_summary: str = ""
    overall_tension_score: float = 0.0
    primary_disagreement: str = ""
    agent_alliances: List[List[str]] = field(default_factory=list)


@dataclass
class MonteCarloResult:
    iterations: int = 0
    node_distributions: Dict[str, Dict[str, float]] = field(default_factory=dict)
    percentiles: Dict[str, Dict[str, float]] = field(default_factory=dict)
    success_probability: float = 0.0
    failure_probability: float = 0.0
    risk_metrics: Dict[str, float] = field(default_factory=dict)
    timeline_comparison: Dict[str, Dict[str, float]] = field(default_factory=dict)
    best_case: Dict[str, float] = field(default_factory=dict)
    expected_case: Dict[str, float] = field(default_factory=dict)
    worst_case: Dict[str, float] = field(default_factory=dict)
    regret_probability: float = 0.0
    opportunity_cost: float = 0.0
    path_dependencies: Dict[str, float] = field(default_factory=dict)


@dataclass
class ConfidenceBreakdown:
    overall: float = 0.0
    agent_agreement: float = 0.0
    data_quality: float = 0.0
    simulation_stability: float = 0.0
    economic_certainty: float = 0.0
    historical_similarity: float = 0.0
    missing_data_penalty: float = 0.0
    data_freshness_score: float = 0.0
    data_completeness_score: float = 0.0
    per_aspect: Dict[str, float] = field(default_factory=dict)
    per_agent: Dict[str, float] = field(default_factory=dict)
    uncertainty_drivers: List[str] = field(default_factory=list)
    tier: str = "low"


@dataclass
class RegretAnalysis:
    will_regret_not_trying: float = 50.0
    will_regret_risk: float = 50.0
    will_regret_delaying: float = 50.0
    will_regret_comfort: float = 50.0
    overall_regret_risk: float = 50.0
    regret_timeline: Dict[str, float] = field(default_factory=dict)
    biggest_regret_source: str = ""
    regret_letter: str = ""
    by_option: Dict[str, float] = field(default_factory=dict)


@dataclass
class LifeDashboard:
    life_satisfaction: float = 50.0
    freedom_index: float = 50.0
    stress_index: float = 50.0
    purpose_index: float = 50.0
    wealth_index: float = 50.0
    relationship_index: float = 50.0
    growth_index: float = 50.0
    regret_risk: float = 50.0
    decision_confidence: float = 50.0
    dimension_breakdown: Dict[str, float] = field(default_factory=dict)
    overall_score: float = 50.0
    trend: str = "stable"
    primary_concern: str = ""
    top_opportunity: str = ""


@dataclass
class CausalEdge:
    source: str
    target: str
    strength: float
    effect_type: str
    description: str


@dataclass
class CausalGraph:
    nodes: List[str] = field(default_factory=list)
    edges: List[CausalEdge] = field(default_factory=list)
    positive_loops: List[List[str]] = field(default_factory=list)
    negative_loops: List[List[str]] = field(default_factory=list)


@dataclass
class PivotResult:
    original_timeline: FuturePath = field(default_factory=FuturePath)
    pivoted_timeline: FuturePath = field(default_factory=FuturePath)
    deltas: Dict[str, float] = field(default_factory=dict)
    agent_changes: Dict[str, float] = field(default_factory=dict)
    confidence_change: float = 0.0
    new_debate: Optional[DebateResult] = None
    new_life_dashboard: Optional[LifeDashboard] = None
    new_regret: Optional[RegretAnalysis] = None


@dataclass
class SimulationResult:
    decision: str
    decision_parsing: Dict[str, Any] = field(default_factory=dict)
    user_profile: UserProfile = field(default_factory=UserProfile)
    economic_data: EconomicData = field(default_factory=EconomicData)

    options: List[DecisionOption] = field(default_factory=list)
    future_paths: Dict[str, FuturePath] = field(default_factory=dict)

    agent_outputs: Dict[str, AgentOutput] = field(default_factory=dict)
    debate_result: Optional[DebateResult] = None
    monte_carlo: Optional[MonteCarloResult] = None
    confidence: ConfidenceBreakdown = field(default_factory=ConfidenceBreakdown)
    regret_analysis: Optional[RegretAnalysis] = None
    life_dashboard: Optional[LifeDashboard] = None

    causal_graph: Optional[CausalGraph] = None
    simulation_id: str = ""
    warnings: List[str] = field(default_factory=list)

    real_data_scores: Optional[Dict[str, Any]] = None
    data_sources_used: List[str] = field(default_factory=list)
    data_freshness: Dict[str, str] = field(default_factory=dict)
    economic_indicators: Dict[str, Any] = field(default_factory=dict)
