import streamlit as st
import pandas as pd
import io
import streamlit.components.v1 as components

st.set_page_config(page_title="Return Packet Scanner", layout="wide", page_icon="🔍")

st.title("🔍 Return Packet Scanner - Meesho OFD Reverse")
st.markdown("Upload CSV/Excel → Scan packets → Track missing items!")

# Session state
if "scanned_counts" not in st.session_state:
    st.session_state.scanned_counts = {}
if "data_loaded" not in st.session_state:
    st.session_state.data_loaded = False
if "total_packets" not in st.session_state:
    st.session_state.total_packets = 0

HEADER_ROW_INDEX = 0  # Meesho CSV mein header top par [file:1]

@st.cache_data
def load_file(file):
    """Robust CSV/Excel reader - handles all Meesho file formats"""
    try:
        # Reset file pointer
        file.seek(0)
        file_bytes = file.read()
        
        # Try CSV first (most common)
        text = file_bytes.decode("utf-8", errors="ignore")
        df = pd.read_csv(
            io.StringIO(text),
            header=HEADER_ROW_INDEX,
            engine="python",
            sep=",",
            quotechar='"',
            on_bad_lines="skip",
            low_memory=False
        )
        return df
    
    except Exception as e1:
        try:
            # Fallback to Excel
            file.seek(0)
            df = pd.read_excel(file, header=HEADER_ROW_INDEX)
            return df
        except Exception as e2:
            st.error(f"File parse error: CSV - {str(e1)[:100]} | Excel - {str(e2)[:100]}")
            return None

# File upload section
st.subheader("📁 File Upload")
uploaded_file = st.file_uploader("CSV/Excel choose karein", type=["csv", "xlsx"], help="Meesho OFD Reverse report")

if uploaded_file is not None and not st.session_state.data_loaded:
    with st.spinner("File analyze kar raha hun..."):
        df = load_file(uploaded_file)
        
        if df is not None and len(df) > 0:
            # Auto-detect columns (Meesho standard format)
            courier_candidates = [col for col in df.columns if "courier" in col.lower()]
            awb_candidates = [col for col in df.columns if "awb" in col.lower() or "track" in col.lower()]
            
            courier_col = courier_candidates[0] if courier_candidates else "Courier Partner"
            awb_col = awb_candidates[0] if awb_candidates else "AWB Number"
            
            # Verify columns exist
            if courier_col not in df.columns:
                courier_col = "Courier Partner"
            if awb_col not in df.columns:
                awb_col = "AWB Number"
            
            # Clean data
            if courier_col in df.columns:
                df[courier_col] = df[courier_col].astype(str).str.strip()
            if awb_col in df.columns:
                df[awb_col] = df[awb_col].astype(str).str.strip()
            
            # Remove duplicates, count unique AWBs
            unique_df = df.drop_duplicates(subset=[awb_col]).dropna(subset=[awb_col])
            total_packets = len(unique_df)
            
            # Save to session
            st.session_state.df = df
            st.session_state.unique_df = unique_df
            st.session_state.courier_col = courier_col
            st.session_state.awb_col = awb_col
            st.session_state.total_packets = total_packets
            st.session_state.data_loaded = True
            
            st.success(f"✅ File loaded! Total unique packets: **{total_packets}** | Columns: {courier_col}, {awb_col}")
            st.rerun()
        else:
            st.error("❌ Empty ya invalid file. Fresh Meesho CSV download karke try karein.")

# Main Dashboard
if st.session_state.get("data_loaded", False):
    df = st.session_state.df
    unique_df = st.session_state.unique_df
    courier_col = st.session_state.courier_col
    awb_col = st.session_state.awb_col
    
    # Metrics & Summary
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📦 Total Expected", st.session_state.total_packets)
    with col2:
        scanned_total = len(st.session_state.scanned_counts)
        st.metric("✅ Scanned", scanned_total, delta=f"{scanned_total}/{st.session_state.total_packets}")
    with col3:
        pending = st.session_state.total_packets - scanned_total
        st.metric("❌ Pending", pending, delta=f"-{pending}")
    
    st.markdown("---")
    
    # Courier Summary Table
    col4, col5 = st.columns([2, 1])
    with col4:
        st.subheader("📊 Courier-wise Summary")
        courier_summary = (
            unique_df.groupby(courier_col)[awb_col]
            .nunique()
            .reset_index(name="Total Packets")
        )
        st.dataframe(courier_summary, use_container_width=True)
    
    # Scanning Section
    st.subheader("🔦 Live Packet Scanner")
    scan_col1, scan_col2 = st.columns([1, 3])
    
    with scan_col1:
        scan_mode = st.radio("Scan Method:", ["Barcode Scanner", "Mobile Camera"], key="scan_mode")
    
    with scan_col2:
        if scan_mode == "Barcode Scanner":
            awb_input = st.text_input(
                "🎯 AWB scan karein (USB scanner ya manually type + Enter)", 
                placeholder="VL0083065008809",
                key="awb_scanner"
            )
        else:
            # Mobile Camera Scanner
            awb_input = st.text_input(
                "📱 Camera scan result (tap container upar)", 
                placeholder="Camera se scan kiya AWB yahan aayega",
                key="awb_camera"
            )
            
            # Simple HTML camera placeholder (works better)
            st.markdown("""
            <div id="cam-preview" style="
                width: 100%; height: 200px; 
                border: 3px dashed #10b981; 
                border-radius: 12px; 
                display: flex; align-items: center; justify-content: center;
                background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
                cursor: pointer; font-size: 16px; color: #059669;">
                📷 Camera Scanner (Mobile Chrome mein best)<br>
                <small>Tap karke scan shuru karein</small>
            </div>
            """, unsafe_allow_html=True)

    # Process scanned AWB
    if 'awb_input' in locals() and awb_input:
        awb = str(awb_input).strip().upper()
        if awb and len(awb) > 5:  # Valid AWB length
            all_awbs = unique_df[awb_col].astype(str).str.strip().str.upper()
            
            if awb in all_awbs.values:
                st.session_state.scanned_counts[awb] = st.session_state.scanned_counts.get(awb, 0) + 1
                courier = unique_df[all_awbs == awb][courier_col].iloc[0]
                st.success(f"✅ **{courier}** ka packet #{st.session_state.scanned_counts[awb]} scan successful!")
                st.rerun()
            else:
                st.error(f"❌ AWB **{awb}** file mein nahi mila!")

    st.markdown("---")
    
    # Results Tables
    col6, col7 = st.columns(2)
    
    with col6:
        st.subheader("✅ Successfully Scanned")
        if st.session_state.scanned_counts:
            scanned_data = []
            for awb, count in st.session_state.scanned_counts.items():
                row = unique_df[unique_df[awb_col].astype(str).str.upper() == awb]
                courier = row[courier_col].iloc[0] if not row.empty else "Unknown"
                scanned_data.append({"Courier": courier, "AWB": awb, "Scans": count})
            
            scanned_df = pd.DataFrame(scanned_data)
            st.dataframe(scanned_df, use_container_width=True)
        else:
            st.info("📝 Abhi koi scan nahi hua. Scanner se shuru karein!")
    
    with col7:
        st.subheader("❌ Missing Packets (RED Alert)")
        all_awbs_set = set(unique_df[awb_col].astype(str).str.strip().str.upper())
        scanned_set = set(st.session_state.scanned_counts.keys())
        missing_awbs = all_awbs_set - scanned_set
        
        if missing_awbs:
            missing_df = unique_df[
                unique_df[awb_col].astype(str).str.upper().isin(missing_awbs)
            ][[courier_col, awb_col]].reset_index(drop=True)
            
            # Red highlight styling
            styled_missing = missing_df.style.apply(
                lambda x: ['background-color: #fee2e2; color: #dc2626; font-weight: bold'] * len(x), 
                axis=1
            )
            st.dataframe(styled_missing, use_container_width=True)
        else:
            st.success("🎉 **ALL PACKETS SCANNED!** No missing items.")

    # Reset & Export
    col8, col9 = st.columns(2)
    with col8:
        if st.button("🔄 Reset All Scans", type="secondary", use_container_width=True):
            st.session_state.scanned_counts = {}
            st.rerun()
    with col9:
        if st.button("💾 Download Report", type="primary", use_container_width=True):
            report_data = []
            for awb, count in st.session_state.scanned_counts.items():
                row = unique_df[unique_df[awb_col].astype(str).str.upper() == awb]
                courier = row[courier_col].iloc[0] if not row.empty else "Unknown"
                report_data.append([courier, awb, count])
            
            report_df = pd.DataFrame(report_data, columns=["Courier", "AWB", "Scan_Count"])
            csv = report_df.to_csv(index=False)
            st.download_button(
                "Download CSV",
                csv,
                "scanning_report.csv",
                "text/csv"
            )

else:
    st.info("🚀 **Quick Start:**\n1. Meesho se OFD Reverse CSV download karein\n2. Yahan upload karein\n3. Scanner se packets scan karein!")
