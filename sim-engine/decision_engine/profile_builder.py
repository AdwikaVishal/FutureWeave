from __future__ import annotations
from typing import Any, Dict
from .types import UserProfile


def build_user_profile(context: Dict[str, Any]) -> UserProfile:
    return UserProfile(
        age=int(context.get("age", 25)),
        location=str(context.get("location", "Bangalore")),
        risk_tolerance=float(context.get("risk_tolerance", 0.5)),
        savings=float(context.get("savings", 0)),
        dependents=int(context.get("dependents", 0)),
        skills=[s.strip() for s in context.get("skills", "").split(",") if s.strip()],
        industry=str(context.get("industry", "technology")),
        role=str(context.get("role", "software_engineer")),
    )
