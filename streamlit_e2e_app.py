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
import altair as alt
import io


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
    """Convert PDF to text using fitzTest3.py. Always return (path, error)."""
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
            # Small wait to ensure file handles are released by child process
            time.sleep(0.8)
            # Find the generated Excel file
            excel_files = list(output_dir.glob("*.xlsx"))
            if excel_files:
                # Rename to original PDF name with robust finalize
                result_file = output_dir / f"{original_pdf_name.replace('.pdf', '')}.xlsx"
                finalized_path = safe_finalize_result(excel_files[0], result_file)
                if finalized_path and Path(finalized_path).exists():
                    return str(finalized_path), None
                else:
                    return None, "Failed to finalize result file due to file lock"
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
                
                # Preview Excel content (retry on Windows locks)
                try:
                    time.sleep(0.3)
                    excel_data = pd.read_excel(result_file, sheet_name=None)
                    # Summary by LOB
                    try:
                        summary_df = compute_lob_summary(excel_data)
                        with st.expander("Summary by LOB", expanded=False):
                            st.dataframe(summary_df, use_container_width=True)
                    except Exception as _:
                        st.warning("Could not compute LOB summary.")

                    # Summary & Charts on demand
                    if st.button("📊 Show Summary & Charts"):
                        try:
                            # Build LOB-wise totals with proper mappings
                            lob_rows = []
                            claims_rows = []
                            for sheet_name, df in excel_data.items():
                                if df is None or df.empty:
                                    continue
                                lob = sheet_name.strip().upper()
                                norm_cols = {_normalize_colname(c): c for c in df.columns}
                                def get_col(cands):
                                    for c in cands:
                                        if c in norm_cols:
                                            return norm_cols[c]
                                    return None
                                # Common columns
                                claim_col = get_col(["claimnumber","claim_no","claim#","claimid","claim"])
                                alae_col = get_col(["alae","totalalae","expense","totalexpense"])
                                # Compute per-row total loss
                                if lob in ["AUTO","PROPERTY"]:
                                    paid_col = get_col(["paidloss","paid_loss","paid","totpaid","totalpaid"])
                                    if paid_col:
                                        losses = pd.Series(df[paid_col]).map(_coerce_money)
                                    else:
                                        losses = pd.Series([0.0]*len(df))
                                elif lob in ["GL","GENERAL LIABILITY","GENERALLIABILITY"]:
                                    bi_col = get_col(["bodilyinjurypaidloss","bipaidloss","bodilyinjury","bodilyinjurypaid"])
                                    pd_col = get_col(["propertydamagepaidloss","pdpailoss","propertydamage","propertydamagepaid"])  # pdpAiLoss typo-safe
                                    bi_vals = pd.Series(df[bi_col]).map(_coerce_money) if bi_col else pd.Series([0.0]*len(df))
                                    pd_vals = pd.Series(df[pd_col]).map(_coerce_money) if pd_col else pd.Series([0.0]*len(df))
                                    losses = bi_vals.add(pd_vals, fill_value=0.0)
                                    lob = "GL"
                                else:  # WC variants
                                    ind_col = get_col(["indemnitypaidloss","indemnitypaid","indemnity"])
                                    med_col = get_col(["medicalpaidloss","medicalpaid","medical"])
                                    ind_vals = pd.Series(df[ind_col]).map(_coerce_money) if ind_col else pd.Series([0.0]*len(df))
                                    med_vals = pd.Series(df[med_col]).map(_coerce_money) if med_col else pd.Series([0.0]*len(df))
                                    losses = ind_vals.add(med_vals, fill_value=0.0)
                                    lob = "WC"
                                alae_vals = pd.Series(df[alae_col]).map(_coerce_money) if alae_col else pd.Series([0.0]*len(df))
                                # LOB totals
                                lob_rows.append({
                                    "LOB": lob,
                                    "Total Loss": float(losses.sum()),
                                    "Total ALAE": float(alae_vals.sum()),
                                })
                                # Per-claim aggregates (loss and alae)
                                if claim_col:
                                    tmp = pd.DataFrame({
                                        "claim_number": df[claim_col].astype(str),
                                        "loss": losses.astype(float),
                                        "alae": alae_vals.astype(float),
                                        "lob": lob,
                                    })
                                    claims_rows.append(tmp)
                            if not lob_rows:
                                st.info("No data available for charts.")
                            else:
                                lob_totals = pd.DataFrame(lob_rows).groupby("LOB", as_index=False).sum(numeric_only=True)
                                # ===== Metric Tiles =====
                                total_loss_all = float(lob_totals["Total Loss"].sum())
                                colA, colB, colC = st.columns(3)
                                with colA:
                                    st.metric("Total Loss (All LOBs)", f"{total_loss_all:,.2f}")
                                with colB:
                                    # LOB-wise total loss as comma-separated summary
                                    lob_str = ", ".join([f"{r.LOB}: {r['Total Loss']:,.2f}" for _, r in lob_totals.iterrows()])
                                    st.metric("LOB-wise Total Loss", lob_str)
                                with colC:
                                    # Average Loss per LOB (Total Loss / number of claims per LOB)
                                    avg_text = "N/A"
                                    try:
                                        if claims_rows:
                                            claims_df_tmp = pd.concat(claims_rows, ignore_index=True)
                                            counts = claims_df_tmp.groupby("lob", as_index=False).size().rename(columns={"size":"count"})
                                            merged_avg = lob_totals.merge(counts, left_on="LOB", right_on="lob", how="left").fillna({"count":0})
                                            merged_avg["avg_loss_per_lob"] = merged_avg.apply(lambda r: (r["Total Loss"] / r["count"]) if r["count"] else 0.0, axis=1)
                                            avg_text = ", ".join([f"{r.LOB}: {r['avg_loss_per_lob']:,.2f}" for _, r in merged_avg.iterrows()])
                                    except Exception:
                                        pass
                                    st.metric("Average Loss per LOB", avg_text)
                                # LOB-wise number of claims tile row
                                if claims_rows:
                                    claims_df_tiles = pd.concat(claims_rows, ignore_index=True)
                                    lob_counts = claims_df_tiles.groupby("lob", as_index=False).size().rename(columns={"size":"count"})
                                    cols = st.columns(min(4, max(1, len(lob_counts))))
                                    for i, row in enumerate(lob_counts.itertuples(index=False)):
                                        with cols[i % len(cols)]:
                                            st.metric(f"Claims ({row.lob})", f"{int(row.count):,}")
                                st.markdown("### LOB-wise Totals")
                                st.dataframe(lob_totals, use_container_width=True)
                                # Pie: LOB-wise total loss
                                pie = alt.Chart(lob_totals).mark_arc().encode(
                                    theta=alt.Theta(field="Total Loss", type="quantitative"),
                                    color=alt.Color(field="LOB", type="nominal"),
                                    tooltip=["LOB","Total Loss","Total ALAE"]
                                ).properties(title="LOB-wise Total Loss (Pie)")
                                st.altair_chart(pie, use_container_width=True)
                                # Bar: LOB-wise total loss
                                bar_lob_loss = alt.Chart(lob_totals).mark_bar().encode(
                                    x=alt.X("LOB:N", sort='-y'), y=alt.Y("Total Loss:Q"), color="LOB:N", tooltip=["LOB","Total Loss"]
                                ).properties(title="LOB-wise Total Loss (Bar)")
                                st.altair_chart(bar_lob_loss, use_container_width=True)
                                # Bar: LOB-wise ALAE
                                bar_lob_alae = alt.Chart(lob_totals).mark_bar(color="#2e8b57").encode(
                                    x=alt.X("LOB:N", sort='-y'), y=alt.Y("Total ALAE:Q"), tooltip=["LOB","Total ALAE"]
                                ).properties(title="LOB-wise ALAE (Bar)")
                                st.altair_chart(bar_lob_alae, use_container_width=True)
                                # Claim-level charts
                                claim_loss = pd.DataFrame()
                                claim_counts = pd.DataFrame()
                                if claims_rows:
                                    claims_df = pd.concat(claims_rows, ignore_index=True)
                                    # Claim number wise loss (top 20)
                                    claim_loss = claims_df.groupby("claim_number", as_index=False)["loss"].sum().sort_values("loss", ascending=False).head(20)
                                    bar_claim_loss = alt.Chart(claim_loss).mark_bar().encode(
                                        x=alt.X("claim_number:N", sort='-y', title="Claim Number"), y=alt.Y("loss:Q", title="Loss"),
                                        tooltip=["claim_number","loss"]
                                    ).properties(title="Claim Number-wise Loss (Top 20)")
                                    st.altair_chart(bar_claim_loss, use_container_width=True)
                                    # Claim number counts
                                    claim_counts = claims_df.groupby("claim_number", as_index=False).size()
                                    claim_counts = claim_counts.rename(columns={"size": "count"}).sort_values("count", ascending=False).head(20)
                                    bar_claim_counts = alt.Chart(claim_counts).mark_bar(color="#1f77b4").encode(
                                        x=alt.X("claim_number:N", sort='-y', title="Claim Number"), y=alt.Y("count:Q", title="Count"),
                                        tooltip=["claim_number","count"]
                                    ).properties(title="Claim Number Counts (Top 20)")
                                    st.altair_chart(bar_claim_counts, use_container_width=True)
                                else:
                                    st.info("Claim-level charts not available (claim number column missing).")
                                # Downloadable summary (Excel with multiple sheets)
                                try:
                                    buffer = io.BytesIO()
                                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                                        lob_totals.to_excel(writer, sheet_name='LOB_Totals', index=False)
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
