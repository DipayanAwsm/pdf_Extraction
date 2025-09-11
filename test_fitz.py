#!/usr/bin/env python3
"""
Test script to diagnose PyMuPDF/fitz import issues
"""

print("Testing PyMuPDF import...")

try:
    import fitz
    print("✅ fitz imported successfully!")
    print(f"PyMuPDF version: {fitz.version}")
    print(f"fitz module location: {fitz.__file__}")
    
    # Test basic functionality
    print("\nTesting basic functionality...")
    doc = fitz.open()  # Create empty document
    print("✅ fitz.open() works!")
    doc.close()
    print("✅ fitz.close() works!")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("\nTrying alternative imports...")
    
    try:
        import PyMuPDF as fitz
        print("✅ PyMuPDF imported as fitz!")
    except ImportError as e2:
        print(f"❌ PyMuPDF import failed: {e2}")
        
        # Check what's installed
        import pkg_resources
        installed_packages = [d.project_name for d in pkg_resources.working_set]
        print(f"\nInstalled packages containing 'pymupdf': {[p for p in installed_packages if 'pymupdf' in p.lower()]}")
        
except Exception as e:
    print(f"❌ Unexpected error: {e}")

print("\nTest completed.")
