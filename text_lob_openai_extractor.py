#!/usr/bin/env python3
import argparse
import json
import time
from pathlib import Path
from typing import Dict, List

import pandas as pd

try:
    from openai import OpenAI
except ImportError:
    raise SystemExit("Please install openai: pip install openai>=1.30.0")


# === Chunking and backoff configuration (overridable by CLI) ===
DEFAULT_MAX_CHARS = 12000
DEFAULT_OVERLAP_CHARS = 800
DEFAULT_CHUNK_SLEEP = 0.5
DEFAULT_MAX_ATTEMPTS = 5


def load_config(config_file: str = "config.py") -> Dict[str, str]:
    config_path = Path(config_file)
    if not config_path.exists():
        print(f"ERROR: Configuration file not found: {config_path}")
        return None
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("config", config_path)
        config_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config_module)
        cfg = {
            'use_azure': getattr(config_module, 'USE_AZURE_OPENAI', False),
            'openai_api_key': getattr(config_module, 'OPENAI_API_KEY', None),
            'openai_model': getattr(config_module, 'OPENAI_MODEL', 'gpt-4o-2024-08-06'),
            'azure_endpoint': getattr(config_module, 'AZURE_OPENAI_ENDPOINT', None),
            'azure_api_key': getattr(config_module, 'AZURE_OPENAI_API_KEY', None),
            'azure_deployment': getattr(config_module, 'AZURE_OPENAI_DEPLOYMENT_NAME', None),
        }
        # Validation
        if cfg['use_azure']:
            missing = [k for k in ['azure_endpoint','azure_api_key','azure_deployment'] if not cfg[k]]
            if missing:
                print(f"ERROR: Missing Azure OpenAI config fields: {missing}")
                return None
        else:
            if not cfg['openai_api_key']:
                print("ERROR: Missing OPENAI_API_KEY in config.py")
                return None
        return cfg
    except Exception as e:
        print(f"ERROR: Error loading config: {e}")
        return None


def setup_openai_client(cfg: Dict[str, str]):
    try:
        if cfg['use_azure']:
            client = OpenAI(
                api_key=cfg['azure_api_key'],
                base_url=f"{cfg['azure_endpoint'].rstrip('/')}/openai/deployments/{cfg['azure_deployment']}",
                default_headers={"api-key": cfg['azure_api_key']},
            )
            return client
        else:
            client = OpenAI(api_key=cfg['openai_api_key'])
            return client
    except Exception as e:
        print(f"ERROR: Failed to setup OpenAI client: {e}")
        return None


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
            if len(candidate) > 2:
                return candidate
    return ""


def _extract_carrier_from_filename(file_path: str) -> str:
    import re
    p = Path(file_path)
    stem = p.stem.replace('_', ' ').replace('-', ' ').replace('.', ' ')
    m = re.search(r"\b([A-Z][A-Za-z0-9 &'.\-/]+(?:Insurance|Ins|Corp|Corporation|Company|Co|LLC|Inc))\b", stem, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    tokens = stem.split()
    if tokens:
        stop_words = {"loss", "run", "report", "claims", "claim", "extract", "extracted", "output", "input", "file"}
        name_parts = []
        for t in tokens:
            if t.lower() in stop_words:
                break
            name_parts.append(t)
            if len(name_parts) >= 3:
                break
        if name_parts:
            return ' '.join(name_parts)
    return ""


def _chunk_text(text: str, max_chars: int = DEFAULT_MAX_CHARS, overlap_chars: int = DEFAULT_OVERLAP_CHARS) -> List[str]:
    chunks: List[str] = []
    if not text:
        return chunks
    start = 0
    n = len(text)
    while start < n:
        end = min(start + max_chars, n)
        if end < n:
            nl = text.rfind("\n", start, end)
            if nl != -1 and nl > start + 1000:
                end = nl
        chunks.append(text[start:end])
        if end >= n:
            break
        start = max(0, end - overlap_chars)
    return chunks


def classify_lobs_multi_openai(client, model: str, text: str) -> List[str]:
    prompt = f"""
You are an insurance domain expert. Determine ALL Lines of Business (LoBs) present in the content.
Choose any that apply from exactly these values: AUTO, GENERAL LIABILITY, WC, PROPERTY.
Return STRICT JSON ONLY with no commentary and no markdown. Use double quotes and valid JSON.
Schema: {{"lobs": ["AUTO"|"GENERAL LIABILITY"|"WC"|"PROPERTY", ...]}}
Content:\n{text}
"""
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=200000,
            response_format={"type": "json_object"}
        )
        content = resp.choices[0].message.content
        obj = json.loads(content)
        lobs = obj.get('lobs') or []
        out = []
        for v in lobs:
            s = str(v).strip().upper()
            if s in {"AUTO","GENERAL LIABILITY","WC","PROPERTY"} and s not in out:
                out.append(s)
        if out:
            return out
    except Exception:
        pass
    # Fallback heuristic
    t = text.upper()
    found = []
    if any(k in t for k in [" AUTO ", " AUTOMOBILE", " VEHICLE", " VIN ", " COLLISION", " COMPREHENSIVE", " LICENSE PLATE", " TOW ", " RENTAL", " SUBROGATION"]):
        found.append("AUTO")
    if any(k in t for k in [" GENERAL LIABILITY", " GL ", " PREMISES", " PRODUCTS LIABILITY", " CGL ", " COVERAGE A", " COVERAGE B", " COVERAGE C", " AGGREGATE LIMIT"]):
        found.append("GENERAL LIABILITY")
    if any(k in t for k in [" WORKERS' COMP", " WORKERS COMP", " WC ", " TTD", " TPD", " INDEMNITY", " MEDICAL ONLY", " LOST TIME", " OSHA ", " EMPLOYEE ", " EMPLOYER "]):
        found.append("WC")
    if any(k in t for k in [" PROPERTY ", " DWELLING", " BUILDING", " CONTENTS", " FIRE", " THEFT", " WIND", " HOMEOWNER", " HO-3", " LANDLORD"]):
        found.append("PROPERTY")
    return found or ["AUTO"]


def extract_fields_openai(client, model: str, text: str, lob: str, max_attempts: int = DEFAULT_MAX_ATTEMPTS) -> Dict:
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
    elif lob == 'PROPERTY':
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
        lob = 'GL'
    else:
        schema = {
            "evaluation_date": "string",
            "carrier": "string",
            "claims": [{
                "claim_number": "string",
                "loss_date": "string",
                "Indemnity_paid_loss": "string",
                "Medical_paid_loss": "string",
                "Indemnity_reserve": "string",
                "Medical_reserve": "string",
                "ALAE": "string"
            }]
        }
        lob = 'WC'

    prompt = f"""
Extract structured fields from the content for LoB={lob}.
Return STRICT JSON ONLY matching this schema with no commentary and no markdown fences:
{schema}
Rules: ISO dates if possible; keep amounts/strings as-is; empty string if missing; preserve row order.
IMPORTANT: Extract the carrier/company name from the content. This is critical.

Content:\n{text}
"""
    delay_seconds = 1.0
    for attempt in range(1, max_attempts + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=200000,
                response_format={"type": "json_object"}
            )
            content = resp.choices[0].message.content
            obj = json.loads(content)
            if isinstance(obj, dict) and 'claims' in obj and isinstance(obj['claims'], list):
                obj.setdefault('evaluation_date','')
                obj.setdefault('carrier','')
                return obj
        except Exception as e:
            # Handle rate limiting or transient errors with exponential backoff
            msg = str(e).lower()
            is_rate = ('rate' in msg) or ('too many requests' in msg) or ('overloaded' in msg)
            is_timeout = ('timeout' in msg) or ('timed out' in msg)
            if attempt == max_attempts:
                print(f"WARNING: OpenAI extraction failed after retries: {e}")
                break
            sleep_for = delay_seconds * (2 ** (attempt - 1))
            if is_rate:
                sleep_for = max(sleep_for, 2.0)
            time.sleep(sleep_for)
            continue
    return {"evaluation_date":"","carrier":"","claims": []}


def extract_fields_openai_chunked(client, model: str, text: str, lob: str, max_chars: int = DEFAULT_MAX_CHARS, overlap_chars: int = DEFAULT_OVERLAP_CHARS, per_chunk_sleep: float = DEFAULT_CHUNK_SLEEP) -> Dict:
    chunks = _chunk_text(text, max_chars=max_chars, overlap_chars=overlap_chars)
    if not chunks:
        chunks = [text]
    merged = {"evaluation_date": "", "carrier": "", "claims": []}
    for idx, part in enumerate(chunks):
        result = extract_fields_openai(client, model, part, lob)
        if result.get('evaluation_date') and not merged['evaluation_date']:
            merged['evaluation_date'] = result.get('evaluation_date','')
        if result.get('carrier') and not merged['carrier']:
            merged['carrier'] = result.get('carrier','')
        if isinstance(result.get('claims'), list):
            merged['claims'].extend(result['claims'])
        time.sleep(per_chunk_sleep)
    return merged


def process_text_file(text_file_path: str, client, model: str, max_chars: int, overlap_chars: int, per_chunk_sleep: float) -> List[Dict]:
    results: List[Dict] = []
    try:
        with open(text_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            text_content = f.read()
        print(f"Processing text file: {text_file_path} ({len(text_content)} chars)")
        lobs = classify_lobs_multi_openai(client, model, text_content[:20000])  # classify on prefix for speed
        print(f"Detected LoBs: {lobs}")
        for lob in lobs:
            fields = extract_fields_openai_chunked(
                client, model, text_content, lob,
                max_chars=max_chars, overlap_chars=overlap_chars, per_chunk_sleep=per_chunk_sleep
            )
            carrier = fields.get('carrier') or _extract_carrier_from_text(text_content) or _extract_carrier_from_filename(text_file_path)
            results.append({
                'lob': lob,
                'carrier': carrier,
                'fields': fields,
                'source_file': text_file_path
            })
    except Exception as e:
        import traceback
        print(f"ERROR: Error processing {text_file_path}: {e}")
        print(traceback.format_exc())
    return results


def write_outputs(per_lob: Dict[str, pd.DataFrame], out_dir: Path):
    auto_df = per_lob.get('AUTO')
    gl_df = per_lob.get('GL')
    wc_df = per_lob.get('WC')
    property_df = per_lob.get('PROPERTY')

    has_auto = auto_df is not None and not auto_df.empty
    has_gl = gl_df is not None and not gl_df.empty
    has_wc = wc_df is not None and not wc_df.empty
    has_property = property_df is not None and not property_df.empty

    if has_auto:
        try:
            d = out_dir / 'auto'; d.mkdir(parents=True, exist_ok=True)
            with pd.ExcelWriter(d / 'AUTO_consolidated.xlsx', engine='openpyxl') as w:
                auto_df.to_excel(w, sheet_name='auto_claims', index=False)
        except Exception as e:
            print(f"WARNING: Failed writing AUTO output: {e}")
    if has_property:
        try:
            d = out_dir / 'property'; d.mkdir(parents=True, exist_ok=True)
            with pd.ExcelWriter(d / 'PROPERTY_consolidated.xlsx', engine='openpyxl') as w:
                property_df.to_excel(w, sheet_name='property_claims', index=False)
        except Exception as e:
            print(f"WARNING: Failed writing PROPERTY output: {e}")
    if has_gl:
        try:
            d = out_dir / 'GL'; d.mkdir(parents=True, exist_ok=True)
            with pd.ExcelWriter(d / 'GL_consolidated.xlsx', engine='openpyxl') as w:
                gl_df.to_excel(w, sheet_name='gl_claims', index=False)
        except Exception as e:
            print(f"WARNING: Failed writing GL output: {e}")
    if has_wc:
        try:
            d = out_dir / 'WC'; d.mkdir(parents=True, exist_ok=True)
            with pd.ExcelWriter(d / 'WC_consolidated.xlsx', engine='openpyxl') as w:
                wc_df.to_excel(w, sheet_name='wc_claims', index=False)
        except Exception as e:
            print(f"WARNING: Failed writing WC output: {e}")

    if has_auto or has_property or has_gl or has_wc:
        try:
            with pd.ExcelWriter(out_dir / 'result.xlsx', engine='openpyxl') as w:
                if has_auto:
                    auto_df.to_excel(w, sheet_name='auto_claims', index=False)
                if has_property:
                    property_df.to_excel(w, sheet_name='property_claims', index=False)
                if has_gl:
                    gl_df.to_excel(w, sheet_name='gl_claims', index=False)
                if has_wc:
                    wc_df.to_excel(w, sheet_name='wc_claims', index=False)
        except Exception as e:
            print(f"WARNING: Failed writing combined result.xlsx: {e}")
    else:
        print("INFO: No data found for any LoB. Skipping result.xlsx creation.")


def main():
    p = argparse.ArgumentParser(description="OpenAI-based LoB extractor for text files")
    p.add_argument("input_path", help="Input text file or directory containing text files")
    p.add_argument("--config", default="config.py", help="Path to config.py")
    p.add_argument("--out", dest="out_dir", default="text_llm_results_openai", help="Output directory")
    p.add_argument("--pattern", default="*.txt", help="File pattern for directory processing (default: *.txt)")
    p.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS, help="Max characters per chunk")
    p.add_argument("--overlap", type=int, default=DEFAULT_OVERLAP_CHARS, help="Overlap characters between chunks")
    p.add_argument("--chunk-sleep", type=float, default=DEFAULT_CHUNK_SLEEP, help="Sleep seconds between chunk calls")
    args = p.parse_args()

    cfg = load_config(args.config)
    if not cfg:
        return
    client = setup_openai_client(cfg)
    if not client:
        return

    out_dir = Path(args.out_dir); out_dir.mkdir(parents=True, exist_ok=True)

    input_path = Path(args.input_path)
    if input_path.is_file():
        text_files = [input_path]
    elif input_path.is_dir():
        text_files = list(input_path.glob(args.pattern))
        if not text_files:
            print(f"ERROR: No files found matching pattern '{args.pattern}' in {input_path}")
            return
    else:
        print(f"ERROR: Input path does not exist: {input_path}")
        return

    print(f"Found {len(text_files)} text file(s) to process")

    auto_rows: List[Dict] = []
    property_rows: List[Dict] = []
    gl_rows: List[Dict] = []
    wc_rows: List[Dict] = []

    for text_file in text_files:
        results = process_text_file(
            str(text_file), client, cfg['use_azure'] and cfg['azure_deployment'] or cfg['openai_model'],
            max_chars=args.max_chars, overlap_chars=args.overlap, per_chunk_sleep=args.chunk_sleep
        )
        if not results:
            continue
        for result in results:
            lob = result['lob']
            carrier = result['carrier']
            fields = result['fields']
            source_file = result['source_file']

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
                        'source_file': source_file
                    })
            elif lob == 'PROPERTY':
                for c in fields.get('claims', []):
                    property_rows.append({
                        'evaluation_date': fields.get('evaluation_date',''),
                        'carrier': c.get('carrier','') or carrier or fields.get('carrier',''),
                        'claim_number': c.get('claim_number',''),
                        'loss_date': c.get('loss_date',''),
                        'paid_loss': c.get('paid_loss',''),
                        'reserve': c.get('reserve',''),
                        'alae': c.get('alae',''),
                        'source_file': source_file
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
                        'source_file': source_file
                    })
            elif lob == 'WC':
                for c in fields.get('claims', []):
                    wc_rows.append({
                        'evaluation_date': fields.get('evaluation_date',''),
                        'carrier': c.get('carrier','') or carrier or fields.get('carrier',''),
                        'claim_number': c.get('claim_number',''),
                        'loss_date': c.get('loss_date',''),
                        'Indemnity_paid_loss': c.get('Indemnity_paid_loss',''),
                        'Medical_paid_loss': c.get('Medical_paid_loss',''),
                        'Indemnity_reserve': c.get('Indemnity_reserve',''),
                        'Medical_reserve': c.get('Medical_reserve',''),
                        'ALAE': c.get('ALAE',''),
                        'source_file': source_file
                    })
            else:
                continue

    per_lob = {}
    if auto_rows:
        per_lob['AUTO'] = pd.DataFrame(auto_rows, columns=['evaluation_date','carrier','claim_number','loss_date','paid_loss','reserve','alae','source_file'])
    else:
        per_lob['AUTO'] = pd.DataFrame()
    if property_rows:
        per_lob['PROPERTY'] = pd.DataFrame(property_rows, columns=['evaluation_date','carrier','claim_number','loss_date','paid_loss','reserve','alae','source_file'])
    else:
        per_lob['PROPERTY'] = pd.DataFrame()
    if gl_rows:
        per_lob['GL'] = pd.DataFrame(gl_rows, columns=['evaluation_date','carrier','claim_number','loss_date','bi_paid_loss','pd_paid_loss','bi_reserve','pd_reserve','alae','source_file'])
    else:
        per_lob['GL'] = pd.DataFrame()
    if wc_rows:
        per_lob['WC'] = pd.DataFrame(wc_rows, columns=['evaluation_date','carrier','claim_number','loss_date','Indemnity_paid_loss','Medical_paid_loss','Indemnity_reserve','Medical_reserve','ALAE','source_file'])
    else:
        per_lob['WC'] = pd.DataFrame()

    write_outputs(per_lob, out_dir)
    print(f"\nProcessing Summary:")
    print(f"   AUTO claims: {len(auto_rows)}")
    print(f"   PROPERTY claims: {len(property_rows)}")
    print(f"   GL claims: {len(gl_rows)}")
    print(f"   WC claims: {len(wc_rows)}")
    print(f"   Output directory: {out_dir}")


if __name__ == "__main__":
    main()
