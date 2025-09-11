#!/usr/bin/env python3
"""
Test script to verify fitzTest3.py functionality
"""

import sys
import os
from pathlib import Path

print("Testing fitzTest3.py functionality...")

# Test 1: Check if fitzTest3.py exists
fitzTest3_path = Path("fitzTest3.py")
if fitzTest3_path.exists():
    print("✅ fitzTest3.py exists")
else:
    print("❌ fitzTest3.py not found")
    sys.exit(1)

# Test 2: Try importing the functions
try:
    sys.path.append(str(Path.cwd()))
    from fitzTest3 import pdf_to_text
    print("✅ pdf_to_text function imported successfully")
except ImportError as e:
    print(f"❌ Import error: {e}")

# Test 3: Check if we can create directories
try:
    test_dir = Path("test_output")
    test_dir.mkdir(exist_ok=True)
    print("✅ Directory creation works")
    test_dir.rmdir()  # Clean up
except Exception as e:
    print(f"❌ Directory creation failed: {e}")

print("\nTest completed. If all tests pass, the script should work.")
print("Try running: python fitzTest3.py your_file.pdf")
