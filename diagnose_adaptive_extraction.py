#!/usr/bin/env python3
"""
Diagnostic script to identify issues with adaptive table extraction.
"""

import sys
import subprocess
from pathlib import Path

# Configuration
PYTHON_CMD = "python"  # Change to "py" on Windows if needed
CONFIG_FILE = "config.py"  # Change to your config file path if needed

def check_dependencies():
    """Check if all required dependencies are installed."""
    print("=== Checking Dependencies ===")
    
    required_packages = [
        'pandas', 'fitz', 'camelot', 'tabula', 'boto3', 
        'pdf2image', 'pytesseract', 'openpyxl'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            if package == 'fitz':
                import fitz
                print(f"✓ {package} (PyMuPDF)")
            elif package == 'camelot':
                import camelot
                print(f"✓ {package}")
            elif package == 'tabula':
                import tabula
                print(f"✓ {package}")
            else:
                __import__(package)
                print(f"✓ {package}")
        except ImportError:
            print(f"✗ {package} - MISSING")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n[WARNING] Missing packages: {', '.join(missing_packages)}")
        print("Install with: pip install -r requirements.txt")
        return False
    else:
        print("\n[SUCCESS] All dependencies installed!")
        return True

def check_config():
    """Check if config.py exists and has required settings."""
    print("\n=== Checking Configuration ===")
    
    config_file = Path("config.py")
    if not config_file.exists():
        print("✗ config.py not found")
        return False
    
    print("✓ config.py exists")
    
    # Try to import and check basic config
    try:
        import config
        required_attrs = ['AWS_ACCESS_KEY', 'AWS_SECRET_KEY', 'AWS_REGION', 'MODEL_ID']
        
        missing_attrs = []
        for attr in required_attrs:
            if not hasattr(config, attr) or not getattr(config, attr):
                missing_attrs.append(attr)
        
        if missing_attrs:
            print(f"✗ Missing config attributes: {', '.join(missing_attrs)}")
            return False
        else:
            print("✓ All required config attributes present")
            return True
            
    except Exception as e:
        print(f"✗ Error reading config: {e}")
        return False

def check_sample_files():
    """Check if sample files exist."""
    print("\n=== Checking Sample Files ===")
    
    samples_dir = Path("samples")
    if not samples_dir.exists():
        print("✗ samples/ directory not found")
        return False
    
    pdf_files = list(samples_dir.glob("*.pdf"))
    if not pdf_files:
        print("✗ No PDF files found in samples/")
        return False
    
    print(f"✓ Found {len(pdf_files)} PDF files in samples/")
    for pdf in pdf_files:
        print(f"  - {pdf.name}")
    
    return True

def test_standalone_extractor():
    """Test the standalone extractor with a sample file."""
    print("\n=== Testing Standalone Extractor ===")
    
    sample_pdf = "samples/sample_claim_variation_1.pdf"
    if not Path(sample_pdf).exists():
        print("✗ Sample PDF not found")
        return False
    
    cmd = [
        PYTHON_CMD, "adaptive_table_extractor_standalone.py",
        sample_pdf, "--out", "test_diagnostic_results", "--config", CONFIG_FILE
    ]
    
    print(f"Running: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        print(f"Return code: {result.returncode}")
        
        if result.returncode == 0:
            print("✓ Standalone extractor works!")
            if result.stdout:
                print("Output preview:")
                print(result.stdout[:500] + "..." if len(result.stdout) > 500 else result.stdout)
            return True
        else:
            print("✗ Standalone extractor failed")
            if result.stderr:
                print("Error details:")
                print(result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print("✗ Command timed out")
        return False
    except Exception as e:
        print(f"✗ Exception: {e}")
        return False

def main():
    """Run all diagnostic checks."""
    print("Adaptive Table Extraction Diagnostic Tool")
    print("=" * 50)
    
    checks = [
        ("Dependencies", check_dependencies),
        ("Configuration", check_config),
        ("Sample Files", check_sample_files),
        ("Standalone Extractor", test_standalone_extractor)
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"✗ {name} check failed with exception: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 50)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 50)
    
    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{name:20} {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("[COMPLETE] All checks passed! Adaptive extraction should work.")
    else:
        print("[WARNING] Some checks failed. Fix the issues above and try again.")
        print("\nQuick fixes:")
        print("1. Install dependencies: pip install -r requirements.txt")
        print("2. Check config.py has valid AWS credentials")
        print("3. Ensure sample PDFs exist in samples/ directory")

if __name__ == "__main__":
    main()
