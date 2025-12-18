import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Meesho Sub Order Merge Tool", layout="wide")
st.title("Meesho Sub Order Merge Tool")

# ---- CONFIG ----
HEADER_SKIP_SET3 = 7  # Meesho CSV में मेटाडेटा रोज़ स्किप करने के लिए

# ---- UPLOAD SECTION ----
with st.expander("Upload Files (click to expand/collapse)", expanded=True):
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Set 1 – Main Data**")
        file_main = st.file_uploader(
            "Main sheet (e.g. sheet1.xlsx with 'Sub Order No')",
            type=["xlsx", "csv"],
            key="main"
        )
    
    with col2:
        st.markdown("**Set 2 – Size Data**")
        files_size = st.file_uploader(
            "Size data (e.g. sheet2.csv with 'Sub Order No' & 'Size')",
            type=["xlsx", "csv"],
            accept_multiple_files=True,
            key="size"
        )
    
    with col3:
        st.markdown("**Set 3 – Return Reason Data**")
        files_reason = st.file_uploader(
            "Return reason data (Meesho CSV; header after metadata)",
            type=["xlsx", "csv"],
            accept_multiple_files=True,
            key="reason"
        )

# ---- HELPERS ----

def read_file(file, skip_rows=0):
    """Read a single Excel/CSV file with optional skipped rows."""
    if file is None:
        return None
    name = file.name.lower()
    try:
        if name.endswith(".xlsx") or name.endswith(".xls"):
            return pd.read_excel(file, skiprows=skip_rows if skip_rows > 0 else None)
        else:
            return pd.read_csv(file, skiprows=skip_rows if skip_rows > 0 else None)
    except Exception as e:
        st.error(f"Error reading file {file.name}: {e}")
        return None

def clean_key_column(series):
    """
    Clean key column for matching:
    - Convert to string
    - Strip leading/trailing spaces
    - Remove extra spaces within
    """
    return series.astype(str).str.strip().str.replace(r'\s+', ' ', regex=True)

def merge_multiple_files_set2(files):
    """Merge multiple Set 2 files (no metadata, header in first row)."""
    if not files:
        return None

    dfs = []
    for i, f in enumerate(files):
        if i == 0:
            df = read_file(f, skip_rows=0)
        else:
            df = read_file(f, skip_rows=1)  # Skip header row only
        if df is not None:
            dfs.append(df)

    if not dfs:
        return None

    return pd.concat(dfs, ignore_index=True, sort=False)

def merge_multiple_files_set3(files):
    """Merge multiple Set 3 files (Meesho return CSVs with metadata)."""
    if not files:
        return None

    dfs = []
    for f in files:
        df = read_file(f, skip_rows=HEADER_SKIP_SET3)
        if df is not None:
            dfs.append(df)

    if not dfs:
        return None

    return pd.concat(dfs, ignore_index=True, sort=False)

# ---- MAIN LOGIC ----

if file_main is not None and files_size and files_reason:
    # Read all files
    df_main = read_file(file_main)
    df_size = merge_multiple_files_set2(files_size)
    df_reason_raw = merge_multiple_files_set3(files_reason)

    # Validate required columns
    required_main_col = "Sub Order No"
    required_size_cols = ["Sub Order No", "Size"]
    required_reason_cols = ["Suborder Number", "Detailed Return Reason"]

    errors = []
    if required_main_col not in df_main.columns:
        errors.append(f"Main sheet missing '{required_main_col}' column.")
    
    if df_size is None:
        errors.append("Set 2 (Size) could not be read/merged.")
    else:
        for col in required_size_cols:
            if col not in df_size.columns:
                errors.append(f"Size sheet(s) missing column: '{col}'")

    if df_reason_raw is None:
        errors.append("Set 3 (Reason) could not be read/merged.")
    else:
        for col in required_reason_cols:
            if col not in df_reason_raw.columns:
                errors.append(f"Reason sheet(s) missing column: '{col}'")

    if errors:
        st.error("Cannot proceed due to the following issues:")
        for e in errors:
            st.write(f"- {e}")
    else:
        # ---- CLEAN KEY COLUMNS ----
        st.subheader("1. Data Cleaning & Validation")
        
        # Clean main sheet
        df_main[required_main_col] = clean_key_column(df_main[required_main_col])
        st.write(f"✓ Cleaned '{required_main_col}' in main sheet: {len(df_main)} rows")
        
        # Clean size sheet
        df_size[required_size_cols[0]] = clean_key_column(df_size[required_size_cols[0]])
        st.write(f"✓ Cleaned '{required_size_cols[0]}' in size sheet: {len(df_size)} rows")
        
        # Clean reason sheet
        df_reason_raw[required_reason_cols[0]] = clean_key_column(df_reason_raw[required_reason_cols[0]])
        st.write(f"✓ Cleaned '{required_reason_cols[0]}' in reason sheet: {len(df_reason_raw)} rows")
        
        # ---- MERGE SET 2 (SIZE) ----
        st.subheader("2. Merging Size Data")
        
        # Prepare size lookup
        size_lookup = df_size[required_size_cols].copy()
        size_lookup = size_lookup.drop_duplicates(subset=[required_size_cols[0]], keep="last")
        size_lookup = size_lookup.set_index(required_size_cols[0])["Size"]
        
        # Check matches
        main_ids = set(df_main[required_main_col].unique())
        size_ids = set(size_lookup.index.unique())
        matched_size = main_ids.intersection(size_ids)
        unmatched_main_size = main_ids - size_ids
        
        st.write(f"✓ Total main IDs: {len(main_ids)}")
        st.write(f"✓ Size IDs found: {len(size_ids)}")
        st.write(f"✓ **Matched for Size: {len(matched_size)}**")
        
        if unmatched_main_size:
            st.warning(f"⚠️ **IDs without Size data ({len(unmatched_main_size)}):**")
            # Show first 10 unmatched IDs
            st.write(list(unmatched_main_size)[:10])
            if len(unmatched_main_size) > 10:
                st.write(f"... and {len(unmatched_main_size) - 10} more")
        
        # Merge
        df_merged = df_main.copy()
        df_merged["Size"] = df_merged[required_main_col].map(size_lookup)
        
        # ---- MERGE SET 3 (REASON) ----
        st.subheader("3. Merging Return Reason Data")
        
        # Prepare reason lookup (by column names, not positions)
        reason_lookup = df_reason_raw[required_reason_cols].copy()
        reason_lookup = reason_lookup.rename(columns={required_reason_cols[0]: required_main_col})
        reason_lookup = reason_lookup.drop_duplicates(subset=[required_main_col], keep="last")
        reason_lookup = reason_lookup.set_index(required_main_col)["Detailed Return Reason"]
        
        # Check matches
        reason_ids = set(reason_lookup.index.unique())
        matched_reason = main_ids.intersection(reason_ids)
        unmatched_main_reason = main_ids - reason_ids
        
        st.write(f"✓ Reason IDs found: {len(reason_ids)}")
        st.write(f"✓ **Matched for Reason: {len(matched_reason)}**")
        
        if unmatched_main_reason:
            st.warning(f"⚠️ **IDs without Reason data ({len(unmatched_main_reason)}):**")
            st.write(list(unmatched_main_reason)[:10])
            if len(unmatched_main_reason) > 10:
                st.write(f"... and {len(unmatched_main_reason) - 10} more")
        
        # Merge
        df_merged["Detailed Return Reason"] = df_merged[required_main_col].map(reason_lookup)
        
        # ---- FINAL STATUS ----
        st.subheader("4. Final Merge Summary")
        
        # Add status columns for visibility
        df_merged["Size_Found"] = df_merged["Size"].notna()
        df_merged["Reason_Found"] = df_merged["Detailed Return Reason"].notna()
        
        summary = {
            "Total Rows": len(df_merged),
            "Size Matched": df_merged["Size_Found"].sum(),
            "Size Missing": (~df_merged["Size_Found"]).sum(),
            "Reason Matched": df_merged["Reason_Found"].sum(),
            "Reason Missing": (~df_merged["Reason_Found"]).sum(),
            "Both Matched": (df_merged["Size_Found"] & df_merged["Reason_Found"]).sum(),
            "Both Missing": (~df_merged["Size_Found"] & ~df_merged["Reason_Found"]).sum()
        }
        
        st.write("**Match Statistics:**")
        for k, v in summary.items():
            st.write(f"- {k}: {v}")
        
        # Show preview with status
        st.subheader("5. Merged Data Preview (with Status)")
        preview_cols = [required_main_col, "Size", "Detailed Return Reason", "Size_Found", "Reason_Found"]
        # Show only columns that exist
        available_preview_cols = [col for col in preview_cols if col in df_merged.columns]
        st.dataframe(df_merged[available_preview_cols].head(20))
        
        # ---- DOWNLOAD ----
        st.subheader("6. Download Merged File")
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df_merged.to_excel(writer, index=False, sheet_name="Merged Data")
        buffer.seek(0)
        
        st.download_button(
            label="Download merged_output.xlsx",
            data=buffer,
            file_name="merged_output.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

else:
    st.info("Please upload Set 1 (main), Set 2 (size) and Set 3 (reason) files to proceed.")
