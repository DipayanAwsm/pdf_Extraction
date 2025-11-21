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
import re
import importlib.util
from pdf2image import convert_from_path
from PIL import Image

# Load configuration
try:
    from streamlit_config import (
        PYTHON_CMD, CONFIG_FILE, ANALYSIS_TIMEOUT, EXTRACTION_TIMEOUT,
        OCR_TIMEOUT, LOB_TIMEOUT, SHOW_DEBUG_INFO, SHOW_COMMAND_OUTPUT
    )
except ImportError:
    # Fallback configuration if streamlit_config.py doesn't exist
    PYTHON_CMD = "python"  # Change to "py" on Windows if needed
    CONFIG_FILE = "config.py"  # Change to your config file path if needed
    ANALYSIS_TIMEOUT = 60
    EXTRACTION_TIMEOUT = 1800
    OCR_TIMEOUT = 1200
    LOB_TIMEOUT = 1800
    SHOW_DEBUG_INFO = True
    SHOW_COMMAND_OUTPUT = True

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
        st.sidebar.info("Add your logo to the 'logo' folder (logo.png, logo.jpg, etc.)")

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
if 'summary_expanded' not in st.session_state:
    st.session_state.summary_expanded = False


def _load_config_module(config_path: str = "config.py"):
    try:
        spec = importlib.util.spec_from_file_location("app_config", config_path)
        if spec and spec.loader:
            cfg = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cfg)
            return cfg
    except Exception:
        return None
    return None


def _determine_engine_from_config(config_path: str = "config.py") -> str:
    cfg = _load_config_module(config_path)
    # Default to Claude
    engine = "claude"
    try:
        if cfg is not None:
            # Prefer explicit override if present
            if hasattr(cfg, "EXTRACTOR_ENGINE"):
                val = str(getattr(cfg, "EXTRACTOR_ENGINE")).strip().lower()
                if val in ("openai", "claude"):
                    return val
            # If OpenAI creds are present, allow switching to openai implicitly
            if getattr(cfg, "OPENAI_API_KEY", None) or getattr(cfg, "USE_AZURE_OPENAI", None):
                engine = "openai"
    except Exception:
        pass
    return engine


# Functions

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
    """Convert PDF to text using fitzTest3.py. Always return (path, error)."""
    try:
        cmd = [PYTHON_CMD, "fitzTest3.py", str(pdf_path), "--output", str(tmp_dir)]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=OCR_TIMEOUT  # OCR processing timeout
        )
        
        if result.returncode == 0:
            # Extract text file path from output
            output_lines = result.stdout.strip().split('\n')
            for line in output_lines:
                if line.startswith("SUCCESS:"):
                    return line.replace("SUCCESS:", "").strip(), None
            # If success but no marker, wait briefly and try to find file
            time.sleep(0.5)
            txts = list(Path(tmp_dir).glob("*_extracted.txt"))
            if txts:
                return str(txts[0]), None
            return None, "Text file not found after conversion"
        
        return None, result.stderr
        
    except subprocess.TimeoutExpired:
        return None, "PDF conversion timed out"
    except Exception as e:
        return None, str(e)


def safe_copy_with_retries(src: Path, dst: Path, retries: int = 5, wait_sec: float = 1.0) -> bool:
    """Copy a file with retries to avoid Windows file-in-use errors."""
    for attempt in range(1, retries + 1):
        try:
            shutil.copy2(src, dst)
            return True
        except PermissionError:
            if attempt == retries:
                return False
            time.sleep(wait_sec)
            wait_sec *= 1.5
        except OSError as e:
            # WinError 32 or similar
            if attempt == retries:
                return False
            time.sleep(wait_sec)
            wait_sec *= 1.5
    return False


def safe_finalize_result(src: Path, desired_dst: Path, retries: int = 6, wait_sec: float = 0.6) -> Path:
    """Try to rename (atomic replace) or copy the src to desired_dst with retries.
    If both fail due to file lock, return the src path to be used as-is.
    """
    # Try os.replace first (atomic move/rename)
    for attempt in range(1, retries + 1):
        try:
            # If src is already the desired file, just return it
            if src.resolve() == desired_dst.resolve():
                return desired_dst
            # Ensure parent exists
            desired_dst.parent.mkdir(parents=True, exist_ok=True)
            os.replace(src, desired_dst)
            return desired_dst
        except Exception:
            if attempt == retries:
                break
            time.sleep(wait_sec)
            wait_sec *= 1.5
    # Try copy2 as fallback
    wait_sec = 0.6
    for attempt in range(1, retries + 1):
        try:
            shutil.copy2(src, desired_dst)
            return desired_dst
        except Exception:
            if attempt == retries:
                # As a last resort, return the original src path to use directly
                return src
            time.sleep(wait_sec)
            wait_sec *= 1.5
    return src


def process_text_file(text_file_path, results_dir, original_pdf_name):
    """Process text file page-by-page via external runner and consolidate results."""
    try:
        # Create output directory for this specific file
        output_dir = results_dir / original_pdf_name.replace('.pdf', '')
        output_dir.mkdir(exist_ok=True)
        
        # Hardcoded best-practice chunking parameters for LLM extractor
        best_max_tokens = 6000
        best_overlap_tokens = 400
        best_chunk_sleep = 0.6
        
        # Resolve engine from config without changing UI
        engine = _determine_engine_from_config("config.py")
        
        cmd = [
            PYTHON_CMD, "pagewise_llm_runner.py",
            str(text_file_path),
            "--config", "config.py",
            "--out", str(output_dir),
            "--max-tokens", str(best_max_tokens),
            "--overlap-tokens", str(best_overlap_tokens),
            "--chunk-sleep", str(best_chunk_sleep),
            "--engine", engine
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=EXTRACTION_TIMEOUT  # allow longer for multi-page processing
        )
        
        if result.returncode == 0:
            # Output path is emitted as SUCCESS:<file>
            out_path = None
            for line in (result.stdout or '').splitlines():
                if line.startswith("SUCCESS:"):
                    out_path = line.replace("SUCCESS:", "").strip()
                    break
            # Fallback search
            if not out_path:
                excel_files = list(output_dir.glob("*.xlsx"))
                if excel_files:
                    out_path = str(excel_files[0])
            if out_path and Path(out_path).exists():
                return out_path, None
            return None, "Runner completed but final Excel not found"
        
        return None, result.stderr or "Runner failed"
        
    except subprocess.TimeoutExpired:
        return None, "Page-wise runner timed out"
    except Exception as e:
        return None, str(e)


## Removed image preview processing to keep app free of image operations


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


def compute_lob_summary(excel_sheets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for sheet_name, df in excel_sheets.items():
        lob = sheet_name.strip().upper()
        n_rows = int(len(df)) if df is not None else 0
        paid_total = 0.0
        alae_total = 0.0
        if df is None or df.empty:
            rows.append({"LOB": lob, "Rows": 0, "Total Paid Loss": 0.0, "Total ALAE": 0.0})
            continue
        # Prepare normalized lookup once
        norm_cols = {_normalize_colname(c): c for c in df.columns}
        def get_col(cands: list[str]):
            for c in cands:
                if c in norm_cols:
                    return norm_cols[c]
            return None
        if lob in ["AUTO", "PROPERTY"]:
            paid_col = get_col(["paidloss", "paid_loss", "paid", "totpaid", "totalpaid"])
            alae_col = get_col(["alae", "totalalae", "expense", "totalexpense"])
            if paid_col:
                paid_total = float(pd.Series(df[paid_col]).map(_coerce_money).sum())
            if alae_col:
                alae_total = float(pd.Series(df[alae_col]).map(_coerce_money).sum())
        elif lob in ["GL", "GENERAL LIABILITY", "GENERALLIABILITY"]:
            bi_col = get_col(["bodilyinjurypaidloss", "bipaidloss", "bodilyinjury", "bodilyinjurypaid"])
            pd_col = get_col(["propertydamagepaidloss", "pdpailoss", "propertydamage", "propertydamagepaid"])
            alae_col = get_col(["alae", "totalalae", "expense", "totalexpense"])
            if bi_col:
                paid_total += float(pd.Series(df[bi_col]).map(_coerce_money).sum())
            if pd_col:
                paid_total += float(pd.Series(df[pd_col]).map(_coerce_money).sum())
            if alae_col:
                alae_total = float(pd.Series(df[alae_col]).map(_coerce_money).sum())
            lob = "GL"
        elif lob in ["WC", "WORKERSCOMP", "WORKERSCOMPENSATION", "WORKERCOMPENSESSASION"]:
            ind_col = get_col(["indemnitypaidloss", "indemnitypaid", "indemnity"])
            med_col = get_col(["medicalpaidloss", "medicalpaid", "medical"])
            alae_col = get_col(["alae", "totalalae", "expense", "totalexpense"])
            if ind_col:
                paid_total += float(pd.Series(df[ind_col]).map(_coerce_money).sum())
            if med_col:
                paid_total += float(pd.Series(df[med_col]).map(_coerce_money).sum())
            if alae_col:
                alae_total = float(pd.Series(df[alae_col]).map(_coerce_money).sum())
            lob = "WC"
        else:
            # Fallback: try generic columns
            paid_col = _find_first_col(df, ["paidloss", "paid", "totalpaid"])
            alae_col = _find_first_col(df, ["alae", "totalalae", "expense", "totalexpense"])
            if paid_col:
                paid_total = float(pd.Series(df[paid_col]).map(_coerce_money).sum())
            if alae_col:
                alae_total = float(pd.Series(df[alae_col]).map(_coerce_money).sum())
        rows.append({
            "LOB": lob,
            "Rows": n_rows,
            "Total Paid Loss": round(paid_total, 2),
            "Total ALAE": round(alae_total, 2)
        })
    return pd.DataFrame(rows)


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
        
        st.markdown('<div class="success-box">[SUCCESS] File uploaded to backup successfully!</div>', unsafe_allow_html=True)
        
        # Step 2: File Preview (thumbnails + large view)
        st.markdown('<h2 class="step-header">Step 2: File Preview</h2>', unsafe_allow_html=True)
        with st.expander("File Details", expanded=False):
            st.write(f"**File Path:** {backup_path}")
            st.write(f"**File Size:** {uploaded_file.size / 1024:.1f} KB")
            st.write(f"**MIME Type:** {uploaded_file.type}")
        
        @st.cache_data(show_spinner=False)
        def _render_pdf_pages_cached(path_str: str, max_pages: int = 6, dpi: int = 120):
            try:
                pages = convert_from_path(path_str, dpi=dpi, first_page=1, last_page=max_pages)
                return pages
            except Exception:
                return []
        
        col_preview, col_large = st.columns([3, 2])
        with col_preview:
            st.caption("Preview thumbnails (first pages)")
            thumbs = _render_pdf_pages_cached(str(backup_path), max_pages=6, dpi=110)
            if thumbs:
                rows = [thumbs[i:i+2] for i in range(0, len(thumbs), 2)]
                for row_imgs in rows:
                    c1, c2 = st.columns(2)
                    for idx, img in enumerate(row_imgs):
                        with (c1 if idx == 0 else c2):
                            st.image(img, use_column_width=True)
            else:
                st.info("No preview available. Ensure Poppler is installed (macOS: brew install poppler).")
        with col_large:
            st.caption("Large preview")
            page_num = st.number_input("Page to preview", min_value=1, max_value=6, value=1, step=1)
            large = _render_pdf_pages_cached(str(backup_path), max_pages=page_num, dpi=160)
            if large:
                st.image(large[-1], use_column_width=True, caption=f"Page {page_num}")
            else:
                st.info("Preview not available for this file.")
        
        # Step 3: Processing
        st.markdown('<h2 class="step-header">Step 3: Process File</h2>', unsafe_allow_html=True)
        
        if st.button("Start Processing", type="primary", disabled=st.session_state.processing_status == "Processing"):
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
                    st.markdown('<div class="error-box">[ERROR] PDF conversion failed</div>', unsafe_allow_html=True)
                    st.error(f"Error: {error}")
                    return
                
                with log_container.expander("PDF Conversion Log", expanded=False):
                    st.text(f"[SUCCESS] Text file created: {text_file_path}")
                
                # Step 2: Process text file
                status_text.text("Step 2/3: Processing text with LLM...")
                progress_bar.progress(0.6)
                
                result_file_path, error = process_text_file(
                    text_file_path,
                    results_dir,
                    uploaded_file.name
                )
                
                if not result_file_path:
                    st.session_state.processing_status = "Error"
                    st.markdown('<div class="error-box">[ERROR] Text processing failed</div>', unsafe_allow_html=True)
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

        # Alternative: Adaptive Table Extraction for Complex PDFs
        st.markdown('<h3 class="step-header">Optional: Adaptive Table Extraction</h3>', unsafe_allow_html=True)
        with st.expander("Smart extraction for complex table structures", expanded=False):
            st.markdown("""
            **Handles all table types:**
            - ✅ Simple bordered tables
            - ✅ Merged/spanned cells  
            - ✅ Nested tables
            - ✅ Page breaks & split tables
            - ✅ Irregular spacing
            - ✅ Tables without borders
            - ✅ 5-200 pages
            """)
            
            col1, col2 = st.columns(2)
            with col1:
                force_strategy = st.selectbox(
                    "Extraction Strategy",
                    ["auto", "camelot_tabula", "claude_text", "claude_image"],
                    help="Auto = smart detection, others = force specific method"
                )
            with col2:
                max_pages = st.number_input("Max Pages", value=50, min_value=5, max_value=200)
            
            if st.button("Analyze PDF Structure", disabled=st.session_state.processing_status == "Processing"):
                try:
                    st.session_state.processing_status = "Processing"
                    with st.spinner("Analyzing PDF structure..."):
                        # Run table type detector (build path in a cross-platform way)
                        analyze_script = str(Path("src") / "claim_extractor" / "table_type_detector.py")
                        cmd_analyze = [
                            PYTHON_CMD, analyze_script, str(backup_path)
                        ]
                        # Ensure Windows resolves the interpreter and paths correctly
                        result = subprocess.run(
                            cmd_analyze,
                            capture_output=True,
                            text=True,
                            timeout=ANALYSIS_TIMEOUT,
                            cwd=str(Path.cwd()),
                            shell=False
                        )
                        
                        if result.returncode == 0:
                            st.success("PDF Analysis Complete")
                            st.text_area("Analysis Results", value=result.stdout, height=200)
                        else:
                            st.warning("Analysis failed, proceeding with adaptive extraction")
                except subprocess.TimeoutExpired:
                    st.session_state.processing_status = "Error"
                    st.error("PDF analysis timed out")
                except Exception as e:
                    st.session_state.processing_status = "Error"
                    st.error(f"PDF analysis failed: {e}")
            
            if st.button("Run Adaptive Extraction", disabled=st.session_state.processing_status == "Processing"):
                try:
                    st.session_state.processing_status = "Processing"
                    with st.spinner("Running adaptive table extraction..."):
                        # Run adaptive extractor (using standalone version to avoid import issues)
                        extract_script = str(Path("adaptive_table_extractor_standalone.py"))
                        cmd_extract = [
                            PYTHON_CMD, extract_script,
                            str(backup_path), "--out", "adaptive_results", "--config", CONFIG_FILE
                        ]
                        if force_strategy != "auto":
                            cmd_extract.extend(["--strategy", force_strategy])
                        
                        result = subprocess.run(
                            cmd_extract,
                            capture_output=True,
                            text=True,
                            timeout=EXTRACTION_TIMEOUT,
                            cwd=str(Path.cwd()),
                            shell=False
                        )
                        
                        # Debug information
                        if SHOW_DEBUG_INFO:
                            st.text(f"Command: {' '.join(cmd_extract)}")
                            st.text(f"Return code: {result.returncode}")
                        if SHOW_COMMAND_OUTPUT and result.stdout:
                            st.text(f"Output: {result.stdout}")
                        if result.stderr:
                            st.text(f"Error: {result.stderr}")
                        
                        if result.returncode == 0:
                            st.success("Adaptive extraction complete!")
                            
                            # Find and display results
                            adaptive_dir = Path("adaptive_results")
                            json_files = list(adaptive_dir.glob(f"{backup_path.stem}_*_tables.json"))
                            excel_files = list(adaptive_dir.glob(f"{backup_path.stem}_*_tables.xlsx"))
                            
                            if json_files or excel_files:
                                st.markdown("**Extracted Files:**")
                                for file in json_files + excel_files:
                                    st.write(f"[FILE] {file.name}")
                                
                                # Show Excel preview if available
                                if excel_files:
                                    try:
                                        excel_data = pd.read_excel(excel_files[0], sheet_name=None)
                                        for sheet_name, df in excel_data.items():
                                            with st.expander(f"[SHEET] {sheet_name}"):
                                                st.dataframe(df, use_container_width=True)
                                    except Exception as e:
                                        st.warning(f"Could not preview Excel: {e}")
                                
                                # Download buttons
                                for file in excel_files:
                                    with open(file, "rb") as f:
                                        st.download_button(
                                            label=f"⬇️ Download {file.name}",
                                            data=f.read(),
                                            file_name=file.name,
                                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                        )
                            else:
                                st.warning("No results found")
                        else:
                            st.error("Adaptive extraction failed")
                            st.text(f"Return code: {result.returncode}")
                            if result.stdout:
                                st.text(f"Output: {result.stdout}")
                            if result.stderr:
                                st.text(f"Error details: {result.stderr}")
                            
                            # Show troubleshooting tips
                            st.markdown("**Troubleshooting Tips:**")
                            st.markdown("""
                            - Check if `config.py` exists and has valid AWS credentials
                            - Ensure all dependencies are installed: `pip install -r requirements.txt`
                            - Try running the command manually in terminal to see detailed error
                            - Check if the PDF file is valid and not corrupted
                            """)
                        
                        st.session_state.processing_status = "Complete"
                        
                except subprocess.TimeoutExpired:
                    st.session_state.processing_status = "Error"
                    st.error("Extraction timed out")
                except Exception as e:
                    st.session_state.processing_status = "Error"
                    st.error(f"Adaptive extraction failed: {e}")
        
        # Legacy: Scripted Claude OCR Text (no in-process LLM; writes to tmp/, then LOB extraction script on text)
        st.markdown('<h3 class="step-header">Legacy: OCR via Claude -> tmp, then LOB Extractor</h3>', unsafe_allow_html=True)
        with st.expander("Run external scripts (no in-app LLM)", expanded=False):
            col_a, col_b, col_c = st.columns([1,1,2])
            with col_a:
                dpi = st.number_input("DPI", value=220, min_value=150, max_value=600, step=10)
            with col_b:
                page_range = st.text_input("Pages (e.g., 1-3 or blank for ALL pages)", value="", 
                                         help="Leave blank to process all pages. Use format like '1-5' for specific range.")
            with col_c:
                cfg_path = st.text_input("Config path", value="config.py")

            if st.button("Run Scripts", disabled=st.session_state.processing_status == "Processing"):
                try:
                    st.session_state.processing_status = "Processing"
                    with st.spinner("Step 1/2: Claude OCR to tmp ..."):
                        # Build command for claude_pdf_image_extractor.py -> tmp text
                        first_last_args = []
                        pr = page_range.replace(" ", "")
                        if pr:
                            if "-" in pr:
                                a, b = pr.split("-", 1)
                                if a.strip():
                                    first_last_args += ["--first", a.strip()]
                                if b.strip():
                                    first_last_args += ["--last", b.strip()]
                            else:
                                first_last_args += ["--first", pr, "--last", pr]

                        tmp_txt_dir = Path("tmp")
                        tmp_txt_dir.mkdir(exist_ok=True)
                        # Output path is internal to the extractor, so we just ensure it writes into a known directory name
                        # We will copy/move the produced file
                        cmd1 = [
                            PYTHON_CMD, "src/claim_extractor/claude_pdf_image_extractor.py",
                            str(backup_path), "--out", str(tmp_txt_dir), "--dpi", str(dpi), "--config", cfg_path
                        ] + first_last_args
                        # Show command being run
                        st.text(f"Command: {' '.join(cmd1)}")
                        
                        res1 = subprocess.run(
                            cmd1,
                            capture_output=True,
                            text=True,
                            timeout=OCR_TIMEOUT,
                            cwd=str(Path.cwd()),
                            shell=False
                        )
                        if res1.returncode != 0:
                            st.session_state.processing_status = "Error"
                            st.error("Claude OCR script failed")
                            st.text(f"Error: {res1.stderr}")
                            st.text(f"Output: {res1.stdout}")
                            return
                        
                        # Show processing info
                        if res1.stdout:
                            st.text(f"Processing output: {res1.stdout}")
                        # Find produced _claude_text.txt in tmp
                        produced = list(tmp_txt_dir.glob(f"{backup_path.stem}_claude_text.txt"))
                        if not produced:
                            produced = list(tmp_txt_dir.glob("*_claude_text.txt"))
                        if not produced:
                            st.session_state.processing_status = "Error"
                            st.error("Did not find extracted text file in tmp")
                            st.text(res1.stdout)
                            return
                        txt_file = produced[0]
                        st.success(f"OCR text ready: {txt_file}")
                        st.text_area("Preview", value=(Path(txt_file).read_text(encoding='utf-8')[:8000]), height=300)

                    with st.spinner("Step 2/2: Running text_lob_llm_extractor on the text file ..."):
                        out_dir = Path("results") / backup_path.stem
                        out_dir.mkdir(parents=True, exist_ok=True)
                        cmd2 = [
                            PYTHON_CMD, "text_lob_llm_extractor.py",
                            str(txt_file), "--config", cfg_path, "--out", str(out_dir)
                        ]
                        res2 = subprocess.run(
                            cmd2,
                            capture_output=True,
                            text=True,
                            timeout=LOB_TIMEOUT,
                            cwd=str(Path.cwd()),
                            shell=False
                        )
                        if res2.returncode != 0:
                            st.session_state.processing_status = "Error"
                            st.error("LOB extractor script failed")
                            st.text(res2.stderr)
                            return
                        # Surface outputs to user
                        excel_files = list(out_dir.glob("*.xlsx"))
                        if excel_files:
                            final_excel = excel_files[0]
                            st.success(f"Extraction complete: {final_excel}")
                            try:
                                excel_data = pd.read_excel(final_excel, sheet_name=None)
                                for sheet_name, df in excel_data.items():
                                    with st.expander(f"{sheet_name}"):
                                        st.dataframe(df, use_container_width=True)
                            except Exception as e:
                                st.warning(f"Could not preview Excel: {e}")
                            with open(final_excel, "rb") as f:
                                st.download_button(
                                    label="⬇️ Download LOB Extract (Excel)",
                                    data=f.read(),
                                    file_name=final_excel.name,
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                )
                        else:
                            st.info("No Excel found from extractor.")
                    st.session_state.processing_status = "Complete"
                except subprocess.TimeoutExpired:
                    st.session_state.processing_status = "Error"
                    st.error("Timed out running scripts.")
                except Exception as e:
                    st.session_state.processing_status = "Error"
                    st.error(f"Scripted flow failed: {e}")
        
        # Step 4: Results
        if st.session_state.processing_complete and st.session_state.result_file:
            st.markdown('<h2 class="step-header">Step 4: Results & Download</h2>', unsafe_allow_html=True)
            
            result_file = Path(st.session_state.result_file)
            
            if result_file.exists():
                st.markdown('<div class="info-box">[RESULTS] Processing Results:</div>', unsafe_allow_html=True)
                
                # Show file info
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Result File", result_file.name)
                with col2:
                    st.metric("File Size", f"{result_file.stat().st_size / 1024:.1f} KB")
                with col3:
                    st.metric("Generated", datetime.fromtimestamp(result_file.stat().st_mtime).strftime("%H:%M:%S"))
                
                # Preview Excel content (retry on Windows locks)
                try:
                    time.sleep(0.3)
                    excel_data = pd.read_excel(result_file, sheet_name=None)
                    
                    # Direct expander for Summary (no extra button/toggle)
                    with st.expander("Summary (click to expand/contract)", expanded=False):
                        try:
                            # Build LOB-wise totals with exact mappings from text_lob_llm_extractor outputs
                            lob_detail_rows = []
                            claims_rows = []
                            for sheet_name, df in excel_data.items():
                                if df is None or df.empty:
                                    continue
                                sn = str(sheet_name).lower()
                                # Infer LOB from sheet name keys: auto_claims, gl_claims, wc_claims
                                if 'auto' in sn:
                                    lob_key = 'AUTO'
                                elif 'gl' in sn and 'claim' in sn:
                                    lob_key = 'GL'
                                elif 'wc' in sn and 'claim' in sn:
                                    lob_key = 'WC'
                                else:
                                    # Unknown -> skip
                                    continue
                                norm_cols = {_normalize_colname(c): c for c in df.columns}
                                def col_exact(norm_name):
                                    return norm_cols.get(norm_name)
                                def series_or_zeros(colname):
                                    return pd.Series(df[colname]).map(_coerce_money) if colname in df.columns else pd.Series([0.0]*len(df))
                                # Common columns
                                claim_col = col_exact("claimnumber") or col_exact("claimno") or col_exact("claim") or col_exact("claimid")
                                alae_col = col_exact("alae") or col_exact("totalalae") or col_exact("expense") or col_exact("totalexpense")
                                alae_vals = pd.Series(df[alae_col]).map(_coerce_money) if alae_col else pd.Series([0.0]*len(df))
                                alae_sum = float(alae_vals.sum())
                                # AUTO: paid_loss
                                if lob_key == 'AUTO':
                                    paid_col = col_exact("paidloss") or col_exact("paid_loss")
                                    losses = pd.Series(df[paid_col]).map(_coerce_money) if paid_col else pd.Series([0.0]*len(df))
                                    total_loss = float(losses.sum())
                                    claim_count = int(df[claim_col].astype(str).str.strip().ne("").sum()) if claim_col else int(len(df))
                                    lob_detail_rows.append({
                                        "LOB": 'AUTO',
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
                                            "lob": 'AUTO',
                                        }))
                                # GL: bi_paid_loss + pd_paid_loss
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
                                # WC: Indemnity_paid_loss + Medical_paid_loss
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
                                st.info("No data available for charts.")
                            else:
                                # Aggregate and render inside the expander
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
                                # Markdown tiles row
                                auto_row = lob_totals[lob_totals["LOB"]=="AUTO"]
                                wc_row = lob_totals[lob_totals["LOB"]=="WC"]
                                gl_row = lob_totals[lob_totals["LOB"]=="GL"]
                                c1, c2, c3 = st.columns(3)
                                with c1:
                                    if not auto_row.empty:
                                        a = auto_row.iloc[0]
                                        st.markdown(f"""
                                        <div class=\"metric-card\">
                                            <div class=\"metric-title\">AUTO</div>
                                            <div class=\"metric-value\">{a['Total Loss']:,.2f}</div>
                                            <div class=\"metric-subtle\">Claims: {int(a['Claim Count'])} | Avg: {a['Avg Claim']:,.2f} | ALAE: {a['Total ALAE']:,.2f}</div>
                                        </div>
                                        """, unsafe_allow_html=True)
                                with c2:
                                    if not wc_row.empty:
                                        w = wc_row.iloc[0]
                                        st.markdown(f"""
                                        <div class=\"metric-card\">
                                            <div class=\"metric-title\">WC</div>
                                            <div class=\"metric-value\">{w['Total Loss']:,.2f}</div>
                                            <div class=\"metric-subtle\">Indemnity: {w['Indemnity Paid Loss']:,.2f} | Medical: {w['Medical Paid Loss']:,.2f} | ALAE: {w['Total ALAE']:,.2f}</div>
                                        </div>
                                        """, unsafe_allow_html=True)
                                with c3:
                                    if not gl_row.empty:
                                        g = gl_row.iloc[0]
                                        st.markdown(f"""
                                        <div class=\"metric-card\">
                                            <div class=\"metric-title\">GL</div>
                                            <div class=\"metric-value\">{g['Total Loss']:,.2f}</div>
                                            <div class=\"metric-subtle\">BI: {g['BI Paid Loss']:,.2f} | PD: {g['PD Paid Loss']:,.2f} | ALAE: {g['Total ALAE']:,.2f}</div>
                                        </div>
                                        """, unsafe_allow_html=True)
                                # LOB-wise top claims
                                if claims_rows:
                                    claims_df = pd.concat(claims_rows, ignore_index=True)
                                    top_n = 10
                                    for lob_filter in ["AUTO","WC","GL"]:
                                        sub = claims_df[claims_df["lob"]==lob_filter]
                                        if sub.empty:
                                            continue
                                        tops = sub.groupby("claim_number", as_index=False)["loss"].sum().sort_values("loss", ascending=False).head(top_n)
                                        chart = alt.Chart(tops).mark_bar().encode(
                                            x=alt.X("claim_number:N", sort='-y', title=f"{lob_filter} Claim Number"), y=alt.Y("loss:Q", title="Total Loss"), tooltip=["claim_number","loss"]
                                        ).properties(title=f"Top {top_n} Claims by Loss - {lob_filter}")
                                        st.altair_chart(chart, use_container_width=True)
                                # Additional overall charts
                                pie = alt.Chart(lob_totals).mark_arc().encode(
                                    theta=alt.Theta(field="Total Loss", type="quantitative"), color=alt.Color(field="LOB", type="nominal"),
                                    tooltip=["LOB","Total Loss","Total ALAE","Claim Count","Avg Claim"]
                                ).properties(title="LOB-wise Total Loss (Pie)")
                                st.altair_chart(pie, use_container_width=True)
                                bar_lob_loss = alt.Chart(lob_totals).mark_bar().encode(
                                    x=alt.X("LOB:N", sort='-y'), y=alt.Y("Total Loss:Q"), color="LOB:N", tooltip=["LOB","Total Loss"]
                                ).properties(title="LOB-wise Total Loss (Bar)")
                                st.altair_chart(bar_lob_loss, use_container_width=True)
                                bar_lob_alae = alt.Chart(lob_totals).mark_bar(color="#2e8b57").encode(
                                    x=alt.X("LOB:N", sort='-y'), y=alt.Y("Total ALAE:Q"), tooltip=["LOB","Total ALAE"]
                                ).properties(title="LOB-wise ALAE (Bar)")
                                st.altair_chart(bar_lob_alae, use_container_width=True)

                                # Claim-level visuals (if claim numbers present)
                                claim_loss = pd.DataFrame(); claim_counts = pd.DataFrame()
                                if claims_rows:
                                    claims_df = pd.concat(claims_rows, ignore_index=True)
                                    claim_loss = claims_df.groupby("claim_number", as_index=False)["loss"].sum().sort_values("loss", ascending=False).head(20)
                                    bar_claim_loss = alt.Chart(claim_loss).mark_bar().encode(
                                        x=alt.X("claim_number:N", sort='-y', title="Claim Number"), y=alt.Y("loss:Q", title="Loss"), tooltip=["claim_number","loss"]
                                    ).properties(title="Claim Number-wise Loss (Top 20)")
                                    st.altair_chart(bar_claim_loss, use_container_width=True)
                                    claim_counts = claims_df.groupby("claim_number", as_index=False).size().rename(columns={"size":"count"}).sort_values("count", ascending=False).head(20)
                                    bar_claim_counts = alt.Chart(claim_counts).mark_bar(color="#1f77b4").encode(
                                        x=alt.X("claim_number:N", sort='-y', title="Claim Number"), y=alt.Y("count:Q", title="Count"), tooltip=["claim_number","count"]
                                    ).properties(title="Claim Number Counts (Top 20)")
                                    st.altair_chart(bar_claim_counts, use_container_width=True)
                                else:
                                    st.info("Claim-level charts not available (claim number column missing).")
                                # Downloadable summary (Excel with corrected totals)
                                try:
                                    buffer = io.BytesIO()
                                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                                        lob_totals.to_excel(writer, sheet_name='LOB_Totals_Detailed', index=False)
                                        try:
                                            summary_df.to_excel(writer, sheet_name='LOB_Summary', index=False)
                                        except Exception:
                                            pass
                                        if not claim_loss.empty:
                                            claim_loss.to_excel(writer, sheet_name='Claim_Loss_Top20', index=False)
                                        if not claim_counts.empty:
                                            claim_counts.to_excel(writer, sheet_name='Claim_Counts_Top20', index=False)
                                    buffer.seek(0)
                                    st.download_button(
                                        label="⬇️ Download Summary (Excel)",
                                        data=buffer,
                                        file_name=f"{result_file.stem}_summary.xlsx",
                                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                    )
                                except Exception as e:
                                    st.warning(f"Could not prepare summary download: {e}")
                        except Exception as e:
                            st.warning(f"Could not build charts: {e}")

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
