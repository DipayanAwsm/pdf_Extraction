#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import boto3

# Reuse normalization utils from PDF code where useful
from src.claim_extractor.extract_text import extract_text_from_pdf, _extract_text_fitz


def load_aws_config_from_py(config_file: str = "config.py") -> Dict[str, str]:
    config_path = Path(config_file)
    if not config_path.exists():
        print(f"❌ Configuration file not found: {config_path}")
        return None
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("config", config_path)
        config_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config_module)
        cfg = {
            'access_key': getattr(config_module, 'AWS_ACCESS_KEY', None),
            'secret_key': getattr(config_module, 'AWS_SECRET_KEY', None),
            'session_token': getattr(config_module, 'AWS_SESSION_TOKEN', None),
            'region': getattr(config_module, 'AWS_REGION', None),
            'model_id': getattr(config_module, 'MODEL_ID', None),
        }
        missing = [k for k, v in cfg.items() if not v]
        if missing:
            print(f"❌ Missing required config fields: {missing}")
            return None
        return cfg
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        return None


def setup_bedrock_client(cfg: Dict[str, str]):
    try:
        session = boto3.Session(
            aws_access_key_id=cfg['access_key'],
            aws_secret_access_key=cfg['secret_key'],
            aws_session_token=cfg['session_token'],
            region_name=cfg['region']
        )
        return session.client('bedrock-runtime')
    except Exception as e:
        print(f"❌ Failed to setup Bedrock client: {e}")
        return None


def _sheet_to_text(df: pd.DataFrame, sheet_name: str) -> str:
    lines: List[str] = [f"SHEET: {sheet_name}"]
    # Headers
    headers = [str(h) for h in df.columns]
    lines.append(" | ".join(headers))
    # Rows (limit per row length)
    for _, row in df.iterrows():
        vals = [str(v) if v is not None else '' for v in row.tolist()]
        lines.append(" | ".join(vals))
    return "\n".join(lines)


def _extract_carrier_from_text(text: str) -> str:
    import re
    patterns = [
        r"\b(?:carrier|company|insurer|provider)\s*[:\-]\s*([A-Za-z0-9 &'.\-/]+)",
        r"\b([A-Z][A-Za-z0-9 &'.\-/]+(?:Insurance|Ins|Corp|Corporation|Company|Co|LLC|Inc))\b",
        r"\b(?:Policy\s*holder|Insured)\s*[:\-]\s*([A-Za-z0-9 &'.\-/]+)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            if len(candidate) > 2:  # basic length filter
                return candidate
    return ""


def classify_lob(bedrock_client, model_id: str, text: str) -> str:
    prompt = f"""
You are an insurance domain expert. Classify the following content into one line of business.
Choose exactly one of: AUTO, GENERAL LIABILITY, WC
Return strict JSON only: {{"lob": "AUTO|GENERAL LIABILITY|WC"}}

Content:\n{text}
"""
    try:
        resp = bedrock_client.invoke_model(
            modelId=model_id,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 100,
                "temperature": 0.0,
                "messages": [{"role": "user", "content": prompt}],
            })
        )
        body = json.loads(resp['body'].read())
        content = body['content'][0]['text']
        start = content.find('{'); end = content.rfind('}') + 1
        if start != -1 and end > start:
            obj = json.loads(content[start:end])
            lob = (obj.get('lob') or '').strip().upper()
            if lob in {"AUTO","GENERAL LIABILITY","WC"}:
                return lob
    except Exception as e:
        print(f"⚠️ LOB classification failed: {e}")
    return "AUTO"  # default fallback


def extract_fields_llm(bedrock_client, model_id: str, text: str, lob: str) -> Dict:
    lob = lob.upper()
    if lob == 'AUTO':
        schema = {
            "evaluation_date": "string",
            "carrier": "string",
            "claims": [{
                "claim_number": "string",
                "loss_date": "string",
                "paid_loss": "string",
                "reserve": "string",
                "alae": "string"
            }]
        }
        guidance = "For AUTO: evaluation_date, carrier, claim_number, loss_date, paid_loss, reserve, alae."
    elif lob in ('GENERAL LIABILITY','GL'):
        schema = {
            "evaluation_date": "string",
            "carrier": "string",
            "claims": [{
                "claim_number": "string",
                "loss_date": "string",
                "bi_paid_loss": "string",
                "pd_paid_loss": "string",
                "bi_reserve": "string",
                "pd_reserve": "string",
                "alae": "string"
            }]
        }
        guidance = "For GL: evaluation_date, carrier, bi_paid_loss, pd_paid_loss, bi_reserve, pd_reserve, alae."
        lob = 'GL'
    else:  # WC
        schema = {
            "evaluation_date": "string",
            "carrier": "string",
            "claims": [{
                "claim_number": "string",
                "loss_date": "string",
                "bi_paid_loss": "string",
                "pd_paid_loss": "string",
                "bi_reserve": "string",
                "pd_reserve": "string",
                "alae": "string"
            }]
        }
        guidance = "For WC: evaluation_date, carrier, bi_paid_loss, pd_paid_loss, bi_reserve, pd_reserve, alae."
        lob = 'WC'

    prompt = f"""
Extract structured fields from the content for LoB={lob}.
Return STRICT JSON ONLY matching this schema:
{schema}
Rules: ISO dates if possible; keep amounts/strings as-is; empty string if missing; preserve row order.
IMPORTANT: Extract the carrier/company name from the content. This is critical.

Content:\n{text}
"""
    try:
        resp = bedrock_client.invoke_model(
            modelId=model_id,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4000,
                "temperature": 0.0,
                "messages": [{"role": "user", "content": prompt}],
            })
        )
        body = json.loads(resp['body'].read())
        content = body['content'][0]['text']
        start = content.find('{'); end = content.rfind('}') + 1
        if start != -1 and end > start:
            obj = json.loads(content[start:end])
            if isinstance(obj, dict) and 'claims' in obj and isinstance(obj['claims'], list):
                obj.setdefault('evaluation_date','')
                obj.setdefault('carrier','')
                return obj
    except Exception as e:
        print(f"⚠️ LLM extraction failed: {e}")
    return {"evaluation_date":"","carrier":"","claims": []}


def write_outputs(per_lob: Dict[str, pd.DataFrame], out_dir: Path):
    # Per-LoB files
    if 'AUTO' in per_lob and not per_lob['AUTO'].empty:
        d = out_dir / 'auto'; d.mkdir(parents=True, exist_ok=True)
        with pd.ExcelWriter(d / 'AUTO_consolidated.xlsx', engine='openpyxl') as w:
            per_lob['AUTO'].to_excel(w, sheet_name='auto_claims', index=False)
    if 'GL' in per_lob and not per_lob['GL'].empty:
        d = out_dir / 'GL'; d.mkdir(parents=True, exist_ok=True)
        with pd.ExcelWriter(d / 'GL_consolidated.xlsx', engine='openpyxl') as w:
            per_lob['GL'].to_excel(w, sheet_name='gl_claims', index=False)
    if 'WC' in per_lob and not per_lob['WC'].empty:
        d = out_dir / 'WC'; d.mkdir(parents=True, exist_ok=True)
        with pd.ExcelWriter(d / 'WC_consolidated.xlsx', engine='openpyxl') as w:
            per_lob['WC'].to_excel(w, sheet_name='wc_claims', index=False)
    # Combined
    with pd.ExcelWriter(out_dir / 'result.xlsx', engine='openpyxl') as w:
        if 'AUTO' in per_lob and not per_lob['AUTO'].empty:
            per_lob['AUTO'].to_excel(w, sheet_name='auto_claims', index=False)
        if 'GL' in per_lob and not per_lob['GL'].empty:
            per_lob['GL'].to_excel(w, sheet_name='gl_claims', index=False)
        if 'WC' in per_lob and not per_lob['WC'].empty:
            per_lob['WC'].to_excel(w, sheet_name='wc_claims', index=False)


def main():
    p = argparse.ArgumentParser(description="LLM-based LoB extractor for multi-sheet Excel + optional PDF")
    p.add_argument("excel_path", help="Input Excel (.xlsx)")
    p.add_argument("--pdf", help="Optional companion PDF for additional text context")
    p.add_argument("--config", default="config.py", help="Path to config.py")
    p.add_argument("--out", dest="out_dir", default="excel_llm_results", help="Output directory")
    args = p.parse_args()

    cfg = load_aws_config_from_py(args.config)
    if not cfg:
        return
    bedrock = setup_bedrock_client(cfg)
    if not bedrock:
        return

    out_dir = Path(args.out_dir); out_dir.mkdir(parents=True, exist_ok=True)

    # Read Excel
    xls = pd.ExcelFile(args.excel_path)
    excel_text_parts = []

    # Read optional PDF using fitz for robust text extraction
    pdf_text = ""
    if args.pdf and Path(args.pdf).exists():
        pdf_text = _extract_text_fitz(args.pdf)
        print(f"📄 Extracted {len(pdf_text)} chars from PDF using fitz")
        excel_text_parts.append(f"PDF_CONTEXT:\n{pdf_text}")

    auto_rows: List[Dict] = []
    gl_rows: List[Dict] = []
    wc_rows: List[Dict] = []

    for sheet in xls.sheet_names:
        df = xls.parse(sheet)
        sheet_text = _sheet_to_text(df, sheet)
        
        # Combine Excel sheet + PDF context for better carrier detection
        combined_text = "\n\n".join(excel_text_parts + [sheet_text])
        
        lob = classify_lob(bedrock, cfg['model_id'], combined_text)
        fields = extract_fields_llm(bedrock, cfg['model_id'], combined_text, lob)
        
        # Ensure carrier is extracted - try multiple sources
        carrier = fields.get('carrier', '')
        if not carrier:
            carrier = _extract_carrier_from_text(combined_text)
        if not carrier:
            # Try from sheet data
            carrier = _extract_carrier_from_text(sheet_text)
        
        print(f"📊 Sheet '{sheet}': LoB={lob}, Carrier='{carrier}'")

        if lob == 'AUTO':
            for c in fields.get('claims', []):
                auto_rows.append({
                    'evaluation_date': fields.get('evaluation_date',''),
                    'carrier': c.get('carrier','') or carrier or fields.get('carrier',''),
                    'claim_number': c.get('claim_number',''),
                    'loss_date': c.get('loss_date',''),
                    'paid_loss': c.get('paid_loss',''),
                    'reserve': c.get('reserve',''),
                    'alae': c.get('alae',''),
                })
        elif lob in ('GENERAL LIABILITY','GL'):
            for c in fields.get('claims', []):
                gl_rows.append({
                    'evaluation_date': fields.get('evaluation_date',''),
                    'carrier': c.get('carrier','') or carrier or fields.get('carrier',''),
                    'claim_number': c.get('claim_number',''),
                    'loss_date': c.get('loss_date',''),
                    'bi_paid_loss': c.get('bi_paid_loss',''),
                    'pd_paid_loss': c.get('pd_paid_loss',''),
                    'bi_reserve': c.get('bi_reserve',''),
                    'pd_reserve': c.get('pd_reserve',''),
                    'alae': c.get('alae',''),
                })
        elif lob == 'WC':
            for c in fields.get('claims', []):
                wc_rows.append({
                    'evaluation_date': fields.get('evaluation_date',''),
                    'carrier': c.get('carrier','') or carrier or fields.get('carrier',''),
                    'claim_number': c.get('claim_number',''),
                    'loss_date': c.get('loss_date',''),
                    'bi_paid_loss': c.get('bi_paid_loss',''),
                    'pd_paid_loss': c.get('pd_paid_loss',''),
                    'bi_reserve': c.get('bi_reserve',''),
                    'pd_reserve': c.get('pd_reserve',''),
                    'alae': c.get('alae',''),
                })
        else:
            # Unknown LOB from model, skip
            continue

    per_lob = {}
    if auto_rows:
        per_lob['AUTO'] = pd.DataFrame(auto_rows, columns=['evaluation_date','carrier','claim_number','loss_date','paid_loss','reserve','alae'])
    else:
        per_lob['AUTO'] = pd.DataFrame()
    if gl_rows:
        per_lob['GL'] = pd.DataFrame(gl_rows, columns=['evaluation_date','carrier','claim_number','loss_date','bi_paid_loss','pd_paid_loss','bi_reserve','pd_reserve','alae'])
    else:
        per_lob['GL'] = pd.DataFrame()
    if wc_rows:
        per_lob['WC'] = pd.DataFrame(wc_rows, columns=['evaluation_date','carrier','claim_number','loss_date','bi_paid_loss','pd_paid_loss','bi_reserve','pd_reserve','alae'])
    else:
        per_lob['WC'] = pd.DataFrame()

    write_outputs(per_lob, out_dir)
    print(f"Done. Outputs under: {out_dir}")


if __name__ == "__main__":
    main()
