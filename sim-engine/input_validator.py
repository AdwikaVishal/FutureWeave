import re
import unicodedata

_MIN_DECISION_LENGTH = 5
_MAX_DECISION_LENGTH = 2000
_MAX_CONTEXT_KEYS = 20
_MAX_OPTION_LENGTH = 200

_ENGLISH_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "i", "me", "my", "we", "our", "you", "your", "he", "she", "it", "they",
    "should", "would", "could", "will", "can", "do", "does", "did", "have",
    "has", "had", "not", "no", "nor", "so", "if", "then", "else", "about",
    "which", "what", "who", "whom", "where", "when", "why", "how",
}

_LATIN_CHARS = set("abcdefghijklmnopqrstuvwxyz")


def is_likely_meaningful(text: str) -> tuple[bool, str]:
    if not text or not text.strip():
        return False, "Input is empty."
    stripped = text.strip()
    if len(stripped) < _MIN_DECISION_LENGTH:
        return False, f"Input is too short ({len(stripped)} chars, minimum {_MIN_DECISION_LENGTH})."
    if len(stripped) > _MAX_DECISION_LENGTH:
        return False, f"Input is too long ({len(stripped)} chars, maximum {_MAX_DECISION_LENGTH})."

    alpha_chars = sum(1 for c in stripped if c.isalpha())
    total_chars = len(stripped)
    if total_chars > 0 and alpha_chars / total_chars < 0.3:
        return False, "Input contains too few letters — it may be gibberish or non-text."

    latin_ratio = 0
    if alpha_chars > 0:
        latin_count = sum(1 for c in stripped if c.isalpha() and c.lower() in _LATIN_CHARS)
        latin_ratio = latin_count / alpha_chars

    if latin_ratio < 0.3 and alpha_chars > 5:
        return False, "Input appears to be in a non-Latin script not yet supported by this system."

    words = re.findall(r"[a-zA-Z]+", stripped)
    if len(words) < 2:
        return False, "Input contains fewer than 2 recognizable words."

    meaningful_words = [w for w in words if w.lower() not in _ENGLISH_STOPWORDS]
    if len(meaningful_words) == 0 and len(words) > 0:
        return False, "Input contains only common stopwords with no meaningful content."

    return True, ""


def describe_detection_failure(decision: str, context: dict) -> list[str]:
    messages = []
    text = decision + " " + str(context)
    text_lower = text.lower()

    from data_grounding import INDUSTRY_KEYWORDS, ROLE_KEYWORDS, LOCATION_MAP
    has_industry = any(
        kw in text_lower for kws in INDUSTRY_KEYWORDS.values() for kw in kws
    )
    has_role = any(
        kw in text_lower for kws in ROLE_KEYWORDS.values() for kw in kws
    )
    has_location = any(
        loc in text_lower for loc in LOCATION_MAP
    )

    if not has_role and not has_industry and not has_location:
        messages.append(
            "I couldn't identify a specific role, industry, or location from your input. "
            "Results will use general India averages."
        )
    elif not has_role:
        messages.append(
            "I couldn't identify a specific job role from your input. "
            "Salary and career projections will use a general professional profile."
        )
    elif not has_industry:
        messages.append(
            "I couldn't identify a specific industry from your input. "
            "Industry growth projections will use a general baseline."
        )

    return messages


def validate_context(context: dict) -> list[str]:
    warnings = []
    if not isinstance(context, dict):
        return ["Context must be a dictionary of user attributes."]
    if len(context) > _MAX_CONTEXT_KEYS:
        warnings.append(f"Context has {len(context)} fields; unusual keys may be ignored.")
    known_keys = {"age", "location", "risk_tolerance", "financial_condition", "interests", "skills", "career_stage", "user_email"}
    unknown = [k for k in context if k not in known_keys and not k.startswith("_")]
    if unknown:
        warnings.append(f"Unrecognized context fields: {', '.join(unknown[:3])}.")
    if "location" in context and not isinstance(context["location"], str):
        warnings.append("Location should be a city name (e.g. 'Bangalore', 'Mumbai').")
    return warnings


def safe_template_substitute(template: str, **kwargs: str) -> str:
    escaped = {}
    for key, value in kwargs.items():
        val = str(value)
        val = val.replace("{", "<<<").replace("}", ">>>")
        escaped[key] = val
    result = template
    for key, value in escaped.items():
        result = result.replace("{" + key + "}", value)
    return result
