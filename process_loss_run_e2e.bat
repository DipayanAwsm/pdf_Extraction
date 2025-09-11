@echo off
REM Complete End-to-End Loss Run Processing Batch Script
REM This script processes PDF files through the entire pipeline

echo ========================================
echo Loss Run Processing - End to End
echo ========================================

REM Check if input file exists
if "%1"=="" (
    echo Error: No input file specified
    echo Usage: process_loss_run_e2e.bat "path\to\input.pdf"
    exit /b 1
)

if not exist "%1" (
    echo Error: Input file does not exist: %1
    exit /b 1
)

REM Set variables
set INPUT_PDF=%1
set BACKUP_DIR=backup
set TMP_DIR=tmp
set RESULTS_DIR=results
set CONFIG_FILE=config.py

REM Create directories
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"
if not exist "%TMP_DIR%" mkdir "%TMP_DIR%"
if not exist "%RESULTS_DIR%" mkdir "%RESULTS_DIR%"

echo Input PDF: %INPUT_PDF%
echo Backup directory: %BACKUP_DIR%
echo Temp directory: %TMP_DIR%
echo Results directory: %RESULTS_DIR%

REM Step 1: Copy PDF to backup (if not already there)
echo.
echo Step 1: Backing up PDF file...
set PDF_NAME=%~nx1
set BACKUP_FILE=%BACKUP_DIR%\%PDF_NAME%
if not exist "%BACKUP_FILE%" (
    copy "%INPUT_PDF%" "%BACKUP_FILE%"
    echo PDF backed up to: %BACKUP_FILE%
) else (
    echo PDF already exists in backup
)

REM Step 2: Convert PDF to text using fitzTest3.py
echo.
echo Step 2: Converting PDF to text...
python fitzTest3.py "%INPUT_PDF%" --output "%TMP_DIR%"

if errorlevel 1 (
    echo Error: Failed to convert PDF to text
    exit /b 1
)

REM Find the generated text file
for %%f in ("%TMP_DIR%\*_extracted.txt") do set TEXT_FILE=%%f

if not exist "%TEXT_FILE%" (
    echo Error: Text file not found after conversion
    exit /b 1
)

echo Text file created: %TEXT_FILE%

REM Step 3: Process text file with LLM extractor
echo.
echo Step 3: Processing text with LLM extractor...

REM Create output directory for this specific file
set PDF_BASE_NAME=%~n1
set OUTPUT_DIR=%RESULTS_DIR%\%PDF_BASE_NAME%
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

python text_lob_llm_extractor.py "%TEXT_FILE%" --config "%CONFIG_FILE%" --out "%OUTPUT_DIR%"

if errorlevel 1 (
    echo Error: LLM extraction failed
    exit /b 1
)

REM Step 4: Rename result file to match original PDF name
echo.
echo Step 4: Finalizing results...

REM Find the generated Excel file
for %%f in ("%OUTPUT_DIR%\*.xlsx") do set EXCEL_FILE=%%f

if exist "%EXCEL_FILE%" (
    set FINAL_RESULT=%OUTPUT_DIR%\%PDF_BASE_NAME%.xlsx
    copy "%EXCEL_FILE%" "%FINAL_RESULT%"
    echo Final result file: %FINAL_RESULT%
) else (
    echo Warning: No Excel file found in output directory
)

echo.
echo ========================================
echo Processing completed successfully!
echo ========================================

REM List all generated files
echo.
echo Generated files:
echo Backup: %BACKUP_FILE%
echo Text: %TEXT_FILE%
if exist "%FINAL_RESULT%" echo Result: %FINAL_RESULT%

REM Show directory contents
echo.
echo Output directory contents:
dir /b "%OUTPUT_DIR%" 2>nul

echo.
echo You can now use the Streamlit app to view and download results:
echo streamlit run streamlit_e2e_app.py
