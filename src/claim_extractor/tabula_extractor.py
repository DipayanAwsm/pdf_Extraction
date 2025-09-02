from typing import List, Dict

import tabula


def extract_with_tabula(pdf_path: str) -> List[Dict]:
    """
    Attempt to extract claims using Tabula (table-oriented). Returns list of
    dicts with keys: claim_number, amount, reason, date.
    Requires Java installed.
    """
    dfs = tabula.read_pdf(pdf_path, pages="all", multiple_tables=True)
    results: List[Dict] = []
    for df in dfs:
        if df is None or df.empty:
            continue
        headers = [str(h).strip().lower() for h in list(df.columns)]

        def find_idx(*candidates):
            for cand in candidates:
                if cand in headers:
                    return headers.index(cand)
            return None

        idx_claim = find_idx("claim number", "claim no", "claim#", "ref", "reference")
        idx_amount = find_idx("amount", "paid", "total", "indemnity")
        idx_reason = find_idx("reason", "cause", "description")
        idx_date = find_idx("date of loss", "dol", "date")

        for _, row in df.iterrows():
            rec = {
                "claim_number": str(row[idx_claim]).strip() if idx_claim is not None else None,
                "amount": str(row[idx_amount]).strip() if idx_amount is not None else None,
                "reason": str(row[idx_reason]).strip() if idx_reason is not None else None,
                "date": str(row[idx_date]).strip() if idx_date is not None else None,
            }
            if any(rec.values()):
                results.append(rec)
    return results


