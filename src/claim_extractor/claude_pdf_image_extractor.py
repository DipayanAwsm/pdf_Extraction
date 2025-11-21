#!/usr/bin/env python3
import argparse
import base64
import io
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import boto3
except ImportError:
    print("ERROR: boto3 is not installed. Install it with: pip install boto3")
    raise

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
    return session.client("bedrock-runtime",verify=False)


def pdf_pages_to_png_bytes(pdf_path: str, dpi: int = 220, first_page: int = None, last_page: int = None) -> List[Tuple[int, bytes]]:
    # If no page range specified, process all pages
    if first_page is None and last_page is None:
        images = convert_from_path(pdf_path, dpi=dpi)
    else:
        images = convert_from_path(pdf_path, dpi=dpi, first_page=first_page, last_page=last_page)
    
    out: List[Tuple[int, bytes]] = []
    for idx, pil_img in enumerate(images, start=first_page or 1):
        buf = io.BytesIO()
        pil_img.save(buf, format="PNG")
        out.append((idx, buf.getvalue()))
    return out


def call_claude_on_image(bedrock, model_id: str, png_bytes: bytes, page_num: int, total_pages: int) -> str:
    b64 = base64.b64encode(png_bytes).decode("utf-8")
    user_text = (
        f"You are an expert OCR assistant. Extract all text from this page image accurately. "
        f"This is page {page_num} of {total_pages}.\n"
        f"Preserve formatting, line breaks, and structure. Return only the extracted text exactly as it appears."
    )
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4000,
        "temperature": 0.0,
        "messages": [
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


def clean_text_response(text: str) -> str:
    """Clean Claude's text response, removing any JSON artifacts."""
    # Remove any potential JSON wrapper artifacts
    text = text.strip()
    # If it looks like JSON, try to extract the content
    if text.startswith('{') and text.endswith('}'):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and 'text' in parsed:
                return parsed['text']
        except:
            pass
    return text


def save_text_to_file(all_text: List[str], txt_path: Path) -> None:
    """Save all extracted text to a single .txt file with page markers."""
    content = []
    for i, page_text in enumerate(all_text, 1):
        content.append(f"--- PAGE {i} ---")
        content.append(page_text)
        content.append("")  # Empty line between pages
    txt_path.write_text("\n".join(content), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Send PDF pages directly to Claude (Bedrock) as images and extract text")
    ap.add_argument("pdf", help="Path to PDF file")
    ap.add_argument("--out", default="claude_text_results", help="Output directory")
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
    print(f"Processing {total_pages} pages from PDF: {pdf_path.name}")
    if args.first or args.last:
        print(f"Page range: {args.first or 1} to {args.last or 'end'}")
    else:
        print("Processing ALL pages")
    
    all_text: List[str] = []

    for page_num, png_bytes in pages:
        try:
            print(f"Processing page {page_num}/{total_pages}...")
            text = call_claude_on_image(bedrock, cfg["model_id"], png_bytes, page_num, total_pages)
            cleaned_text = clean_text_response(text)
            all_text.append(cleaned_text)
            print(f"[SUCCESS] Page {page_num}: extracted {len(cleaned_text)} characters")
        except Exception as e:
            print(f"[ERROR] Page {page_num} failed: {e}")
            all_text.append(f"[Error extracting page {page_num}]")

    # write output
    txt_path = out_dir / f"{base}_claude_text.txt"
    save_text_to_file(all_text, txt_path)
    print(f"Saved text: {txt_path}")


if __name__ == "__main__":
    main()


