#!/usr/bin/env python3
"""
Test script to verify the standalone adaptive table extractor works correctly
when called from Streamlit (simulating subprocess call).
"""

import subprocess
import sys
from pathlib import Path

# Configuration
PYTHON_CMD = "python"  # Change to "py" on Windows if needed
CONFIG_FILE = "config.py"  # Change to your config file path if needed

def test_standalone_extractor():
    """Test the standalone adaptive table extractor."""
    
    # Check if we have a sample PDF
    sample_pdf = "samples/sample_claim_variation_1.pdf"
    if not Path(sample_pdf).exists():
        print(f"[ERROR] Sample PDF not found: {sample_pdf}")
        return False
    
    print("Testing standalone adaptive table extractor...")
    print(f"Sample PDF: {sample_pdf}")
    
    # Test command (same as Streamlit would use)
    cmd = [
        PYTHON_CMD, "adaptive_table_extractor_standalone.py",
        sample_pdf, "--out", "test_adaptive_results", "--config", CONFIG_FILE
    ]
    
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        print(f"Return code: {result.returncode}")
        print(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            print(f"STDERR:\n{result.stderr}")
        
        if result.returncode == 0:
            print("[SUCCESS] Standalone extractor works correctly!")
            
            # Check if results were created
            results_dir = Path("test_adaptive_results")
            if results_dir.exists():
                files = list(results_dir.glob("*.json")) + list(results_dir.glob("*.xlsx"))
                print(f"[SUCCESS] Created {len(files)} result files:")
                for file in files:
                    print(f"  - {file.name}")
            else:
                print("[WARNING] No results directory created")
            
            return True
        else:
            print("[ERROR] Standalone extractor failed")
            return False
            
    except subprocess.TimeoutExpired:
        print("[ERROR] Command timed out")
        return False
    except Exception as e:
        print(f"[ERROR] Exception: {e}")
        return False

if __name__ == "__main__":
    success = test_standalone_extractor()
    if success:
        print("\n[COMPLETE] Integration test passed!")
    else:
        print("\n[ERROR] Integration test failed!")
        sys.exit(1)
