#!/usr/bin/env python3
"""
Standalone PDF to Claude extractor using AWS Bedrock.
Extracts text from PDFs and sends to Claude for table extraction.
Exports results to both JSON and Excel formats.
"""

import boto3
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd

from src.claim_extractor.extract_text import extract_text_from_pdf


def setup_aws_client(access_key: str, secret_key: str, session_token: str, region: str):
    """Setup AWS Bedrock client with provided credentials."""
    try:
        session = boto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            aws_session_token=session_token,
            region_name=region
        )
        bedrock = session.client('bedrock-runtime')
        return bedrock
    except Exception as e:
        print(f"❌ Failed to setup AWS client: {str(e)}")
        return None


def extract_text_from_pdf_page_by_page(pdf_path: str, use_ocr_fallback: bool = True, dpi: int = 300):
    """Extract text from PDF page by page to handle large documents better."""
    import pdfplumber
    from pdf2image import convert_from_path
    import pytesseract
    
    all_text = []
    used_ocr = False
    
    try:
        # Try native text extraction first
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            print(f"📄 Total pages in PDF: {total_pages}")
            
            for page_num, page in enumerate(pdf.pages, 1):
                print(f"📖 Processing page {page_num}/{total_pages}...")
                
                # Extract text from current page
                page_text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
                
                if not page_text.strip() and use_ocr_fallback:
                    # If no text, try OCR for this page
                    print(f"📷 Using OCR for page {page_num}...")
                    images = convert_from_path(pdf_path, dpi=dpi, first_page=page_num, last_page=page_num)
                    if images:
                        page_text = pytesseract.image_to_string(images[0], lang="eng")
                        used_ocr = True
                
                if page_text.strip():
                    all_text.append(f"--- PAGE {page_num} ---\n{page_text.strip()}")
                    print(f"✅ Page {page_num}: {len(page_text)} characters")
                else:
                    print(f"⚠️ Page {page_num}: No text extracted")
                    all_text.append(f"--- PAGE {page_num} ---\n[No text content]")
                
                # Add a small delay to prevent overwhelming the system
                import time
                time.sleep(0.1)
        
        return "\n\n".join(all_text), used_ocr
        
    except Exception as e:
        print(f"❌ Error in page-by-page extraction: {str(e)}")
        # Fallback to original method
        return extract_text_from_pdf(pdf_path, use_ocr_fallback, dpi)


def detect_line_of_business(pdf_text: str) -> str:
    """Detect the line of business from PDF content."""
    pdf_text_upper = pdf_text.upper()
    
    # Define business type patterns
    business_patterns = {
        'AUTO': [
            'AUTO', 'AUTOMOBILE', 'VEHICLE', 'CAR', 'TRUCK', 'MOTOR',
            'AUTO LIABILITY', 'AUTO PHYSICAL DAMAGE', 'PERSONAL AUTO',
            'COMMERCIAL AUTO', 'GARAGE LIABILITY', 'MOTOR CARRIER'
        ],
        'GENERAL LIABILITY': [
            'GENERAL LIABILITY', 'GL', 'COMMERCIAL GENERAL LIABILITY',
            'CGL', 'PROPERTY', 'LIABILITY', 'BUSINESS LIABILITY',
            'PROFESSIONAL LIABILITY', 'PRODUCTS LIABILITY'
        ],
        'WC': [
            'WORKERS COMPENSATION', 'WORKER COMPENSATION', 'WC',
            'WORKERS COMP', 'EMPLOYER LIABILITY', 'WORK COMP',
            'WORKERS COMPENSATION AND EMPLOYERS LIABILITY'
        ]
    }
    
    # Count matches for each business type
    business_scores = {}
    for business_type, patterns in business_patterns.items():
        score = 0
        for pattern in patterns:
            if pattern in pdf_text_upper:
                score += pdf_text_upper.count(pattern)
        business_scores[business_type] = score
    
    # Find the business type with highest score
    if business_scores:
        detected_business = max(business_scores, key=business_scores.get)
        if business_scores[detected_business] > 0:
            print(f"🏢 Detected Line of Business: {detected_business} (Score: {business_scores[detected_business]})")
            return detected_business
    
    print("⚠️ Could not detect specific line of business")
    return "UNKNOWN"


def load_aws_config_from_py(config_file: str = "config.py") -> Dict[str, str]:
    """Load AWS credentials and model configuration from Python config file."""
    config_path = Path(config_file)
    
    if not config_path.exists():
        print(f"❌ Configuration file not found: {config_path}")
        print("Please create config.py with your AWS credentials and model:")
        print("""
# AWS Configuration
AWS_ACCESS_KEY = "YOUR_ACCESS_KEY_ID"
AWS_SECRET_KEY = "YOUR_SECRET_ACCESS_KEY"
AWS_SESSION_TOKEN = "YOUR_SESSION_TOKEN"
AWS_REGION = "us-east-1"
MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"
        """)
        return None
    
    try:
        # Import the config file as a module
        import importlib.util
        spec = importlib.util.spec_from_file_location("config", config_path)
        config_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config_module)
        
        # Extract configuration values
        config = {
            'access_key': getattr(config_module, 'AWS_ACCESS_KEY', None),
            'secret_key': getattr(config_module, 'AWS_SECRET_KEY', None),
            'session_token': getattr(config_module, 'AWS_SESSION_TOKEN', None),
            'region': getattr(config_module, 'AWS_REGION', None),
            'model_id': getattr(config_module, 'MODEL_ID', None),
            'max_chunk_size': getattr(config_module, 'MAX_CHUNK_SIZE', 15000),
            'api_delay': getattr(config_module, 'API_DELAY', 1)
        }
        
        # Validate required fields
        required_fields = ['access_key', 'secret_key', 'session_token', 'region', 'model_id']
        missing_fields = [field for field in required_fields if not config[field]]
        
        if missing_fields:
            print(f"❌ Missing required fields in config: {missing_fields}")
            return None
        
        # Validate model ID format
        valid_model_prefixes = [
            "anthropic.claude-3-sonnet",
            "anthropic.claude-3-haiku", 
            "anthropic.claude-3-opus",
            "anthropic.claude-v2",
            "anthropic.claude-instant"
        ]
        
        model_is_valid = any(config['model_id'].startswith(prefix) for prefix in valid_model_prefixes)
        if not model_is_valid:
            print(f"⚠️ Warning: Model ID '{config['model_id']}' may not be valid")
            print("Valid model prefixes:", valid_model_prefixes)
        
        print(f"✅ Configuration loaded from: {config_path}")
        print(f"🤖 Model configured: {config['model_id']}")
        print(f"🌍 AWS Region: {config['region']}")
        
        return config
        
    except Exception as e:
        print(f"❌ Error reading config file: {e}")
        return None


def extract_tables_with_claude_page_by_page(bedrock_client, pdf_text: str, pdf_name: str, model_id: str, max_chunk_size: int = 15000, api_delay: int = 1) -> List[Dict[str, Any]]:
    """Extract tables from PDF text using AWS Bedrock Claude with better handling of large content."""
    
    # Split text into manageable chunks if it's very long
    text_chunks = []
    
    if len(pdf_text) > max_chunk_size:
        print(f"📏 Text is very long ({len(pdf_text)} chars), splitting into chunks...")
        # Split by page boundaries
        pages = pdf_text.split("--- PAGE")
        current_chunk = ""
        
        for page in pages:
            if not page.strip():
                continue
            if len(current_chunk) + len(page) > max_chunk_size and current_chunk:
                text_chunks.append(current_chunk.strip())
                current_chunk = page
            else:
                current_chunk += "\n--- PAGE" + page
        
        if current_chunk.strip():
            text_chunks.append(current_chunk.strip())
        
        print(f"📦 Split into {len(text_chunks)} chunks")
    else:
        text_chunks = [pdf_text]
    
    all_tables = []
    
    for chunk_idx, chunk in enumerate(text_chunks, 1):
        print(f"🤖 Processing chunk {chunk_idx}/{len(text_chunks)} ({len(chunk)} chars)...")
        
        prompt = f"""
        You are an expert at extracting structured data from insurance and claims documents. 
        
        Please analyze the following PDF content chunk and extract ALL tables and structured data you can find.
        This is chunk {chunk_idx} of {len(text_chunks)} from the document.
        
        IMPORTANT: Also identify the Line of Business from these options:
        1. AUTO - Automobile insurance, vehicle claims, motor vehicle liability
        2. GENERAL LIABILITY - Commercial general liability, property, business liability
        3. WC - Workers Compensation, employer liability, work comp claims
        
        For each table or structured section, provide:
        1. A descriptive name for the table/section
        2. The extracted data in a structured format (JSON)
        3. Any relevant metadata (headers, row counts, etc.)
        4. Line of Business classification
        
        PDF Name: {pdf_name}
        Chunk: {chunk_idx}/{len(text_chunks)}
        
        Content:
        {chunk}
        
        Please respond with a JSON array where each element represents a table/section:
        [
            {{
                "table_name": "Description of the table",
                "headers": ["Column1", "Column2", "Column3"],
                "data": [
                    ["Row1Col1", "Row1Col2", "Row1Col3"],
                    ["Row2Col1", "Row2Col2", "Row2Col3"]
                ],
                "metadata": {{
                    "row_count": 2,
                    "column_count": 3,
                    "description": "Brief description of what this table contains",
                    "chunk_source": {chunk_idx},
                    "line_of_business": "AUTO|GENERAL LIABILITY|WC"
                }}
            }}
        ]
        
        If no structured tables are found, extract any organized information in a table-like format.
        Focus on finding tables, lists, and structured data in this chunk.
        Be sure to classify the Line of Business based on the content.
        """
        
        try:
            response = bedrock_client.invoke_model(
                modelId=model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4000,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                })
            )
            
            response_body = json.loads(response['body'].read())
            content = response_body['content'][0]['text']
            
            print(f"✅ Claude response received for chunk {chunk_idx}")
            
            # Try to extract JSON from Claude's response
            try:
                start_idx = content.find('[')
                end_idx = content.rfind(']') + 1
                if start_idx != -1 and end_idx != -1:
                    json_content = content[start_idx:end_idx]
                    chunk_tables = json.loads(json_content)
                    print(f"📊 Extracted {len(chunk_tables)} tables from chunk {chunk_idx}")
                    all_tables.extend(chunk_tables)
                else:
                    print(f"⚠️ Could not parse structured response from Claude for chunk {chunk_idx}")
            except json.JSONDecodeError as e:
                print(f"⚠️ Could not parse JSON response from Claude for chunk {chunk_idx}: {e}")
                
        except Exception as e:
            print(f"❌ Error calling AWS Bedrock for chunk {chunk_idx}: {str(e)}")
            continue
        
        # Add delay between chunks to prevent rate limiting
        import time
        time.sleep(api_delay)
    
    print(f"🎯 Total tables extracted across all chunks: {len(all_tables)}")
    return all_tables


def save_to_excel(tables_data: List[Dict[str, Any]], output_path: str, pdf_name: str = None):
    """Save extracted tables to Excel file with different sheets."""
    try:
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Create a summary sheet
            summary_data = []
            for i, table in enumerate(tables_data):
                summary_data.append({
                    'Sheet_Name': f"Table_{i+1}",
                    'Table_Name': table.get('table_name', f'Table {i+1}'),
                    'Source_File': table.get('source_file', pdf_name or 'Unknown'),
                    'Extraction_Method': table.get('extraction_method', 'Unknown'),
                    'Row_Count': len(table.get('data', [])),
                    'Column_Count': len(table.get('headers', [])),
                    'Description': table.get('metadata', {}).get('description', 'N/A')
                })
            
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Create individual table sheets
            for i, table in enumerate(tables_data):
                if not table.get('data') or not table.get('headers'):
                    continue
                    
                # Create DataFrame
                df = pd.DataFrame(table['data'], columns=table['headers'])
                
                # Clean sheet name (Excel has restrictions)
                sheet_name = f"Table_{i+1}_{table.get('table_name', 'Unknown')[:20]}"
                sheet_name = "".join(c for c in sheet_name if c.isalnum() or c in (' ', '_', '-'))[:31]
                
                # Write to Excel
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                
                # Add metadata sheet for each table
                if table.get('metadata'):
                    metadata_df = pd.DataFrame([table['metadata']])
                    metadata_sheet_name = f"Meta_{i+1}"[:31]
                    metadata_df.to_excel(writer, sheet_name=metadata_sheet_name, index=False)
        
        print(f"💾 Excel file saved: {output_path}")
        return True
        
    except Exception as e:
        print(f"❌ Error saving Excel file: {str(e)}")
        return False


def _lob_folder_name(line_of_business: str) -> str:
    lob = (line_of_business or "UNKNOWN").upper().strip()
    if lob == "AUTO":
        return "auto"
    if lob in ("GENERAL LIABILITY", "GL"):
        return "GL"
    if lob == "WC":
        return "WC"
    return "UNKNOWN"


def classify_line_of_business_via_bedrock(bedrock_client, pdf_text: str, model_id: str) -> str:
    """Classify line of business (AUTO, GENERAL LIABILITY, WC) using Claude via Bedrock.

    Returns one of: 'AUTO', 'GENERAL LIABILITY', 'WC', or 'UNKNOWN' on failure.
    """
    try:
        prompt = f"""
You are an insurance domain expert. Read the following document text and classify the dominant line of business.
Choose exactly one from this set:
- AUTO
- GENERAL LIABILITY
- WC

Return ONLY strict JSON: {{"line_of_business": "AUTO|GENERAL LIABILITY|WC"}} with no extra text.

Document text:
{pdf_text}
"""
        response = bedrock_client.invoke_model(
            modelId=model_id,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 100,
                "temperature": 0.0,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
            }),
        )
        response_body = json.loads(response["body"].read())
        content = response_body["content"][0]["text"]
        # Extract JSON only
        start_idx = content.find("{")
        end_idx = content.rfind("}") + 1
        if start_idx != -1 and end_idx > start_idx:
            try:
                obj = json.loads(content[start_idx:end_idx])
                lob = (obj.get("line_of_business") or "").strip().upper()
                if lob in {"AUTO", "GENERAL LIABILITY", "WC"}:
                    return lob
            except Exception:
                pass
        print("⚠️ Claude LOB classification not parseable; falling back to heuristic.")
        return "UNKNOWN"
    except Exception as exc:
        print(f"❌ LOB classification via Bedrock failed: {exc}")
        return "UNKNOWN"


def process_pdf(pdf_path: str, bedrock_client, output_dir: str = None, model_id: str = None, max_chunk_size: int = 15000, api_delay: int = 1):
    """Process a single PDF file and extract tables using Claude."""
    pdf_path = Path(pdf_path)
    
    if not pdf_path.exists():
        print(f"❌ PDF file not found: {pdf_path}")
        return None
    
    print(f"\n📄 Processing: {pdf_path.name}")
    print("=" * 50)
    
    try:
        # Extract complete text from PDF page by page (no truncation)
        print("📖 Extracting complete text from PDF page by page...")
        pdf_text, used_ocr = extract_text_from_pdf_page_by_page(str(pdf_path), use_ocr_fallback=True)
        
        if used_ocr:
            print(f"📷 OCR used for some pages (scanned content)")
        else:
            print(f"📝 Text extraction used for all pages")
        
        print(f"📏 Complete text length: {len(pdf_text)} characters")
        print(f"📄 Text preview (first 200 chars): {pdf_text[:200]}...")
        
        if not pdf_text.strip():
            print("⚠️ No text extracted from PDF. File may be image-only or corrupted.")
            return []
        
        # Detect line of business via API first; fallback to heuristic
        line_of_business = classify_line_of_business_via_bedrock(bedrock_client, pdf_text, model_id)
        if line_of_business == "UNKNOWN":
            line_of_business = detect_line_of_business(pdf_text)
        
        # Extract tables using Claude with complete text (page by page approach)
        print("🤖 Sending complete text to Claude for table extraction...")
        tables = extract_tables_with_claude_page_by_page(bedrock_client, pdf_text, pdf_path.name, model_id, max_chunk_size, api_delay)
        
        if tables:
            # Add file information to tables
            for table in tables:
                table['source_file'] = pdf_path.name
                table['extraction_method'] = 'OCR' if used_ocr else 'Text'
                table['total_text_length'] = len(pdf_text)
                table['line_of_business'] = line_of_business
                
                # Ensure metadata has line of business
                if 'metadata' not in table:
                    table['metadata'] = {}
                table['metadata']['line_of_business'] = line_of_business
            
            # Create filename with line of business
            safe_business_name = line_of_business.replace(' ', '_').replace('&', 'AND')
            base_filename = f"{pdf_path.stem}_{safe_business_name}"
            
            # Determine subfolder by LOB and ensure it exists
            lob_folder = _lob_folder_name(line_of_business)
            target_dir = Path(output_dir) / lob_folder if output_dir else Path.cwd() / lob_folder
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Save results to JSON
            if output_dir:
                json_path = target_dir / f"{base_filename}_claude_results.json"
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(tables, f, indent=2, ensure_ascii=False)
                print(f"💾 JSON results saved to: {json_path}")
                
                # Save to Excel
                excel_path = target_dir / f"{base_filename}_claude_results.xlsx"
                save_to_excel(tables, str(excel_path), pdf_path.name)
            
            # Display summary
            print(f"📊 Summary for {pdf_path.name}:")
            print(f"🏢 Line of Business: {line_of_business}")
            for i, table in enumerate(tables):
                table_name = table.get('table_name', f'Table {i+1}')
                headers = table.get('headers', [])
                data = table.get('data', [])
                chunk_source = table.get('metadata', {}).get('chunk_source', 'Unknown')
                print(f"  Table {i+1}: {table_name}")
                print(f"    Headers: {headers}")
                print(f"    Rows: {len(data)}")
                print(f"    Columns: {len(headers)}")
                print(f"    Source: Chunk {chunk_source}")
            
            return tables
        else:
            print(f"⚠️ No tables found in {pdf_path.name}")
            return []
            
    except Exception as e:
        print(f"❌ Error processing {pdf_path.name}: {str(e)}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Extract tables from PDFs using Claude via AWS Bedrock")
    parser.add_argument("pdf_path", help="Path to PDF file or directory")
    parser.add_argument("--config", default="config.py", help="Path to Python configuration file (default: config.py)")
    parser.add_argument("--output-dir", default="claude_results", help="Output directory for results (default: claude_results)")
    
    args = parser.parse_args()
    
    # Load AWS configuration
    print("🔑 Loading AWS configuration...")
    aws_config = load_aws_config_from_py(args.config)
    
    if not aws_config:
        print("❌ Failed to load AWS configuration. Exiting.")
        return
    
    # Create output directory if it doesn't exist
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    print(f"📁 Output directory: {output_dir.absolute()}")
    
    # Setup AWS client
    print("🔑 Setting up AWS Bedrock client...")
    bedrock_client = setup_aws_client(
        aws_config['access_key'], 
        aws_config['secret_key'], 
        aws_config['session_token'], 
        aws_config['region']
    )
    
    if not bedrock_client:
        print("❌ Failed to setup AWS client. Exiting.")
        return
    
    print("✅ AWS Bedrock client ready!")
    
    # Process PDF(s)
    pdf_path = Path(args.pdf_path)
    
    if pdf_path.is_file() and pdf_path.suffix.lower() == '.pdf':
        # Single PDF file
        process_pdf(str(pdf_path), bedrock_client, args.output_dir, aws_config['model_id'], 
                   aws_config['max_chunk_size'], aws_config['api_delay'])
        
    elif pdf_path.is_dir():
        # Directory of PDFs
        pdf_files = list(pdf_path.glob("*.pdf"))
        if not pdf_files:
            print(f"❌ No PDF files found in directory: {pdf_path}")
            return
        
        print(f"📁 Found {len(pdf_files)} PDF files")
        
        all_results = []
        for pdf_file in pdf_files:
            result = process_pdf(str(pdf_file), bedrock_client, args.output_dir, aws_config['model_id'],
                               aws_config['max_chunk_size'], aws_config['api_delay'])
            if result:
                all_results.extend(result)
        
        # Save combined results
        if all_results:
            # Combined JSON
            combined_json_path = output_dir / "all_claude_results.json"
            with open(combined_json_path, 'w', encoding='utf-8') as f:
                json.dump(all_results, f, indent=2, ensure_ascii=False)
            print(f"\n💾 Combined JSON results saved to: {combined_json_path}")
            
            # Combined Excel with all tables
            combined_excel_path = output_dir / "all_claude_results.xlsx"
            save_to_excel(all_results, str(combined_excel_path))
            
            print(f"📊 Total tables extracted: {len(all_results)}")
            print(f"📁 All results saved to: {output_dir.absolute()}")
            
    else:
        print(f"❌ Invalid path: {pdf_path}")
        print("Please provide a valid PDF file or directory containing PDFs")


if __name__ == "__main__":
    main()
