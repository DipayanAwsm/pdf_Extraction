# Dependency Compatibility Report

## Summary
All libraries in `requirements.txt` are compatible with Python 3.9+ and each other.

## Compatibility Analysis

### Core Dependencies
- **Python Version**: 3.9+ (required)
- **pandas 2.2.0+**: Compatible with Python 3.9+, works with all other packages
- **Pillow 10.4.0**: Compatible with Python 3.9+, required by pdf2image
- **streamlit 1.32.0+**: Compatible with Python 3.9+, works with boto3 and pandas

### AWS/Bedrock Dependencies
- **boto3 1.34.0+**: Compatible with Python 3.9+
  - Note: May have transitive dependency conflicts with aiobotocore if installed separately
  - Solution: boto3 manages its own botocore dependency
- **openai >=1.30.0**: Compatible with Python 3.9+, no conflicts

### PDF Processing Dependencies
- **PyMuPDF 1.26.4+**: Compatible with Python 3.9+
- **pdfplumber 0.11.0**: Compatible with Python 3.9+, works with Pillow
- **pdf2image 1.17.0**: Requires Pillow, compatible
- **pytesseract 0.3.10**: Compatible, requires system Tesseract installation
- **camelot-py[cv] 0.11.0**: Requires OpenCV and Ghostscript (system packages)
- **tabula-py 2.9.0**: Requires Java (system package)

### Excel/Data Processing
- **pandas 2.2.0+**: Compatible with all versions
- **openpyxl 3.1.2+**: Works with pandas for Excel export
- **altair 5.3.0+**: Compatible with pandas and streamlit

### Other Dependencies
- **click 8.1.7**: CLI framework, no conflicts
- **python-dateutil 2.9.0.post0**: Date parsing, compatible
- **reportlab 4.2.2**: PDF generation, compatible
- **tiktoken 0.7.0**: Token counting for LLM, compatible
- **pymupdf4llm 0.0.17**: PyMuPDF extension, compatible
- **pdfalign 0.3.7**: PDF alignment, compatible

## Known Considerations

1. **System Dependencies** (not in requirements.txt):
   - Tesseract OCR: `brew install tesseract` (macOS) or `apt-get install tesseract-ocr` (Linux)
   - Poppler: `brew install poppler` (macOS) or `apt-get install poppler-utils` (Linux)
   - OpenCV: `brew install opencv` (for camelot-py[cv])
   - Ghostscript: `brew install ghostscript` (for camelot-py)
   - Java: `brew install --cask temurin` (for tabula-py)

2. **Version Ranges**: Updated to use compatible version ranges (e.g., `>=X.Y.Z,<N.0.0`) to allow patch updates while preventing breaking changes.

3. **No Known Conflicts**: All packages have been tested and verified to work together.

## Testing
Run `python check_compatibility.py` to verify your installation.

## Installation
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

