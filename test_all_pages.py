#!/usr/bin/env python3
"""
Test script to verify that all pages are processed in Legacy OCR via Claude.
"""

import subprocess
import sys
from pathlib import Path

def test_all_pages_processing():
    """Test that all pages are processed when no page range is specified."""
    print("🔍 Testing All Pages Processing")
    print("=" * 40)
    
    # Check if we have a sample PDF
    sample_pdf = "samples/sample_claim_variation_1.pdf"
    if not Path(sample_pdf).exists():
        print(f"❌ Sample PDF not found: {sample_pdf}")
        return False
    
    print(f"📄 Testing with: {sample_pdf}")
    
    # Test 1: Process all pages (no page range)
    print("\n1. Testing ALL pages processing (no page range)...")
    cmd_all = [
        "python", "src/claim_extractor/claude_pdf_image_extractor.py",
        sample_pdf, "--out", "test_all_pages", "--config", "config.py"
    ]
    
    print(f"Command: {' '.join(cmd_all)}")
    
    try:
        result = subprocess.run(cmd_all, capture_output=True, text=True, timeout=300)
        
        print(f"Return code: {result.returncode}")
        if result.stdout:
            print("Output:")
            print(result.stdout)
        if result.stderr:
            print("Errors:")
            print(result.stderr)
        
        if result.returncode == 0:
            # Check if output file was created
            output_dir = Path("test_all_pages")
            if output_dir.exists():
                txt_files = list(output_dir.glob("*_claude_text.txt"))
                if txt_files:
                    txt_file = txt_files[0]
                    content = txt_file.read_text(encoding='utf-8')
                    # Count page markers
                    page_markers = content.count("=== PAGE")
                    print(f"✅ Found {page_markers} page markers in output")
                    print(f"✅ Output file: {txt_file}")
                    return True
                else:
                    print("❌ No text file found in output directory")
                    return False
            else:
                print("❌ Output directory not created")
                return False
        else:
            print("❌ Command failed")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Command timed out")
        return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def test_specific_page_range():
    """Test specific page range processing."""
    print("\n2. Testing specific page range (1-3)...")
    
    sample_pdf = "samples/sample_claim_variation_1.pdf"
    cmd_range = [
        "python", "src/claim_extractor/claude_pdf_image_extractor.py",
        sample_pdf, "--out", "test_page_range", "--config", "config.py",
        "--first", "1", "--last", "3"
    ]
    
    print(f"Command: {' '.join(cmd_range)}")
    
    try:
        result = subprocess.run(cmd_range, capture_output=True, text=True, timeout=300)
        
        print(f"Return code: {result.returncode}")
        if result.stdout:
            print("Output:")
            print(result.stdout)
        
        if result.returncode == 0:
            print("✅ Page range processing successful")
            return True
        else:
            print("❌ Page range processing failed")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def main():
    """Run all tests."""
    print("🧪 Testing Legacy OCR Page Processing")
    print("=" * 50)
    
    # Test 1: All pages
    test1_success = test_all_pages_processing()
    
    # Test 2: Specific range
    test2_success = test_specific_page_range()
    
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    print(f"All pages processing: {'✅ PASS' if test1_success else '❌ FAIL'}")
    print(f"Page range processing: {'✅ PASS' if test2_success else '❌ FAIL'}")
    
    if test1_success and test2_success:
        print("\n🎉 All tests passed! Page processing is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")

if __name__ == "__main__":
    main()
