import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Return Packet Scanner", layout="wide", page_icon="🔍")

st.title("🔍 Return Packet Scanner - Meesho OFD Reverse")
st.markdown("**Upload → Scan → Track Missing**")

# Session state
if "scanned_counts" not in st.session_state:
    st.session_state.scanned_counts = {}
if "data_loaded" not in st.session_state:
    st.session_state.data_loaded = False
if "total_packets" not in st.session_state:
    st.session_state.total_packets = 0

def load_file_safe(file):
    """100% safe CSV/Excel loader - NO CACHE"""
    try:
        # Always read as bytes first
        file_bytes = file.read()
        file.seek(0)  # Reset for later use
        
        # Method 1: CSV with manual parsing
        text_content = file_bytes.decode('utf-8', errors='ignore')
        
        # Skip first 6 lines (Meesho metadata) [file:1]
        lines = text_content.split('\n')
        data_lines = []
        header_found = False
        header_line = None
        
        for i, line in enumerate(lines):
            if i < 6:  # Skip metadata
                continue
            if not header_found and ',' in line and len(line.strip()) > 10:
                header_found = True
                header_line = line
                data_lines.append(line)
            elif header_found:
                data_lines.append(line)
        
        if header_line:
            csv_buffer = io.StringIO('\n'.join(data_lines))
            df = pd.read_csv(csv_buffer, engine='python')
            return df
        else:
            # Fallback: raw CSV
            csv_buffer = io.StringIO(text_content)
            df = pd.read_csv(csv_buffer, header=0, engine='python', 
                           sep=',', quotechar='"', on_bad_lines='skip')
            return df
            
    except:
        try:
            # Excel fallback
            file.seek(0)
            df = pd.read_excel(file)
            return df
        except:
            return None

# File upload
st.subheader("📁 File Upload")
uploaded_file = st.file_uploader("Meesho CSV/Excel upload karein", type=["csv", "xlsx"])

if uploaded_file is not None and not st.session_state.data_loaded:
    with st.spinner("🔄 File processing..."):
        df = load_file_safe(uploaded_file)
        
        if df is not None and len(df) > 0:
            st.session_state.raw_df = df.copy()
            
            # Auto find columns
            courier_col = next((col for col in df.columns if 'courier' in str(col).lower()), 'Courier Partner')
            awb_col = next((col for col in df.columns if 'awb' in str(col).lower()), 'AWB Number')
            
            # Verify columns exist
            available_cols = [col for col in df.columns]
            if courier_col not in df.columns:
                courier_col = 'Courier Partner' if 'Courier Partner' in available_cols else available_cols[14] if len(available_cols)>14 else available_cols[0]
            if awb_col not in df.columns:
                awb_col = 'AWB Number' if 'AWB Number' in available_cols else available_cols[15] if len(available_cols)>15 else available_cols[1]
            
            # Clean data
            df[courier_col] = df[courier_col].astype(str).str.strip()
            df[awb_col] = df[awb_col].astype(str).str.strip()
            
            # Unique AWBs only
            unique_df = df.drop_duplicates(subset=[awb_col]).dropna(subset=[awb_col])
            total_packets = len(unique_df)
            
            st.session_state.df = df
            st.session_state.unique_df = unique_df
            st.session_state.courier_col = courier_col
            st.session_state.awb_col = awb_col
            st.session_state.total_packets = total_packets
            st.session_state.data_loaded = True
            
            st.success(f"✅ **Loaded!** {total_packets} unique packets | Courier: {courier_col} | AWB: {awb_col}")
            st.info(f"📋 Columns found: {list(df.columns[:5])}...")
            st.rerun()
        else:
            st.error("❌ File empty ya corrupt. Fresh Meesho CSV download karein.")

# MAIN DASHBOARD
if st.session_state.get("data_loaded"):
    df = st.session_state.df
    unique_df = st.session_state.unique_df
    courier_col = st.session_state.courier_col
    awb_col = st.session_state.awb_col
    
    # Metrics
    col1, col2, col3 = st.columns(3)
    total = st.session_state.total_packets
    scanned = len(st.session_state.scanned_counts)
    pending = total - scanned
    
    with col1: st.metric("📦 Total", total)
    with col2: st.metric("✅ Scanned", scanned, f"{scanned}/{total}")
    with col3: st.metric("❌ Pending", pending, delta=f"-{pending}")
    
    st.markdown("---")
    
    # Courier table
    col4, col5 = st.columns([2,1])
    with col4:
        st.subheader("📊 Courier Summary")
        courier_summary = unique_df.groupby(courier_col)[awb_col].nunique().reset_index(name="Packets")
        st.dataframe(courier_summary)
    
    # Scanner
    st.subheader("🔦 **Live Scanner**")
    col6, col7 = st.columns([1,3])
    
    with col6:
        mode = st.radio("Mode:", ["Scanner", "Manual"], key="mode")
    
    with col7:
        if mode == "Scanner":
            awb_input = st.text_input("🎯 AWB scan (Enter press karein)", key="awb_scan")
        else:
            awb_input = st.text_input("Type AWB:", key="awb_manual")
    
    # Process scan
    if awb_input:
        awb = str(awb_input).strip().upper()
        if len(awb) > 5:
            all_awbs = unique_df[awb_col].astype(str).str.strip().str.upper()
            
            if awb in all_awbs.values:
                st.session_state.scanned_counts[awb] = st.session_state.scanned_counts.get(awb, 0) + 1
                courier = unique_df[all_awbs == awb][courier_col].iloc[0]
                st.success(f"✅ **{courier}** | AWB: {awb} | Scan #{st.session_state.scanned_counts[awb]}")
                st.rerun()
            else:
                st.error(f"❌ **{awb}** not in file!")
    
    # Results
    col8, col9 = st.columns(2)
    
    with col8:
        st.subheader("✅ Scanned")
        if st.session_state.scanned_counts:
            scanned_data = []
            for awb, cnt in st.session_state.scanned_counts.items():
                row = unique_df[unique_df[awb_col].str.upper() == awb]
                courier = row[courier_col].iloc[0] if len(row)>0 else "?"
                scanned_data.append([courier, awb, cnt])
            st.dataframe(pd.DataFrame(scanned_data, columns=['Courier','AWB','Count']))
    
    with col9:
        st.subheader("❌ **MISSING** (RED)")
        all_awbs_set = set(unique_df[awb_col].str.strip().str.upper())
        scanned_set = set(st.session_state.scanned_counts)
        missing = all_awbs_set - scanned_set
        
        if missing:
            missing_df = unique_df[unique_df[awb_col].str.upper().isin(missing)]
            st.dataframe(missing_df[[courier_col, awb_col]])
        else:
            st.success("🎉 **COMPLETE!**")
    
    # Controls
    col10, col11 = st.columns(2)
    with col10:
        if st.button("🔄 Reset", use_container_width=True):
            st.session_state.scanned_counts = {}
            st.rerun()
    with col11:
        if st.button("💾 Export", use_container_width=True):
            report = pd.DataFrame([
                [courier, awb, cnt] 
                for awb, cnt in st.session_state.scanned_counts.items()
                for courier in [unique_df[unique_df[awb_col].str.upper()==awb][courier_col].iloc[0]]
            ], columns=['Courier','AWB','Scans'])
            csv = report.to_csv(index=False)
            st.download_button("Download", csv, "report.csv", "text/csv")

else:
    st.markdown("""
    ## 🚀 **Quick Start**
    1. Meesho → Supplier Panel → OFD Reverse Report Download
    2. Yahan CSV upload kariye
    3. Barcode scanner ya manually AWB scan karein
    4. Missing packets **RED** mein dikhega!
    """)
