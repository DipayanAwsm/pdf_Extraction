#!/usr/bin/env python3
"""
Streamlit Configuration File
Modify these settings to match your system configuration.
"""

# Python Command Configuration
# On Windows, you might need to use "py" instead of "python"
# On Linux/Mac, use "python" or "python3"
PYTHON_CMD = "python"  # Change to "py" on Windows if needed

# Config File Path
# Path to your main configuration file (usually config.py)
CONFIG_FILE = "config.py"  # Change to your config file path if needed

# Timeout Settings (in seconds)
ANALYSIS_TIMEOUT = 60      # PDF analysis timeout
EXTRACTION_TIMEOUT = 1800  # Table extraction timeout (30 minutes)
OCR_TIMEOUT = 1200         # OCR processing timeout (20 minutes)
LOB_TIMEOUT = 1800         # LOB extraction timeout (30 minutes)

# Output Directories
ADAPTIVE_RESULTS_DIR = "adaptive_results"
TMP_DIR = "tmp"
RESULTS_DIR = "results"

# File Processing Settings
MAX_FILE_SIZE_MB = 100     # Maximum file size in MB
SUPPORTED_EXTENSIONS = [".pdf"]  # Supported file extensions

# Debug Settings
SHOW_DEBUG_INFO = True     # Show detailed debug information in Streamlit
SHOW_COMMAND_OUTPUT = True # Show subprocess command output

# System-specific Settings
# Uncomment and modify for your system:
# PYTHON_CMD = "py"  # Windows
# PYTHON_CMD = "python3"  # Linux/Mac with Python 3
# CONFIG_FILE = "my_config.py"  # Custom config file
