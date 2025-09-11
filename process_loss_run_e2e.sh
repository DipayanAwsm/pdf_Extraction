#!/bin/bash
# Complete End-to-End Loss Run Processing Shell Script
# This script processes PDF files through the entire pipeline

echo "========================================"
echo "Loss Run Processing - End to End"
echo "========================================"

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
INPUT_PDF="$1"
BACKUP_DIR="backup"
TMP_DIR="tmp"
RESULTS_DIR="results"
CONFIG_FILE="config.py"

# Create directories
mkdir -p "$BACKUP_DIR"
mkdir -p "$TMP_DIR"
mkdir -p "$RESULTS_DIR"

echo "Input PDF: $INPUT_PDF"
echo "Backup directory: $BACKUP_DIR"
echo "Temp directory: $TMP_DIR"
echo "Results directory: $RESULTS_DIR"

# Step 1: Copy PDF to backup (if not already there)
echo ""
echo "Step 1: Backing up PDF file..."
PDF_NAME=$(basename "$INPUT_PDF")
BACKUP_FILE="$BACKUP_DIR/$PDF_NAME"

if [ ! -f "$BACKUP_FILE" ]; then
    cp "$INPUT_PDF" "$BACKUP_FILE"
    echo "PDF backed up to: $BACKUP_FILE"
else
    echo "PDF already exists in backup"
fi

# Step 2: Convert PDF to text using fitzTest3.py
echo ""
echo "Step 2: Converting PDF to text..."
python3 fitzTest3.py "$INPUT_PDF" --output "$TMP_DIR"

if [ $? -ne 0 ]; then
    echo "Error: Failed to convert PDF to text"
    exit 1
fi

# Find the generated text file
TEXT_FILE=$(find "$TMP_DIR" -name "*_extracted.txt" | head -1)

if [ -z "$TEXT_FILE" ] || [ ! -f "$TEXT_FILE" ]; then
    echo "Error: Text file not found after conversion"
    exit 1
fi

echo "Text file created: $TEXT_FILE"

# Step 3: Process text file with LLM extractor
echo ""
echo "Step 3: Processing text with LLM extractor..."

# Create output directory for this specific file
PDF_BASE_NAME=$(basename "$INPUT_PDF" .pdf)
OUTPUT_DIR="$RESULTS_DIR/$PDF_BASE_NAME"
mkdir -p "$OUTPUT_DIR"

python3 text_lob_llm_extractor.py "$TEXT_FILE" --config "$CONFIG_FILE" --out "$OUTPUT_DIR"

if [ $? -ne 0 ]; then
    echo "Error: LLM extraction failed"
    exit 1
fi

# Step 4: Rename result file to match original PDF name
echo ""
echo "Step 4: Finalizing results..."

# Find the generated Excel file
EXCEL_FILE=$(find "$OUTPUT_DIR" -name "*.xlsx" | head -1)

if [ -n "$EXCEL_FILE" ] && [ -f "$EXCEL_FILE" ]; then
    FINAL_RESULT="$OUTPUT_DIR/${PDF_BASE_NAME}.xlsx"
    cp "$EXCEL_FILE" "$FINAL_RESULT"
    echo "Final result file: $FINAL_RESULT"
else
    echo "Warning: No Excel file found in output directory"
fi

echo ""
echo "========================================"
echo "Processing completed successfully!"
echo "========================================"

# List all generated files
echo ""
echo "Generated files:"
echo "Backup: $BACKUP_FILE"
echo "Text: $TEXT_FILE"
if [ -f "$FINAL_RESULT" ]; then
    echo "Result: $FINAL_RESULT"
fi

# Show directory contents
echo ""
echo "Output directory contents:"
ls -la "$OUTPUT_DIR" 2>/dev/null

echo ""
echo "You can now use the Streamlit app to view and download results:"
echo "streamlit run streamlit_e2e_app.py"
