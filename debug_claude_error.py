#!/usr/bin/env python3
"""
Debug script to identify Claude API validation errors in adaptive table extraction.
"""

import sys
import json
from pathlib import Path

def check_config():
    """Check if config.py has valid AWS credentials."""
    print("=== Checking Configuration ===")
    
    try:
        import config
        
        # Check required attributes
        required_attrs = ['AWS_ACCESS_KEY', 'AWS_SECRET_KEY', 'AWS_REGION', 'MODEL_ID']
        missing_attrs = []
        
        for attr in required_attrs:
            if not hasattr(config, attr):
                missing_attrs.append(attr)
            else:
                value = getattr(config, attr)
                if not value or value.startswith('YOUR_'):
                    missing_attrs.append(f"{attr} (placeholder value)")
        
        if missing_attrs:
            print("[ERROR] Configuration issues found:")
            for attr in missing_attrs:
                print(f"   - {attr}")
            return False
        else:
            print("[SUCCESS] Configuration looks valid")
            return True
            
    except ImportError:
        print("[ERROR] config.py not found")
        return False
    except Exception as e:
        print(f"[ERROR] Error reading config: {e}")
        return False

def test_bedrock_connection():
    """Test Bedrock connection with current config."""
    print("\n=== Testing Bedrock Connection ===")
    
    try:
        import config
        import boto3
        
        # Create Bedrock client
        bedrock = boto3.client(
            'bedrock-runtime',
            aws_access_key_id=config.AWS_ACCESS_KEY,
            aws_secret_access_key=config.AWS_SECRET_KEY,
            aws_session_token=getattr(config, 'AWS_SESSION_TOKEN', None),
            region_name=config.AWS_REGION
        )
        
        # Test with a simple request
        test_prompt = "Hello, this is a test message. Please respond with 'Test successful'."
        
        response = bedrock.invoke_model(
            modelId=config.MODEL_ID,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 100,
                "temperature": 0.0,
                "messages": [{"role": "user", "content": test_prompt}]
            })
        )
        
        # Check response
        content = json.loads(response["body"].read())["content"][0]["text"]
        print(f"[SUCCESS] Test response: {content[:100]}...")
        
        print("[SUCCESS] Bedrock connection successful")
        return True
        
    except Exception as e:
        print(f"[ERROR] Bedrock connection failed: {e}")
        return False

def test_image_processing():
    """Test image processing with a small sample."""
    print("\n=== Testing Image Processing ===")
    
    try:
        from adaptive_table_extractor_standalone import AdaptiveTableExtractor
        
        # Create extractor
        extractor = AdaptiveTableExtractor()
        
        if not extractor.bedrock:
            print("[ERROR] Bedrock client not initialized")
            return False
        
        print("[SUCCESS] Bedrock client initialized")
        return True
        
    except Exception as e:
        print(f"[ERROR] Image processing test failed: {e}")
        return False

def suggest_fixes():
    """Suggest fixes for common issues."""
    print("\n=== Suggested Fixes ===")
    
    print("1. Update config.py with real AWS credentials:")
    print("   - Replace 'YOUR_ACCESS_KEY_ID' with actual access key")
    print("   - Replace 'YOUR_SECRET_ACCESS_KEY' with actual secret key")
    print("   - Replace 'YOUR_SESSION_TOKEN' with actual session token (if using)")
    
    print("\n2. Verify AWS credentials have Bedrock permissions:")
    print("   - Check IAM policy includes 'bedrock:InvokeModel'")
    print("   - Ensure region is correct (us-east-1, us-west-2, etc.)")
    
    print("\n3. Try a different model:")
    print("   - MODEL_ID = 'anthropic.claude-3-haiku-20240307-v1:0'  # Faster, cheaper")
    print("   - MODEL_ID = 'anthropic.claude-3-sonnet-20240229-v1:0'  # Balanced")
    
    print("\n4. Reduce image size/quality:")
    print("   - Use lower DPI (150 instead of 220)")
    print("   - Process fewer pages at once")
    
    print("\n5. Check PDF file:")
    print("   - Ensure PDF is not corrupted")
    print("   - Try with a smaller PDF first")
    print("   - Check if PDF has images (not just text)")

def main():
    """Run all diagnostic checks."""
    print(" Claude API Validation Error Diagnostic")
    print("=" * 50)
    
    checks = [
        ("Configuration", check_config),
        ("Bedrock Connection", test_bedrock_connection),
        ("Image Processing", test_image_processing)
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"[ERROR] {name} check failed with exception: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 50)
    print(" DIAGNOSTIC SUMMARY")
    print("=" * 50)
    
    all_passed = True
    for name, passed in results:
        status = "[SUCCESS] PASS" if passed else "[ERROR] FAIL"
        print(f"{name:20} {status}")
        if not passed:
            all_passed = False
    
    if not all_passed:
        suggest_fixes()
    
    print("\n" + "=" * 50)
    if all_passed:
        print("[COMPLETE] All checks passed! The issue might be with the specific PDF or request size.")
    else:
        print("[WARNING]  Fix the configuration issues above and try again.")

if __name__ == "__main__":
    main()
