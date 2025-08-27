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

### Requirements
Python 3.9+

System packages (macOS):
- `brew install tesseract`
- `brew install poppler` (needed by pdf2image)

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



