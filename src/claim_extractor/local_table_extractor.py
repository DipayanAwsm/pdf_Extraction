#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import List, Dict

import pandas as pd

from .camelot_extractor import extract_with_camelot
from .tabula_extractor import extract_with_tabula
from .claude_text_extractor import extract_text_pagewise, claude_clean_text, load_config, setup_bedrock_client


def try_camelot_then_tabula(pdf_path: str) -> List[Dict]:
    try:
        cam = extract_with_camelot(pdf_path)
    except Exception:
        cam = []
    if cam:
        return cam
    try:
        tab = extract_with_tabula(pdf_path)
    except Exception:
        tab = []
    return tab


def save_records_to_excel(records: List[Dict], out_xlsx: Path) -> None:
    if not records:
        # create empty placeholder
        with pd.ExcelWriter(out_xlsx, engine='openpyxl') as w:
            pd.DataFrame(columns=['claim_number','loss_date','amount','reserve','alae','reason']).to_excel(w, sheet_name='claims', index=False)
        return
    # normalize keys
    rows = []
    for r in records:
        rows.append({
            'claim_number': r.get('claim_number',''),
            'loss_date': r.get('loss_date') or r.get('date',''),
            'amount': r.get('amount',''),
            'reserve': r.get('reserve',''),
            'alae': r.get('alae',''),
            'reason': r.get('reason',''),
        })
    df = pd.DataFrame(rows, columns=['claim_number','loss_date','amount','reserve','alae','reason'])
    with pd.ExcelWriter(out_xlsx, engine='openpyxl') as w:
        df.to_excel(w, sheet_name='claims', index=False)


def main():
    ap = argparse.ArgumentParser(description='Extract tables locally (Camelot/Tabula) with optional Claude fallback. No S3 required.')
    ap.add_argument('pdf', help='Path to PDF file')
    ap.add_argument('--out', default='local_results', help='Output directory')
    ap.add_argument('--clean', action='store_true', help='Use Claude to clean OCR text if table extractors fail')
    ap.add_argument('--config', default='config.py', help='Path to config.py (or fallback to aws_config.json)')
    args = ap.parse_args()

    pdf_path = Path(args.pdf)
    out_dir = Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)
    base = pdf_path.stem

    # 1) Try Camelot/Tabula
    records = try_camelot_then_tabula(str(pdf_path))
    if records:
        xlsx_path = out_dir / f'{base}_tables.xlsx'
        save_records_to_excel(records, xlsx_path)
        print(f'Saved table extraction to: {xlsx_path}')
        return

    # 2) Fallback: OCR text and optionally Claude-clean; save .txt outputs
    print('No tables found via Camelot/Tabula. Falling back to OCR text extraction...')
    raw_text, used_ocr = extract_text_pagewise(str(pdf_path), use_ocr_fallback=True)
    raw_txt_path = out_dir / f'{base}.txt'
    raw_txt_path.write_text(raw_text, encoding='utf-8')
    print(f'Saved raw text: {raw_txt_path}')

    if args.clean:
        cfg = load_config(args.config)
        if cfg and cfg.get('access_key'):
            bedrock = setup_bedrock_client(cfg['access_key'], cfg['secret_key'], cfg['session_token'], cfg['region'])
            cleaned = claude_clean_text(bedrock, cfg['model_id'], raw_text) if bedrock else raw_text
            cleaned_txt_path = out_dir / f'{base}_cleaned.txt'
            cleaned_txt_path.write_text(cleaned, encoding='utf-8')
            print(f'Saved cleaned text: {cleaned_txt_path}')
        else:
            print('Skipping Claude cleaning: credentials not available.')


if __name__ == '__main__':
    main()


