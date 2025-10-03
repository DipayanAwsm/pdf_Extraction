#!/usr/bin/env python3
"""
Page-wise LLM Runner
- Splits a combined text file into pages using markers like `--- PAGE N ---`
- Runs `text_lob_llm_extractor.py` once per page with fixed chunking parameters
- Aggregates per-page Excel outputs by sheet name into a single consolidated Excel
"""

import argparse
import sys
import re
from pathlib import Path
import subprocess
import time
import pandas as pd


def run_extractor_on_page(page_txt_path: Path, out_dir: Path, config_path: Path,
                          max_tokens: int = 6000, overlap_tokens: int = 400, chunk_sleep: float = 0.3,
                          timeout_sec: int = 300, engine: str = "claude") -> bool:
    if engine.lower() == "openai":
        script = "text_lob_openai_extractor.py"
    else:
        script = "text_lob_llm_extractor.py"
    cmd = [
        "python", script,
        str(page_txt_path),
        "--config", str(config_path),
        "--out", str(out_dir),
        "--max-tokens", str(max_tokens),
        "--overlap-tokens", str(overlap_tokens),
        "--chunk-sleep", str(chunk_sleep)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
    return result.returncode == 0


def consolidate_excels(per_page_root: Path, final_excel_path: Path) -> bool:
    # sheet_name -> list of DataFrames
    aggregated: dict[str, list[pd.DataFrame]] = {}
    for page_dir in sorted(per_page_root.glob("page_*_out")):
        excels = list(page_dir.glob("*.xlsx"))
        if not excels:
            continue
        try:
            page_data = pd.read_excel(excels[0], sheet_name=None)
        except Exception:
            continue
        for sheet_name, df in page_data.items():
            if df is None or df.empty:
                continue
            aggregated.setdefault(sheet_name, []).append(df)
    if not aggregated:
        return False
    try:
        with pd.ExcelWriter(final_excel_path, engine='openpyxl') as writer:
            # Add README sheet first
            readme_data = {
                'Instruction': [
                    '1. All AUTO, WC, GL data has been extracted from the PDF file',
                    '2. You just need to pull the data from the respective sheets',
                    '',
                    'Sheet Structure:',
                    '- AUTO_claims: Auto insurance claims data',
                    '- WC_claims: Workers Compensation claims data', 
                    '- GL_claims: General Liability claims data',
                    '',
                    'Data Fields Available:',
                    '- Claim Number, Loss Date, Paid Loss, Reserves, ALAE',
                    '- LOB-specific fields (BI/PD for GL, Indemnity/Medical for WC)',
                    '',
                    'Usage:',
                    '- Each sheet contains structured claim data ready for analysis',
                    '- Data is consolidated from all pages of the original PDF',
                    '- Use standard Excel functions to analyze, filter, or export data'
                ]
            }
            readme_df = pd.DataFrame(readme_data)
            readme_df.to_excel(writer, sheet_name='README', index=False)
            
            # Add consolidated data sheets
            for sheet_name, df_list in aggregated.items():
                try:
                    combined = pd.concat(df_list, ignore_index=True)
                except Exception:
                    combined = df_list[0]
                safe_sheet = str(sheet_name)[:31]
                combined.to_excel(writer, sheet_name=safe_sheet, index=False)
        return True
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Process text file page-by-page with LLM and consolidate outputs")
    parser.add_argument("text_path", help="Path to combined text file with page markers")
    parser.add_argument("--config", default="config.py", help="Path to config.py for credentials and settings")
    parser.add_argument("--out", required=True, help="Output directory for final Excel and intermediates")
    parser.add_argument("--max-tokens", type=int, default=6000, help="Max tokens per chunk for LLM")
    parser.add_argument("--overlap-tokens", type=int, default=400, help="Overlap tokens between chunks")
    parser.add_argument("--chunk-sleep", type=float, default=0.3, help="Sleep between chunks in seconds")
    parser.add_argument("--engine", choices=["claude", "openai"], default="claude", help="Extractor engine to use")
    args = parser.parse_args()

    text_path = Path(args.text_path)
    out_dir = Path(args.out)
    config_path = Path(args.config)
    if not text_path.exists():
        print(f"ERROR: Text file not found: {text_path}")
        sys.exit(1)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        full_text = text_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"ERROR: Failed to read text file: {e}")
        sys.exit(1)

    # Split on markers
    parts = re.split(r"^--- PAGE\s+(\d+)\s+---\s*$", full_text, flags=re.MULTILINE)
    page_items: list[tuple[int | None, str]] = []
    if len(parts) >= 3:
        it = iter(parts)
        _ = next(it, '')
        for page_num_str, page_text in zip(it, it):
            try:
                page_num = int(str(page_num_str).strip())
            except Exception:
                page_num = None
            page_text = str(page_text or '').strip()
            if page_text:
                page_items.append((page_num, page_text))
    else:
        single_text = full_text.strip()
        if single_text:
            page_items.append((1, single_text))

    if not page_items:
        print("ERROR: No page content found to process")
        sys.exit(2)

    per_page_dir = out_dir / "per_page"
    per_page_dir.mkdir(exist_ok=True)

    # Process each page
    processed_any = False
    for idx, (pg, ptext) in enumerate(page_items, start=1):
        page_label = f"page_{pg if pg is not None else idx}"
        page_txt_path = per_page_dir / f"{page_label}.txt"
        try:
            page_txt_path.write_text(ptext, encoding='utf-8')
        except Exception as e:
            print(f"WARN: Failed writing temp page text {page_label}: {e}")
            continue
        page_out_dir = per_page_dir / f"{page_label}_out"
        page_out_dir.mkdir(exist_ok=True)
        ok = False
        try:
            ok = run_extractor_on_page(
                page_txt_path,
                page_out_dir,
                config_path,
                max_tokens=args["max_tokens"] if isinstance(args, dict) else args.max_tokens,
                overlap_tokens=args["overlap_tokens"] if isinstance(args, dict) else args.overlap_tokens,
                chunk_sleep=args["chunk_sleep"] if isinstance(args, dict) else args.chunk_sleep,
                engine=args["engine"] if isinstance(args, dict) else args.engine,
            )
        except Exception:
            ok = False
        if ok:
            processed_any = True
        time.sleep(0.2)

    if not processed_any:
        print("ERROR: No pages processed successfully")
        sys.exit(3)

    final_excel = out_dir / f"{text_path.stem}.xlsx"
    if consolidate_excels(per_page_dir, final_excel):
        print(f"SUCCESS:{final_excel}")
        sys.exit(0)
    else:
        print("ERROR: Consolidation failed")
        sys.exit(4)


if __name__ == "__main__":
    main()
