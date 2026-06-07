"""
Career & education profiles for deterministic simulation.

Each profile scores dimensions on a 0-10 scale used as multipliers
in the Simulation Engine's growth formulas. Salary data references
the existing STUDENT_SALARY_DATABASE / SALARY_DATABASE in data_grounding.

Usage:
    profile = get_profile("CSE")
    profile = get_profile("startup founder", decision_type="career")
"""

import logging
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class DecisionProfile(BaseModel):
    """Type-safe profile model — never allows strings where dicts expected."""
    growth: float = Field(ge=0, le=10, default=5)
    salary_potential: float = Field(ge=0, le=10, default=5)
    risk: float = Field(ge=0, le=10, default=5)
    stress: float = Field(ge=0, le=10, default=5)
    work_life_balance: float = Field(ge=0, le=10, default=5)
    demand: float = Field(ge=0, le=10, default=5)
    satisfaction: float = Field(ge=0, le=10, default=5)
    stability: float = Field(ge=0, le=10, default=5)
    aliases: list[str] = Field(default_factory=list)

    @field_validator("aliases", mode="before")
    @classmethod
    def ensure_list(cls, v):
        if isinstance(v, str):
            return [v]
        return v if isinstance(v, list) else []


def validate_profile(profile: dict, context: str = "profile") -> dict:
    """Validate that a profile is a proper dict with correct types.
    Raises TypeError if types are wrong."""
    if not isinstance(profile, dict):
        raise TypeError(
            f"Expected dict for {context}, got {type(profile).__name__}: {profile!r}"
        )
    try:
        validated = DecisionProfile(**profile)
        return validated.model_dump()
    except Exception as e:
        raise TypeError(
            f"Profile validation failed for {context}: {e}. Data: {profile!r}"
        )


_NORMALIZED_DECISIONS = {
    "drop out of college": {
        "category": "education",
        "path": "dropout",
        "cgpa": None,
        "profile_override": {
            "growth": 4, "salary_potential": 5, "risk": 8,
            "stress": 7, "work_life_balance": 6, "demand": 5,
            "satisfaction": 4, "stability": 3,
        },
    },
    "continue college": {
        "category": "education",
        "path": "continue_college",
        "cgpa": None,
        "profile_override": {
            "growth": 6, "salary_potential": 6, "risk": 3,
            "stress": 5, "work_life_balance": 7, "demand": 6,
            "satisfaction": 6, "stability": 7,
        },
    },
    "mba": {
        "category": "education",
        "path": "mba",
        "profile_override": {
            "growth": 8, "salary_potential": 9, "risk": 4,
            "stress": 7, "work_life_balance": 5, "demand": 8,
            "satisfaction": 7, "stability": 7,
        },
    },
    "job": {
        "category": "career",
        "path": "job",
        "profile_override": {
            "growth": 6, "salary_potential": 7, "risk": 4,
            "stress": 6, "work_life_balance": 6, "demand": 7,
            "satisfaction": 6, "stability": 7,
        },
    },
    "startup": {
        "category": "career",
        "path": "startup",
        "profile_override": {
            "growth": 10, "salary_potential": 10, "risk": 9,
            "stress": 9, "work_life_balance": 3, "demand": 7,
            "satisfaction": 8, "stability": 2,
        },
    },
}


def normalize_decision(option: str) -> dict | None:
    """Normalize common decision options to structured profiles.
    
    Input: "continue it with a 6 CGPA"
    Output: {"category": "education", "path": "continue_college", "cgpa": 6.0}
    
    Input: "drop out of college"
    Output: {"category": "education", "path": "dropout"}
    """
    text = option.lower().strip()
    
    # Check for CGPA mention
    cgpa = None
    cgpa_match = __import__("re").search(r"(\d+(?:\.\d+)?)\s*cgpa", text)
    if cgpa_match:
        cgpa = float(cgpa_match.group(1))
    
    # Exact match
    if text in _NORMALIZED_DECISIONS:
        result = dict(_NORMALIZED_DECISIONS[text])
        if cgpa is not None:
            result["cgpa"] = cgpa
        return result
    
    # Fuzzy match: check keywords
    if "drop out" in text or "dropout" in text or "quit college" in text or "leave college" in text:
        result = dict(_NORMALIZED_DECISIONS["drop out of college"])
        if cgpa is not None:
            result["cgpa"] = cgpa
        return result
    
    if any(kw in text for kw in ["continue", "stay in college", "remain", "complete"]):
        result = dict(_NORMALIZED_DECISIONS["continue college"])
        if cgpa is not None:
            result["cgpa"] = cgpa
        return result
    
    if any(kw in text for kw in ["mba", "master of business", "business school"]):
        return dict(_NORMALIZED_DECISIONS["mba"])
    
    if any(kw in text for kw in ["higher studies", "masters", "master's", "phd", "ms in", "mtech", "msc"]):
        return {
            "category": "education",
            "path": "higher_studies",
            "profile_override": {
                "growth": 7, "salary_potential": 8, "risk": 3,
                "stress": 6, "work_life_balance": 6, "demand": 7,
                "satisfaction": 7, "stability": 6,
            },
        }
    
    if any(kw in text for kw in ["startup", "found", "entrepreneur", "own business"]):
        return dict(_NORMALIZED_DECISIONS["startup"])
    
    if any(kw in text for kw in ["job", "work", "employ", "placement", "offer"]):
        return dict(_NORMALIZED_DECISIONS["job"])
    
    return None

EDUCATION_PROFILES = {
    "computer science": {
        "growth": 8, "salary_potential": 9, "risk": 3,
        "stress": 5, "work_life_balance": 7, "demand": 9,
        "satisfaction": 7, "stability": 8,
        "aliases": ["cse", "computer engineering", "cs", "computers"],
    },
    "aiml": {
        "growth": 10, "salary_potential": 10, "risk": 6,
        "stress": 7, "work_life_balance": 5, "demand": 10,
        "satisfaction": 8, "stability": 6,
        "aliases": ["ai/ml", "artificial intelligence", "machine learning", "ai", "ml"],
    },
    "data science": {
        "growth": 9, "salary_potential": 9, "risk": 5,
        "stress": 6, "work_life_balance": 6, "demand": 9,
        "satisfaction": 8, "stability": 7,
        "aliases": ["data science", "data analytics", "analytics"],
    },
    "electrical engineering": {
        "growth": 5, "salary_potential": 6, "risk": 3,
        "stress": 5, "work_life_balance": 7, "demand": 6,
        "satisfaction": 6, "stability": 8,
        "aliases": ["eee", "ece", "electronics", "electrical"],
    },
    "mechanical engineering": {
        "growth": 4, "salary_potential": 5, "risk": 3,
        "stress": 5, "work_life_balance": 7, "demand": 5,
        "satisfaction": 6, "stability": 8,
        "aliases": ["mechanical", "mech"],
    },
    "civil engineering": {
        "growth": 4, "salary_potential": 5, "risk": 3,
        "stress": 6, "work_life_balance": 6, "demand": 5,
        "satisfaction": 6, "stability": 8,
        "aliases": ["civil"],
    },
    "mba": {
        "growth": 8, "salary_potential": 9, "risk": 4,
        "stress": 7, "work_life_balance": 5, "demand": 8,
        "satisfaction": 7, "stability": 7,
        "aliases": ["master of business administration", "business", "management"],
    },
}

CAREER_PROFILES = {
    "software engineer": {
        "growth": 8, "salary_potential": 9, "risk": 4,
        "stress": 6, "work_life_balance": 6, "demand": 9,
        "satisfaction": 7, "stability": 7,
        "aliases": ["developer", "programmer", "coder", "sde", "software dev"],
    },
    "data scientist": {
        "growth": 9, "salary_potential": 9, "risk": 5,
        "stress": 6, "work_life_balance": 6, "demand": 9,
        "satisfaction": 8, "stability": 7,
        "aliases": ["ml engineer", "data analyst", "ai engineer"],
    },
    "product manager": {
        "growth": 8, "salary_potential": 8, "risk": 5,
        "stress": 7, "work_life_balance": 5, "demand": 8,
        "satisfaction": 7, "stability": 7,
        "aliases": ["pm", "product owner"],
    },
    "designer": {
        "growth": 6, "salary_potential": 6, "risk": 5,
        "stress": 5, "work_life_balance": 7, "demand": 6,
        "satisfaction": 7, "stability": 6,
        "aliases": ["ui/ux", "product designer", "graphic designer"],
    },
    "startup founder": {
        "growth": 10, "salary_potential": 10, "risk": 9,
        "stress": 9, "work_life_balance": 3, "demand": 7,
        "satisfaction": 8, "stability": 2,
        "aliases": ["entrepreneur", "co-founder", "founder", "startup"],
    },
    "corporate professional": {
        "growth": 5, "salary_potential": 6, "risk": 2,
        "stress": 5, "work_life_balance": 7, "demand": 7,
        "satisfaction": 5, "stability": 9,
        "aliases": ["corporate", "9 to 5", "employee", "executive"],
    },
    "mechanical engineer": {
        "growth": 4, "salary_potential": 5, "risk": 3,
        "stress": 5, "work_life_balance": 7, "demand": 5,
        "satisfaction": 6, "stability": 8,
        "aliases": ["mechanical"],
    },
}

_DIMENSIONS = [
    "growth", "salary_potential", "risk", "stress",
    "work_life_balance", "demand", "satisfaction", "stability",
]


def get_profile(option: str, decision_type: str = "educational") -> dict | None:
    """Look up a profile by option name with alias matching.
    
    First tries normalized decision mapping, then falls back to
    EDUCATION_PROFILES / CAREER_PROFILES with alias matching.
    Returns validated profile dict or None.
    """
    key = option.lower().strip()
    
    # Try normalized decision paths first (dropout, continue, MBA, etc.)
    normalized = normalize_decision(option)
    if normalized and "profile_override" in normalized:
        override = normalized["profile_override"]
        return validate_profile(override, context=f"normalized:{option}")
    
    profiles = EDUCATION_PROFILES if decision_type == "educational" else CAREER_PROFILES
    
    direct = profiles.get(key)
    if direct:
        return validate_profile(direct, context=f"direct:{key}")
    
    for name, profile in profiles.items():
        profile_aliases = profile.get("aliases", [])
        if isinstance(profile_aliases, list):
            if key in [a.lower() for a in profile_aliases]:
                return validate_profile(dict(profile), context=f"alias:{key}")
        elif isinstance(profile_aliases, str) and key == profile_aliases.lower():
            return validate_profile(dict(profile), context=f"alias:{key}")
    
    return None


def get_profile_or_default(option: str, decision_type: str = "educational") -> dict:
    """Return a profile or generate a reasonable default.
    
    Always returns a validated dict — never a string or None.
    """
    profile = get_profile(option, decision_type)
    if profile is not None:
        return profile
    
    default_profile = validate_profile(
        {dim: 5 for dim in _DIMENSIONS},
        context=f"default:{option}",
    )
    return default_profile


def profile_to_scores(profile: dict) -> dict:
    """Map a 0-10 profile into 0-100 baseline scores for the simulation nodes."""
    base = 50
    spread = 30
    return {
        "income": _clamp(base + (profile["salary_potential"] - 5) * spread / 5),
        "career_growth": _clamp(base + (profile["growth"] - 5) * spread / 5),
        "stress": _clamp(base + (profile["stress"] - 5) * spread / 5),
        "health": _clamp(65 - max(0, profile["stress"] - 5) * 3),
        "relationships": _clamp(60 - max(0, profile["risk"] - 5) * 2),
        "happiness": _clamp(52 + (profile["satisfaction"] - 5) * 4),
        "opportunity": _clamp(base + (profile["demand"] - 5) * spread / 5),
    }


def _clamp(val: float) -> int:
    return max(0, min(100, int(round(val))))
