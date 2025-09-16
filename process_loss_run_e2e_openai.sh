#!/bin/bash
# End-to-End Loss Run Processing (OpenAI)

echo "========================================"
echo "Loss Run Processing - OpenAI (End to End)"
echo "========================================"

if [ $# -eq 0 ]; then
    echo "Error: No input file specified"
    echo "Usage: $0 <path/to/input.pdf>"
    exit 1
fi

if [ ! -f "$1" ]; then
    echo "Error: Input file does not exist: $1"
    exit 1
fi

INPUT_PDF="$1"
BACKUP_DIR="backup"
TMP_DIR="tmp"
RESULTS_DIR="results_openai"
CONFIG_FILE="config.py"

mkdir -p "$BACKUP_DIR" "$TMP_DIR" "$RESULTS_DIR"

echo "Input PDF: $INPUT_PDF"
echo "Backup directory: $BACKUP_DIR"
echo "Temp directory: $TMP_DIR"
echo "Results directory: $RESULTS_DIR"

PDF_NAME=$(basename "$INPUT_PDF")
BACKUP_FILE="$BACKUP_DIR/$PDF_NAME"
if [ ! -f "$BACKUP_FILE" ]; then
    cp "$INPUT_PDF" "$BACKUP_FILE"
    echo "PDF backed up to: $BACKUP_FILE"
else
    echo "PDF already exists in backup"
fi

echo "Converting PDF to text..."
python3 fitzTest3.py "$INPUT_PDF" --output "$TMP_DIR"
if [ $? -ne 0 ]; then
    echo "Error: Failed to convert PDF to text"
    exit 1
fi

TEXT_FILE=$(find "$TMP_DIR" -name "*_extracted.txt" | head -1)
if [ -z "$TEXT_FILE" ] || [ ! -f "$TEXT_FILE" ]; then
    echo "Error: Text file not found after conversion"
    exit 1
fi

echo "Text file: $TEXT_FILE"

PDF_BASE_NAME=$(basename "$INPUT_PDF" .pdf)
OUTPUT_DIR="$RESULTS_DIR/$PDF_BASE_NAME"
mkdir -p "$OUTPUT_DIR"

echo "Running OpenAI extraction..."
python3 text_lob_openai_extractor.py "$TEXT_FILE" --config "$CONFIG_FILE" --out "$OUTPUT_DIR"
if [ $? -ne 0 ]; then
    echo "Error: OpenAI extraction failed"
    exit 1
fi

EXCEL_FILE=$(find "$OUTPUT_DIR" -name "*.xlsx" | head -1)
if [ -n "$EXCEL_FILE" ] && [ -f "$EXCEL_FILE" ]; then
    FINAL_RESULT="$OUTPUT_DIR/${PDF_BASE_NAME}.xlsx"
    cp "$EXCEL_FILE" "$FINAL_RESULT"
    echo "Final result file: $FINAL_RESULT"
else
    echo "Warning: No Excel file found in output directory"
fi

echo "========================================"
echo "Processing completed successfully!"
echo "========================================"

echo "Generated files:"
echo "Backup: $BACKUP_FILE"
echo "Text: $TEXT_FILE"
if [ -f "$FINAL_RESULT" ]; then
    echo "Result: $FINAL_RESULT"
fi

echo "Done."
