@echo off
REM End-to-End Loss Run Processing (OpenAI)

echo ========================================
echo Loss Run Processing - OpenAI (End to End)
echo ========================================

if "%1"=="" (
    echo Error: No input file specified
    echo Usage: process_loss_run_e2e_openai.bat "path\to\input.pdf"
    exit /b 1
)

if not exist "%1" (
    echo Error: Input file does not exist: %1
    exit /b 1
)

set INPUT_PDF=%1
set BACKUP_DIR=backup
set TMP_DIR=tmp
set RESULTS_DIR=results_openai
set CONFIG_FILE=config.py

if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"
if not exist "%TMP_DIR%" mkdir "%TMP_DIR%"
if not exist "%RESULTS_DIR%" mkdir "%RESULTS_DIR%"

echo Input PDF: %INPUT_PDF%
echo Backup directory: %BACKUP_DIR%
echo Temp directory: %TMP_DIR%
echo Results directory: %RESULTS_DIR%

REM Backup
set PDF_NAME=%~nx1
set BACKUP_FILE=%BACKUP_DIR%\%PDF_NAME%
if not exist "%BACKUP_FILE%" (
    copy "%INPUT_PDF%" "%BACKUP_FILE%"
    echo PDF backed up to: %BACKUP_FILE%
) else (
    echo PDF already exists in backup
)

REM Convert PDF to text
echo Converting PDF to text...
python fitzTest3.py "%INPUT_PDF%" --output "%TMP_DIR%"
if errorlevel 1 (
    echo Error: Failed to convert PDF to text
    exit /b 1
)
for %%f in ("%TMP_DIR%\*_extracted.txt") do set TEXT_FILE=%%f
if not exist "%TEXT_FILE%" (
    echo Error: Text file not found after conversion
    exit /b 1
)
echo Text file: %TEXT_FILE%

REM Process text file with OpenAI extractor
set PDF_BASE_NAME=%~n1
set OUTPUT_DIR=%RESULTS_DIR%\%PDF_BASE_NAME%
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

echo Running OpenAI extraction...
python text_lob_openai_extractor.py "%TEXT_FILE%" --config "%CONFIG_FILE%" --out "%OUTPUT_DIR%"
if errorlevel 1 (
    echo Error: OpenAI extraction failed
    exit /b 1
)

REM Rename result file to match original PDF name
for %%f in ("%OUTPUT_DIR%\*.xlsx") do set EXCEL_FILE=%%f
if exist "%EXCEL_FILE%" (
    set FINAL_RESULT=%OUTPUT_DIR%\%PDF_BASE_NAME%.xlsx
    copy "%EXCEL_FILE%" "%FINAL_RESULT%"
    echo Final result file: %FINAL_RESULT%
) else (
    echo Warning: No Excel file found in output directory
)

echo ========================================
echo Processing completed successfully!
echo ========================================

echo Generated files:
echo Backup: %BACKUP_FILE%
echo Text: %TEXT_FILE%
if exist "%FINAL_RESULT%" echo Result: %FINAL_RESULT%

echo Done.
