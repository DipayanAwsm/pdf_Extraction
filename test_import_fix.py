#!/usr/bin/env python3
"""
Test script to verify the import fix works correctly.
"""

import sys
from pathlib import Path

# Add the src directory to Python path
sys.path.append(str(Path(__file__).parent / "src" / "claim_extractor"))

try:
    print("Testing import fix...")
    
    # Test the adaptive table extractor import
    from adaptive_table_extractor import AdaptiveTableExtractor
    print("[SUCCESS] AdaptiveTableExtractor imported successfully")
    
    # Test instantiation
    extractor = AdaptiveTableExtractor()
    print("[SUCCESS] AdaptiveTableExtractor instantiated successfully")
    
    print("\n[COMPLETE] All imports working correctly!")
    
except ImportError as e:
    print(f"[ERROR] Import error: {e}")
except Exception as e:
    print(f"[ERROR] Error: {e}")
