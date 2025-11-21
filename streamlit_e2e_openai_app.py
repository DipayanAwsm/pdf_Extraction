#!/usr/bin/env python3
import streamlit as st
import os
import subprocess
import time
import pandas as pd
from pathlib import Path
import shutil
from datetime import datetime
import altair as alt
import io
import importlib.util
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None
from PIL import Image

# Load configuration
try:
    from streamlit_config import (
        PYTHON_CMD, CONFIG_FILE, OCR_TIMEOUT, LOB_TIMEOUT, SHOW_DEBUG_INFO, SHOW_COMMAND_OUTPUT
    )
except ImportError:
    PYTHON_CMD = "python"
    CONFIG_FILE = "config.py"
    OCR_TIMEOUT = 1200
    LOB_TIMEOUT = 1800
    SHOW_DEBUG_INFO = True
    SHOW_COMMAND_OUTPUT = True

# Page configuration
st.set_page_config(
    page_title="Loss Run Processing System (OpenAI)",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Add logo to sidebar
def display_logo():
    """Display logo from logo folder in the sidebar"""
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🏢 Company Logo")
    
    logo_dir = Path("logo")
    logo_dir.mkdir(exist_ok=True)
    
    logo_extensions = [".png", ".jpg", ".jpeg", ".gif", ".svg", ".bmp"]
    logo_file = None
    
    for ext in logo_extensions:
        for name in ["logo", "company_logo", "brand_logo", "main_logo"]:
            potential_logo = logo_dir / f"{name}{ext}"
            if potential_logo.exists():
                logo_file = potential_logo
                break
        if logo_file:
            break
    
    if logo_file:
        try:
            st.sidebar.image(str(logo_file), width=200, caption="")
        except Exception as e:
            st.sidebar.error(f"Error loading logo: {e}")
            display_text_logo()
    else:
        display_text_logo()
        st.sidebar.info("Add your logo to the 'logo' folder (logo.png, logo.jpg, etc.)")

def display_text_logo():
    """Display text-based logo as fallback"""
    st.sidebar.markdown("""
    <div style="text-align: center; padding: 1rem; background-color: #f0f2f6; border-radius: 0.5rem; margin: 1rem 0;">
        <h3 style="color: #1f77b4; margin: 0;">🤖</h3>
        <h4 style="color: #2e8b57; margin: 0.5rem 0;">Loss Run</h4>
        <p style="color: #666; margin: 0; font-size: 0.8rem;">Processing System (OpenAI)</p>
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
    .metric-card {
        padding: 1rem;
        border-radius: 0.75rem;
        border: 1px solid #e6e6e6;
        background: linear-gradient(180deg, #ffffff 0%, #f7f9fc 100%);
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        margin-bottom: 1rem;
    }
    .metric-title {
        font-size: 0.9rem;
        color: #6b7280;
        margin-bottom: 0.35rem;
    }
    .metric-value {
        font-size: 1.6rem;
        font-weight: 700;
        color: #111827;
        margin-bottom: 0.25rem;
    }
    .metric-subtle {
        font-size: 0.8rem;
        color: #6b7280;
    }
    .time-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #e7f3ff;
        border: 1px solid #b3d9ff;
        color: #004085;
        font-weight: bold;
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
if 'processing_times' not in st.session_state:
    st.session_state.processing_times = {}
if 'debug_mode' not in st.session_state:
    st.session_state.debug_mode = False  # Default to OFF
if 'debug_logs' not in st.session_state:
    st.session_state.debug_logs = []
if 'pdf_pages' not in st.session_state:
    st.session_state.pdf_pages = []

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

def convert_pdf_to_text(pdf_path, tmp_dir, debug_log_container=None):
    """Convert PDF to text using fitzTest3.py"""
    try:
        cmd = [PYTHON_CMD, "fitzTest3.py", str(pdf_path), "--output", str(tmp_dir)]
        
        if st.session_state.debug_mode and debug_log_container:
            # Real-time output capture
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            output_lines = []
            log_buffer = []
            for line in process.stdout:
                line = line.rstrip()
                if line:
                    output_lines.append(line)
                    log_line = f"[PDF->Text] {line}"
                    log_buffer.append(log_line)
                    st.session_state.debug_logs.append(log_line)
            
            # Update debug log container with all lines
            if debug_log_container and log_buffer:
                debug_log_container.code('\n'.join(log_buffer), language='text')
            
            process.wait()
            result_code = process.returncode
            stdout_text = '\n'.join(output_lines)
        else:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=OCR_TIMEOUT
            )
            result_code = result.returncode
            stdout_text = result.stdout
        
        if result_code == 0:
            output_lines = stdout_text.strip().split('\n')
            for line in output_lines:
                if line.startswith("SUCCESS:"):
                    return line.replace("SUCCESS:", "").strip(), None
            time.sleep(0.5)
            txts = list(Path(tmp_dir).glob("*_extracted.txt"))
            if txts:
                return str(txts[0]), None
            return None, "Text file not found after conversion"
        
        return None, stdout_text or "Conversion failed"
        
    except subprocess.TimeoutExpired:
        return None, "PDF conversion timed out"
    except Exception as e:
        return None, str(e)

def process_text_with_openai(text_file_path, results_dir, original_pdf_name, debug_log_container=None):
    """Process text file using text_lob_openai_extractor.py"""
    try:
        # Create timestamped output directory with original filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        original_name_no_ext = Path(original_pdf_name).stem
        output_dir_name = f"{original_name_no_ext}_{timestamp}"
        output_dir = results_dir / output_dir_name
        output_dir.mkdir(exist_ok=True)
        
        cmd = [
            PYTHON_CMD, "text_lob_openai_extractor.py",
            str(text_file_path),
            "--config", CONFIG_FILE,
            "--out", str(output_dir)
        ]
        
        if st.session_state.debug_mode and debug_log_container:
            # Real-time output capture
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            output_lines = []
            log_buffer = []
            for line in process.stdout:
                line = line.rstrip()
                if line:
                    output_lines.append(line)
                    log_line = f"[OpenAI] {line}"
                    log_buffer.append(log_line)
                    st.session_state.debug_logs.append(log_line)
            
            # Update debug log container with all lines
            if debug_log_container and log_buffer:
                debug_log_container.code('\n'.join(log_buffer), language='text')
            
            process.wait()
            result_code = process.returncode
            stderr_text = '\n'.join(output_lines)
        else:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=LOB_TIMEOUT
            )
            result_code = result.returncode
            stderr_text = result.stderr
        
        if result_code == 0:
            excel_files = list(output_dir.glob("result.xlsx"))
            if excel_files:
                # Rename result.xlsx to include original filename and timestamp
                original_result = excel_files[0]
                new_filename = f"{original_name_no_ext}_{timestamp}_result.xlsx"
                final_result_path = output_dir / new_filename
                
                # Copy the file with new name
                shutil.copy2(original_result, final_result_path)
                
                return str(final_result_path), None
            return None, "Extraction completed but result.xlsx not found"
        
        return None, stderr_text or "Extraction failed"
        
    except subprocess.TimeoutExpired:
        return None, "OpenAI extraction timed out"
    except Exception as e:
        return None, str(e)

def _normalize_colname(name: str) -> str:
    return ''.join(c for c in name.lower() if c.isalnum())

def _coerce_money(value):
    if pd.isna(value):
        return 0.0
    try:
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value)
        negative = False
        s = s.strip()
        if s.startswith('(') and s.endswith(')'):
            negative = True
            s = s[1:-1]
        s = s.replace('$', '').replace(',', '').replace(' ', '')
        if s == '' or s == '-':
            return 0.0
        num = float(s)
        return -num if negative else num
    except Exception:
        return 0.0

def _find_first_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    if df is None or df.empty:
        return None
    norm_map = {_normalize_colname(c): c for c in df.columns}
    for cand in candidates:
        if cand in norm_map:
            return norm_map[cand]
    return None

def format_time(seconds):
    """Format seconds into readable time string"""
    if seconds < 60:
        return f"{seconds:.2f} seconds"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes} minutes {secs:.1f} seconds"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours} hours {minutes} minutes {secs:.1f} seconds"

def main():
    display_logo()
    
    st.markdown('<h1 class="main-header">🤖 Loss Run Processing System (OpenAI)</h1>', unsafe_allow_html=True)
    
    backup_dir, tmp_dir, results_dir = create_directories()
    
    # Step 1: File Upload
    st.markdown('<h2 class="step-header">Step 1: Upload PDF File</h2>', unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader(
        "Choose a PDF file for loss run processing",
        type=['pdf'],
        help="Upload a PDF file containing loss run data"
    )
    
    if uploaded_file is not None:
        backup_path = save_to_backup(uploaded_file, backup_dir)
        st.session_state.uploaded_file = backup_path
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("File Name", uploaded_file.name)
        with col2:
            st.metric("File Size", f"{uploaded_file.size / 1024:.1f} KB")
        with col3:
            st.metric("Upload Time", datetime.now().strftime("%H:%M:%S"))
        
        st.markdown('<div class="success-box">[SUCCESS] File uploaded to backup successfully!</div>', unsafe_allow_html=True)
        
        # Step 2: PDF Preview
        st.markdown('<h2 class="step-header">Step 2: PDF Preview</h2>', unsafe_allow_html=True)
        
        if fitz is None:
            st.warning("⚠️ PyMuPDF (fitz) is not installed. Install with: `pip install PyMuPDF`")
        else:
            try:
                doc = fitz.open(backup_path)
                total_pages = len(doc)
                
                @st.cache_data(show_spinner=False)
                def _render_page_with_fitz(pdf_path: str, page_num: int, zoom: float = 1.5):
                    """Render a single PDF page using PyMuPDF"""
                    try:
                        doc = fitz.open(pdf_path)
                        if page_num < 1 or page_num > len(doc):
                            return None
                        page = doc[page_num - 1]  # 0-indexed
                        mat = fitz.Matrix(zoom, zoom)  # Zoom factor for quality
                        pix = page.get_pixmap(matrix=mat)
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        doc.close()
                        return img
                    except Exception as e:
                        return None
                
                col_preview, col_large = st.columns([3, 2])
                
                with col_preview:
                    st.caption("📑 Preview thumbnails (first pages)")
                    max_preview_pages = min(6, total_pages)
                    
                    # Render thumbnails in 2-column grid
                    rows = []
                    for i in range(0, max_preview_pages, 2):
                        rows.append((i+1, min(i+2, max_preview_pages)))
                    
                    for start_page, end_page in rows:
                        c1, c2 = st.columns(2)
                        for idx, page_num in enumerate(range(start_page, end_page + 1)):
                            with (c1 if idx == 0 else c2):
                                thumb_img = _render_page_with_fitz(str(backup_path), page_num, zoom=1.0)
                                if thumb_img:
                                    st.image(thumb_img, use_container_width=True, caption=f"Page {page_num}")
                                else:
                                    st.info(f"Could not render page {page_num}")
                
                with col_large:
                    st.caption("🔍 Large preview")
                    page_num = st.number_input("Page to preview", min_value=1, max_value=total_pages, value=1, step=1)
                    
                    large_img = _render_page_with_fitz(str(backup_path), page_num, zoom=2.0)
                    if large_img:
                        st.image(large_img, use_container_width=True, caption=f"Page {page_num} of {total_pages}")
                    else:
                        st.info("Preview not available for this page.")
                
                with st.expander("File Details", expanded=False):
                    st.write(f"**File Path:** {backup_path}")
                    st.write(f"**Total Pages:** {total_pages}")
                    st.write(f"**File Size:** {uploaded_file.size / 1024:.1f} KB")
                    st.write(f"**MIME Type:** {uploaded_file.type}")
                    
                    # Additional PDF metadata
                    try:
                        metadata = doc.metadata
                        if metadata:
                            st.write("**PDF Metadata:**")
                            for key, value in metadata.items():
                                if value:
                                    st.write(f"  - {key}: {value}")
                    except:
                        pass
                
                doc.close()
                
            except Exception as e:
                st.error(f"⚠️ Could not load PDF for preview: {str(e)}")
                st.info("💡 Make sure the PDF file is valid and not corrupted.")
        
        # Step 3: Processing
        st.markdown('<h2 class="step-header">Step 2: Process File with OpenAI</h2>', unsafe_allow_html=True)
        
        # Debug mode toggle
        debug_mode = st.checkbox("🐛 Debug Mode (Show Real-time Logs)", value=st.session_state.debug_mode)
        st.session_state.debug_mode = debug_mode
        
        if st.button("🚀 Start Processing", type="primary", disabled=st.session_state.processing_status == "Processing"):
            st.session_state.processing_status = "Processing"
            st.session_state.processing_times = {}
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            log_container = st.empty()
            debug_log_container = st.empty() if st.session_state.debug_mode else None
            
            # Clear debug logs at start
            if st.session_state.debug_mode:
                st.session_state.debug_logs = []
            
            try:
                start_total = time.time()
                
                # Step 1: Convert PDF to text
                status_text.text("Step 1/3: Converting PDF to text...")
                progress_bar.progress(0.2)
                
                if st.session_state.debug_mode:
                    st.markdown("**📋 Real-time Debug Logs (PDF to Text):**")
                    debug_placeholder = st.empty()
                else:
                    debug_placeholder = None
                
                start_ocr = time.time()
                text_file_path, error = convert_pdf_to_text(backup_path, tmp_dir, debug_placeholder)
                ocr_time = time.time() - start_ocr
                st.session_state.processing_times['PDF to Text'] = ocr_time
                
                if not text_file_path:
                    st.session_state.processing_status = "Error"
                    st.markdown('<div class="error-box">[ERROR] PDF conversion failed</div>', unsafe_allow_html=True)
                    st.error(f"Error: {error}")
                    return
                
                with log_container.expander("PDF Conversion Log", expanded=False):
                    st.text(f"[SUCCESS] Text file created: {text_file_path}")
                    st.text(f"Time taken: {format_time(ocr_time)}")
                
                # Step 2: Process with OpenAI
                status_text.text("Step 2/3: Processing text with OpenAI...")
                progress_bar.progress(0.6)
                
                if st.session_state.debug_mode:
                    st.markdown("**📋 Real-time Debug Logs (OpenAI Extraction):**")
                    debug_placeholder_openai = st.empty()
                else:
                    debug_placeholder_openai = None
                
                start_openai = time.time()
                result_file_path, error = process_text_with_openai(
                    text_file_path,
                    results_dir,
                    uploaded_file.name,
                    debug_placeholder_openai
                )
                openai_time = time.time() - start_openai
                st.session_state.processing_times['OpenAI Extraction'] = openai_time
                
                if not result_file_path:
                    st.session_state.processing_status = "Error"
                    st.markdown('<div class="error-box">[ERROR] OpenAI extraction failed</div>', unsafe_allow_html=True)
                    st.error(f"Error: {error}")
                    return
                
                # Step 3: Complete
                total_time = time.time() - start_total
                st.session_state.processing_times['Total Time'] = total_time
                
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
        
        # Step 4: Results & Summary
        if st.session_state.processing_complete and st.session_state.result_file:
            st.markdown('<h2 class="step-header">Step 3: Results & Summary</h2>', unsafe_allow_html=True)
            
            result_file = Path(st.session_state.result_file)
            
            if result_file.exists():
                # Display processing times
                if st.session_state.processing_times:
                    st.markdown('<h3 class="step-header">⏱️ Processing Times</h3>', unsafe_allow_html=True)
                    times_df = pd.DataFrame([
                        {"Step": k, "Time (seconds)": v, "Formatted": format_time(v)}
                        for k, v in st.session_state.processing_times.items()
                    ])
                    st.dataframe(times_df[["Step", "Formatted"]], use_container_width=True, hide_index=True)
                
                st.markdown('<div class="info-box">[RESULTS] Processing Results:</div>', unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Result File", result_file.name)
                with col2:
                    st.metric("File Size", f"{result_file.stat().st_size / 1024:.1f} KB")
                with col3:
                    st.metric("Generated", datetime.fromtimestamp(result_file.stat().st_mtime).strftime("%H:%M:%S"))
                
                # Preview Excel content
                try:
                    time.sleep(0.3)
                    excel_data = pd.read_excel(result_file, sheet_name=None)
                    
                    # Summary section
                    with st.expander("📊 Summary (click to expand/contract)", expanded=True):
                        try:
                            lob_detail_rows = []
                            claims_rows = []
                            
                            for sheet_name, df in excel_data.items():
                                if df is None or df.empty:
                                    continue
                                sn = str(sheet_name).lower()
                                
                                if 'auto' in sn:
                                    lob_key = 'AUTO'
                                elif 'property' in sn:
                                    lob_key = 'PROPERTY'
                                elif 'gl' in sn and 'claim' in sn:
                                    lob_key = 'GL'
                                elif 'wc' in sn and 'claim' in sn:
                                    lob_key = 'WC'
                                else:
                                    continue
                                
                                norm_cols = {_normalize_colname(c): c for c in df.columns}
                                
                                def col_exact(norm_name):
                                    return norm_cols.get(norm_name)
                                
                                claim_col = col_exact("claimnumber") or col_exact("claimno") or col_exact("claim") or col_exact("claimid")
                                alae_col = col_exact("alae") or col_exact("totalalae") or col_exact("expense") or col_exact("totalexpense")
                                alae_vals = pd.Series(df[alae_col]).map(_coerce_money) if alae_col else pd.Series([0.0]*len(df))
                                alae_sum = float(alae_vals.sum())
                                
                                if lob_key in ['AUTO', 'PROPERTY']:
                                    paid_col = col_exact("paidloss") or col_exact("paid_loss")
                                    losses = pd.Series(df[paid_col]).map(_coerce_money) if paid_col else pd.Series([0.0]*len(df))
                                    total_loss = float(losses.sum())
                                    claim_count = int(df[claim_col].astype(str).str.strip().ne("").sum()) if claim_col else int(len(df))
                                    lob_detail_rows.append({
                                        "LOB": lob_key,
                                        "Total Loss": total_loss,
                                        "Total ALAE": alae_sum,
                                        "BI Paid Loss": 0.0,
                                        "PD Paid Loss": 0.0,
                                        "Indemnity Paid Loss": 0.0,
                                        "Medical Paid Loss": 0.0,
                                        "Claim Count": claim_count
                                    })
                                    if claim_col:
                                        claims_rows.append(pd.DataFrame({
                                            "claim_number": df[claim_col].astype(str),
                                            "loss": losses.astype(float),
                                            "alae": alae_vals.astype(float),
                                            "lob": lob_key,
                                        }))
                                
                                elif lob_key == 'GL':
                                    bi_col = col_exact("bodilyinjurypaidloss") or col_exact("bipaidloss")
                                    pd_col = col_exact("propertydamagepaidloss") or col_exact("pdpaidloss")
                                    bi_vals = pd.Series(df[bi_col]).map(_coerce_money) if bi_col else pd.Series([0.0]*len(df))
                                    pd_vals = pd.Series(df[pd_col]).map(_coerce_money) if pd_col else pd.Series([0.0]*len(df))
                                    bi_sum = float(bi_vals.sum())
                                    pd_sum = float(pd_vals.sum())
                                    total_loss = bi_sum + pd_sum
                                    claim_count = int(df[claim_col].astype(str).str.strip().ne("").sum()) if claim_col else int(len(df))
                                    lob_detail_rows.append({
                                        "LOB": 'GL',
                                        "Total Loss": total_loss,
                                        "Total ALAE": alae_sum,
                                        "BI Paid Loss": bi_sum,
                                        "PD Paid Loss": pd_sum,
                                        "Indemnity Paid Loss": 0.0,
                                        "Medical Paid Loss": 0.0,
                                        "Claim Count": claim_count
                                    })
                                    if claim_col:
                                        claims_rows.append(pd.DataFrame({
                                            "claim_number": df[claim_col].astype(str),
                                            "loss": (bi_vals.add(pd_vals, fill_value=0.0)).astype(float),
                                            "alae": alae_vals.astype(float),
                                            "lob": 'GL',
                                        }))
                                
                                elif lob_key == 'WC':
                                    ind_col = col_exact("indemnity_paid_loss") or col_exact("indemnitypaidloss")
                                    med_col = col_exact("medical_paid_loss") or col_exact("medicalpaidloss")
                                    ind_vals = pd.Series(df[ind_col]).map(_coerce_money) if ind_col else pd.Series([0.0]*len(df))
                                    med_vals = pd.Series(df[med_col]).map(_coerce_money) if med_col else pd.Series([0.0]*len(df))
                                    ind_sum = float(ind_vals.sum())
                                    med_sum = float(med_vals.sum())
                                    total_loss = ind_sum + med_sum
                                    claim_count = int(df[claim_col].astype(str).str.strip().ne("").sum()) if claim_col else int(len(df))
                                    lob_detail_rows.append({
                                        "LOB": 'WC',
                                        "Total Loss": total_loss,
                                        "Total ALAE": alae_sum,
                                        "BI Paid Loss": 0.0,
                                        "PD Paid Loss": 0.0,
                                        "Indemnity Paid Loss": ind_sum,
                                        "Medical Paid Loss": med_sum,
                                        "Claim Count": claim_count
                                    })
                                    if claim_col:
                                        claims_rows.append(pd.DataFrame({
                                            "claim_number": df[claim_col].astype(str),
                                            "loss": (ind_vals.add(med_vals, fill_value=0.0)).astype(float),
                                            "alae": alae_vals.astype(float),
                                            "lob": 'WC',
                                        }))
                            
                            if not lob_detail_rows:
                                st.info("No data available for summary.")
                            else:
                                lob_detail_df = pd.DataFrame(lob_detail_rows)
                                agg_map = {
                                    "Total Loss": "sum",
                                    "Total ALAE": "sum",
                                    "BI Paid Loss": "sum",
                                    "PD Paid Loss": "sum",
                                    "Indemnity Paid Loss": "sum",
                                    "Medical Paid Loss": "sum",
                                    "Claim Count": "sum",
                                }
                                lob_totals = lob_detail_df.groupby("LOB", as_index=False).agg(agg_map)
                                lob_totals["Avg Claim"] = lob_totals.apply(lambda r: (r["Total Loss"] / r["Claim Count"]) if r["Claim Count"] else 0.0, axis=1)
                                
                                # Display metrics
                                cols = st.columns(min(len(lob_totals), 4))
                                for idx, row in lob_totals.iterrows():
                                    with cols[idx % len(cols)]:
                                        st.markdown(f"""
                                        <div class="metric-card">
                                            <div class="metric-title">{row['LOB']}</div>
                                            <div class="metric-value">${row['Total Loss']:,.2f}</div>
                                            <div class="metric-subtle">Claims: {int(row['Claim Count'])} | Avg: ${row['Avg Claim']:,.2f}</div>
                                        </div>
                                        """, unsafe_allow_html=True)
                                
                                # Charts
                                if claims_rows:
                                    claims_df = pd.concat(claims_rows, ignore_index=True)
                                    for lob_filter in ["AUTO", "PROPERTY", "WC", "GL"]:
                                        sub = claims_df[claims_df["lob"]==lob_filter]
                                        if sub.empty:
                                            continue
                                        tops = sub.groupby("claim_number", as_index=False)["loss"].sum().sort_values("loss", ascending=False).head(10)
                                        if not tops.empty:
                                            chart = alt.Chart(tops).mark_bar().encode(
                                                x=alt.X("claim_number:N", sort='-y', title=f"{lob_filter} Claim Number"),
                                                y=alt.Y("loss:Q", title="Total Loss"),
                                                tooltip=["claim_number","loss"]
                                            ).properties(title=f"Top 10 Claims by Loss - {lob_filter}")
                                            st.altair_chart(chart, use_container_width=True)
                                
                                pie = alt.Chart(lob_totals).mark_arc().encode(
                                    theta=alt.Theta(field="Total Loss", type="quantitative"),
                                    color=alt.Color(field="LOB", type="nominal"),
                                    tooltip=["LOB","Total Loss","Total ALAE","Claim Count","Avg Claim"]
                                ).properties(title="LOB-wise Total Loss (Pie)")
                                st.altair_chart(pie, use_container_width=True)
                                
                        except Exception as e:
                            st.warning(f"Could not build summary: {e}")
                    
                    # Display sheets
                    if len(excel_data) == 1:
                        sheet_name = list(excel_data.keys())[0]
                        df = excel_data[sheet_name]
                        st.write(f"**Sheet:** {sheet_name}")
                        st.dataframe(df, use_container_width=True)
                    else:
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
    st.sidebar.write(f"**Debug Mode:** {'✅ ON' if st.session_state.debug_mode else '❌ OFF'}")
    
    if st.session_state.uploaded_file:
        st.sidebar.write(f"**File:** {Path(st.session_state.uploaded_file).name}")
    
    if st.session_state.result_file:
        st.sidebar.write(f"**Result:** {Path(st.session_state.result_file).name}")
    
    # Debug logs in sidebar
    if st.session_state.debug_mode and st.session_state.debug_logs:
        with st.sidebar.expander("🐛 Debug Logs", expanded=False):
            for log in st.session_state.debug_logs[-50:]:  # Show last 50 lines
                st.text(log)
    
    if st.sidebar.button("🔄 Reset Session"):
        # Reset all session state except debug_mode preference
        debug_pref = st.session_state.get('debug_mode', False)
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.session_state.debug_mode = debug_pref
        st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Directory Structure")
    st.sidebar.write(f"**Backup:** {backup_dir}")
    st.sidebar.write(f"**Temp:** {tmp_dir}")
    st.sidebar.write(f"**Results:** {results_dir}")

if __name__ == "__main__":
    main()

