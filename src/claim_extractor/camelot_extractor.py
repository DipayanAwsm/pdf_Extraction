from typing import List, Dict

import camelot


def extract_with_camelot(pdf_path: str) -> List[Dict]:
    """
    Attempt to extract claims using Camelot (table-oriented). Returns list of
    dicts with keys: claim_number, amount, reason, date.
    """
    tables = camelot.read_pdf(pdf_path, pages="all", flavor="lattice")
    results: List[Dict] = []
    for table in tables:
        df = table.df
        # Heuristic: look for columns that resemble expected fields
        headers = [h.strip().lower() for h in df.iloc[0].tolist()]
        data = df.iloc[1:]
        # Try find indices
        def find_idx(*candidates):
            for cand in candidates:
                if cand in headers:
                    return headers.index(cand)
            return None

        idx_claim = find_idx("claim number", "claim no", "claim#", "ref", "reference")
        idx_amount = find_idx("amount", "paid", "total", "indemnity")
        idx_reason = find_idx("reason", "cause", "description")
        idx_date = find_idx("date of loss", "dol", "date")

        for _, row in data.iterrows():
            rec = {
                "claim_number": row[idx_claim].strip() if idx_claim is not None else None,
                "amount": row[idx_amount].strip() if idx_amount is not None else None,
                "reason": row[idx_reason].strip() if idx_reason is not None else None,
                "date": row[idx_date].strip() if idx_date is not None else None,
            }
            if any(rec.values()):
                results.append(rec)
    return results


