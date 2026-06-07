"""
SQLAlchemy models for longitudinal tracking.
"""
from sqlalchemy import create_engine, Column, String, Integer, DateTime, JSON, Text, Float, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

Base = declarative_base()

# Use SQLite for development, PostgreSQL for production
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///simulations.db")

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Simulation(Base):
    __tablename__ = "simulations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String(255), nullable=True)
    decision = Column(Text, nullable=False)
    context = Column(JSON, nullable=False)
    timelines = Column(JSON, nullable=False)
    regrets = Column(JSON, nullable=False)
    comparison = Column(JSON, nullable=False)
    letters = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "user_email": self.user_email,
            "decision": self.decision,
            "context": self.context,
            "timelines": self.timelines,
            "regrets": self.regrets,
            "comparison": self.comparison,
            "letters": self.letters,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class FollowUp(Base):
    __tablename__ = "followups"
    
    id = Column(Integer, primary_key=True, index=True)
    simulation_id = Column(Integer, nullable=False, index=True)
    user_email = Column(String(255), nullable=True)
    actual_timeline = Column(String(50), nullable=True)  # "Timeline A", "B", or "C"
    feedback = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "simulation_id": self.simulation_id,
            "user_email": self.user_email,
            "actual_timeline": self.actual_timeline,
            "feedback": self.feedback,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CounsellorNote(Base):
    __tablename__ = "counsellor_notes"

    id = Column(Integer, primary_key=True, index=True)
    simulation_id = Column(Integer, nullable=False, index=True)
    counsellor_email = Column(String(255), nullable=False, index=True)
    note = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "simulation_id": self.simulation_id,
            "counsellor_email": self.counsellor_email,
            "note": self.note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class OutcomeRecord(Base):
    """Anonymised longitudinal outcome — populated from FollowUp responses."""
    __tablename__ = "outcome_records"

    id = Column(Integer, primary_key=True, index=True)
    simulation_id = Column(Integer, nullable=False, index=True)
    decision_hash = Column(String(64), nullable=False, index=True)  # SHA-256 of decision text
    context_snapshot = Column(JSON, nullable=False)   # anonymised context (no email)
    predicted_scores = Column(JSON, nullable=False)   # causal scores at Year1
    chosen_timeline = Column(String(50), nullable=True)
    actual_outcome = Column(Text, nullable=True)
    months_elapsed = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "decision_hash": self.decision_hash,
            "context_snapshot": self.context_snapshot,
            "predicted_scores": self.predicted_scores,
            "chosen_timeline": self.chosen_timeline,
            "actual_outcome": self.actual_outcome,
            "months_elapsed": self.months_elapsed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class EconomicSnapshot(Base):
    __tablename__ = "economic_snapshot"

    id = Column(Integer, primary_key=True, index=True)
    simulation_id = Column(Integer, nullable=True, index=True)
    role = Column(String(255), nullable=False, index=True)
    industry = Column(String(255), nullable=False, index=True)
    location = Column(String(255), nullable=False, index=True)
    confidence = Column(Integer, nullable=False)
    gaps = Column(JSON, nullable=False)
    provider_status = Column(JSON, nullable=False)
    monitoring = Column(JSON, nullable=False)
    grounding = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "simulation_id": self.simulation_id,
            "role": self.role,
            "industry": self.industry,
            "location": self.location,
            "confidence": self.confidence,
            "gaps": self.gaps,
            "provider_status": self.provider_status,
            "monitoring": self.monitoring,
            "grounding": self.grounding,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SalaryData(Base):
    __tablename__ = "salary_data"

    id = Column(Integer, primary_key=True, index=True)
    economic_snapshot_id = Column(Integer, nullable=False, index=True)
    role = Column(String(255), nullable=False, index=True)
    location = Column(String(255), nullable=False, index=True)
    source = Column(String(255), nullable=False)
    min_lpa = Column(Float, nullable=True)
    max_lpa = Column(Float, nullable=True)
    source_url = Column(Text, nullable=True)
    available = Column(Boolean, default=False)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class JobMarketData(Base):
    __tablename__ = "job_market_data"

    id = Column(Integer, primary_key=True, index=True)
    economic_snapshot_id = Column(Integer, nullable=False, index=True)
    role = Column(String(255), nullable=False, index=True)
    location = Column(String(255), nullable=False, index=True)
    source = Column(String(255), nullable=False)
    trend_payload = Column(JSON, nullable=False)
    available = Column(Boolean, default=False)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class InflationData(Base):
    __tablename__ = "inflation_data"

    id = Column(Integer, primary_key=True, index=True)
    economic_snapshot_id = Column(Integer, nullable=False, index=True)
    country = Column(String(16), nullable=False, default="IN")
    source = Column(String(255), nullable=False)
    inflation_pct = Column(Float, nullable=True)
    unemployment_pct = Column(Float, nullable=True)
    gdp_growth_pct = Column(Float, nullable=True)
    year = Column(String(16), nullable=True)
    available = Column(Boolean, default=False)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class V2Simulation(Base):
    """LangGraph-powered simulation result."""
    __tablename__ = "v2_simulations"

    id = Column(Integer, primary_key=True, index=True)
    simulation_id = Column(String(64), unique=True, nullable=False, index=True)
    user_email = Column(String(255), nullable=True)
    decision = Column(Text, nullable=False)
    context = Column(JSON, nullable=False)
    agent_outputs = Column(JSON, nullable=True)
    timelines = Column(JSON, nullable=True)
    future_selves = Column(JSON, nullable=True)
    synthesis = Column(JSON, nullable=True)
    monte_carlo = Column(JSON, nullable=True)
    events = Column(JSON, nullable=True)
    economic_snapshot = Column(JSON, nullable=True)
    latency_ms = Column(Float, default=0.0)
    phase = Column(String(50), default="complete")
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "simulation_id": self.simulation_id,
            "user_email": self.user_email,
            "decision": self.decision,
            "context": self.context,
            "agent_outputs": self.agent_outputs,
            "timelines": self.timelines,
            "future_selves": self.future_selves,
            "synthesis": self.synthesis,
            "monte_carlo": self.monte_carlo,
            "events": self.events,
            "economic_snapshot": self.economic_snapshot,
            "latency_ms": self.latency_ms,
            "phase": self.phase,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class FutureChatLog(Base):
    """Conversation history with future self personas."""
    __tablename__ = "future_chat_logs"

    id = Column(Integer, primary_key=True, index=True)
    simulation_id = Column(String(64), nullable=False, index=True)
    timeline_label = Column(String(50), nullable=False)
    user_question = Column(Text, nullable=False)
    agent_response = Column(Text, nullable=False)
    conversation_context = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AgentTrace(Base):
    """Observability trace for LangGraph agent execution."""
    __tablename__ = "agent_traces"

    id = Column(Integer, primary_key=True, index=True)
    simulation_id = Column(String(64), nullable=False, index=True)
    agent_name = Column(String(100), nullable=False)
    phase = Column(String(50), nullable=False)
    confidence = Column(Float, nullable=True)
    latency_ms = Column(Float, default=0.0)
    model_used = Column(String(100), nullable=True)
    token_count = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)
    output_preview = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
