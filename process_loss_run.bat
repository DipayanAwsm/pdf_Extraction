@echo off
REM Batch script for processing loss run PDFs
REM This script converts PDF to text and runs the LLM extraction

echo Starting Loss Run Processing...
echo ================================

REM Check if input file exists
if "%1"=="" (
    echo Error: No input file specified
    echo Usage: process_loss_run.bat "path\to\input.pdf"
    exit /b 1
)

if not exist "%1" (
    echo Error: Input file does not exist: %1
    exit /b 1
)

REM Set variables
set INPUT_FILE=%1
set OUTPUT_DIR=outputs
set CONFIG_FILE=config.py
set PYTHON_SCRIPT=text_lob_llm_extractor.py

REM Create output directory
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

echo Input file: %INPUT_FILE%
echo Output directory: %OUTPUT_DIR%

REM Convert PDF to text using fitz (PyMuPDF)
echo Converting PDF to text...
python -c "
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
" "%INPUT_FILE%" "%OUTPUT_DIR%"

if errorlevel 1 (
    echo Error: Failed to convert PDF to text
    exit /b 1
)

REM Find the generated text file
for %%f in ("%OUTPUT_DIR%\*_extracted.txt") do set TEXT_FILE=%%f

if not exist "%TEXT_FILE%" (
    echo Error: Text file not found after conversion
    exit /b 1
)

echo Text file created: %TEXT_FILE%

REM Run the LLM extraction
echo Running LLM extraction...
python "%PYTHON_SCRIPT%" "%TEXT_FILE%" --config "%CONFIG_FILE%" --out "%OUTPUT_DIR%"

if errorlevel 1 (
    echo Error: LLM extraction failed
    exit /b 1
)

echo Processing completed successfully!
echo Check the output directory: %OUTPUT_DIR%

REM List generated files
echo Generated files:
dir /b "%OUTPUT_DIR%\*.xlsx" 2>nul
dir /b "%OUTPUT_DIR%\*.xls" 2>nul

echo ================================
echo Loss Run Processing Complete!
