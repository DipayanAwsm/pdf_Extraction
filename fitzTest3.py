#!/usr/bin/env python3
"""
PDF to Text Converter using PyMuPDF (fitz)
Converts PDF files to text format for further processing
"""

import fitz  # PyMuPDF - PDF processing library
import sys
from pathlib import Path
import argparse


def pdf_to_text(pdf_path: str, output_dir: str = "./tmp") -> str:
    """
    Convert PDF to text using PyMuPDF (fitz)
    
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
        
        print(f"📄 Processing PDF: {pdf_path}")
        print(f"📊 Total pages: {len(doc)}")
        
        # Extract text from all pages
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_text = page.get_text()
            text_content += f"--- PAGE {page_num + 1} ---\n"
            text_content += page_text
            text_content += "\n\n"
            print(f"✅ Processed page {page_num + 1}")
        
        doc.close()
        
        # Generate output filename
        pdf_name = Path(pdf_path).stem
        text_file_path = output_path / f"{pdf_name}_extracted.txt"
        
        # Save text file
        with open(text_file_path, 'w', encoding='utf-8') as f:
            f.write(text_content)
        
        print(f"✅ Text extracted successfully!")
        print(f"📁 Output file: {text_file_path}")
        print(f"📊 Total characters: {len(text_content)}")
        
        return str(text_file_path)
        
    except Exception as e:
        print(f"❌ Error converting PDF: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Convert PDF to text using PyMuPDF")
    parser.add_argument("pdf_path", help="Path to input PDF file")
    parser.add_argument("--output", "-o", default="./tmp", help="Output directory for text file")
    
    args = parser.parse_args()
    
    if not Path(args.pdf_path).exists():
        print(f"❌ Error: PDF file not found: {args.pdf_path}")
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