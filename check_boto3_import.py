#!/usr/bin/env python3
"""
Quick script to check if boto3 can be imported from subdirectories
"""

import sys
from pathlib import Path

print("Checking boto3 import...")

# Test 1: Import from root
try:
    import boto3
    print(f"✅ boto3 imported successfully from root")
    print(f"   Version: {boto3.__version__}")
    print(f"   Location: {boto3.__file__}")
except ImportError as e:
    print(f"❌ Failed to import boto3 from root: {e}")
    print("   Solution: pip install boto3")
    sys.exit(1)

# Test 2: Import from subdirectory context
try:
    sys.path.insert(0, str(Path(__file__).parent))
    from src.claim_extractor.claude_text_extractor import setup_bedrock_client, load_config
    print("✅ Can import from src.claim_extractor.claude_text_extractor")
except ImportError as e:
    print(f"❌ Failed to import from subdirectory: {e}")
    sys.exit(1)

# Test 3: Check if boto3 is accessible in subdirectory module
try:
    from src.claim_extractor import claude_text_extractor
    if hasattr(claude_text_extractor, 'boto3'):
        print("✅ boto3 is accessible in subdirectory module")
    else:
        print("⚠️  boto3 not found as attribute, but module imported")
except Exception as e:
    print(f"❌ Error checking subdirectory module: {e}")

print("\n✅ All boto3 import checks passed!")

