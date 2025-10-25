#!/usr/bin/env python3
"""
Test script to verify adaptive table extractor imports work correctly.
"""

import sys
from pathlib import Path

# Add the src directory to Python path
sys.path.append(str(Path(__file__).parent / "src" / "claim_extractor"))

try:
    from adaptive_table_extractor import AdaptiveTableExtractor
    print("[SUCCESS] AdaptiveTableExtractor imported successfully")
    
    from table_type_detector import TableTypeDetector
    print("[SUCCESS] TableTypeDetector imported successfully")
    
    # Test basic functionality
    detector = TableTypeDetector()
    print("[SUCCESS] TableTypeDetector instantiated successfully")
    
    extractor = AdaptiveTableExtractor()
    print("[SUCCESS] AdaptiveTableExtractor instantiated successfully")
    
    print("\n[COMPLETE] All imports working correctly!")
    
except ImportError as e:
    print(f"[ERROR] Import error: {e}")
except Exception as e:
    print(f"[ERROR] Error: {e}")
