from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, Text, DateTime, JSON, ForeignKey, create_engine
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users_v2"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    simulations = relationship("SimulationV2", back_populates="user")


class SimulationV2(Base):
    __tablename__ = "simulations_v2"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users_v2.id"), nullable=True)
    decision = Column(Text, nullable=False)
    decision_parsing = Column(JSON, default=dict)
    user_profile = Column(JSON, default=dict)
    economic_data = Column(JSON, default=dict)
    confidence_overall = Column(Float, default=0.0)
    confidence_tier = Column(String(16), default="low")
    simulation_version = Column(String(16), default="2.0")
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="simulations")
    timelines = relationship("TimelineRow", back_populates="simulation", cascade="all, delete-orphan")
    agent_outputs = relationship("AgentOutputRow", back_populates="simulation", cascade="all, delete-orphan")
    monte_carlo_runs = relationship("MonteCarloRun", back_populates="simulation", cascade="all, delete-orphan")
    pivot_events = relationship("PivotEvent", back_populates="simulation", cascade="all, delete-orphan")


class TimelineRow(Base):
    __tablename__ = "timelines_v2"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    simulation_id = Column(String(36), ForeignKey("simulations_v2.id"), nullable=False)
    key = Column(String(32), nullable=False)
    archetype = Column(String(64), nullable=False)
    final_score = Column(Float, default=50.0)
    regret = Column(Text, default="")
    letter = Column(Text, default="")
    year1_data = Column(JSON, default=dict)
    year3_data = Column(JSON, default=dict)
    year5_data = Column(JSON, default=dict)
    year10_data = Column(JSON, default=dict)
    events = Column(JSON, default=list)
    simulation = relationship("SimulationV2", back_populates="timelines")


class AgentOutputRow(Base):
    __tablename__ = "agent_outputs_v2"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    simulation_id = Column(String(36), ForeignKey("simulations_v2.id"), nullable=False)
    agent_name = Column(String(64), nullable=False)
    score = Column(Float, default=50.0)
    confidence = Column(Float, default=0.0)
    reasoning = Column(Text, default="")
    evidence = Column(JSON, default=list)
    assumptions = Column(JSON, default=list)
    risks = Column(JSON, default=list)
    opportunities = Column(JSON, default=list)
    recommendation = Column(Text, default="")
    impact = Column(String(32), default="neutral")
    year_scores = Column(JSON, default=dict)
    simulation = relationship("SimulationV2", back_populates="agent_outputs")


class MonteCarloRun(Base):
    __tablename__ = "monte_carlo_runs_v2"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    simulation_id = Column(String(36), ForeignKey("simulations_v2.id"), nullable=False)
    iterations = Column(Integer, default=10000)
    node_distributions = Column(JSON, default=dict)
    percentiles = Column(JSON, default=dict)
    success_probability = Column(Float, default=0.0)
    failure_probability = Column(Float, default=0.0)
    risk_metrics = Column(JSON, default=dict)
    timeline_comparison = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    simulation = relationship("SimulationV2", back_populates="monte_carlo_runs")


class PivotEvent(Base):
    __tablename__ = "pivot_events_v2"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    simulation_id = Column(String(36), ForeignKey("simulations_v2.id"), nullable=False)
    original_timeline_key = Column(String(32), nullable=False)
    event_year = Column(String(16), nullable=False)
    alternative_outcome = Column(Text, nullable=False)
    deltas = Column(JSON, default=dict)
    agent_changes = Column(JSON, default=dict)
    confidence_change = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    simulation = relationship("SimulationV2", back_populates="pivot_events")


def init_db_v2(database_url: str = "sqlite:///simulations_v2.db"):
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    return engine
