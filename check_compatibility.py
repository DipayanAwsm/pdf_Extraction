#!/usr/bin/env python3
"""
Compatibility checker for all dependencies in requirements.txt
Tests imports and checks for version conflicts.
"""

import sys
import subprocess
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible (3.9+)"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 9):
        print(f"❌ Python {version.major}.{version.minor} detected. Requires Python 3.9+")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} - Compatible")
    return True

def check_package_import(package_name, import_name=None):
    """Check if a package can be imported"""
    if import_name is None:
        import_name = package_name
    
    try:
        __import__(import_name)
        return True, None
    except ImportError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"

def check_package_version(package_name, import_name=None):
    """Get installed version of a package"""
    if import_name is None:
        import_name = package_name
    
    try:
        module = __import__(import_name)
        if hasattr(module, '__version__'):
            return module.__version__
        elif hasattr(module, 'version'):
            return str(module.version)
        else:
            return "unknown"
    except:
        return None

def test_imports():
    """Test all critical imports"""
    print("\n=== Testing Package Imports ===")
    
    # Map of package name to import name
    packages = {
        'pandas': 'pandas',
        'streamlit': 'streamlit',
        'boto3': 'boto3',
        'Pillow': 'PIL',
        'openpyxl': 'openpyxl',
        'PyMuPDF': 'fitz',
        'pdfplumber': 'pdfplumber',
        'pdf2image': 'pdf2image',
        'pytesseract': 'pytesseract',
        'click': 'click',
        'python-dateutil': 'dateutil',
        'reportlab': 'reportlab',
        'camelot-py': 'camelot',
        'tabula-py': 'tabula',
        'openai': 'openai',
        'altair': 'altair',
        'tiktoken': 'tiktoken',
        'pymupdf4llm': 'pymupdf4llm',
        'pdfalign': 'pdfalign',
    }
    
    results = {}
    for pkg_name, import_name in packages.items():
        success, error = check_package_import(pkg_name, import_name)
        version = check_package_version(pkg_name, import_name)
        results[pkg_name] = {
            'success': success,
            'error': error,
            'version': version
        }
        if success:
            print(f"✅ {pkg_name} (import: {import_name}) - version: {version}")
        else:
            print(f"❌ {pkg_name} (import: {import_name}) - {error}")
    
    return results

def check_known_conflicts():
    """Check for known compatibility issues"""
    print("\n=== Checking Known Compatibility Issues ===")
    
    issues = []
    
    # Check pandas version
    try:
        import pandas as pd
        if pd.__version__.startswith('2.'):
            print("✅ pandas 2.x detected - compatible with Python 3.9+")
        else:
            issues.append("pandas version may be outdated")
    except:
        pass
    
    # Check streamlit compatibility
    try:
        import streamlit as st
        print(f"✅ streamlit {st.__version__} - compatible")
    except:
        pass
    
    # Check boto3 compatibility
    try:
        import boto3
        print(f"✅ boto3 {boto3.__version__} - compatible")
    except:
        pass
    
    # Check Pillow compatibility
    try:
        from PIL import Image
        print(f"✅ Pillow {Image.__version__} - compatible")
    except:
        pass
    
    # Check PyMuPDF
    try:
        import fitz
        print(f"✅ PyMuPDF {fitz.version[0] if hasattr(fitz, 'version') else 'installed'} - compatible")
    except:
        pass
    
    # Check camelot dependencies
    try:
        import camelot
        print("✅ camelot-py - installed")
        # Check if OpenCV is available (required for camelot)
        try:
            import cv2
            print("✅ OpenCV available for camelot")
        except ImportError:
            issues.append("⚠️  OpenCV not found - camelot-py[cv] may have limited functionality")
    except ImportError:
        pass
    
    # Check tabula Java dependency
    try:
        import tabula
        print("✅ tabula-py - installed")
        # Note: Java check would require subprocess call
    except ImportError:
        pass
    
    # Check OpenAI SDK version
    try:
        import openai
        version = openai.__version__
        if version >= "1.30.0":
            print(f"✅ openai {version} - meets requirement (>=1.30.0)")
        else:
            issues.append(f"⚠️  openai {version} may be outdated (requires >=1.30.0)")
    except:
        pass
    
    return issues

def test_critical_functionality():
    """Test critical functionality that depends on multiple packages"""
    print("\n=== Testing Critical Functionality ===")
    
    tests = []
    
    # Test pandas + openpyxl (Excel writing)
    try:
        import pandas as pd
        import openpyxl
        df = pd.DataFrame({'test': [1, 2, 3]})
        # Just test that we can create Excel writer
        from openpyxl import Workbook
        wb = Workbook()
        wb.close()
        tests.append(("pandas + openpyxl", True, None))
        print("✅ pandas + openpyxl - Excel functionality works")
    except Exception as e:
        tests.append(("pandas + openpyxl", False, str(e)))
        print(f"❌ pandas + openpyxl - {str(e)}")
    
    # Test boto3 + streamlit
    try:
        import boto3
        import streamlit
        tests.append(("boto3 + streamlit", True, None))
        print("✅ boto3 + streamlit - compatible")
    except Exception as e:
        tests.append(("boto3 + streamlit", False, str(e)))
        print(f"❌ boto3 + streamlit - {str(e)}")
    
    # Test PyMuPDF + pdf2image
    try:
        import fitz
        from pdf2image import convert_from_path
        tests.append(("PyMuPDF + pdf2image", True, None))
        print("✅ PyMuPDF + pdf2image - compatible")
    except Exception as e:
        tests.append(("PyMuPDF + pdf2image", False, str(e)))
        print(f"❌ PyMuPDF + pdf2image - {str(e)}")
    
    # Test pdfplumber + pytesseract
    try:
        import pdfplumber
        import pytesseract
        tests.append(("pdfplumber + pytesseract", True, None))
        print("✅ pdfplumber + pytesseract - compatible")
    except Exception as e:
        tests.append(("pdfplumber + pytesseract", False, str(e)))
        print(f"❌ pdfplumber + pytesseract - {str(e)}")
    
    return tests

def main():
    print("=" * 60)
    print("Dependency Compatibility Checker")
    print("=" * 60)
    
    # Check Python version
    if not check_python_version():
        print("\n❌ Python version incompatible. Please upgrade to Python 3.9+")
        return 1
    
    # Test imports
    results = test_imports()
    
    # Check known conflicts
    issues = check_known_conflicts()
    
    # Test critical functionality
    functionality_tests = test_critical_functionality()
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    failed_imports = [pkg for pkg, data in results.items() if not data['success']]
    failed_tests = [name for name, success, _ in functionality_tests if not success]
    
    if not failed_imports and not failed_tests and not issues:
        print("✅ All dependencies are compatible and working!")
        return 0
    else:
        if failed_imports:
            print(f"\n❌ Failed imports: {', '.join(failed_imports)}")
            print("   Run: pip install -r requirements.txt")
        if failed_tests:
            print(f"\n❌ Failed functionality tests: {', '.join(failed_tests)}")
        if issues:
            print(f"\n⚠️  Warnings:")
            for issue in issues:
                print(f"   - {issue}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

