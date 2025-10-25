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
    print("✅ AdaptiveTableExtractor imported successfully")
    
    from table_type_detector import TableTypeDetector
    print("✅ TableTypeDetector imported successfully")
    
    # Test basic functionality
    detector = TableTypeDetector()
    print("✅ TableTypeDetector instantiated successfully")
    
    extractor = AdaptiveTableExtractor()
    print("✅ AdaptiveTableExtractor instantiated successfully")
    
    print("\n🎉 All imports working correctly!")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
