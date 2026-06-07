"""
LangGraph State Definition for FutureWeave Multi-Agent System.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class SimulationPhase(str, Enum):
    ORCHESTRATION = "orchestration"
    PARALLEL_AGENTS = "parallel_agents"
    DEBATE = "debate"
    TIMELINE = "timeline"
    EVENTS = "events"
    CRITIQUE = "critique"
    FUTURE_SELF = "future_self"
    SYNTHESIS = "synthesis"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class AgentOutput:
    agent_name: str
    output: dict
    confidence: float
    latency_ms: float
    model_used: str
    token_count: int = 0
    error: Optional[str] = None


@dataclass
class EconomicState:
    gdp_growth: Optional[float] = None
    inflation_cpi: Optional[float] = None
    unemployment_rate: Optional[float] = None
    salary_growth_pct: Optional[float] = None
    cost_of_living_index: Optional[float] = None
    industry_health: Optional[float] = None
    automation_risk: Optional[float] = None
    interest_rate: Optional[float] = None
    data_sources: List[str] = field(default_factory=list)
    confidence: float = 0.0
    data_available: bool = False
    data_freshness: Dict[str, str] = field(default_factory=dict)
    data_errors: Dict[str, str] = field(default_factory=dict)


@dataclass
class CareerState:
    skill_growth: float = 50.0
    employability: float = 60.0
    promotion_timeline: List[str] = field(default_factory=list)
    leadership_score: float = 30.0
    industry_demand: float = 65.0
    role: str = "software_engineer"
    seniority: str = "entry"
    projected_roles: List[str] = field(default_factory=list)


@dataclass
class FinancialState:
    net_worth: float = 0.0
    savings_rate: float = 44.3
    monthly_income: float = 0.0
    monthly_expenses: float = 44000.0
    disposable_income: float = 0.0
    debt: float = 0.0
    investment_return: float = 10.0
    risk_profile: str = "moderate"


@dataclass
class HealthState:
    burnout_risk: float = 35.0
    stress_score: float = 38.0
    work_life_balance: float = 60.0
    physical_health: float = 65.0
    mental_health: float = 60.0


@dataclass
class RelationshipState:
    family_stability: float = 52.0
    social_connection: float = 60.0
    romantic_relationship: float = 50.0
    community_support: float = 55.0


@dataclass
class OpportunityState:
    career_opportunities: float = 65.0
    startup_opportunities: float = 70.0
    educational_opportunities: float = 60.0
    network_opportunities: float = 55.0
    detected_opportunities: List[dict] = field(default_factory=list)


@dataclass
class DebateEntry:
    topic: str
    agent_a: str
    agent_b: str
    position_a: str
    position_b: str
    resolution: str
    tradeoff_identified: str


@dataclass
class CriticEvaluation:
    agent_name: str
    score: float
    passed: bool
    issues: List[str]
    recommendations: List[str]


@dataclass
class YearState:
    year_label: str
    narrative: str
    economic: EconomicState = field(default_factory=EconomicState)
    career: CareerState = field(default_factory=CareerState)
    financial: FinancialState = field(default_factory=FinancialState)
    health: HealthState = field(default_factory=HealthState)
    relationship: RelationshipState = field(default_factory=RelationshipState)
    opportunity: OpportunityState = field(default_factory=OpportunityState)


@dataclass
class TimelineState:
    label: str
    archetype: str
    years: Dict[str, YearState] = field(default_factory=dict)
    events: List[dict] = field(default_factory=list)
    final_outcome: Optional[dict] = None
    critic_evaluation: Optional[CriticEvaluation] = None


@dataclass
class FutureSelfState:
    timeline_label: str
    persona: str
    biography: str
    memory: List[str] = field(default_factory=list)
    perspectives: Dict[str, str] = field(default_factory=dict)


@dataclass
class SimulationState:
    decision: str
    context: dict
    phase: SimulationPhase = SimulationPhase.ORCHESTRATION
    error: Optional[str] = None

    economic: EconomicState = field(default_factory=EconomicState)
    career: CareerState = field(default_factory=CareerState)
    financial: FinancialState = field(default_factory=FinancialState)
    health: HealthState = field(default_factory=HealthState)
    relationship: RelationshipState = field(default_factory=RelationshipState)
    opportunity: OpportunityState = field(default_factory=OpportunityState)

    agent_outputs: Dict[str, AgentOutput] = field(default_factory=dict)
    debates: List[DebateEntry] = field(default_factory=list)
    timelines: Dict[str, TimelineState] = field(default_factory=dict)
    future_selves: Dict[str, FutureSelfState] = field(default_factory=dict)
    events: Dict[str, list] = field(default_factory=dict)
    critic_evaluations: List[CriticEvaluation] = field(default_factory=list)
    synthesis_result: Optional[dict] = None

    timeline_raw_data: Dict[str, dict] = field(default_factory=dict)
    critic_result: Optional[dict] = None
    monte_carlo_results: Optional[dict] = None
    memory_context: Optional[dict] = None
    simulation_id: Optional[str] = None
    token_usage: Dict[str, int] = field(default_factory=dict)
    latency_ms: float = 0.0


@dataclass
class FutureChatState:
    timeline_label: str
    user_question: str
    conversation_history: List[dict] = field(default_factory=list)
    future_self_persona: Optional[FutureSelfState] = None
    response: Optional[str] = None
