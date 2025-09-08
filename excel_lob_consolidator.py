#!/usr/bin/env python3
import argparse
import re
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd


def _detect_lob_from_name(name: str) -> Optional[str]:
    if not name:
        return None
    s = name.upper()
    if any(k in s for k in ["AUTO", "AUTOMOBILE", "VEHICLE"]):
        return "AUTO"
    if any(k in s for k in ["GENERAL LIABILITY", "GL", "CGL"]):
        return "GL"
    if any(k in s for k in ["WORKERS COMP", "WORKERS COMPENSATION", "WC"]):
        return "WC"
    return None


def _first_group(patterns: List[str], text: str) -> str:
    for pat in patterns:
        m = re.search(pat, text or "", flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


def _normalize_date_str(s: str) -> str:
    try:
        from dateutil import parser as date_parser
        return date_parser.parse(str(s), fuzzy=True).strftime("%Y-%m-%d")
    except Exception:
        return str(s) if s is not None else ""


def _find_col_idx(headers: List[str], *candidates: str) -> Optional[int]:
    if not headers:
        return None
    lower = [str(h).strip().lower() for h in headers]
    for cand in candidates:
        if cand.lower() in lower:
            return lower.index(cand.lower())
    for i, h in enumerate(lower):
        for cand in candidates:
            if cand.lower() in h:
                return i
    return None


EVALUATION_DATE_PATTERNS = [
    r"\b(?:evaluation\s*date|as\s*of|report\s*date|run\s*date|valuation\s*date)\s*[:\-]?\s*([A-Za-z]{3,9}\s+\d{1,2},\s*\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})",
]

CARRIER_PATTERNS = [
    r"\b(?:carrier|company|insurer|provider)\s*[:\-]\s*([A-Za-z0-9 &'.\-/]+)",
]


def _extract_meta_from_values(values_text: str) -> Dict[str, str]:
    evaluation_date = _first_group(EVALUATION_DATE_PATTERNS, values_text)
    carrier = _first_group(CARRIER_PATTERNS, values_text)
    return {
        "evaluation_date": _normalize_date_str(evaluation_date) if evaluation_date else "",
        "carrier": carrier,
    }


def normalize_auto_df(df: pd.DataFrame, sheet_name: str) -> Dict:
    headers = [str(h) for h in df.columns]
    i_claim = _find_col_idx(headers, 'claim number', 'claim no', 'claim#', 'reference', 'ref')
    i_loss_date = _find_col_idx(headers, 'loss date', 'date of loss', 'dol', 'accident date')
    i_paid = _find_col_idx(headers, 'paid loss', 'paid', 'indemnity paid', 'total paid')
    i_reserve = _find_col_idx(headers, 'reserve', 'reserves', 'loss reserve', 'remaining reserve')
    i_alae = _find_col_idx(headers, 'alae', 'allocated loss adjustment expense', 'expense', 'total expense')
    i_carrier = _find_col_idx(headers, 'carrier', 'company', 'insurer', 'provider')

    claims = []
    for _, row in df.iterrows():
        rec = {
            'carrier': str(row[i_carrier]).strip() if i_carrier is not None else '',
            'claim_number': str(row[i_claim]).strip() if i_claim is not None else '',
            'loss_date': _normalize_date_str(row[i_loss_date]) if i_loss_date is not None else '',
            'paid_loss': str(row[i_paid]).strip() if i_paid is not None else '',
            'reserve': str(row[i_reserve]).strip() if i_reserve is not None else '',
            'alae': str(row[i_alae]).strip() if i_alae is not None else '',
        }
        if any(rec.values()):
            claims.append(rec)

    meta = _extract_meta_from_values("\n".join(df.astype(str).fillna("").values.flatten().tolist()))
    return {"evaluation_date": meta["evaluation_date"], "carrier": meta["carrier"], "claims": claims}


def normalize_gl_df(df: pd.DataFrame, sheet_name: str) -> Dict:
    headers = [str(h) for h in df.columns]
    i_claim = _find_col_idx(headers, 'claim number', 'claim no', 'claim#', 'reference', 'ref')
    i_loss_date = _find_col_idx(headers, 'loss date', 'date of loss', 'dol', 'accident date')
    i_bi_paid = _find_col_idx(headers, 'bodily injury paid loss', 'bi paid', 'paid bodily injury')
    i_pd_paid = _find_col_idx(headers, 'property damage paid loss', 'pd paid', 'paid property damage')
    i_bi_res = _find_col_idx(headers, 'bodily injury reserves', 'bi reserve', 'bodily injury reserve')
    i_pd_res = _find_col_idx(headers, 'property damage reserves', 'pd reserve', 'property damage reserve')
    i_alae = _find_col_idx(headers, 'alae', 'allocated loss adjustment expense', 'expense', 'total expense')
    i_carrier = _find_col_idx(headers, 'carrier', 'company', 'insurer', 'provider')

    claims = []
    for _, row in df.iterrows():
        rec = {
            'carrier': str(row[i_carrier]).strip() if i_carrier is not None else '',
            'claim_number': str(row[i_claim]).strip() if i_claim is not None else '',
            'loss_date': _normalize_date_str(row[i_loss_date]) if i_loss_date is not None else '',
            'bi_paid_loss': str(row[i_bi_paid]).strip() if i_bi_paid is not None else '',
            'pd_paid_loss': str(row[i_pd_paid]).strip() if i_pd_paid is not None else '',
            'bi_reserve': str(row[i_bi_res]).strip() if i_bi_res is not None else '',
            'pd_reserve': str(row[i_pd_res]).strip() if i_pd_res is not None else '',
            'alae': str(row[i_alae]).strip() if i_alae is not None else '',
        }
        if any(rec.values()):
            claims.append(rec)

    meta = _extract_meta_from_values("\n".join(df.astype(str).fillna("").values.flatten().tolist()))
    return {"evaluation_date": meta["evaluation_date"], "carrier": meta["carrier"], "claims": claims}


def normalize_wc_df(df: pd.DataFrame, sheet_name: str) -> Dict:
    # Same schema as GL per requirement
    return normalize_gl_df(df, sheet_name)


def consolidate_and_write(excel_path: str, out_dir: str) -> None:
    path = Path(excel_path)
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    xls = pd.ExcelFile(path)

    auto_rows = []
    gl_rows = []
    wc_rows = []

    for sheet in xls.sheet_names:
        df = xls.parse(sheet)
        lob = _detect_lob_from_name(sheet) or _detect_lob_from_name(" ".join(map(str, df.columns)))
        if lob == 'AUTO':
            norm = normalize_auto_df(df, sheet)
            for c in norm['claims']:
                auto_rows.append({
                    'evaluation_date': norm['evaluation_date'],
                    'carrier': c.get('carrier','') or norm.get('carrier',''),
                    'claim_number': c.get('claim_number',''),
                    'loss_date': c.get('loss_date',''),
                    'paid_loss': c.get('paid_loss',''),
                    'reserve': c.get('reserve',''),
                    'alae': c.get('alae',''),
                })
        elif lob == 'GL':
            norm = normalize_gl_df(df, sheet)
            for c in norm['claims']:
                gl_rows.append({
                    'evaluation_date': norm['evaluation_date'],
                    'carrier': c.get('carrier','') or norm.get('carrier',''),
                    'claim_number': c.get('claim_number',''),
                    'loss_date': c.get('loss_date',''),
                    'bi_paid_loss': c.get('bi_paid_loss',''),
                    'pd_paid_loss': c.get('pd_paid_loss',''),
                    'bi_reserve': c.get('bi_reserve',''),
                    'pd_reserve': c.get('pd_reserve',''),
                    'alae': c.get('alae',''),
                })
        elif lob == 'WC':
            norm = normalize_wc_df(df, sheet)
            for c in norm['claims']:
                wc_rows.append({
                    'evaluation_date': norm['evaluation_date'],
                    'carrier': c.get('carrier','') or norm.get('carrier',''),
                    'claim_number': c.get('claim_number',''),
                    'loss_date': c.get('loss_date',''),
                    'bi_paid_loss': c.get('bi_paid_loss',''),
                    'pd_paid_loss': c.get('pd_paid_loss',''),
                    'bi_reserve': c.get('bi_reserve',''),
                    'pd_reserve': c.get('pd_reserve',''),
                    'alae': c.get('alae',''),
                })
        else:
            # Unknown sheet; skip
            continue

    # Write per-LoB and combined result.xlsx
    auto_df = pd.DataFrame(auto_rows) if auto_rows else None
    gl_df = pd.DataFrame(gl_rows) if gl_rows else None
    wc_df = pd.DataFrame(wc_rows) if wc_rows else None

    # Per-LoB
    if auto_df is not None:
        d = output_dir / 'auto'
        d.mkdir(parents=True, exist_ok=True)
        with pd.ExcelWriter(d / 'AUTO_consolidated.xlsx', engine='openpyxl') as w:
            auto_df.to_excel(w, sheet_name='auto_claims', index=False)
    if gl_df is not None:
        d = output_dir / 'GL'
        d.mkdir(parents=True, exist_ok=True)
        with pd.ExcelWriter(d / 'GL_consolidated.xlsx', engine='openpyxl') as w:
            gl_df.to_excel(w, sheet_name='gl_claims', index=False)
    if wc_df is not None:
        d = output_dir / 'WC'
        d.mkdir(parents=True, exist_ok=True)
        with pd.ExcelWriter(d / 'WC_consolidated.xlsx', engine='openpyxl') as w:
            wc_df.to_excel(w, sheet_name='wc_claims', index=False)

    # Combined
    with pd.ExcelWriter(output_dir / 'result.xlsx', engine='openpyxl') as w:
        if auto_df is not None:
            auto_df.to_excel(w, sheet_name='auto_claims', index=False)
        if gl_df is not None:
            gl_df.to_excel(w, sheet_name='gl_claims', index=False)
        if wc_df is not None:
            wc_df.to_excel(w, sheet_name='wc_claims', index=False)

    print(f"Done. Wrote outputs under: {output_dir}")


def main():
    p = argparse.ArgumentParser(description="Consolidate multi-sheet Excel to normalized LoB outputs")
    p.add_argument("excel_path", help="Path to input Excel file (.xlsx)")
    p.add_argument("--out", dest="out_dir", default="excel_results", help="Output directory")
    args = p.parse_args()
    consolidate_and_write(args.excel_path, args.out_dir)


if __name__ == "__main__":
    main()
