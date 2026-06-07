"""
Domain definitions for the universal decision framework.

Maps each DecisionDomain to its:
  - metrics (scoring dimensions)
  - weights (for recommendation)
  - narrative labels
  - regret/letter templates
  - data provider requirements

This is the single source of truth for domain-specific behaviour.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DecisionDomain(str, Enum):
    CAREER = "career"
    EDUCATION = "education"
    BUSINESS = "business"
    FINANCIAL = "financial"
    RELOCATION = "relocation"
    RELATIONSHIP = "relationship"
    HEALTH = "health"
    LIFESTYLE = "lifestyle"
    GENERAL = "general"


# ── Domain Metrics ─────────────────────────────────────────────────────────────

@dataclass
class DomainMetrics:
    name: str
    nodes: list[str]
    weights: dict[str, float]
    year_labels: dict[str, str]
    primary_metric: str
    ignore_income: bool = False
    ignore_macro: bool = False
    description: str = ""


DOMAIN_METRICS: dict[DecisionDomain, DomainMetrics] = {}


def _register(domain: DecisionDomain, metrics: DomainMetrics) -> None:
    DOMAIN_METRICS[domain] = metrics


_register(DecisionDomain.CAREER, DomainMetrics(
    name="career",
    nodes=["income", "career_growth", "stress", "health", "relationships", "happiness", "opportunity"],
    weights={"income": 0.25, "career_growth": 0.20, "happiness": 0.20, "stress": -0.10, "health": 0.10, "relationships": 0.10, "opportunity": 0.05},
    year_labels={"Year1": "Career Start", "Year3": "Growth & Promotion", "Year5": "Mid-Career Inflection", "Year10": "Senior Leadership"},
    primary_metric="income",
    ignore_income=False,
    ignore_macro=False,
    description="Job and career decisions (job switch, promotion, industry change).",
))

_register(DecisionDomain.EDUCATION, DomainMetrics(
    name="education",
    nodes=["learning_growth", "placement_potential", "research_opportunities", "future_optionality", "academic_pressure", "skill_development", "happiness", "health", "relationships"],
    weights={"placement_potential": 0.30, "learning_growth": 0.25, "future_optionality": 0.25, "academic_pressure": -0.20},
    year_labels={"Year1": "Foundation & Preparation", "Year3": "Core Learning & Exams", "Year5": "Placements & Graduation", "Year10": "Career Outcome Post-Graduation"},
    primary_metric="placement_potential",
    ignore_income=True,
    ignore_macro=True,
    description="Educational decisions (CSE vs AIML, NEET vs JEE, college choice).",
))

_register(DecisionDomain.BUSINESS, DomainMetrics(
    name="business",
    nodes=["revenue_potential", "failure_risk", "market_opportunity", "burn_rate", "wealth_creation", "stress", "happiness", "health", "relationships", "freedom"],
    weights={"wealth_creation": 0.35, "failure_risk": -0.25, "market_opportunity": 0.20, "stress": -0.20},
    year_labels={"Year1": "Launch & Validation", "Year3": "Growth & Traction", "Year5": "Scale & Market Fit", "Year10": "Exit or Maturity"},
    primary_metric="wealth_creation",
    ignore_income=False,
    ignore_macro=False,
    description="Entrepreneurial and business decisions (startup, venture, side business).",
))

_register(DecisionDomain.FINANCIAL, DomainMetrics(
    name="financial",
    nodes=["wealth_growth", "cash_flow", "risk", "liquidity", "financial_security", "stress", "happiness"],
    weights={"wealth_growth": 0.30, "cash_flow": 0.20, "risk": -0.20, "financial_security": 0.20, "liquidity": 0.10},
    year_labels={"Year1": "Initial Investment", "Year3": "Portfolio Growth", "Year5": "Wealth Accumulation", "Year10": "Financial Independence"},
    primary_metric="wealth_growth",
    ignore_income=False,
    ignore_macro=False,
    description="Financial decisions (buy vs rent, invest, loan, retirement planning).",
))

_register(DecisionDomain.RELOCATION, DomainMetrics(
    name="relocation",
    nodes=["cost_of_living", "career_access", "social_support", "quality_of_life", "commute", "safety", "stress", "happiness", "health", "relationships"],
    weights={"quality_of_life": 0.30, "cost_of_living": 0.25, "career_access": 0.25, "social_support": 0.20},
    year_labels={"Year1": "Relocation & Setup", "Year3": "Settlement & Adjustment", "Year5": "Community & Growth", "Year10": "Rooted & Thriving"},
    primary_metric="quality_of_life",
    ignore_income=False,
    ignore_macro=False,
    description="Relocation decisions (move city, country, remote vs office).",
))

_register(DecisionDomain.RELATIONSHIP, DomainMetrics(
    name="relationship",
    nodes=["emotional_health", "compatibility", "communication", "personal_growth", "future_alignment", "stress", "happiness", "health"],
    weights={"emotional_health": 0.25, "compatibility": 0.20, "communication": 0.20, "future_alignment": 0.20, "personal_growth": 0.15},
    year_labels={"Year1": "Bonding & Foundation", "Year3": "Deepening & Challenges", "Year5": "Commitment & Growth", "Year10": "Shared Life & Partnership"},
    primary_metric="emotional_health",
    ignore_income=True,
    ignore_macro=True,
    description="Relationship decisions (marriage, breakup, commitment, partnership).",
))

_register(DecisionDomain.HEALTH, DomainMetrics(
    name="health",
    nodes=["treatment_efficacy", "recovery_rate", "quality_of_life", "care_access", "long_term_outlook", "stress", "happiness", "health", "relationships"],
    weights={"treatment_efficacy": 0.30, "recovery_rate": 0.25, "quality_of_life": 0.25, "long_term_outlook": 0.20},
    year_labels={"Year1": "Diagnosis & Treatment", "Year3": "Recovery & Adjustment", "Year5": "Stability & Management", "Year10": "Long-Term Wellness"},
    primary_metric="quality_of_life",
    ignore_income=True,
    ignore_macro=True,
    description="Health decisions (treatment options, surgery, therapy, lifestyle change).",
))

_register(DecisionDomain.LIFESTYLE, DomainMetrics(
    name="lifestyle",
    nodes=["fulfillment", "work_life_balance", "personal_growth", "social_connection", "financial_freedom", "stress", "happiness", "health"],
    weights={"fulfillment": 0.30, "happiness": 0.25, "work_life_balance": 0.20, "personal_growth": 0.15, "financial_freedom": 0.10},
    year_labels={"Year1": "New Path", "Year3": "Finding Rhythm", "Year5": "Deepening Practice", "Year10": "Integrated Life"},
    primary_metric="happiness",
    ignore_income=False,
    ignore_macro=False,
    description="Lifestyle decisions (gap year, freelance, creative pursuit, location independence).",
))

_register(DecisionDomain.GENERAL, DomainMetrics(
    name="general",
    nodes=["income", "career_growth", "stress", "health", "relationships", "happiness", "opportunity"],
    weights={"happiness": 0.25, "income": 0.20, "career_growth": 0.15, "stress": -0.10, "health": 0.10, "relationships": 0.10, "opportunity": 0.10},
    year_labels={"Year1": "Starting Point", "Year3": "Building Momentum", "Year5": "Mid-Point Assessment", "Year10": "Long-Term Outcome"},
    primary_metric="happiness",
    ignore_income=False,
    ignore_macro=False,
    description="General or unclassified decisions — uses universal dimensions.",
))


# ── Domain-Specific Regrets ────────────────────────────────────────────────────

DOMAIN_REGRETS: dict[str, dict[str, Any]] = {
    "education": {
        "A": {
            "lost_opportunity": "Not exploring research opportunities during your academic years.",
            "missed_identity": "The version of yourself who chose passion over prestige.",
            "emotional_cost": "The question of 'what if I had picked the other branch?' that never quite fades.",
        },
        "B": {
            "lost_opportunity": "Choosing the popular field over the one that genuinely interested you.",
            "missed_identity": "A version of yourself who followed curiosity instead of the crowd.",
            "emotional_cost": "The subtle awareness that you optimised for placement rather than purpose.",
        },
        "C": {
            "lost_opportunity": "Ignoring specialization opportunities in favour of breadth.",
            "missed_identity": "The specialist you could have become if you'd gone deeper, not wider.",
            "emotional_cost": "The feeling of being good at many things but excellent at none.",
        },
    },
    "business": {
        "A": {
            "lost_opportunity": "The market window you didn't move on because the timing felt wrong.",
            "missed_identity": "A version of yourself who took the leap before the spreadsheet said yes.",
            "emotional_cost": "Watching someone else build the idea you had first but didn't execute.",
        },
        "B": {
            "lost_opportunity": "Not starting earlier when the cost of experimentation was lower.",
            "missed_identity": "The founder who trusted instinct more than data, at least once.",
            "emotional_cost": "The tension between building something meaningful and meeting payroll.",
        },
        "C": {
            "lost_opportunity": "Taking unnecessary risks that burned through runway too fast.",
            "missed_identity": "A version of yourself who built sustainably instead of chasing spikes.",
            "emotional_cost": "The realisation that growth at all costs came with a price you didn't account for.",
        },
    },
    "relocation": {
        "A": {
            "lost_opportunity": "Not moving sooner when the cost of staying was higher than you admitted.",
            "missed_identity": "The person who would have thrived in a different environment.",
            "emotional_cost": "Losing the local support network and starting from zero socially.",
        },
        "B": {
            "lost_opportunity": "The city's hidden opportunities you discovered too late to fully leverage.",
            "missed_identity": "A version of yourself who explored more before committing.",
            "emotional_cost": "The distance from family that never stops feeling like a trade-off.",
        },
        "C": {
            "lost_opportunity": "Missing the unique opportunities your new city offers because you stayed in your bubble.",
            "missed_identity": "Someone who fully integrated instead of remaining a transplant.",
            "emotional_cost": "The awareness that home is now two places and you belong fully to neither.",
        },
    },
    "relationship": {
        "A": {
            "lost_opportunity": "Not addressing the small issues before they became patterns.",
            "missed_identity": "A version of yourself who was more vulnerable earlier.",
            "emotional_cost": "The weight of what was left unsaid for too long.",
        },
        "B": {
            "lost_opportunity": "The personal growth you sacrificed for relationship stability.",
            "missed_identity": "Someone who maintained their individuality within the partnership.",
            "emotional_cost": "The quiet erosion of personal boundaries in the name of togetherness.",
        },
        "C": {
            "lost_opportunity": "Not recognising when effort stopped being reciprocated.",
            "missed_identity": "A version of yourself who walked away sooner with grace.",
            "emotional_cost": "The gap between the relationship you had and the one you thought you were building.",
        },
    },
    "financial": {
        "A": {
            "lost_opportunity": "The investment you didn't make because you were waiting for the 'right time'.",
            "missed_identity": "A version of yourself who took calculated financial risks earlier.",
            "emotional_cost": "The quiet frustration of watching your savings erode against inflation.",
        },
        "B": {
            "lost_opportunity": "Not diversifying when you had the chance to reduce risk.",
            "missed_identity": "Someone who balanced growth and security more wisely.",
            "emotional_cost": "The anxiety of having too much concentrated in one asset class.",
        },
        "C": {
            "lost_opportunity": "The liquidity you sacrificed for returns that didn't materialise.",
            "missed_identity": "A version of yourself who prioritised cash flow over speculation.",
            "emotional_cost": "The sleepless nights when markets turned and your positions were overleveraged.",
        },
    },
    "health": {
        "A": {
            "lost_opportunity": "Not seeking a second opinion when the first plan didn't feel right.",
            "missed_identity": "Someone who advocated more aggressively for their own wellbeing.",
            "emotional_cost": "The regret of not prioritising prevention over treatment.",
        },
        "B": {
            "lost_opportunity": "Delaying care because life was too busy for recovery.",
            "missed_identity": "A version of yourself who put health first, before there was a crisis.",
            "emotional_cost": "The awareness that you can't buy back lost years of wellbeing.",
        },
        "C": {
            "lost_opportunity": "Choosing the aggressive option without fully considering quality of life.",
            "missed_identity": "Someone who valued peace of mind as much as treatment outcomes.",
            "emotional_cost": "The realisation that some costs can't be measured in clinical outcomes.",
        },
    },
    "lifestyle": {
        "A": {
            "lost_opportunity": "Not exploring enough before committing to a path.",
            "missed_identity": "A version of yourself who took more risks when the stakes were lower.",
            "emotional_cost": "The recurring wonder about the life you didn't choose.",
        },
        "B": {
            "lost_opportunity": "The financial stability you traded for freedom and passion.",
            "missed_identity": "Someone who found a way to have both purpose and security.",
            "emotional_cost": "The quiet pressure of watching peers take traditional paths to wealth.",
        },
        "C": {
            "lost_opportunity": "The relationships that faded when you prioritised your unconventional path.",
            "missed_identity": "A version of yourself who was present for the people who mattered.",
            "emotional_cost": "The loneliness of walking a path few around you understand.",
        },
    },
    "career": {
        "A": {
            "lost_opportunity": "The high-growth role you turned down because the commute felt too disruptive.",
            "missed_identity": "A version of yourself who found out what you were capable of when the stakes were real.",
            "emotional_cost": "The Sunday evenings when you scroll past someone else's announcement and feel something you can't name.",
        },
        "B": {
            "lost_opportunity": "The founding team offer you declined because the salary was 30% lower.",
            "missed_identity": "A version of yourself who trusted instinct over spreadsheet, just once, at the right moment.",
            "emotional_cost": "The recurring awareness that you've been competent for a decade and still feel like you're waiting for your real life to start.",
        },
        "C": {
            "lost_opportunity": "The relationship that ended because you cancelled one too many weekends for a deal that didn't close.",
            "missed_identity": "A version of yourself who was present — not just available on Slack.",
            "emotional_cost": "The moment when the income hit the number you always wanted and there was no one to call.",
        },
    },
    "general": {
        "A": {
            "lost_opportunity": "An alternative path with higher risk and potentially higher reward.",
            "missed_identity": "A version who pushed harder earlier in their journey.",
            "emotional_cost": "The occasional wonder about roads not taken.",
        },
        "B": {
            "lost_opportunity": "A path you didn't explore because it felt impractical at the time.",
            "missed_identity": "Someone who trusted their gut more and their fears less.",
            "emotional_cost": "The awareness that playing it safe has its own hidden costs.",
        },
        "C": {
            "lost_opportunity": "The stability you sacrificed for experiences that didn't last.",
            "missed_identity": "A version of yourself who balanced ambition with groundedness.",
            "emotional_cost": "The realisation that not all risks were worth taking, in hindsight.",
        },
    },
}


# ── Domain-Specific Letter Templates ───────────────────────────────────────────

DOMAIN_LETTERS: dict[str, dict[str, str]] = {
    "education": {
        "A": (
            "You chose the steady path — the one that felt safe and familiar. "
            "It gave you a solid foundation, good grades, and a clear trajectory. "
            "Most days, that feels like enough."
        ),
        "B": (
            "You played it smart — not too risky, not too safe. "
            "You picked a field with good placement and solid growth. "
            "The career is promising, the degree was worth it. "
            "But you sometimes wonder if you chose the field or the field chose you."
        ),
        "C": (
            "You went after what excited you, even when it scared you. "
            "Some courses were harder than they needed to be. "
            "Some semesters tested your limits. "
            "But you learned something no syllabus could teach — how to bet on yourself."
        ),
    },
    "business": {
        "A": (
            "You built something the steady way. Slow growth, controlled risk, "
            "sustainable operations. The business is profitable. The stress is manageable. "
            "You didn't become a unicorn, but you also didn't crash and burn."
        ),
        "B": (
            "You built, you scaled, you pivoted. The journey had more plot twists "
            "than your original business plan. But you adapted. The revenue grew. "
            "You learned more in five years than most careers teach in twenty."
        ),
        "C": (
            "You went all-in on the vision. The highs were intoxicating — funding rounds, "
            "media coverage, hockey-stick growth. The lows were brutal. "
            "But you built something that mattered, and that's more than most ever do."
        ),
    },
    "relocation": {
        "A": (
            "You made the move cautiously — researched thoroughly, visited twice, "
            "had a backup plan. The transition was smoother than you feared. "
            "You found your rhythm faster than expected."
        ),
        "B": (
            "You took the leap with a plan but not a safety net. "
            "The first year was harder than you expected — new systems, new people, "
            "new version of yourself to build. But you built it."
        ),
        "C": (
            "You moved on instinct, with little more than a suitcase and a reason to leave. "
            "The uncertainty was the point. You discovered parts of yourself "
            "that comfort zones never reveal."
        ),
    },
    "relationship": {
        "A": (
            "You chose the path of steadiness and care. "
            "The relationship became your anchor in a changing world. "
            "You built a shared life, one conversation at a time."
        ),
        "B": (
            "You invested deeply — in communication, in compromise, in showing up. "
            "The relationship had seasons of closeness and distance. "
            "You learned that love is less about finding the right person "
            "and more about being the right person."
        ),
        "C": (
            "You loved without reservation, even when it hurt. "
            "You learned that some connections are meant to transform you, "
            "not to last forever. The growth came from the letting go."
        ),
    },
    "financial": {
        "A": (
            "You played the long game — steady savings, diversified investments, "
            "no get-rich-quick schemes. The returns were moderate but consistent. "
            "You sleep well at night knowing your finances are secure."
        ),
        "B": (
            "You found the balance — growth when the market was right, "
            "caution when it wasn't. Your portfolio reflects strategic thinking, "
            "not just luck. Financial independence is within sight."
        ),
        "C": (
            "You swung for the fences. Some bets paid off brilliantly. "
            "Others were expensive lessons. The volatility taught you things "
            "that no finance course ever could — about risk, resilience, and yourself."
        ),
    },
    "health": {
        "A": (
            "You took the cautious approach — followed the protocol, "
            "prioritised recovery, listened to your body. "
            "The progress was gradual but steady. You gave yourself the gift of patience."
        ),
        "B": (
            "You navigated the middle path — evidence-based decisions "
            "with room for your own intuition. Some treatments worked, "
            "some didn't. You learned to advocate for yourself."
        ),
        "C": (
            "You pursued every option, fought every battle, "
            "refused to accept limits. Your determination was remarkable. "
            "You learned that healing happens on its own timeline, "
            "no matter how hard you push."
        ),
    },
    "lifestyle": {
        "A": (
            "You chose the unconventional path with a plan. "
            "The freedom came with structure you designed yourself. "
            "Life didn't look like everyone else's — and that was exactly the point."
        ),
        "B": (
            "You found your own rhythm — part freedom, part responsibility. "
            "Some days felt like purpose, others like drifting. "
            "But you never stopped asking yourself what matters."
        ),
        "C": (
            "You burned the map and followed the compass. "
            "The path was unpredictable, the security was optional, "
            "but the life you built is yours alone. No template, no regrets."
        ),
    },
    "career": {
        "A": (
            "You chose the settled life, and it gave you exactly what it promised — "
            "stability, familiar faces, a mortgage that's almost paid off. "
            "Most days that feels like winning."
        ),
        "B": (
            "You climbed. Not the fastest, not the flashiest — but deliberately, "
            "and the view from Year 10 is genuinely good. "
            "The career is solid. The income is real. The relationships survived."
        ),
        "C": (
            "You went all in. Every time. The income chart looks like a mountain range. "
            "The stress chart looks the same. You got the life you gambled on — "
            "and discovered that winning a bet doesn't mean you bet on the right thing."
        ),
    },
    "general": {
        "A": "You took the steady path. The one with fewer surprises and more predictability. It served you well.",
        "B": "You balanced ambition with wisdom. Not every bet paid off, but enough did to make the journey worthwhile.",
        "C": "You trusted the unknown. The volatility was real, but so was the growth. You lived without a safety net and learned to fly.",
    },
}


# ── Domain Archetype Descriptions ──────────────────────────────────────────────

DOMAIN_ARCHETYPES: dict[str, dict[str, str]] = {
    "education": {
        "A": "The Steady Scholar: chooses stability and breadth. Balances all subjects, maintains consistent grades, avoids risk in course selection.",
        "B": "The Strategic Student: focused, ambitious. Optimises for placement outcomes and skill development. Takes calculated academic risks.",
        "C": "The Bold Explorer: follows passion over prestige. Pursues niche interests, deep specialisation, and unconventional academic paths.",
    },
    "business": {
        "A": "The Steady Builder: bootstraps, grows organically, minimises debt. Prioritises profitability over growth. Sustainable and deliberate.",
        "B": "The Strategic Founder: seeks product-market fit, raises smart capital, builds a team. Balances vision with operational discipline.",
        "C": "The Bold Visionary: swings for the fences, raises aggressively, moves fast. High risk, high reward — or high burn.",
    },
    "relocation": {
        "A": "The Careful Mover: researches thoroughly, visits first, has a backup plan. Prioritises safety and stability in the new location.",
        "B": "The Strategic Relocator: moves for opportunity, plans the transition, builds a network. Balances adventure with practical considerations.",
        "C": "The Bold Adventurer: moves on instinct, embraces uncertainty, figures it out as they go. Seeks transformation through displacement.",
    },
    "relationship": {
        "A": "The Steady Partner: prioritises stability, communication, and shared routines. Builds slowly and carefully.",
        "B": "The Balanced Partner: invests in emotional health while maintaining individuality, navigates challenges with honesty and effort.",
        "C": "The Passionate Partner: loves deeply and fully, embraces vulnerability, takes emotional risks. Growth through intensity.",
    },
    "financial": {
        "A": "The Conservative Saver: prioritises capital preservation, diversified low-risk investments, emergency funds. Sleeps well at night.",
        "B": "The Strategic Investor: balances growth and security, researches opportunities, rebalances periodically. Disciplined but opportunistic.",
        "C": "The Bold Speculator: seeks high returns, concentrates positions, times the market. Maximum upside, maximum volatility.",
    },
    "health": {
        "A": "The Cautious Patient: follows medical protocol, prioritises recovery, respects limits. Slow and steady healing.",
        "B": "The Engaged Patient: researches options, seeks second opinions, combines conventional and complementary approaches. Informed and proactive.",
        "C": "The Aggressive Fighter: pursues every possible treatment, challenges prognoses, refuses to accept limitations. Determined and exhaustive.",
    },
    "lifestyle": {
        "A": "The Mindful Explorer: designs freedom with structure. Maintains routines, income streams, and connections while pursuing passion.",
        "B": "The Balanced Seeker: pursues unconventional paths with strategic grounding. Takes calculated leaps in the direction of fulfillment.",
        "C": "The Radical Freedom Seeker: burns the map, follows the compass, embraces uncertainty as the price of authenticity.",
    },
    "career": {
        "A": "The Settler: chooses security and roots. Optimises for stability, relationships, and quality of life over income.",
        "B": "The Climber: disciplined, strategic ambition. Takes calculated risks, invests in skills, seeks promotions through merit.",
        "C": "The Gambler: bets big and moves fast. Job hops, launches side projects, chases equity. High ceiling, real floor risk.",
    },
    "general": {
        "A": "The Steady Path: prioritises stability, consistency, and risk management. Slow and deliberate progress.",
        "B": "The Balanced Path: mixes ambition with caution, seeks growth without reckless exposure. Strategic and measured.",
        "C": "The Bold Path: embraces risk, pursues maximum upside, accepts volatility as the cost of potential breakthroughs.",
    },
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def get_domain(decision_type: str) -> DecisionDomain:
    norm = decision_type.lower().strip()
    # Handle legacy aliases from the decision parser
    ALIASES = {
        "educational": "education",
        "choice": "general",
        "startup": "business",
        "unknown": "general",
    }
    if norm in ALIASES:
        norm = ALIASES[norm]
    for domain in DecisionDomain:
        if domain.value == norm:
            return domain
    return DecisionDomain.GENERAL


def get_metrics(domain: DecisionDomain) -> DomainMetrics:
    return DOMAIN_METRICS.get(domain, DOMAIN_METRICS[DecisionDomain.GENERAL])


def get_metrics_by_type(decision_type: str) -> DomainMetrics:
    return get_metrics(get_domain(decision_type))


def get_regrets(domain: str, archetype_key: str) -> dict:
    domain_regrets = DOMAIN_REGRETS.get(domain, DOMAIN_REGRETS["general"])
    return dict(domain_regrets.get(archetype_key, domain_regrets["B"]))


def get_letter(domain: str, archetype_key: str) -> str:
    domain_letters = DOMAIN_LETTERS.get(domain, DOMAIN_LETTERS["general"])
    return domain_letters.get(archetype_key, domain_letters["B"])


def get_archetype_label(domain: str, archetype_key: str) -> str:
    domain_archs = DOMAIN_ARCHETYPES.get(domain, DOMAIN_ARCHETYPES["general"])
    return domain_archs.get(archetype_key, domain_archs["B"])


DOMAIN_MAP = {d.value: d for d in DecisionDomain}
