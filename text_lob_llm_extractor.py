#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import boto3


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
You are an insurance domain expert. Determine the Line of Business (LoB) present in the content.
You MUST choose exactly one of these values: AUTO, GENERAL LIABILITY, WC.

Decision rules and strong signals:
- AUTO: mentions like Auto, Automobile, vehicle, VIN, Bodily Injury/Property Damage split for auto claims, collision, comprehensive, adjuster notes about drivers, policy for auto, traffic accident, liability/PD/BI typical for auto, claimant driver/passenger, license plate, total loss, rental car, tow, subrogation with other driver.
- GENERAL LIABILITY: mentions like General Liability, GL, premises liability, slip and fall, products liability, CGL, occurrence/aggregate limits typical to GL, third-party bodily injury/property damage at premises, insured as a business entity, coverage parts: Coverage A/B/C.
- WC: mentions like Workers' Compensation, WC, work comp, employee injury, TTD/TPD, indemnity, medical only, lost time, OSHA, employer, adjuster notes for claimant as employee, wage statements.

Return STRICT JSON ONLY with no commentary: {"lob": "AUTO" | "GENERAL LIABILITY" | "WC"}
If uncertain, pick the most probable, but NEVER return empty.

Content:\n{text}
"""
    try:
        resp = bedrock_client.invoke_model(
            modelId=model_id,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 300,
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


def classify_lobs_multi(bedrock_client, model_id: str, text: str) -> List[str]:
    prompt = f"""
You are an insurance domain expert. Determine ALL Lines of Business (LoBs) present in the content.
Choose any that apply from exactly these values: AUTO, GENERAL LIABILITY, WC.

Decision rules and strong signals:
- AUTO: Auto/Automobile/vehicle, VIN, collision/comprehensive, driver/passenger, license plate, rental, tow, subrogation with other driver, BI/PD typical to auto.
- GENERAL LIABILITY: General Liability/GL, premises/products liability, CGL, Coverage A/B/C, occurrence/aggregate limits, third-party injury/damage at premises.
- WC: Workers' Compensation/WC, employee injury, TTD/TPD, indemnity, medical only, lost time, OSHA, wage statements, employer/employee terminology.

Return STRICT JSON ONLY with no commentary: {"lobs": ["AUTO" | "GENERAL LIABILITY" | "WC", ...]}
If uncertain, include the most probable, but NEVER return an empty list.

Content:\n{text}
"""
    try:
        resp = bedrock_client.invoke_model(
            modelId=model_id,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 400,
                "temperature": 0.0,
                "messages": [{"role": "user", "content": prompt}],
            })
        )
        body = json.loads(resp['body'].read())
        content = body['content'][0]['text']
        start = content.find('{'); end = content.rfind('}') + 1
        if start != -1 and end > start:
            obj = json.loads(content[start:end])
            lobs = obj.get('lobs') or []
            if isinstance(lobs, list):
                cleaned = []
                for v in lobs:
                    s = str(v).strip().upper()
                    if s in {"AUTO","GENERAL LIABILITY","WC"} and s not in cleaned:
                        cleaned.append(s)
                if cleaned:
                    return cleaned
    except Exception as e:
        print(f"⚠️ Multi-LOB classification failed: {e}")
    # Fallback to single classifier
    single = classify_lob(bedrock_client, model_id, text)
    return [single] if single else ["AUTO"]


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


def process_text_file(text_file_path: str, bedrock_client, model_id: str) -> List[Dict]:
    """Process a single text file and return a list of extracted results per detected LoB"""
    results: List[Dict] = []
    try:
        with open(text_file_path, 'r', encoding='utf-8') as f:
            text_content = f.read()
        
        print(f"📄 Processing text file: {text_file_path} ({len(text_content)} chars)")
        
        # Classify all LoBs present
        lobs = classify_lobs_multi(bedrock_client, model_id, text_content)
        print(f"🔎 Detected LoBs: {lobs}")
        
        for lob in lobs:
            # Extract fields using LLM for this LoB only
            fields = extract_fields_llm(bedrock_client, model_id, text_content, lob)
            
            # Ensure carrier is extracted - try multiple sources
            carrier = fields.get('carrier', '')
            if not carrier:
                carrier = _extract_carrier_from_text(text_content)
            
            print(f"📊 File '{text_file_path}': LoB={lob}, Carrier='{carrier}'")
            
            results.append({
                'lob': lob,
                'carrier': carrier,
                'fields': fields,
                'source_file': text_file_path
            })
        
    except Exception as e:
        print(f"❌ Error processing {text_file_path}: {e}")
    return results


def main():
    p = argparse.ArgumentParser(description="LLM-based LoB extractor for text files (extracted using fitz)")
    p.add_argument("input_path", help="Input text file or directory containing text files")
    p.add_argument("--config", default="config.py", help="Path to config.py")
    p.add_argument("--out", dest="out_dir", default="text_llm_results", help="Output directory")
    p.add_argument("--pattern", default="*.txt", help="File pattern for directory processing (default: *.txt)")
    args = p.parse_args()

    cfg = load_aws_config_from_py(args.config)
    if not cfg:
        return
    bedrock = setup_bedrock_client(cfg)
    if not bedrock:
        return

    out_dir = Path(args.out_dir); out_dir.mkdir(parents=True, exist_ok=True)

    # Determine input files
    input_path = Path(args.input_path)
    if input_path.is_file():
        text_files = [input_path]
    elif input_path.is_dir():
        text_files = list(input_path.glob(args.pattern))
        if not text_files:
            print(f"❌ No files found matching pattern '{args.pattern}' in {input_path}")
            return
    else:
        print(f"❌ Input path does not exist: {input_path}")
        return

    print(f"📁 Found {len(text_files)} text file(s) to process")

    auto_rows: List[Dict] = []
    gl_rows: List[Dict] = []
    wc_rows: List[Dict] = []

    # Process each text file
    for text_file in text_files:
        results = process_text_file(str(text_file), bedrock, cfg['model_id'])
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
                        'bi_paid_loss': c.get('bi_paid_loss',''),
                        'pd_paid_loss': c.get('pd_paid_loss',''),
                        'bi_reserve': c.get('bi_reserve',''),
                        'pd_reserve': c.get('pd_reserve',''),
                        'alae': c.get('alae',''),
                        'source_file': source_file
                    })
            else:
                # Unknown LOB from model, skip
                continue

    # Create DataFrames
    per_lob = {}
    if auto_rows:
        per_lob['AUTO'] = pd.DataFrame(auto_rows, columns=['evaluation_date','carrier','claim_number','loss_date','paid_loss','reserve','alae','source_file'])
    else:
        per_lob['AUTO'] = pd.DataFrame()
    if gl_rows:
        per_lob['GL'] = pd.DataFrame(gl_rows, columns=['evaluation_date','carrier','claim_number','loss_date','bi_paid_loss','pd_paid_loss','bi_reserve','pd_reserve','alae','source_file'])
    else:
        per_lob['GL'] = pd.DataFrame()
    if wc_rows:
        per_lob['WC'] = pd.DataFrame(wc_rows, columns=['evaluation_date','carrier','claim_number','loss_date','bi_paid_loss','pd_paid_loss','bi_reserve','pd_reserve','alae','source_file'])
    else:
        per_lob['WC'] = pd.DataFrame()

    # Write outputs
    write_outputs(per_lob, out_dir)
    
    # Print summary
    print(f"\n📊 Processing Summary:")
    print(f"   AUTO claims: {len(auto_rows)}")
    print(f"   GL claims: {len(gl_rows)}")
    print(f"   WC claims: {len(wc_rows)}")
    print(f"   Output directory: {out_dir}")


if __name__ == "__main__":
    main()
