import json
from pathlib import Path
from typing import List, Dict, Tuple

import click

from .extract_text import extract_text_from_pdf
from .regex_extractor import extract_with_regex_unstructured
from .camelot_extractor import extract_with_camelot
from .tabula_extractor import extract_with_tabula


def _load_groundtruth(truth_path: str) -> List[Dict]:
    records: List[Dict] = []
    with open(truth_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def _normalize_amount_str(s: str) -> str:
    if s is None:
        return ""
    s = str(s)
    s = s.replace("USD", "").strip()
    if not s.startswith("$"):
        s = "$" + s
    return s.replace(" ", "")


def _normalize_claim_no(s: str) -> str:
    return (s or "").strip().upper()


def _normalize_reason(s: str) -> str:
    return (s or "").strip().lower()


def _normalize_date(s: str) -> str:
    return (s or "").strip()


def _score(preds: List[Dict], truth: List[Dict]) -> Tuple[float, float, float, float]:
    # Simple pairwise compare by order. In practice, matching could be by claim_number keys.
    n = min(len(preds), len(truth))
    correct_no = correct_amt = correct_reason = correct_date = 0
    for i in range(n):
        p, t = preds[i], truth[i]
        if _normalize_claim_no(p.get("claim_number")) == _normalize_claim_no(t.get("claim_number")):
            correct_no += 1
        if _normalize_amount_str(p.get("amount")) == _normalize_amount_str(t.get("amount")):
            correct_amt += 1
        if _normalize_reason(p.get("reason")) == _normalize_reason(t.get("reason")):
            correct_reason += 1
        if _normalize_date(p.get("date")) == _normalize_date(t.get("date")):
            correct_date += 1
    denom = max(1, n)
    return (
        round(correct_no / denom, 3),
        round(correct_amt / denom, 3),
        round(correct_reason / denom, 3),
        round(correct_date / denom, 3),
    )


@click.command()
@click.argument("pdf_path", type=click.Path(exists=True))
@click.option("--truth", "truth_path", type=click.Path(exists=True), required=True, help="Path to JSONL ground-truth file")
@click.option("--ocr/--no-ocr", default=True, help="Enable OCR for regex extractor")
def main(pdf_path: str, truth_path: str, ocr: bool) -> None:
    truth = _load_groundtruth(truth_path)

    # Regex approach on unstructured text
    text, _ = extract_text_from_pdf(pdf_path, use_ocr_fallback=ocr)
    regex_preds = extract_with_regex_unstructured(text)

    # Camelot and Tabula (table oriented)
    camelot_preds = extract_with_camelot(pdf_path)
    tabula_preds = extract_with_tabula(pdf_path)

    headers = ["model", "claim_no", "amount", "reason", "date"]
    rows = []
    rows.append(["regex_unstructured", *_score(regex_preds, truth)])
    rows.append(["camelot", *_score(camelot_preds, truth)])
    rows.append(["tabula", *_score(tabula_preds, truth)])

    # Print a small report
    click.echo("Model accuracy (exact match by position):")
    click.echo("model,claim_no,amount,reason,date")
    for r in rows:
        click.echo(",".join([str(x) for x in r]))


if __name__ == "__main__":
    main()


