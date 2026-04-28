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

