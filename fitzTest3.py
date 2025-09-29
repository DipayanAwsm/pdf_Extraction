#!/usr/bin/env python3
"""
PDF to Text Converter using PyMuPDF (fitz)
Converts PDF files to text format for further processing
"""

import fitz  # PyMuPDF - PDF processing library
import sys
from pathlib import Path
import argparse
import time

# Try enhanced extractor built on top of PyMuPDF
try:
    import pymupdf4llm  # optional improved text/markdown extractor
    _HAS_PU4LLM = True
except Exception:
    pymupdf4llm = None
    _HAS_PU4LLM = False


def pdf_to_text(pdf_path: str, output_dir: str = "./tmp") -> str:
    """
    Convert PDF to text using PyMuPDF (fitz). If available, use pymupdf4llm for
    higher-quality extraction; otherwise fall back to per-page get_text().
    
    Args:
        pdf_path: Path to input PDF file
        output_dir: Directory to save text file
        
    Returns:
        Path to generated text file
    """
    try:
        # Create output directory if it doesn't exist
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Open PDF document
        doc = fitz.open(pdf_path)
        text_content = ''
        
        print(f"Processing PDF: {pdf_path}")
        print(f"Total pages: {len(doc)}")
        
        # Prefer pymupdf4llm if available (handles layout, images, etc.)
        if _HAS_PU4LLM:
            try:
                # Can accept a document or a file path; use document to avoid re-open
                text_content = pymupdf4llm.to_markdown(doc)
                if not isinstance(text_content, str) or not text_content.strip():
                    # Fallback to plain text if markdown came back empty
                    raise ValueError("Empty markdown from pymupdf4llm")
                print("Used pymupdf4llm for extraction")
            except Exception as _e:
                print("pymupdf4llm failed, falling back to PyMuPDF get_text()")
                text_content = ''
        
        # Fallback: standard per-page text extraction
        if not text_content:
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                page_text = page.get_text()
                text_content += f"--- PAGE {page_num + 1} ---\n"
                text_content += page_text
                text_content += "\n\n"
                print(f"Processed page {page_num + 1}")
        
        doc.close()
        
        # Generate output filename
        pdf_name = Path(pdf_path).stem
        text_file_path = output_path / f"{pdf_name}_extracted.txt"
        
        # Save text file with retry mechanism for Windows file locking
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with open(text_file_path, 'w', encoding='utf-8') as f:
                    f.write(text_content)
                break
            except PermissionError as e:
                if attempt < max_retries - 1:
                    print(f"File locked, retrying in 2 seconds... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(2)
                else:
                    raise e
        
        print(f"Text extracted successfully!")
        print(f"Output file: {text_file_path}")
        print(f"Total characters: {len(text_content)}")
        
        return str(text_file_path)
        
    except Exception as e:
        print(f"ERROR: Error converting PDF: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Convert PDF to text using PyMuPDF / pymupdf4llm")
    parser.add_argument("pdf_path", help="Path to input PDF file")
    parser.add_argument("--output", "-o", default="./tmp", help="Output directory for text file")
    
    args = parser.parse_args()
    
    if not Path(args.pdf_path).exists():
        print(f"ERROR: PDF file not found: {args.pdf_path}")
        sys.exit(1)
    
    result = pdf_to_text(args.pdf_path, args.output)
    
    if result:
        print(f"SUCCESS:{result}")
        sys.exit(0)
    else:
        print("FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()