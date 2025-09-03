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


def extract_tables_with_claude(bedrock_client, pdf_text: str, pdf_name: str) -> List[Dict[str, Any]]:
    """Extract tables from PDF text using AWS Bedrock Claude."""
    
    prompt = f"""
    You are an expert at extracting structured data from PDF documents. 
    
    Please analyze the following PDF content and extract ALL tables and structured data you can find.
    For each table or structured section, provide:
    1. A descriptive name for the table/section
    2. The extracted data in a structured format (JSON)
    3. Any relevant metadata (headers, row counts, etc.)
    
    PDF Name: {pdf_name}
    
    Content:
    {pdf_text[:8000]}  # Limit content length for API
    
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
                "description": "Brief description of what this table contains"
            }}
        }}
    ]
    
    If no structured tables are found, extract any organized information in a table-like format.
    """
    
    try:
        print(f"🤖 Sending request to Claude for {pdf_name}...")
        
        response = bedrock_client.invoke_model(
            modelId="anthropic.claude-3-sonnet-20240229-v1:0",
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
        
        print(f"✅ Claude response received for {pdf_name}")
        
        # Try to extract JSON from Claude's response
        try:
            # Look for JSON content in the response
            start_idx = content.find('[')
            end_idx = content.rfind(']') + 1
            if start_idx != -1 and end_idx != -1:
                json_content = content[start_idx:end_idx]
                tables = json.loads(json_content)
                print(f"📊 Extracted {len(tables)} tables from {pdf_name}")
                return tables
            else:
                print(f"⚠️ Could not parse structured response from Claude for {pdf_name}")
                return []
        except json.JSONDecodeError as e:
            print(f"⚠️ Could not parse JSON response from Claude for {pdf_name}: {e}")
            return []
            
    except Exception as e:
        print(f"❌ Error calling AWS Bedrock: {str(e)}")
        return []


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


def process_pdf(pdf_path: str, bedrock_client, output_dir: str = None):
    """Process a single PDF file and extract tables using Claude."""
    pdf_path = Path(pdf_path)
    
    if not pdf_path.exists():
        print(f"❌ PDF file not found: {pdf_path}")
        return None
    
    print(f"\n📄 Processing: {pdf_path.name}")
    print("=" * 50)
    
    try:
        # Extract text from PDF
        pdf_text, used_ocr = extract_text_from_pdf(str(pdf_path), use_ocr_fallback=True)
        
        if used_ocr:
            print(f"📷 OCR used (scanned document)")
        else:
            print(f"📝 Text extraction used")
        
        print(f"📏 Text length: {len(pdf_text)} characters")
        
        # Extract tables using Claude
        tables = extract_tables_with_claude(bedrock_client, pdf_text, pdf_path.name)
        
        if tables:
            # Add file information to tables
            for table in tables:
                table['source_file'] = pdf_path.name
                table['extraction_method'] = 'OCR' if used_ocr else 'Text'
            
            # Save results to JSON
            if output_dir:
                json_path = Path(output_dir) / f"{pdf_path.stem}_claude_results.json"
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(tables, f, indent=2, ensure_ascii=False)
                print(f"💾 JSON results saved to: {json_path}")
                
                # Save to Excel
                excel_path = Path(output_dir) / f"{pdf_path.stem}_claude_results.xlsx"
                save_to_excel(tables, str(excel_path), pdf_path.name)
            
            # Display summary
            print(f"📊 Summary for {pdf_path.name}:")
            for i, table in enumerate(tables):
                table_name = table.get('table_name', f'Table {i+1}')
                headers = table.get('headers', [])
                data = table.get('data', [])
                print(f"  Table {i+1}: {table_name}")
                print(f"    Headers: {headers}")
                print(f"    Rows: {len(data)}")
                print(f"    Columns: {len(headers)}")
            
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
    parser.add_argument("--access-key", required=True, help="AWS Access Key ID")
    parser.add_argument("--secret-key", required=True, help="AWS Secret Access Key")
    parser.add_argument("--session-token", required=True, help="AWS Session Token")
    parser.add_argument("--region", default="us-east-1", help="AWS Region (default: us-east-1)")
    parser.add_argument("--output-dir", default="claude_results", help="Output directory for results (default: claude_results)")
    
    args = parser.parse_args()
    
    # Create output directory if it doesn't exist
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    print(f"📁 Output directory: {output_dir.absolute()}")
    
    # Setup AWS client
    print("🔑 Setting up AWS Bedrock client...")
    bedrock_client = setup_aws_client(
        args.access_key, 
        args.secret_key, 
        args.session_token, 
        args.region
    )
    
    if not bedrock_client:
        print("❌ Failed to setup AWS client. Exiting.")
        return
    
    print("✅ AWS Bedrock client ready!")
    
    # Process PDF(s)
    pdf_path = Path(args.pdf_path)
    
    if pdf_path.is_file() and pdf_path.suffix.lower() == '.pdf':
        # Single PDF file
        process_pdf(str(pdf_path), bedrock_client, args.output_dir)
        
    elif pdf_path.is_dir():
        # Directory of PDFs
        pdf_files = list(pdf_path.glob("*.pdf"))
        if not pdf_files:
            print(f"❌ No PDF files found in directory: {pdf_path}")
            return
        
        print(f"📁 Found {len(pdf_files)} PDF files")
        
        all_results = []
        for pdf_file in pdf_files:
            result = process_pdf(str(pdf_file), bedrock_client, args.output_dir)
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
