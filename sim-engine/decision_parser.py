"""
Decision Parser — extracts structured options from natural-language decision text.

Examples:
  "CSE or AIML at VIT in 2026?"
    → options=["CSE", "AIML"], institution="VIT", year=2026, type="educational"

  "Should I quit my job to start a company?"
    → options=["stay at current job", "start a company"], type="career"

  "MBA now or work for 2 more years first?"
    → options=["MBA now", "work for 2 more years"], type="educational"

Usage:
    parsed = parse_decision("CSE or AIML at VIT in 2026?")
    print(parsed.options)   # ["CSE", "AIML"]
    print(parsed.type)      # "educational"
"""
import re
import sys
from dataclasses import dataclass, field

_MAX_INPUT_LENGTH = 5000

_EDU_BRANCHES = [
    "cse", "aiml", "ece", "eee", "it", "btech", "mtech", "mba", "cs",
    "computer science", "information technology", "mechanical", "civil", "electrical",
]

_EDU_INSTITUTIONS = [
    "ggsipu", "vit", "bits", "iit", "nit", "iiit", "du", "iim", "nsut", "jmi",
]


@dataclass
class ParsedDecision:
    question: str
    options: list[str] = field(default_factory=list)
    decision_type: str = "unknown"
    institution: str | None = None
    year: int | None = None
    confidence: int = 100  # 0-100, how confident we are in parsing


# Pattern: "X or Y ...?" — capture full rest of text after "or"
_OR_PATTERN = re.compile(
    r'(?:should\s+i\s+)?(.+?)\s+or\s+(.+?)(?:\s*[?]|\s*$)',
    re.IGNORECASE | re.DOTALL,
)

# Pattern: "X vs Y"
_VS_PATTERN = re.compile(
    r'(.+?)\s+vs\.?\s+(.+?)(?:\s*[?]|\s*$)',
    re.IGNORECASE | re.DOTALL,
)


def _clean_option(text: str) -> str | None:
    """Remove leading/trailing noise and trailing context from an option string."""
    original = text.strip()
    text = original.strip('"').strip("'").strip('?').strip()
    # Remove trailing context like " at VIT", " in 2026", " in Bangalore"
    text = re.sub(r'\s+at\s+.+$', '', text).strip()
    text = re.sub(r'\s+in\s+\d{4}$', '', text).strip()
    text = re.sub(r'\s+in\s+\w+[\s\w]*$', '', text).strip()
    return text if text else original[:50]


def _extract_institution(question: str) -> str | None:
    """Extract institution name from patterns like 'at VIT', 'in GGSIPU', or 'IIT vs NIT'."""
    m = re.search(r'\b(?:at|from|in)\s+([A-Za-z\s]+?)(?:\s+in\s|\s*,|\s*$|\s*[?])', question)
    if m:
        inst = m.group(1).strip()
        # Filter out common false positives
        non_inst = {
            "home", "work", "school", "college", "university",
            "my current company", "my current job", "the office",
            "a startup", "a company", "an mnc", "a big company",
        }
        low = inst.lower()
        if low not in non_inst and len(inst) > 2:
            if low in {token.lower() for token in _EDU_INSTITUTIONS}:
                return inst.upper()
            return inst
    return None


def _extract_year(question: str) -> int | None:
    """Extract a 4-digit year from the question."""
    m = re.search(r'\b(20\d{2})\b', question)
    if m:
        return int(m.group(1))
    return None


def _detect_type(question: str, options: list[str]) -> str:
    """Classify the decision type using word-boundary matching."""
    q = question.lower()
    import re as _re
    def _has_word(words: list[str]) -> bool:
        return any(_re.search(rf'\b{re.escape(w)}\b', q) for w in words)

    edu_keywords = [
        "cse", "aiml", "btech", "mtech", "degree", "college",
        "university", "admission", "study", "course", "major",
        "mba", "phd", "master", "graduate", "school", "neet", "jee",
        "gate", "cat", "xat", "clat", "upsc", "ssc", "ibps",
    ]
    institution_keywords = [
        "ggsipu", "vit", "bits", "iit", "nit", "iiit", "du", "iim",
        "nsut", "jmi", "college", "university", "school",
    ]
    if _has_word(edu_keywords) or _has_word(institution_keywords):
        return "educational"
    if _has_word(["surgery", "medication", "treatment", "therapy", "health"]):
        return "health"
    if _has_word(["marry", "marriage", "propose", "girlfriend", "boyfriend", "partner", "relationship", "divorce", "breakup", "commit"]):
        return "relationship"
    if _has_word(["gap year", "freelance", "side hustle", "quit job", "travel", "lifestyle"]):
        return "lifestyle"
    if _has_word(["startup", "saas", "venture", "entrepreneur", "business", "funding"]):
        return "business"
    if _has_word(["invest", "money", "buy", "loan", "financial", "house", "apartment", "rent", "mortgage"]):
        return "financial"
    if _has_word(["relocat", "move", "country", "bangalore", "bengaluru", "delhi", "mumbai", "pune", "hyderabad", "chennai", "kolkata", "abroad"]):
        return "relocation"
    if _has_word(["job", "career", "work", "company", "salary", "switch to", "promot", "offer", "lpa", "ctc"]):
        return "career"
    if options:
        return "choice"
    return "unknown"


def _detect_educational_tokens(question: str) -> tuple[str | None, str | None]:
    """Return a branch and institution when the question is clearly educational."""
    q = question.lower()
    branch = None
    for token in _EDU_BRANCHES:
        if re.search(rf"\b{re.escape(token)}\b", q):
            branch = token.upper() if token != "computer science" else "Computer Science"
            break

    institution = None
    for token in _EDU_INSTITUTIONS:
        if re.search(rf"\b{re.escape(token)}\b", q):
            institution = token.upper()
            break

    if institution in {"IIT", "NIT", "IIM", "IIIT", "DU", "NSUT", "JMI"} and not branch:
        branch = institution
    return branch, institution


def parse_decision(question: str) -> ParsedDecision:
    """
    Parse a natural-language decision into structured options.
    """
    parsed = ParsedDecision(question=question)
    q = question.strip()
    if len(q) > _MAX_INPUT_LENGTH:
        q = q[:_MAX_INPUT_LENGTH]
        parsed.confidence = 30

    # Try "or" pattern first
    or_match = _OR_PATTERN.search(q)
    vs_match = _VS_PATTERN.search(q)

    if or_match:
        opt_a = _clean_option(or_match.group(1))
        opt_b = _clean_option(or_match.group(2))
        # Strip leading "should i" if present
        if opt_a.lower().startswith("should i "):
            opt_a = opt_a[9:]
        if opt_a:
            parsed.options = [opt_a, opt_b] if opt_b else [opt_a]
        parsed.confidence = 90
    elif vs_match:
        opt_a = _clean_option(vs_match.group(1))
        opt_b = _clean_option(vs_match.group(2))
        if opt_a:
            parsed.options = [opt_a, opt_b] if opt_b else [opt_a]
        parsed.confidence = 85
    else:
        # Single-question decisions ("Should I start a company?")
        q_lower = q.lower()
        if q_lower.startswith("should i "):
            action = q_lower[9:].rstrip("?").strip()
            if action:
                inverse = f"not {action}"
                parsed.options = [action, inverse]
                parsed.confidence = 70
        elif q_lower.startswith("which "):
            # "Which college should I choose?" — can't extract specific options
            parsed.confidence = 40
        else:
            parsed.confidence = 30

    branch, institution = _detect_educational_tokens(q)
    if not parsed.options and (branch or institution):
        if branch and institution:
            parsed.options = [branch, institution]
        elif branch:
            parsed.options = [branch]
        elif institution:
            parsed.options = [institution]
        parsed.confidence = 90 if (branch and institution) else 85

    if not parsed.options:
        parsed.confidence = min(parsed.confidence, 20)

    parsed.institution = _extract_institution(q) or institution
    parsed.year = _extract_year(q)
    parsed.decision_type = _detect_type(q, parsed.options)
    if parsed.decision_type == "choice" and (branch or institution):
        parsed.decision_type = "educational"
        parsed.confidence = max(parsed.confidence, 85)

    return parsed


def format_options_for_prompt(parsed: ParsedDecision) -> str:
    """Format parsed decision as a prompt-friendly block."""
    lines = [f"USER QUESTION: {parsed.question}"]
    if parsed.options:
        lines.append(f"DETECTED OPTIONS: {', '.join(parsed.options)}")
    if parsed.institution:
        lines.append(f"INSTITUTION: {parsed.institution}")
    if parsed.year:
        lines.append(f"YEAR: {parsed.year}")
    lines.append(f"DECISION TYPE: {parsed.decision_type}")
    lines.append(f"PARSING CONFIDENCE: {parsed.confidence}%")
    return "\n".join(lines)
