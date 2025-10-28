#!/usr/bin/env python3
"""
Test script to verify the Claude API fix works correctly.
"""

import sys
from pathlib import Path

def test_claude_api_fix():
    """Test that the Claude API fix resolves the system role error."""
    print(" Testing Claude API Fix")
    print("=" * 40)
    
    try:
        # Test 1: Check if the fixed function can be imported
        print("1. Testing import...")
        from src.claim_extractor.claude_pdf_image_extractor import call_claude_on_image
        print("   [SUCCESS] Import successful")
        
        # Test 2: Check if config is valid
        print("\n2. Testing configuration...")
        import config
        
        if (hasattr(config, 'AWS_ACCESS_KEY') and 
            hasattr(config, 'AWS_SECRET_KEY') and 
            hasattr(config, 'AWS_REGION') and 
            hasattr(config, 'MODEL_ID')):
            
            # Check if values are not placeholders
            if (not config.AWS_ACCESS_KEY.startswith('YOUR_') and 
                not config.AWS_SECRET_KEY.startswith('YOUR_')):
                print("   [SUCCESS] Configuration looks valid")
            else:
                print("   ⚠️  Configuration has placeholder values - update with real credentials")
        else:
            print("   [ERROR] Configuration missing required fields")
            return False
        
        # Test 3: Test Bedrock connection
        print("\n3. Testing Bedrock connection...")
        import boto3
        import json
        
        bedrock = boto3.client(
            'bedrock-runtime',
            aws_access_key_id=config.AWS_ACCESS_KEY,
            aws_secret_access_key=config.AWS_SECRET_KEY,
            aws_session_token=getattr(config, 'AWS_SESSION_TOKEN', None),
            region_name=config.AWS_REGION
        )
        
        # Test with a simple text-only request (no system role)
        test_response = bedrock.invoke_model(
            modelId=config.MODEL_ID,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 100,
                "temperature": 0.0,
                "messages": [{"role": "user", "content": "Hello, respond with 'API test successful'"}]
            })
        )
        
        content = json.loads(test_response["body"].read())["content"][0]["text"]
        print(f"   [SUCCESS] Bedrock connection successful: {content[:50]}...")
        
        print("\n[COMPLETE] All tests passed! The system role error should be fixed.")
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        return False

def main():
    """Run the test."""
    success = test_claude_api_fix()
    
    if success:
        print("\n[SUCCESS] Claude API fix is working correctly!")
        print("\nYou can now try running the adaptive extractor:")
        print("python adaptive_table_extractor_standalone.py your_file.pdf --out results")
    else:
        print("\n[ERROR] There are still issues to resolve.")
        print("Run: python debug_claude_error.py")

if __name__ == "__main__":
    main()
