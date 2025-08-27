import json
import os
import csv
from pathlib import Path
from typing import List, Dict

import click

from .extract_text import extract_text_from_pdf
from .parse_fields import parse_fields


def _gather_pdfs(input_path: str) -> List[str]:
    p = Path(input_path)
    if p.is_file() and p.suffix.lower() == ".pdf":
        return [str(p)]
    if p.is_dir():
        return [str(f) for f in p.rglob("*.pdf")]
    raise click.ClickException(f"No PDF found at {input_path}")


@click.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.option("--format", "out_format", type=click.Choice(["json", "csv"]), default="json")
@click.option("--out", "out_path", type=click.Path(), default="-")
@click.option("--no-ocr", is_flag=True, help="Disable OCR fallback (use text layer only)")
@click.option("--dpi", type=int, default=300, help="DPI for OCR rasterization")
def main(input_path: str, out_format: str, out_path: str, no_ocr: bool, dpi: int) -> None:
    pdf_files = _gather_pdfs(input_path)
    results: List[Dict] = []

    for pdf in pdf_files:
        try:
            text, used_ocr = extract_text_from_pdf(pdf, use_ocr_fallback=not no_ocr, dpi=dpi)
            fields = parse_fields(text)
            record = {
                "file_path": pdf,
                **fields,
            }
            results.append(record)
        except Exception as exc:
            results.append({
                "file_path": pdf,
                "claim_number": None,
                "name": None,
                "date": None,
                "confidence": 0.0,
                "error": str(exc),
            })

    if out_format == "json":
        payload = json.dumps(results, indent=2)
        if out_path == "-":
            click.echo(payload)
        else:
            Path(out_path).write_text(payload, encoding="utf-8")
            click.echo(f"Wrote {len(results)} records to {out_path}")
    else:
        # CSV
        columns = ["file_path", "claim_number", "name", "date", "confidence", "error"]
        rows = []
        for r in results:
            rows.append({k: r.get(k, "") for k in columns})
        if out_path == "-":
            writer = csv.DictWriter(click.get_text_stream('stdout'), fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        else:
            with open(out_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=columns)
                writer.writeheader()
                writer.writerows(rows)
            click.echo(f"Wrote {len(results)} records to {out_path}")


if __name__ == "__main__":
    main()



