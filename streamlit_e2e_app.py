#!/usr/bin/env python3
import streamlit as st
import os
import subprocess
import time
import pandas as pd
from pathlib import Path
import shutil
from datetime import datetime
import fitz  # PyMuPDF - PDF processing library


# Page configuration
st.set_page_config(
    page_title="Loss Run Processing System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Add logo to sidebar (upper left)
def display_logo():
    """Display logo from logo folder in the sidebar"""
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🏢 Company Logo")
    
    # Create logo directory if it doesn't exist
    logo_dir = Path("logo")
    logo_dir.mkdir(exist_ok=True)
    
    # Look for logo files in the logo folder
    logo_extensions = [".png", ".jpg", ".jpeg", ".gif", ".svg", ".bmp"]
    logo_file = None
    
    for ext in logo_extensions:
        # Try different common logo names
        for name in ["logo", "company_logo", "brand_logo", "main_logo"]:
            potential_logo = logo_dir / f"{name}{ext}"
            if potential_logo.exists():
                logo_file = potential_logo
                break
        if logo_file:
            break
    
    # Display logo if found
    if logo_file:
        try:
            st.sidebar.image(str(logo_file), width=200, caption="")
        except Exception as e:
            st.sidebar.error(f"Error loading logo: {e}")
            # Fallback to text logo
            display_text_logo()
    else:
        # Fallback to text-based logo if no image found
        display_text_logo()
        st.sidebar.info("💡 Add your logo to the 'logo' folder (logo.png, logo.jpg, etc.)")

def display_text_logo():
    """Display text-based logo as fallback"""
    st.sidebar.markdown("""
    <div style="text-align: center; padding: 1rem; background-color: #f0f2f6; border-radius: 0.5rem; margin: 1rem 0;">
        <h3 style="color: #1f77b4; margin: 0;">📊</h3>
        <h4 style="color: #2e8b57; margin: 0.5rem 0;">Loss Run</h4>
        <p style="color: #666; margin: 0; font-size: 0.8rem;">Processing System</p>
    </div>
    """, unsafe_allow_html=True)

# Custom CSS
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
    .processing-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        color: #856404;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'uploaded_file' not in st.session_state:
    st.session_state.uploaded_file = None
if 'processing_complete' not in st.session_state:
    st.session_state.processing_complete = False
if 'result_file' not in st.session_state:
    st.session_state.result_file = None
if 'processing_status' not in st.session_state:
    st.session_state.processing_status = "Ready"


def create_directories():
    """Create necessary directories"""
    backup_dir = Path("./backup")
    tmp_dir = Path("./tmp")
    results_dir = Path("./results")
    
    backup_dir.mkdir(exist_ok=True)
    tmp_dir.mkdir(exist_ok=True)
    results_dir.mkdir(exist_ok=True)
    
    return backup_dir, tmp_dir, results_dir


def save_to_backup(uploaded_file, backup_dir):
    """Save uploaded file to backup directory"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{uploaded_file.name}"
    file_path = backup_dir / filename
    
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    return file_path


def convert_pdf_to_text(pdf_path, tmp_dir):
    """Convert PDF to text using fitzTest3.py"""
    try:
        cmd = ["python", "fitzTest3.py", str(pdf_path), "--output", str(tmp_dir)]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout
        )
        
        if result.returncode == 0:
            # Extract text file path from output
            output_lines = result.stdout.strip().split('\n')
            for line in output_lines:
                if line.startswith("SUCCESS:"):
                    return line.replace("SUCCESS:", "").strip()
        
        return None, result.stderr
        
    except subprocess.TimeoutExpired:
        return None, "PDF conversion timed out"
    except Exception as e:
        return None, str(e)


def process_text_file(text_file_path, results_dir, original_pdf_name):
    """Process text file using text_lob_llm_extractor.py"""
    try:
        # Create output directory for this specific file
        output_dir = results_dir / original_pdf_name.replace('.pdf', '')
        output_dir.mkdir(exist_ok=True)
        
        cmd = [
            "python", "text_lob_llm_extractor.py",
            str(text_file_path),
            "--config", "config.py",
            "--out", str(output_dir)
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode == 0:
            # Find the generated Excel file
            excel_files = list(output_dir.glob("*.xlsx"))
            if excel_files:
                # Rename to original PDF name
                result_file = output_dir / f"{original_pdf_name.replace('.pdf', '')}.xlsx"
                shutil.copy2(excel_files[0], result_file)
                return str(result_file), None
            else:
                return None, "No Excel file generated"
        
        return None, result.stderr
        
    except subprocess.TimeoutExpired:
        return None, "Text processing timed out"
    except Exception as e:
        return None, str(e)


def preview_pdf(pdf_path):
    """Generate a simple PDF preview using PyMuPDF (fitz)"""
    try:
        doc = fitz.open(pdf_path)  # PyMuPDF
        
        # Get first page for preview
        page = doc.load_page(0)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # PyMuPDF 2x zoom
        img_data = pix.tobytes("png")
        
        doc.close()
        
        return img_data
    except Exception as e:
        st.error(f"Error generating preview: {e}")
        return None


def main():
    # Display logo in sidebar (upper left)
    display_logo()
    
    # Header
    st.markdown('<h1 class="main-header">📊 Loss Run Processing System</h1>', unsafe_allow_html=True)
    
    # Create directories
    backup_dir, tmp_dir, results_dir = create_directories()
    
    # Step 1: File Upload
    st.markdown('<h2 class="step-header">Step 1: Upload PDF File</h2>', unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader(
        "Choose a PDF file for loss run processing",
        type=['pdf'],
        help="Upload a PDF file containing loss run data"
    )
    
    if uploaded_file is not None:
        # Save to backup
        backup_path = save_to_backup(uploaded_file, backup_dir)
        st.session_state.uploaded_file = backup_path
        
        # Show file info
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("File Name", uploaded_file.name)
        with col2:
            st.metric("File Size", f"{uploaded_file.size / 1024:.1f} KB")
        with col3:
            st.metric("Upload Time", datetime.now().strftime("%H:%M:%S"))
        
        st.markdown('<div class="success-box">✅ File uploaded to backup successfully!</div>', unsafe_allow_html=True)
        
        # Step 2: Preview
        st.markdown('<h2 class="step-header">Step 2: File Preview</h2>', unsafe_allow_html=True)
        
        if st.button("📄 Generate Preview"):
            with st.spinner("Generating preview..."):
                img_data = preview_pdf(backup_path)
                if img_data:
                    st.image(img_data, caption="PDF Preview (First Page)", use_column_width=True)
                else:
                    st.info("Preview not available. File will be processed normally.")
        
        # Step 3: Processing
        st.markdown('<h2 class="step-header">Step 3: Process File</h2>', unsafe_allow_html=True)
        
        if st.button("🚀 Start Processing", type="primary", disabled=st.session_state.processing_status == "Processing"):
            st.session_state.processing_status = "Processing"
            
            # Create progress containers
            progress_bar = st.progress(0)
            status_text = st.empty()
            log_container = st.empty()
            
            try:
                # Step 1: Convert PDF to text
                status_text.text("Step 1/3: Converting PDF to text...")
                progress_bar.progress(0.2)
                
                text_file_path, error = convert_pdf_to_text(backup_path, tmp_dir)
                
                if not text_file_path:
                    st.session_state.processing_status = "Error"
                    st.markdown('<div class="error-box">❌ PDF conversion failed</div>', unsafe_allow_html=True)
                    st.error(f"Error: {error}")
                    return
                
                with log_container.expander("PDF Conversion Log", expanded=False):
                    st.text(f"✅ Text file created: {text_file_path}")
                
                # Step 2: Process text file
                status_text.text("Step 2/3: Processing text with LLM...")
                progress_bar.progress(0.6)
                
                result_file_path, error = process_text_file(text_file_path, results_dir, uploaded_file.name)
                
                if not result_file_path:
                    st.session_state.processing_status = "Error"
                    st.markdown('<div class="error-box">❌ Text processing failed</div>', unsafe_allow_html=True)
                    st.error(f"Error: {error}")
                    return
                
                # Step 3: Complete
                status_text.text("Step 3/3: Finalizing results...")
                progress_bar.progress(1.0)
                
                st.session_state.processing_complete = True
                st.session_state.result_file = result_file_path
                st.session_state.processing_status = "Complete"
                
                st.markdown('<div class="success-box">🎉 Processing completed successfully!</div>', unsafe_allow_html=True)
                
            except Exception as e:
                st.session_state.processing_status = "Error"
                st.markdown('<div class="error-box">❌ Processing failed with exception</div>', unsafe_allow_html=True)
                st.error(f"Exception: {str(e)}")
        
        # Step 4: Results
        if st.session_state.processing_complete and st.session_state.result_file:
            st.markdown('<h2 class="step-header">Step 4: Results & Download</h2>', unsafe_allow_html=True)
            
            result_file = Path(st.session_state.result_file)
            
            if result_file.exists():
                st.markdown('<div class="info-box">📊 Processing Results:</div>', unsafe_allow_html=True)
                
                # Show file info
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Result File", result_file.name)
                with col2:
                    st.metric("File Size", f"{result_file.stat().st_size / 1024:.1f} KB")
                with col3:
                    st.metric("Generated", datetime.fromtimestamp(result_file.stat().st_mtime).strftime("%H:%M:%S"))
                
                # Preview Excel content
                try:
                    excel_data = pd.read_excel(result_file, sheet_name=None)
                    
                    if len(excel_data) == 1:
                        # Single sheet
                        sheet_name = list(excel_data.keys())[0]
                        df = excel_data[sheet_name]
                        st.write(f"**Sheet:** {sheet_name}")
                        st.dataframe(df, use_container_width=True)
                    else:
                        # Multiple sheets
                        for sheet_name, df in excel_data.items():
                            with st.expander(f"📄 {sheet_name}", expanded=(sheet_name == list(excel_data.keys())[0])):
                                st.dataframe(df, use_container_width=True)
                    
                except Exception as e:
                    st.warning(f"Could not preview Excel content: {e}")
                
                # Download button
                with open(result_file, "rb") as f:
                    st.download_button(
                        label="📥 Download Excel File",
                        data=f.read(),
                        file_name=result_file.name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary"
                    )
                
            else:
                st.error("Result file not found!")
    
    else:
        st.info("👆 Please upload a PDF file to begin the loss run processing.")
    
    # Sidebar
    st.sidebar.title("Processing Status")
    st.sidebar.markdown("---")
    st.sidebar.write(f"**Status:** {st.session_state.processing_status}")
    
    if st.session_state.uploaded_file:
        st.sidebar.write(f"**File:** {Path(st.session_state.uploaded_file).name}")
    
    if st.session_state.result_file:
        st.sidebar.write(f"**Result:** {Path(st.session_state.result_file).name}")
    
    # Reset button
    if st.sidebar.button("🔄 Reset Session"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    
    # Directory info
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Directory Structure")
    st.sidebar.write(f"**Backup:** {backup_dir}")
    st.sidebar.write(f"**Temp:** {tmp_dir}")
    st.sidebar.write(f"**Results:** {results_dir}")


if __name__ == "__main__":
    main()
