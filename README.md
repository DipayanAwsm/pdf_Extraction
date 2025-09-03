## PDF Claim Extractor (Offline, Python)

Extract claim number, claimant name, and date from unstructured PDFs using offline text extraction and OCR. No external API calls.

### Features
- PDF text extraction via native text layer (fast) with automatic fallback to OCR
- Heuristics to detect:
  - Claim number (Claim No/Number, Claim#, etc.)
  - Claimant/Insured Name (Name:, Claimant:, Insured:) with fallbacks
  - Date in many formats (MM/DD/YYYY, DD-MM-YYYY, Month DD, YYYY, etc.)
- CLI to process a single file or a directory; outputs JSON or CSV
- Sample PDF generator for unstructured layouts
 - Optional model comparisons: Regex vs Camelot vs Tabula against ground truth

### Requirements
Python 3.9+

System packages (macOS):
- `brew install tesseract`
- `brew install poppler` (needed by pdf2image)
- Camelot/tabula extras:
  - `pip install camelot-py[cv] tabula-py`
  - For Camelot (lattice), install OpenCV and Ghostscript if needed (`brew install ghostscript opencv`)
  - For Tabula, ensure Java is installed (`brew install --cask temurin`)

Linux equivalents: install `tesseract-ocr` and `poppler-utils` via your package manager.

### Install
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Generate sample PDFs
- Basic samples (3 small variations):
```bash
python scripts/generate_samples.py --out samples
```

- Two-page instructions PDF (your provided text):
```bash
python scripts/generate_samples.py --out samples --instructions
```

- Bulk unstructured claims PDFs (narrative text, not tables), each claim separated by a blank line; includes claim number, amount, reason, and date of loss. Defaults to a single PDF with 50 claims:
```bash
python scripts/generate_samples.py --out samples --bulk
```

- Control count, duplicates, and reproducibility:
```bash
python scripts/generate_samples.py \
  --out samples \
  --bulk \
  --bulk-pdfs 2 \
  --bulk-claims 50 \
  --dup-ratio 0.3 \
  --seed 7
```

Notes:
- Duplicate claim numbers can appear across generated PDFs according to `--dup-ratio`.
- Bulk mode writes narrative lines like: "Claim# ABC-12345 noted with amount $1,234.56. Reason: Fire damage. Date of loss: 03/21/2024." Claims are delimited by a blank line.

### Compare extraction methods (Regex vs Camelot vs Tabula)
1) Generate a bulk PDF and its ground truth JSONL:
```bash
python scripts/generate_samples.py --out samples --bulk --bulk-claims 50 --dup-ratio 0.2 --seed 7
```
This creates `samples/bulk_claims_1.pdf` and `samples/bulk_claims_1.groundtruth.jsonl`.

2) Run the comparator:
```bash
python -m claim_extractor.compare_models samples/bulk_claims_1.pdf --truth samples/bulk_claims_1.groundtruth.jsonl
```
Output shows per-field exact-match accuracy by position: model,claim_no,amount,reason,date.

Notes:
- Regex approach is for unstructured narrative PDFs. Camelot/Tabula target table PDFs.
- Tabula requires Java; Camelot may need Ghostscript/OpenCV depending on flavor.

### Run the extractor
- Single file to JSON (stdout):
```bash
python -m claim_extractor.cli ./samples/sample_claim_variation_1.pdf --format json
```

- Directory to CSV file:
```bash
python -m claim_extractor.cli ./samples --format csv --out results.csv
```

### Output schema
Each record contains:
```json
{
  "file_path": "...",
  "claim_number": "...",
  "name": "...",
  "date": "YYYY-MM-DD",
  "confidence": 0.0
}
```

Notes:
- `confidence` is a heuristic score (0.0–1.0) based on signal quality of matches.
- If a field cannot be confidently extracted, it may be empty.

### Project structure
```
.
├── README.md
├── requirements.txt
├── scripts/
│   └── generate_samples.py
├── samples/  (created by script)
└── src/
    └── claim_extractor/
        ├── __init__.py
        ├── extract_text.py
        ├── parse_fields.py
        └── cli.py
```

### Notes and tips
- OCR requires Tesseract and Poppler installed and discoverable in PATH.
- For best OCR accuracy, ensure PDFs are at least ~200 DPI when rasterized (handled by default).
- You can tweak regex patterns for claim number/name/date in `parse_fields.py` to fit your documents.

## Streamlit Web App (AWS Bedrock Claude)

Use a browser UI to upload multiple PDFs (scanned or text), extract tables with Claude via AWS Bedrock, preview them, and export to a single Excel file with one sheet per table.

### Prerequisites
- Installed dependencies (already in requirements.txt):
  - streamlit, boto3, pandas, openpyxl
- AWS Bedrock access in your AWS account
- Your AWS credentials:
  - AWS Access Key ID
  - AWS Secret Access Key
  - AWS Session Token
  - AWS Region (e.g., us-east-1)

### Start the app
```bash
streamlit run streamlit_app.py
```
Then open `http://localhost:8501` in your browser if it does not open automatically.

### Using the app
1. Enter AWS credentials in the left sidebar and pick your region. Optionally click "Test AWS Connection".
2. Upload one or more PDF files (scanned and text-based are supported). The app will OCR when needed.
3. Click "Extract Tables" to process all PDFs using Claude. The app:
   - Extracts text locally (with OCR fallback)
   - Sends only text to Bedrock Claude to extract table-like structures
   - Displays per-PDF results and a summary
4. Review tables in the UI. Expand each table to see rows and metadata.
5. Click "Download Excel File" to export all tables into `extracted_tables.xlsx` (one sheet per table).

### Notes
- The app uses model `anthropic.claude-3-sonnet-20240229-v1:0` on AWS Bedrock.
- Scanned PDFs are processed with OCR locally (no image data is sent; only text is sent to Bedrock).
- Sheet names are sanitized to meet Excel constraints (<=31 chars, no invalid characters).
- If Claude returns non-JSON or partial JSON, the app attempts to parse the JSON segment; unparseable outputs are skipped with a warning.
- Usage of Bedrock may incur AWS charges.

### Troubleshooting
- If Camelot/Tabula are installed but not needed for the Streamlit app, you can ignore Java/Ghostscript warnings; the app does not use them.
- Ensure your AWS credentials have permission for Bedrock `bedrock:InvokeModel` in the selected region.
- For very large PDFs, try splitting the file or uploading fewer at a time.



