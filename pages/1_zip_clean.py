# app.py - Updated with Upload area moved to main screen with Hide/Show triangle

import os
import re
import zipfile
import tempfile
from io import BytesIO
from datetime import datetime
import shutil
import pandas as pd
import streamlit as st

# ------------------------------
# Page / app basic setup
# ------------------------------
st.set_page_config(layout="wide", page_title="Meesho Merge & Clean (Web)")

st.title("📦 Meesho — Merge, Clean & Export (Web)")
st.caption("Based on your all_in_one_marge_v2.py logic — multi-ZIP supported, A1/A3 deletion and numeric coercion preserved.")

# ------------------------------
# Utility / cleaning functions (taken from your original script)
# ------------------------------
def is_suborder_or_blank(series: pd.Series) -> pd.Series:
    is_blank = series.isna()
    s_str = series.astype(str).str.strip()
    s_norm = s_str.replace(r"\s+", " ", regex=True)
    is_empty = s_norm.eq("") | s_norm.str.lower().eq("nan")
    is_sub_order = s_norm.str.casefold().eq("sub order")
    return is_blank | is_empty | is_sub_order

def coerce_numeric_df(df: pd.DataFrame) -> pd.DataFrame:
    def coerce_col(col: pd.Series) -> pd.Series:
        if pd.api.types.is_numeric_dtype(col):
            return col
        original = col.copy()
        mask = original.notna()
        s = original[mask].astype(str)
        s = s.str.replace(r"^\\((.*)\\)$", r"-\\1", regex=True)
        s = s.str.replace("−", "-", regex=False).str.replace("–", "-", regex=False)
        s = s.str.replace(r"[₹,]", "", regex=True).str.replace(r"\s+", "", regex=True)
        nums = pd.to_numeric(s, errors="coerce")
        out = original.copy()
        out.loc[mask & nums.notna()] = nums.loc[nums.notna()]
        return out
    return df.apply(coerce_col, axis=0)

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Remove rows where column A (index 0) OR column C (index 2) are blank/'Sub Order'. Then coerce numeric."""
    if df is None or df.empty:
        return df
    df = df.copy()
    try:
        cond_a1 = is_suborder_or_blank(df.iloc[:, 0])
    except Exception:
        cond_a1 = pd.Series(False, index=df.index)
    
    if df.shape[1] >= 3:
        try:
            cond_a3 = is_suborder_or_blank(df.iloc[:, 2])
        except Exception:
            cond_a3 = pd.Series(False, index=df.index)
    else:
        cond_a3 = pd.Series(False, index=df.index)
    
    df = df.loc[~(cond_a1 | cond_a3)].copy()
    df = coerce_numeric_df(df)
    df.reset_index(drop=True, inplace=True)
    return df

def clean_excel_file(file_path, output_path):
    """Remove fully-empty rows/cols and save cleaned workbook (like original script)."""
    try:
        xls = pd.ExcelFile(file_path, engine="openpyxl")
        writer = pd.ExcelWriter(output_path, engine="openpyxl")
        for sheet in xls.sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet, engine="openpyxl", header=None)
            df.dropna(axis=0, how="all", inplace=True)
            df.dropna(axis=1, how="all", inplace=True)
            df.reset_index(drop=True, inplace=True)
            df.to_excel(writer, sheet_name=sheet, index=False, header=False)
        writer.close()
    except Exception as e:
        st.write("Error cleaning file:", file_path, "->", e)

# ------------------------------
# Main processor: multiple zips
# ------------------------------
def process_multiple_zip_files(uploaded_zip_files):
    """
    uploaded_zip_files: list of Streamlit UploadedFile objects
    Returns: (BytesIO buffer of final merged excel, number_part_string, list of extracted cleaned filenames)
    """
    temp_root = tempfile.mkdtemp(prefix="meesho_web_")
    extracted_dir = os.path.join(temp_root, "extracted")
    cleaned_dir = os.path.join(temp_root, "cleaned")
    os.makedirs(extracted_dir, exist_ok=True)
    os.makedirs(cleaned_dir, exist_ok=True)

    # 1) save each uploaded zip to temp and extract .xlsx
    for i, up in enumerate(uploaded_zip_files):
        try:
            # save uploaded to temp .zip file
            tmp_zip_path = os.path.join(temp_root, f"upload_{i}_{os.path.basename(up.name)}")
            with open(tmp_zip_path, "wb") as f:
                f.write(up.getbuffer())
            
            # extract xlsx entries
            with zipfile.ZipFile(tmp_zip_path, 'r') as zf:
                for member in zf.namelist():
                    if member.endswith(".xlsx"):
                        try:
                            # write extracted file to extracted_dir (flatten name)
                            data = zf.read(member)
                            out_name = os.path.basename(member)
                            out_path = os.path.join(extracted_dir, out_name)
                            with open(out_path, "wb") as out_f:
                                out_f.write(data)
                        except Exception as e:
                            st.write("⚠️ Could not extract", member, "from", up.name, "->", e)
        except Exception as e:
            st.write("⚠️ Error processing uploaded ZIP:", up.name, e)

    # 2) Clean each extracted workbook into cleaned_dir (cleaned_{origname}.xlsx)
    for fname in sorted(os.listdir(extracted_dir)):
        if fname.endswith(".xlsx") and not fname.startswith("~$"):
            in_path = os.path.join(extracted_dir, fname)
            out_path = os.path.join(cleaned_dir, f"cleaned_{fname}")
            try:
                clean_excel_file(in_path, out_path)
            except Exception as e:
                st.write("⚠️ clean_excel_file failed for", in_path, e)

    # 3) Merge logic (same sheets as original)
    wanted_sheets = ["Order Payments", "Ads Cost", "Referral Payments"]
    merged_data = {sheet: [] for sheet in wanted_sheets}
    first_file = True
    
    # try to detect number_part (like original: cleaned_(\d+)_SP)
    number_part = "UNKNOWN"
    sample_file = next((f for f in os.listdir(cleaned_dir) if f.endswith(".xlsx") and not f.startswith("~$")), None)
    if sample_file:
        m = re.search(r"cleaned_(\d+)_SP", sample_file, flags=re.IGNORECASE)
        if m:
            number_part = m.group(1)

    for fname in sorted(os.listdir(cleaned_dir)):
        if not fname.endswith(".xlsx") or fname.startswith("~$"):
            continue
        full_path = os.path.join(cleaned_dir, fname)
        try:
            xls = pd.ExcelFile(full_path, engine="openpyxl")
            for sheet in wanted_sheets:
                if sheet in xls.sheet_names:
                    if first_file:
                        df = pd.read_excel(full_path, sheet_name=sheet, engine="openpyxl", header=None)
                    else:
                        df = pd.read_excel(full_path, sheet_name=sheet, engine="openpyxl", header=None, skiprows=3)
                    df.dropna(how='all', inplace=True)
                    if not df.empty:
                        # apply A1/A3 deletion logic for this sheet (per file)
                        try:
                            df = clean_dataframe(df)
                        except Exception:
                            pass
                        merged_data[sheet].append(df)
            first_file = False
        except Exception as e:
            st.write("⚠️ Error reading cleaned file", fname, "->", e)

    # 4) Compose final Excel in-memory
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for sheet in wanted_sheets:
            if merged_data[sheet]:
                final_df = pd.concat(merged_data[sheet], ignore_index=True)
                # final clean
                final_df = clean_dataframe(final_df)
                # write without header (same as original script)
                final_df.to_excel(writer, sheet_name=sheet, index=False, header=False)
    buf.seek(0)

    # cleanup temp if desired (we'll remove temp_root)
    try:
        shutil.rmtree(temp_root)
    except Exception:
        pass

    # date string like original
    date_str = datetime.now().strftime("%d-%b-%y")
    return buf, number_part, date_str

# ------------------------------
# NEW: Main screen layout with collapsible upload section next to download
# ------------------------------
col1, col2 = st.columns([3, 1])

with col1:
    st.subheader("📊 Clean Excel Preview & Download")
    if 'merged_buf' in st.session_state and st.session_state.merged_buf:
        try:
            xls = pd.ExcelFile(st.session_state.merged_buf)
            if "Order Payments" in xls.sheet_names:
                df_preview = pd.read_excel(xls, sheet_name="Order Payments", engine="openpyxl", header=None)
            else:
                df_preview = pd.read_excel(xls, sheet_name=xls.sheet_names[0], engine="openpyxl", header=None)
            st.dataframe(df_preview.head(50), use_container_width=True)
        except Exception as e:
            st.write("Preview not available:", e)

with col2:
    # Hide/Show Upload area with triangle
    with st.expander("⬆️ ZIP Upload (Hide/Show)", expanded=True):
        st.markdown("**Multi-ZIP supported**")
        uploaded_zips = st.file_uploader(
            "Select one or more .zip files that contain Meesho .xlsx files",
            type=["zip"],
            accept_multiple_files=True,
            key="main_uploader"
        )

# Process button below upload area
if uploaded_zips:
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🚀 Process uploaded ZIP(s) → Merge & Clean", type="primary", use_container_width=True):
            with st.spinner("Processing ZIPs — extracting, cleaning and merging (यह काम सर्वर पर होता है)..."):
                try:
                    merged_buf, number_part, date_str = process_multiple_zip_files(uploaded_zips)
                    filename = f"{number_part}_{date_str}.xlsx"
                    st.session_state.merged_buf = merged_buf
                    st.session_state.filename = filename
                    st.session_state.number_part = number_part
                    st.rerun()
                except Exception as e:
                    st.error("Processing failed: " + str(e))
    
    # Download button next to process button
    if 'merged_buf' in st.session_state and st.session_state.merged_buf:
        with col_btn2:
            st.download_button(
                label="⬇️ Download Clean Excel",
                data=st.session_state.merged_buf.getvalue(),
                file_name=st.session_state.filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            st.success("✅ Clean Excel तैयार है - Download करें!")

else:
    st.info("कृपया ऊपर के Upload क्षेत्र में ZIP files चुनें।")

# ------------------------------
# Sidebar empty now (clean look)
# ------------------------------
st.sidebar.markdown("### 👋 Clean Interface")
st.sidebar.markdown("Upload अब main screen पर है!")

# ------------------------------
# Requirements note
# ------------------------------
st.markdown("---")
st.markdown("""
**Requirements:**
