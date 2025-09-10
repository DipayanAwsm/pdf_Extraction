#!/bin/bash
# Shell script for processing loss run PDFs
# This script converts PDF to text and runs the LLM extraction

echo "Starting Loss Run Processing..."
echo "================================"

# Check if input file exists
if [ $# -eq 0 ]; then
    echo "Error: No input file specified"
    echo "Usage: $0 <path/to/input.pdf>"
    exit 1
fi

if [ ! -f "$1" ]; then
    echo "Error: Input file does not exist: $1"
    exit 1
fi

# Set variables
INPUT_FILE="$1"
OUTPUT_DIR="outputs"
CONFIG_FILE="config.py"
PYTHON_SCRIPT="text_lob_llm_extractor.py"

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "Input file: $INPUT_FILE"
echo "Output directory: $OUTPUT_DIR"

# Convert PDF to text using fitz (PyMuPDF)
echo "Converting PDF to text..."
python3 -c "
import fitz
import sys
from pathlib import Path

def pdf_to_text(pdf_path, output_dir):
    try:
        doc = fitz.open(pdf_path)
        text_content = ''
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text_content += page.get_text()
            text_content += '\n\n--- PAGE BREAK ---\n\n'
        
        doc.close()
        
        # Save text file
        output_path = Path(output_dir) / f'{Path(pdf_path).stem}_extracted.txt'
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text_content)
        
        print(f'Text extracted to: {output_path}')
        return str(output_path)
        
    except Exception as e:
        print(f'Error converting PDF: {e}')
        return None

if __name__ == '__main__':
    pdf_path = sys.argv[1]
    output_dir = sys.argv[2]
    result = pdf_to_text(pdf_path, output_dir)
    if result:
        print(f'SUCCESS:{result}')
    else:
        print('FAILED')
" "$INPUT_FILE" "$OUTPUT_DIR"

if [ $? -ne 0 ]; then
    echo "Error: Failed to convert PDF to text"
    exit 1
fi

# Find the generated text file
TEXT_FILE=$(find "$OUTPUT_DIR" -name "*_extracted.txt" | head -1)

if [ -z "$TEXT_FILE" ] || [ ! -f "$TEXT_FILE" ]; then
    echo "Error: Text file not found after conversion"
    exit 1
fi

echo "Text file created: $TEXT_FILE"

# Run the LLM extraction
echo "Running LLM extraction..."
python3 "$PYTHON_SCRIPT" "$TEXT_FILE" --config "$CONFIG_FILE" --out "$OUTPUT_DIR"

if [ $? -ne 0 ]; then
    echo "Error: LLM extraction failed"
    exit 1
fi

echo "Processing completed successfully!"
echo "Check the output directory: $OUTPUT_DIR"

# List generated files
echo "Generated files:"
find "$OUTPUT_DIR" -name "*.xlsx" -o -name "*.xls" | while read file; do
    echo "  - $(basename "$file")"
done

echo "================================"
echo "Loss Run Processing Complete!"
