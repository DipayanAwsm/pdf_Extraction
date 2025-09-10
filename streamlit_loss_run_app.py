#!/usr/bin/env python3
import streamlit as st
import os
import subprocess
import time
import pandas as pd
from pathlib import Path
import shutil
import threading
from datetime import datetime


# Page configuration
st.set_page_config(
    page_title="Loss Run Ingestion System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .step-header {
        font-size: 1.5rem;
        color: #2e8b57;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
    .error-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
    }
    .info-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        color: #0c5460;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'uploaded_file' not in st.session_state:
    st.session_state.uploaded_file = None
if 'processing_complete' not in st.session_state:
    st.session_state.processing_complete = False
if 'output_files' not in st.session_state:
    st.session_state.output_files = []
if 'processing_status' not in st.session_state:
    st.session_state.processing_status = "Ready"


def create_upload_directory():
    """Create upload directory if it doesn't exist"""
    upload_dir = Path("uploads")
    upload_dir.mkdir(exist_ok=True)
    return upload_dir


def create_output_directory():
    """Create output directory if it doesn't exist"""
    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)
    return output_dir


def save_uploaded_file(uploaded_file, upload_dir):
    """Save uploaded file to directory"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{uploaded_file.name}"
    file_path = upload_dir / filename
    
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    return file_path


def run_processing_script(input_file, output_dir):
    """Run the processing script and return status"""
    try:
        # Create a batch/shell script call
        # This will call our text_lob_llm_extractor.py script
        script_path = "text_lob_llm_extractor.py"
        config_path = "config.py"
        
        # Convert PDF to text first (you might want to use fitz here)
        # For now, we'll assume the PDF is already converted to text
        # In a real scenario, you'd add PDF to text conversion here
        
        cmd = [
            "python", script_path,
            str(input_file),
            "--config", config_path,
            "--out", str(output_dir)
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        return result.returncode == 0, result.stdout, result.stderr
        
    except subprocess.TimeoutExpired:
        return False, "", "Processing timed out after 5 minutes"
    except Exception as e:
        return False, "", str(e)


def find_output_files(output_dir):
    """Find generated Excel files in output directory"""
    excel_files = []
    for pattern in ["*.xlsx", "*.xls"]:
        excel_files.extend(output_dir.glob(pattern))
    return excel_files


def main():
    # Header
    st.markdown('<h1 class="main-header">📊 Loss Run Ingestion System</h1>', unsafe_allow_html=True)
    
    # Sidebar
    st.sidebar.title("Navigation")
    st.sidebar.markdown("---")
    
    # Step 1: File Upload
    st.markdown('<h2 class="step-header">Step 1: Upload PDF File</h2>', unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader(
        "Choose a PDF file for loss run ingestion",
        type=['pdf'],
        help="Upload a PDF file containing loss run data"
    )
    
    if uploaded_file is not None:
        # Create directories
        upload_dir = create_upload_directory()
        output_dir = create_output_directory()
        
        # Save uploaded file
        file_path = save_uploaded_file(uploaded_file, upload_dir)
        st.session_state.uploaded_file = file_path
        
        # Show file info
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("File Name", uploaded_file.name)
        with col2:
            st.metric("File Size", f"{uploaded_file.size / 1024:.1f} KB")
        with col3:
            st.metric("Upload Time", datetime.now().strftime("%H:%M:%S"))
        
        st.markdown('<div class="success-box">✅ File uploaded successfully!</div>', unsafe_allow_html=True)
        
        # Step 2: Preview (placeholder for PDF preview)
        st.markdown('<h2 class="step-header">Step 2: File Preview</h2>', unsafe_allow_html=True)
        
        st.info("📄 PDF Preview functionality can be added here. For now, showing file details:")
        
        with st.expander("File Details", expanded=True):
            st.write(f"**File Path:** {file_path}")
            st.write(f"**File Type:** {uploaded_file.type}")
            st.write(f"**Upload Status:** Success")
        
        # Step 3: Processing
        st.markdown('<h2 class="step-header">Step 3: Process File</h2>', unsafe_allow_html=True)
        
        if st.button("🚀 Start Processing", type="primary", disabled=st.session_state.processing_status == "Processing"):
            st.session_state.processing_status = "Processing"
            
            # Create progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Processing steps
            steps = [
                "Initializing processing...",
                "Converting PDF to text...",
                "Classifying Line of Business...",
                "Extracting claim data...",
                "Normalizing data...",
                "Generating Excel output...",
                "Finalizing results..."
            ]
            
            try:
                for i, step in enumerate(steps):
                    status_text.text(step)
                    progress_bar.progress((i + 1) / len(steps))
                    time.sleep(1)  # Simulate processing time
                
                # Run actual processing
                status_text.text("Running processing script...")
                success, stdout, stderr = run_processing_script(file_path, output_dir)
                
                if success:
                    progress_bar.progress(1.0)
                    status_text.text("✅ Processing completed successfully!")
                    st.session_state.processing_complete = True
                    st.session_state.processing_status = "Complete"
                    
                    # Find output files
                    output_files = find_output_files(output_dir)
                    st.session_state.output_files = output_files
                    
                    st.markdown('<div class="success-box">🎉 Processing completed! Check the results below.</div>', unsafe_allow_html=True)
                    
                else:
                    st.session_state.processing_status = "Error"
                    st.markdown('<div class="error-box">❌ Processing failed. Error details:</div>', unsafe_allow_html=True)
                    st.error(f"Error: {stderr}")
                    if stdout:
                        st.text("Output:")
                        st.text(stdout)
                        
            except Exception as e:
                st.session_state.processing_status = "Error"
                st.markdown('<div class="error-box">❌ Processing failed with exception.</div>', unsafe_allow_html=True)
                st.error(f"Exception: {str(e)}")
        
        # Step 4: Results
        if st.session_state.processing_complete and st.session_state.output_files:
            st.markdown('<h2 class="step-header">Step 4: Results & Download</h2>', unsafe_allow_html=True)
            
            st.markdown('<div class="info-box">📊 Generated Excel files:</div>', unsafe_allow_html=True)
            
            for i, excel_file in enumerate(st.session_state.output_files):
                with st.expander(f"📄 {excel_file.name}", expanded=(i == 0)):
                    try:
                        # Read and display Excel file
                        if excel_file.suffix == '.xlsx':
                            # Try to read all sheets
                            excel_data = pd.read_excel(excel_file, sheet_name=None)
                            
                            if len(excel_data) == 1:
                                # Single sheet
                                sheet_name = list(excel_data.keys())[0]
                                df = excel_data[sheet_name]
                                st.write(f"**Sheet:** {sheet_name}")
                                st.dataframe(df, use_container_width=True)
                            else:
                                # Multiple sheets
                                for sheet_name, df in excel_data.items():
                                    st.write(f"**Sheet:** {sheet_name}")
                                    st.dataframe(df, use_container_width=True)
                                    st.markdown("---")
                        
                        # Download button
                        with open(excel_file, "rb") as f:
                            st.download_button(
                                label=f"📥 Download {excel_file.name}",
                                data=f.read(),
                                file_name=excel_file.name,
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key=f"download_{i}"
                            )
                            
                    except Exception as e:
                        st.error(f"Error reading Excel file: {str(e)}")
                        # Still provide download option
                        with open(excel_file, "rb") as f:
                            st.download_button(
                                label=f"📥 Download {excel_file.name}",
                                data=f.read(),
                                file_name=excel_file.name,
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key=f"download_{i}"
                            )
    
    else:
        st.info("👆 Please upload a PDF file to begin the loss run ingestion process.")
    
    # Sidebar information
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Processing Status")
    st.sidebar.write(f"**Status:** {st.session_state.processing_status}")
    
    if st.session_state.uploaded_file:
        st.sidebar.write(f"**File:** {st.session_state.uploaded_file.name}")
    
    if st.session_state.processing_complete:
        st.sidebar.write(f"**Output Files:** {len(st.session_state.output_files)}")
    
    # Reset button
    if st.sidebar.button("🔄 Reset Session"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


if __name__ == "__main__":
    main()
