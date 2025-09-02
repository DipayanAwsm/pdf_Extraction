import re
from typing import List, Dict

from .parse_fields import DATE_PATTERNS, _normalize_date


CLAIM_NO_PAT = re.compile(r"\b(?:claim\s*(?:no\.?|number|#|id)\s*[:\-]?|ref(?:erence)?\s*[:\-]?)\s*([A-Z0-9\-/]{5,})\b", re.IGNORECASE)
AMOUNT_PAT = re.compile(r"\$\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})|[0-9]+(?:\.[0-9]{2}))")
REASON_PAT = re.compile(r"(?:reason|cause|description)\s*[:\-]?\s*([^.;\n]+)", re.IGNORECASE)


def extract_with_regex_unstructured(text: str) -> List[Dict]:
    """
    Extract multiple claims from unstructured narrative text where each claim is
    separated by a blank line. Uses regexes to find claim number, amount,
    reason, and date.
    """
    # Split on blank lines as delimiters
    chunks = re.split(r"\n\s*\n+", text.strip())
    results: List[Dict] = []
    for chunk in chunks:
        claim_no = None
        amount = None
        reason = None
        date = None

        m = CLAIM_NO_PAT.search(chunk)
        if m:
            claim_no = m.group(1).strip()

        m = AMOUNT_PAT.search(chunk)
        if m:
            amount = f"${m.group(1)}"

        m = REASON_PAT.search(chunk)
        if m:
            reason = m.group(1).strip()

        # find dates using existing patterns
        for pat in DATE_PATTERNS:
            d = re.search(pat, chunk, re.IGNORECASE)
            if d:
                normalized = _normalize_date(d.group(1))
                if normalized:
                    date = normalized
                    break

        if any([claim_no, amount, reason, date]):
            results.append({
                "claim_number": claim_no,
                "amount": amount,
                "reason": reason,
                "date": date,
            })
    return results


