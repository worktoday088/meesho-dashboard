import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Meesho Sub Order Merge Tool", layout="wide")
st.title("Meesho Sub Order Merge Tool")

# Collapsible upload section
with st.expander("Upload Files (Click to expand/collapse)", expanded=True):
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Set 1 (Main Data)**")
        file_main = st.file_uploader(
            "Main sheet (e.g., sheet1.xlsx with 'Sub Order No')",
            type=["xlsx", "csv"],
            key="main"
        )
    
    with col2:
        st.markdown("**Set 2 (Size Data)**")
        files_size = st.file_uploader(
            "Size data (e.g., sheet2.csv with 'Sub Order No' and 'Size')",
            type=["xlsx", "csv"],
            accept_multiple_files=True,
            key="size"
        )
    
    with col3:
        st.markdown("**Set 3 (Return Reason)**")
        files_reason = st.file_uploader(
            "Return reason data (e.g., sheet3.csv, header starts at row 8)",
            type=["xlsx", "csv"],
            accept_multiple_files=True,
            key="reason"
        )

def read_file(file, skip_rows=0):
    """Read a single file (Excel or CSV)"""
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

def merge_multiple_files(files, skip_rows=0, is_set3=False):
    """Merge multiple files, keeping first file's header and removing headers from subsequent files"""
    if not files:
        return None
    
    dataframes = []
    
    for i, file in enumerate(files):
        if i == 0:
            # First file: read with skip_rows (7 for Set 3, 0 for Set 2)
            df = read_file(file, skip_rows=skip_rows)
        else:
            # Subsequent files: skip header row + metadata rows if needed
            if is_set3:
                # Set 3: skip 8 rows (7 metadata + 1 header) for non-first files
                df = read_file(file, skip_rows=8)
            else:
                # Set 2: skip 1 header row for non-first files
                df = read_file(file, skip_rows=1)
            
            # Assign columns from first file to maintain consistency
            if dataframes:
                df.columns = dataframes[0].columns
        
        if df is not None:
            dataframes.append(df)
    
    if not dataframes:
        return None
    
    # Combine all dataframes into one
    return pd.concat(dataframes, ignore_index=True, sort=False)

if file_main is not None and files_size and files_reason:
    # Process main file
    df_main = read_file(file_main)
    
    # Merge multiple files for Set 2 and Set 3
    df_size = merge_multiple_files(files_size, skip_rows=0, is_set3=False)
    df_reason = merge_multiple_files(files_reason, skip_rows=7, is_set3=True)
    
    # Display previews side by side
    st.subheader("1. Uploaded Data Preview")
    col_preview1, col_preview2, col_preview3 = st.columns(3)
    
    with col_preview1:
        st.write("**Main (Set 1) - First 5 rows:**")
        st.dataframe(df_main.head())
    
    with col_preview2:
        st.write("**Size (Set 2) - First 5 rows:**")
        st.dataframe(df_size.head())
    
    with col_preview3:
        st.write("**Reason (Set 3) - First 5 rows:**")
        st.dataframe(df_reason.head())
    
    # Validate required columns
    required_main_col = "Sub Order No"
    required_size_cols = ["Sub Order No", "Size"]
    required_reason_cols = ["Suborder Number", "Detailed Return Reason"]
    
    errors = []
    
    if required_main_col not in df_main.columns:
        errors.append(f"Main sheet missing '{required_main_col}' column.")
    
    for col in required_size_cols:
        if col not in df_size.columns:
            errors.append(f"Size sheet missing '{col}' column.")
    
    for col in required_reason_cols:
        if col not in df_reason.columns:
            errors.append(f"Reason sheet missing '{col}' column.")
    
    if errors:
        st.error("Cannot proceed due to the following errors:")
        for error in errors:
            st.write(f"- {error}")
    else:
        # Merge Set 2 (Size)
        size_cols = df_size[["Sub Order No", "Size"]].copy()
        size_cols = size_cols.drop_duplicates(subset=["Sub Order No"], keep="last")
        
        df_merged = df_main.merge(
            size_cols,
            on="Sub Order No",
            how="left",
            suffixes=("", "_from_size")
        )
        
        # Merge Set 3 (Reason)
        reason_cols = df_reason[["Suborder Number", "Detailed Return Reason"]].copy()
        reason_cols = reason_cols.rename(columns={"Suborder Number": "Sub Order No"})
        reason_cols = reason_cols.drop_duplicates(subset=["Sub Order No"], keep="last")
        
        df_merged = df_merged.merge(
            reason_cols,
            on="Sub Order No",
            how="left",
            suffixes=("", "_from_reason")
        )
        
        # Show merged data
        st.subheader("2. Merged Data Preview")
        st.write("Top 20 rows of merged data:")
        st.dataframe(df_merged.head(20))
        
        # Download button
        st.subheader("3. Download Merged File")
        
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
    st.info("Please upload all three file sets to proceed.")
