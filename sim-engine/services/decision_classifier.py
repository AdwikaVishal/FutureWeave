import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class DecisionCategory(str, Enum):
    EDUCATIONAL = "educational"
    CAREER = "career"
    FINANCIAL = "financial"
    BUSINESS = "business"
    HEALTH = "health"
    LIFESTYLE = "lifestyle"
    RELOCATION = "relocation"
    STARTUP = "startup"
    RELATIONSHIP = "relationship"
    SKILL_DEVELOPMENT = "skill_development"
    TECHNOLOGY = "technology"
    GENERAL = "general"


@dataclass
class DecisionRoutingProfile:
    category: DecisionCategory
    subcategory: str = ""
    confidence: float = 0.0
    requires_salary_data: bool = False
    requires_job_market: bool = False
    requires_cost_of_living: bool = False
    requires_education_data: bool = False
    requires_health_data: bool = False
    requires_macro_data: bool = False
    requires_business_data: bool = False
    requires_immigration_data: bool = False
    primary_metric: str = "general"
    options: list[str] = field(default_factory=list)


EDUCATION_KEYWORDS = [
    r"\b(jee|neet|gate|cat|mat|xat|clat|upsc|ssc|ibps)\b",
    r"\b(iit|nit|iiit|vit|bits|amrita|srcc|fms|xlri|isb|iim)\b",
    r"\b(btech|mtech|bsc|msc|bba|mba|bca|mca|bcom|mcom|ba|ma|phd)\b",
    r"\b(admission|college|university|institute|course|degree|program|study)\b",
    r"\b(cse|ece|eee|mech|civil|aiml|data science|computer science)\b",
    r"\b(versus|vs|or)\s+(jee|neet|gate|cat|iit|nit|btech|mtech|cse|aiml)\b",
]

CAREER_KEYWORDS = [
    r"\b(salary|job|career|placement|package|lpa|ctc|offer|hiring)\b",
    r"\b(software engineer|developer|sde|data scientist|analyst|consultant)\b",
    r"\b(promotion|growth|switch|resign|notice|interview)\b",
    r"\b(startup|corporate|govt|government|private|psu|public sector)\b",
    r"\b(research|industry|academia|teaching|professor)\b",
]

FINANCIAL_KEYWORDS = [
    r"\b(invest|save|loan|emi|sip|mutual fund|stock|bond|fd|rd)\b",
    r"\b(buy|rent|mortgage|property|real estate|down payment)\b",
    r"\b(tax|insurance|premium|retirement|pension|ppf|epf|nps)\b",
    r"\b(budget|expense|income|earning|passive income|side hustle)\b",
]

HEALTH_KEYWORDS = [
    r"\b(treatment|surgery|therapy|medicine|diagnosis|disease|condition)\b",
    r"\b(doctor|hospital|clinic|medical|health|wellness|fitness|diet)\b",
    r"\b(option a|option b|treatment plan|alternative|procedure)\b",
]

RELOCATION_KEYWORDS = [
    r"\b(move|relocate|abroad|foreign|visa|immigrate|settle)\b",
    r"\b(country|city|canada|usa|uk|australia|europe|dubai|singapore)\b",
    r"\b(quality of life|cost of living|safety|standard of living)\b",
]

BUSINESS_KEYWORDS = [
    r"\b(startup|business|venture|entrepreneur|founder|co-founder)\b",
    r"\b(launch|expand|scale|market|revenue|profit|funding|investor)\b",
    r"\b(competition|industry|sector|b2b|b2c|saas|product)\b",
]

RELATIONSHIP_KEYWORDS = [
    r"\b(marriage|married|wedding|partner|spouse|relationship|dating)\b",
    r"\b(engagement|commit|family|children|baby|parenthood)\b",
]

LIFESTYLE_KEYWORDS = [
    r"\b(gap year|travel|explore|passion|hobby|side project|freelance)\b",
    r"\b(artist|writer|musician|creator|influencer|content)\b",
    r"\b(work life balance|remote|flexible|part time|full time)\b",
]


def _compile(patterns: list[str]) -> re.Pattern:
    return re.compile("|".join(patterns), re.IGNORECASE)


_EDU_RE = _compile(EDUCATION_KEYWORDS)
_CAREER_RE = _compile(CAREER_KEYWORDS)
_FINANCIAL_RE = _compile(FINANCIAL_KEYWORDS)
_HEALTH_RE = _compile(HEALTH_KEYWORDS)
_RELOCATION_RE = _compile(RELOCATION_KEYWORDS)
_BUSINESS_RE = _compile(BUSINESS_KEYWORDS)
_RELATIONSHIP_RE = _compile(RELATIONSHIP_KEYWORDS)
_LIFESTYLE_RE = _compile(LIFESTYLE_KEYWORDS)


def classify_decision(decision: str, context: dict | None = None) -> DecisionRoutingProfile:
    text = decision.lower() + " " + str(context or {}).lower()

    scores: dict[DecisionCategory, float] = {}

    edu_matches = len(_EDU_RE.findall(text))
    career_matches = len(_CAREER_RE.findall(text))
    financial_matches = len(_FINANCIAL_RE.findall(text))
    health_matches = len(_HEALTH_RE.findall(text))
    relocation_matches = len(_RELOCATION_RE.findall(text))
    business_matches = len(_BUSINESS_RE.findall(text))
    relationship_matches = len(_RELATIONSHIP_RE.findall(text))
    lifestyle_matches = len(_LIFESTYLE_RE.findall(text))

    scores[DecisionCategory.EDUCATIONAL] = edu_matches * 20
    scores[DecisionCategory.CAREER] = career_matches * 18
    scores[DecisionCategory.FINANCIAL] = financial_matches * 18
    scores[DecisionCategory.HEALTH] = health_matches * 20
    scores[DecisionCategory.RELOCATION] = relocation_matches * 18
    scores[DecisionCategory.BUSINESS] = business_matches * 18
    scores[DecisionCategory.STARTUP] = (business_matches * 15) + (1 if "startup" in text else 0) * 25
    scores[DecisionCategory.RELATIONSHIP] = relationship_matches * 20
    scores[DecisionCategory.LIFESTYLE] = lifestyle_matches * 15
    scores[DecisionCategory.TECHNOLOGY] = (10 if re.search(r"\b(should i use|technology|framework|tool|platform|migrate)", text) else 0)
    scores[DecisionCategory.SKILL_DEVELOPMENT] = (10 if re.search(r"\b(learn|skill|course|certification|training|upskill)", text) else 0)
    scores[DecisionCategory.GENERAL] = 5

    best = max(scores, key=scores.get)
    confidence = min(100, scores[best])
    second_best = sorted(scores.values(), reverse=True)[1] if len(scores) > 1 else 0

    if confidence < 15:
        best = DecisionCategory.GENERAL
        confidence = 30

    options = _extract_options(decision)

    profile = DecisionRoutingProfile(
        category=best,
        confidence=confidence,
        options=options,
    )

    if best == DecisionCategory.EDUCATIONAL:
        profile.requires_education_data = True
        profile.primary_metric = "education_outcome"
    elif best in (DecisionCategory.CAREER, DecisionCategory.STARTUP):
        profile.requires_salary_data = True
        profile.requires_job_market = True
        profile.requires_macro_data = True
        profile.requires_cost_of_living = True
        profile.primary_metric = "career_outcome"
    elif best == DecisionCategory.FINANCIAL:
        profile.requires_macro_data = True
        profile.requires_cost_of_living = True
        profile.primary_metric = "financial_outcome"
    elif best == DecisionCategory.HEALTH:
        profile.requires_health_data = True
        profile.requires_cost_of_living = True
        profile.primary_metric = "health_outcome"
    elif best == DecisionCategory.RELOCATION:
        profile.requires_cost_of_living = True
        profile.requires_job_market = True
        profile.requires_immigration_data = True
        profile.requires_macro_data = True
        profile.primary_metric = "relocation_outcome"
    elif best == DecisionCategory.BUSINESS:
        profile.requires_business_data = True
        profile.requires_macro_data = True
        profile.requires_cost_of_living = True
        profile.primary_metric = "business_outcome"
    elif best == DecisionCategory.RELATIONSHIP:
        profile.requires_cost_of_living = True
        profile.primary_metric = "relationship_outcome"
    elif best in (DecisionCategory.LIFESTYLE, DecisionCategory.SKILL_DEVELOPMENT, DecisionCategory.TECHNOLOGY):
        profile.requires_cost_of_living = True
        profile.requires_macro_data = True
        profile.primary_metric = "personal_outcome"
    else:
        profile.primary_metric = "general_outcome"

    return profile


def _extract_options(decision: str) -> list[str]:
    patterns = [
        r"(?:should I|should i)\s+(.+?)\s+or\s+(.+?)(?:\?|$|\.)",
        r"(.+?)\s+vs\s+(.+?)(?:\?|$|\.)",
        r"(.+?)\s+versus\s+(.+?)(?:\?|$|\.)",
        r"(.+?)\s+or\s+(.+?)\s+at\s+",
    ]
    for pat in patterns:
        m = re.search(pat, decision, re.IGNORECASE)
        if m:
            opts = [m.group(1).strip(), m.group(2).strip()]
            return [o for o in opts if o]
    return []


def get_required_data_sources(profile: DecisionRoutingProfile) -> list[str]:
    required = []
    if profile.requires_salary_data:
        required.extend(["adzuna", "ambitionbox"])
    if profile.requires_job_market:
        required.append("job_market")
    if profile.requires_cost_of_living:
        required.append("cost_of_living")
    if profile.requires_education_data:
        required.append("education")
    if profile.requires_health_data:
        required.append("health")
    if profile.requires_macro_data:
        required.extend(["worldbank", "imf"])
    if profile.requires_business_data:
        required.append("business")
    if profile.requires_immigration_data:
        required.append("immigration")
    return required
