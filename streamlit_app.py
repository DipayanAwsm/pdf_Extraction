import streamlit as st
import boto3
import json
import pandas as pd
from pathlib import Path
import tempfile
import os
from typing import List, Dict, Any
import base64

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
        st.error(f"Failed to setup AWS client: {str(e)}")
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
        
        # Try to extract JSON from Claude's response
        try:
            # Look for JSON content in the response
            start_idx = content.find('[')
            end_idx = content.rfind(']') + 1
            if start_idx != -1 and end_idx != -1:
                json_content = content[start_idx:end_idx]
                tables = json.loads(json_content)
                return tables
            else:
                st.warning(f"Could not parse structured response from Claude for {pdf_name}")
                return []
        except json.JSONDecodeError:
            st.warning(f"Could not parse JSON response from Claude for {pdf_name}")
            return []
            
    except Exception as e:
        st.error(f"Error calling AWS Bedrock: {str(e)}")
        return []


def save_to_excel(tables_data: List[Dict[str, Any]], output_path: str):
    """Save extracted tables to Excel file with different sheets."""
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
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
    
    return output_path


def main():
    st.set_page_config(
        page_title="PDF Table Extractor with AWS Bedrock",
        page_icon="📊",
        layout="wide"
    )
    
    st.title("📊 PDF Table Extractor with AWS Bedrock Claude")
    st.markdown("Extract tables from PDFs using AI and export to Excel")
    
    # Sidebar for AWS credentials
    with st.sidebar:
        st.header("🔑 AWS Credentials")
        access_key = st.text_input("AWS Access Key ID", type="password")
        secret_key = st.text_input("AWS Secret Access Key", type="password")
        session_token = st.text_input("AWS Session Token", type="password")
        region = st.selectbox("AWS Region", ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"])
        
        if st.button("🔗 Test AWS Connection"):
            if access_key and secret_key and session_token:
                bedrock = setup_aws_client(access_key, secret_key, session_token, region)
                if bedrock:
                    st.success("✅ AWS connection successful!")
                else:
                    st.error("❌ AWS connection failed!")
            else:
                st.error("Please fill in all AWS credentials")
    
    # Main content
    if not all([access_key, secret_key, session_token, region]):
        st.warning("⚠️ Please configure AWS credentials in the sidebar to continue")
        return
    
    # File upload
    st.header("📁 Upload PDF Files")
    uploaded_files = st.file_uploader(
        "Choose PDF files", 
        type=['pdf'], 
        accept_multiple_files=True,
        help="Upload one or more PDF files. Both scanned and text-based PDFs are supported."
    )
    
    if uploaded_files:
        st.success(f"📁 {len(uploaded_files)} PDF file(s) uploaded")
        
        # Process files
        if st.button("🚀 Extract Tables"):
            bedrock_client = setup_aws_client(access_key, secret_key, session_token, region)
            if not bedrock_client:
                st.error("Failed to setup AWS client")
                return
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            all_tables = []
            processed_files = []
            
            for idx, uploaded_file in enumerate(uploaded_files):
                status_text.text(f"Processing {uploaded_file.name}...")
                
                # Save uploaded file temporarily
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_path = tmp_file.name
                
                try:
                    # Extract text from PDF
                    pdf_text, used_ocr = extract_text_from_pdf(tmp_path, use_ocr_fallback=True)
                    
                    if used_ocr:
                        st.info(f"📷 OCR used for {uploaded_file.name} (scanned document)")
                    else:
                        st.info(f"📝 Text extraction used for {uploaded_file.name}")
                    
                    # Extract tables using Claude
                    tables = extract_tables_with_claude(bedrock_client, pdf_text, uploaded_file.name)
                    
                    if tables:
                        # Add file information to tables
                        for table in tables:
                            table['source_file'] = uploaded_file.name
                            table['extraction_method'] = 'OCR' if used_ocr else 'Text'
                        
                        all_tables.extend(tables)
                        processed_files.append({
                            'filename': uploaded_file.name,
                            'tables_found': len(tables),
                            'method': 'OCR' if used_ocr else 'Text'
                        })
                        
                        st.success(f"✅ {uploaded_file.name}: {len(tables)} tables extracted")
                    else:
                        st.warning(f"⚠️ {uploaded_file.name}: No tables found")
                    
                except Exception as e:
                    st.error(f"❌ Error processing {uploaded_file.name}: {str(e)}")
                
                finally:
                    # Clean up temp file
                    os.unlink(tmp_path)
                
                progress_bar.progress((idx + 1) / len(uploaded_files))
            
            status_text.text("Processing complete!")
            
            # Display results
            if all_tables:
                st.header("📊 Extracted Tables")
                
                # Summary
                st.subheader("📈 Summary")
                summary_df = pd.DataFrame(processed_files)
                st.dataframe(summary_df)
                
                # Display tables
                for i, table in enumerate(all_tables):
                    with st.expander(f"📋 {table.get('table_name', f'Table {i+1}')} - {table.get('source_file', 'Unknown')}"):
                        if table.get('data') and table.get('headers'):
                            df = pd.DataFrame(table['data'], columns=table['headers'])
                            st.dataframe(df)
                            
                            # Metadata
                            if table.get('metadata'):
                                st.json(table['metadata'])
                        else:
                            st.warning("No structured data found in this table")
                
                # Export to Excel
                st.header("💾 Export Results")
                if st.button("📥 Download Excel File"):
                    # Create Excel file
                    output_path = "extracted_tables.xlsx"
                    save_to_excel(all_tables, output_path)
                    
                    # Read file for download
                    with open(output_path, "rb") as f:
                        excel_data = f.read()
                    
                    # Create download button
                    b64 = base64.b64encode(excel_data).decode()
                    href = f'<a href="data:application/octet-stream;base64,{b64}" download="extracted_tables.xlsx">📥 Download Excel File</a>'
                    st.markdown(href, unsafe_allow_html=True)
                    
                    # Clean up
                    os.unlink(output_path)
            else:
                st.warning("No tables were extracted from the uploaded PDFs")


if __name__ == "__main__":
    main()
