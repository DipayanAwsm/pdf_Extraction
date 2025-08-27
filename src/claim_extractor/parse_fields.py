import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

from dateutil import parser as date_parser


CLAIM_PATTERNS = [
    r"\bclaim\s*(?:no\.?|number|#|id)\s*[:\-]?\s*([A-Z0-9\-/]{5,})\b",
    r"\bclaim\s*[:\-]?\s*([A-Z0-9\-/]{5,})\b",
]

NAME_PATTERNS = [
    r"\b(?:claimant|insured|name)\s*[:\-]\s*([A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+)+)\b",
]

DATE_PATTERNS = [
    r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",
    r"\b([A-Za-z]{3,9}\s+\d{1,2},\s*\d{4})\b",
    r"\b(\d{4}[/-]\d{1,2}[/-]\d{1,2})\b",
]


def _first_match(patterns, text: str, flags=re.IGNORECASE) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            return match.group(1).strip()
    return None


def _normalize_date(date_str: str) -> Optional[str]:
    try:
        dt = date_parser.parse(date_str, dayfirst=False, yearfirst=False, fuzzy=True)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def _score(result: Dict[str, Optional[str]]) -> float:
    score = 0.0
    if result.get("claim_number"):
        score += 0.4
    if result.get("name"):
        score += 0.3
    if result.get("date"):
        score += 0.3
    return round(score, 2)


def parse_fields(text: str) -> Dict[str, Optional[str]]:
    text = text or ""

    claim_number = _first_match(CLAIM_PATTERNS, text)
    name = _first_match(NAME_PATTERNS, text)

    raw_date = _first_match(DATE_PATTERNS, text)
    normalized_date = _normalize_date(raw_date) if raw_date else None

    result = {
        "claim_number": claim_number,
        "name": name,
        "date": normalized_date,
    }
    result["confidence"] = _score(result)
    return result



