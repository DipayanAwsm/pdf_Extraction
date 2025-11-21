#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
from typing import Tuple, List

try:
    import boto3
except ImportError:
    print("ERROR: boto3 is not installed. Install it with: pip install boto3")
    raise


def setup_bedrock_client(access_key: str, secret_key: str, session_token: str, region: str):
    try:
        session = boto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            aws_session_token=session_token,
            region_name=region,
        )
        return session.client("bedrock-runtime")
    except Exception as e:
        print(f"ERROR: Failed to setup Bedrock client: {e}")
        return None


def load_config(py_config_path: str = "config.py", json_config_path: str = "aws_config.json") -> dict:
    # Prefer Python config for consistency with existing tools
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
        except Exception as e:
            print(f"WARN: Could not load {py_config_path}: {e}")
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
        except Exception as e:
            print(f"WARN: Could not load {json_config_path}: {e}")
    return cfg


def extract_text_pagewise(pdf_path: str, use_ocr_fallback: bool = True, dpi: int = 300) -> Tuple[str, bool]:
    # Reuse the same logic as in pagewise_llm_runner for page markers
    import pdfplumber
    from pdf2image import convert_from_path
    import pytesseract

    used_ocr = False
    pages_text: List[str] = []

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        for page_idx, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
            if not text.strip() and use_ocr_fallback:
                images = convert_from_path(pdf_path, dpi=dpi, first_page=page_idx, last_page=page_idx)
                if images:
                    text = pytesseract.image_to_string(images[0], lang="eng")
                    used_ocr = True
            if not text.strip():
                text = "[No text content]"
            pages_text.append(f"--- PAGE {page_idx} ---\n{text.strip()}")
    return "\n\n".join(pages_text), used_ocr


def claude_clean_text(bedrock_client, model_id: str, text: str) -> str:
    prompt = f"""
You are an expert OCR post-processor. Clean noisy OCR text while preserving content faithfully.
- Fix broken words, remove duplicated headers/footers, normalize whitespace.
- Do NOT summarize. Keep page order markers starting with '--- PAGE ' intact.

Content to clean:
{text}
"""
    try:
        resp = bedrock_client.invoke_model(
            modelId=model_id,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4000,
                "temperature": 0.0,
                "messages": [{"role": "user", "content": prompt}],
            }),
        )
        body = json.loads(resp["body"].read())
        return body["content"][0]["text"]
    except Exception as e:
        print(f"WARN: Claude cleaning failed, returning raw text: {e}")
        return text


def main():
    ap = argparse.ArgumentParser(description="Extract text from scanned PDFs with OCR and optional Claude cleaning")
    ap.add_argument("pdf", help="Path to local PDF file")
    ap.add_argument("--out", default="text_outputs", help="Directory to write outputs")
    ap.add_argument("--clean", action="store_true", help="Run Claude cleaning over extracted text")
    ap.add_argument("--config", default="config.py", help="Path to config.py; falls back to aws_config.json")
    args = ap.parse_args()

    cfg = load_config(args.config)
    bedrock = None
    if args.clean and cfg and cfg.get("access_key"):
        bedrock = setup_bedrock_client(cfg["access_key"], cfg["secret_key"], cfg["session_token"], cfg["region"])

    raw_text, used_ocr = extract_text_pagewise(args.pdf, use_ocr_fallback=True)

    out_dir = Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)
    base = Path(args.pdf).stem
    raw_path = out_dir / f"{base}.txt"
    cleaned_path = out_dir / f"{base}_cleaned.txt"

    raw_path.write_text(raw_text, encoding="utf-8")
    print(f"Saved raw text: {raw_path}")

    if args.clean and bedrock is not None:
        cleaned = claude_clean_text(bedrock, cfg["model_id"], raw_text)
        cleaned_path.write_text(cleaned, encoding="utf-8")
        print(f"Saved cleaned text: {cleaned_path}")
    else:
        print("Skipping Claude cleaning (use --clean and ensure credentials).")


if __name__ == "__main__":
    main()


