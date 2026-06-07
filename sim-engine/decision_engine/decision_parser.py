from __future__ import annotations
import re
from typing import Any, Dict, List, Optional


ParsedDecision = Dict[str, Any]


def parse_decision(decision: str) -> ParsedDecision:
    text = decision.strip()
    options: List[str] = []
    decision_type = "binary"
    confidence = 85
    institution = None
    year = None

    patterns = [
        (r"(.+?)\s+(?:or|vs\.?|versus|rather than)\s+(.+?)$", "binary"),
        (r"(?:should I|should we)\s+(.+?)\s+(?:or|vs\.?)\s+(.+?)$", "binary"),
        (r"(?:which|what)\s+(?:should|do|is)\s+(.+?)\s+(?:or|vs\.?)\s+(.+?)$", "binary"),
    ]

    for pattern, dtype in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            options = [m.group(1).strip(), m.group(2).strip()]
            decision_type = dtype
            break

    if not options:
        options = ["pursue", "decline"]
        decision_type = "binary"
        confidence = 40

    inst_match = re.search(r'(?:at|in|from)\s+([A-Z][A-Za-z.\s&]+?)(?:\s+(?:in|for|at|,)\s|$)', text)
    if inst_match:
        institution = inst_match.group(1).strip().rstrip(",")

    year_match = re.search(r'\b(20\d{2})\b', text)
    if year_match:
        year = int(year_match.group(1))

    return {
        "options": options,
        "decision_type": decision_type,
        "confidence": confidence,
        "institution": institution,
        "year": year,
        "raw_text": decision,
    }
