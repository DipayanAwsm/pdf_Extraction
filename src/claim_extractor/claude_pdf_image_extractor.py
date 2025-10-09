#!/usr/bin/env python3
import argparse
import base64
import io
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import boto3
import pandas as pd
from pdf2image import convert_from_path


def load_config(py_config_path: str = "config.py", json_config_path: str = "aws_config.json") -> dict:
    cfg = {}
    py_path = Path(py_config_path)
    if py_path.exists():
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("config", py_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cfg = {
                "access_key": getattr(module, "AWS_ACCESS_KEY", None),
                "secret_key": getattr(module, "AWS_SECRET_KEY", None),
                "session_token": getattr(module, "AWS_SESSION_TOKEN", None),
                "region": getattr(module, "AWS_REGION", "us-east-1"),
                "model_id": getattr(module, "MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0"),
            }
        except Exception:
            cfg = {}
    if (not cfg or not cfg.get("access_key")) and Path(json_config_path).exists():
        try:
            cfg_json = json.loads(Path(json_config_path).read_text())
            cfg = {
                "access_key": cfg_json.get("access_key"),
                "secret_key": cfg_json.get("secret_key"),
                "session_token": cfg_json.get("session_token"),
                "region": cfg_json.get("region", "us-east-1"),
                "model_id": cfg_json.get("model_id", "anthropic.claude-3-haiku-20240307-v1:0"),
            }
        except Exception:
            pass
    return cfg


def setup_bedrock_client(cfg: dict):
    session = boto3.Session(
        aws_access_key_id=cfg.get("access_key"),
        aws_secret_access_key=cfg.get("secret_key"),
        aws_session_token=cfg.get("session_token"),
        region_name=cfg.get("region", "us-east-1"),
    )
    return session.client("bedrock-runtime")


def pdf_pages_to_png_bytes(pdf_path: str, dpi: int = 220, first_page: int = None, last_page: int = None) -> List[Tuple[int, bytes]]:
    images = convert_from_path(pdf_path, dpi=dpi, first_page=first_page, last_page=last_page)
    out: List[Tuple[int, bytes]] = []
    for idx, pil_img in enumerate(images, start=first_page or 1):
        buf = io.BytesIO()
        pil_img.save(buf, format="PNG")
        out.append((idx, buf.getvalue()))
    return out


def call_claude_on_image(bedrock, model_id: str, png_bytes: bytes, page_num: int, total_pages: int) -> str:
    b64 = base64.b64encode(png_bytes).decode("utf-8")
    system = (
        "You convert images of insurance claim reports into structured JSON tables. "
        "Return STRICT JSON only. No markdown."
    )
    user_text = (
        f"Extract all tabular data from this page image. This is page {page_num} of {total_pages}.\n"
        "Respond as a JSON array of table objects:\n"
        "[ {\n"
        "  \"table_name\": string,\n"
        "  \"headers\": [string, ...],\n"
        "  \"data\": [[string,...], ...],\n"
        "  \"metadata\": {\n"
        "     \"row_count\": number,\n"
        "     \"column_count\": number,\n"
        "     \"page\": number\n"
        "  }\n"
        "} ]\n"
        "If no tables, return []."
    )
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4000,
        "temperature": 0.0,
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": b64,
                        },
                    },
                ],
            },
        ],
    }
    resp = bedrock.invoke_model(modelId=model_id, body=json.dumps(body))
    content = json.loads(resp["body"].read())
    return content["content"][0]["text"]


def parse_json_from_text(text: str) -> List[Dict[str, Any]]:
    try:
        start = text.find("["); end = text.rfind("]") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
    except Exception:
        pass
    return []


def tables_to_excel(tables: List[Dict[str, Any]], excel_path: Path, pdf_name: str) -> None:
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        # summary sheet
        summary_rows = []
        for i, t in enumerate(tables):
            headers = t.get("headers") or []
            data = t.get("data") or []
            meta = t.get("metadata") or {}
            summary_rows.append({
                "Sheet": f"Table_{i+1}",
                "Table_Name": t.get("table_name", f"Table {i+1}"),
                "Rows": len(data),
                "Columns": len(headers),
                "Page": meta.get("page"),
            })
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False)

        # per-table sheets
        for i, t in enumerate(tables):
            headers = t.get("headers") or []
            data = t.get("data") or []
            if headers and data:
                df = pd.DataFrame(data, columns=headers)
            else:
                df = pd.DataFrame(data)
            sheet = f"Table_{i+1}"
            df.to_excel(writer, sheet_name=sheet[:31], index=False)


def main():
    ap = argparse.ArgumentParser(description="Send PDF pages directly to Claude (Bedrock) as images and extract tables")
    ap.add_argument("pdf", help="Path to PDF file")
    ap.add_argument("--out", default="claude_image_results", help="Output directory")
    ap.add_argument("--dpi", type=int, default=220, help="Image DPI for page renders")
    ap.add_argument("--first", type=int, default=None, help="First page to process (1-based)")
    ap.add_argument("--last", type=int, default=None, help="Last page to process (inclusive)")
    ap.add_argument("--config", default="config.py", help="Path to config.py or use aws_config.json fallback")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if not cfg or not cfg.get("access_key"):
        print("ERROR: Missing Bedrock credentials. Update config.py or aws_config.json")
        return
    bedrock = setup_bedrock_client(cfg)

    pdf_path = Path(args.pdf)
    out_dir = Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)
    base = pdf_path.stem

    pages = pdf_pages_to_png_bytes(str(pdf_path), dpi=args.dpi, first_page=args.first, last_page=args.last)
    total_pages = len(pages)
    all_tables: List[Dict[str, Any]] = []

    for page_num, png_bytes in pages:
        try:
            text = call_claude_on_image(bedrock, cfg["model_id"], png_bytes, page_num, total_pages)
            page_tables = parse_json_from_text(text)
            # tag page in metadata if missing
            for t in page_tables:
                meta = t.setdefault("metadata", {})
                meta.setdefault("page", page_num)
            all_tables.extend(page_tables)
            print(f"Page {page_num}: extracted {len(page_tables)} tables")
        except Exception as e:
            print(f"WARN: Page {page_num} failed: {e}")

    # write outputs
    json_path = out_dir / f"{base}_claude_image.json"
    Path(json_path).write_text(json.dumps(all_tables, indent=2), encoding="utf-8")
    print(f"Saved JSON: {json_path}")

    if all_tables:
        xlsx_path = out_dir / f"{base}_claude_image.xlsx"
        tables_to_excel(all_tables, xlsx_path, pdf_path.name)
        print(f"Saved Excel: {xlsx_path}")
    else:
        print("No tables extracted.")


if __name__ == "__main__":
    main()


