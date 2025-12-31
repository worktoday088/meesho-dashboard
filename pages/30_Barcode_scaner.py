import streamlit as st
import pandas as pd
import io
import time

st.set_page_config(page_title="Return Packet Scanner", layout="wide", page_icon="🔍")

st.title("🔍 Return Packet Scanner - **AUTO SUBMIT**")
st.markdown("**Barcode scanner plug & play - No click needed!**")

# Session state
if "scanned_counts" not in st.session_state:
    st.session_state.scanned_counts = {}
if "data_loaded" not in st.session_state:
    st.session_state.data_loaded = False
if "total_packets" not in st.session_state:
    st.session_state.total_packets = 0
if "last_awb_time" not in st.session_state:
    st.session_state.last_awb_time = 0

def load_file_safe(file):
    """Skip Meesho metadata lines"""
    try:
        file_bytes = file.read()
        file.seek(0)
        text_content = file_bytes.decode('utf-8', errors='ignore')
        
        lines = text_content.split('\n')
        # Skip first 6 metadata lines [file:1]
        data_start = 6
        data_lines = lines[data_start:]
        
        csv_buffer = io.StringIO('\n'.join(data_lines))
        df = pd.read_csv(csv_buffer, engine='python', sep=',', quotechar='"', on_bad_lines='skip')
        return df
    except:
        try:
            file.seek(0)
            return pd.read_excel(file)
        except:
            return None

# File upload
st.subheader("📁 File Upload")
uploaded_file = st.file_uploader("Meesho CSV", type=["csv", "xlsx"])

if uploaded_file is not None and not st.session_state.data_loaded:
    with st.spinner("Loading..."):
        df = load_file_safe(uploaded_file)
        if df is not None and len(df) > 0:
            # Auto-detect columns
            courier_col = next((col for col in df.columns if 'courier' in str(col).lower()), 'Courier Partner')
            awb_col = next((col for col in df.columns if 'awb' in str(col).lower()), 'AWB Number')
            
            df[courier_col] = df[courier_col].astype(str).str.strip()
            df[awb_col] = df[awb_col].astype(str).str.strip()
            
            unique_df = df.drop_duplicates(subset=[awb_col]).dropna(subset=[awb_col])
            
            st.session_state.df = df
            st.session_state.unique_df = unique_df
            st.session_state.courier_col = courier_col
            st.session_state.awb_col = awb_col
            st.session_state.total_packets = len(unique_df)
            st.session_state.data_loaded = True
            
            st.success(f"✅ **{len(unique_df)} unique packets loaded!**")
            st.rerun()

# MAIN DASHBOARD
if st.session_state.get("data_loaded"):
    unique_df = st.session_state.unique_df
    courier_col = st.session_state.courier_col
    awb_col = st.session_state.awb_col
    
    # METRICS
    total = st.session_state.total_packets
    scanned_total = len(st.session_state.scanned_counts)
    pending_total = total - scanned_total
    
    col1, col2, col3 = st.columns(3)
    col1.metric("📦 Total", total)
    col2.metric("✅ Scanned", scanned_total, f"{scanned_total}/{total}")
    col3.metric("❌ Pending", pending_total, delta=f"-{pending_total}")
    
    st.markdown("---")
    
    # **COURIER TABLE WITH PENDING COLUMN** ✅
    st.subheader("📊 **Courier Summary** (Pending dikhega)")
    courier_stats = unique_df.groupby(courier_col)[awb_col].nunique().reset_index(name="Total")
    
    # Calculate scanned per courier
    scanned_per_courier = {}
    for awb, _ in st.session_state.scanned_counts.items():
        row = unique_df[unique_df[awb_col].str.upper() == awb.upper()]
        if not row.empty:
            courier = row[courier_col].iloc[0]
            scanned_per_courier[courier] = scanned_per_courier.get(courier, 0) + 1
    
    courier_stats['Scanned'] = courier_stats[courier_col].map(scanned_per_courier).fillna(0)
    courier_stats['Pending'] = courier_stats['Total'] - courier_stats['Scanned']
    
    # Color pending column RED
    def highlight_pending(val):
        return 'background-color: #fee2e2; color: #dc2626; font-weight: bold' if val > 0 else ''
    
    styled_courier = courier_stats.style.applymap(highlight_pending, subset=['Pending'])
    st.dataframe(styled_courier, use_container_width=True)
    
    st.markdown("---")
    
    # **🔥 AUTO-SCANNING SECTION** 
    st.subheader("🔦 **AUTO SCANNER** - Plug & Play!")
    
    # BIG FOCUSED INPUT - Always active
    awb_input = st.text_input(
        "🎯 **SCAN HERE** (Auto-submit on Enter/Tab)",
        placeholder="VL0083065008809 ← Scanner automatically fills",
        key="MAIN_SCANNER",
        help="Barcode scanner will auto-focus here + Enter/Tab = Instant scan!"
    )
    
    # **AUTO PROCESS** - No button needed!
    current_time = time.time()
    if awb_input and (current_time - st.session_state.last_awb_time > 1):  # Debounce 1 sec
        awb = str(awb_input).strip().upper()
        if len(awb) > 8:  # Valid AWB length
            all_awbs = unique_df[awb_col].astype(str).str.strip().str.upper()
            
            if awb in all_awbs.values:
                st.session_state.scanned_counts[awb] = st.session_state.scanned_counts.get(awb, 0) + 1
                courier = unique_df[all_awbs == awb][courier_col].iloc[0]
                
                # SUCCESS FEEDBACK
                st.success(f"✅ **{courier}** | {awb} | **#{st.session_state.scanned_counts[awb]}** ✓")
                st.session_state.last_awb_time = current_time
                st.rerun()
            else:
                st.warning(f"⚠️ **{awb}** NOT IN FILE! Check label.")
                st.session_state.last_awb_time = current_time
    
    st.markdown("---")
    
    # RESULTS
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.subheader("✅ **SCANNED**")
        if st.session_state.scanned_counts:
            scanned_data = []
            for awb, cnt in st.session_state.scanned_counts.items():
                row = unique_df[unique_df[awb_col].str.upper() == awb]
                courier = row[courier_col].iloc[0] if len(row)>0 else "?"
                scanned_data.append([courier, awb, cnt])
            st.dataframe(pd.DataFrame(scanned_data, columns=['Courier','AWB','Count']), use_container_width=True)
    
    with col_right:
        st.subheader("❌ **MISSING**")
        all_awbs_set = set(unique_df[awb_col].str.strip().str.upper())
        scanned_set = set(st.session_state.scanned_counts.keys())
        missing = all_awbs_set - scanned_set
        
        if missing:
            missing_df = unique_df[unique_df[awb_col].str.upper().isin(missing)]
            st.dataframe(missing_df[[courier_col, awb_col]], use_container_width=True)
        else:
            st.success("🎉 **ALL COMPLETE!**")
    
    # CONTROLS
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🔄 **RESET ALL**", use_container_width=True):
            st.session_state.scanned_counts = {}
            st.rerun()
    with col_btn2:
        if st.button("💾 **EXPORT REPORT**", use_container_width=True):
            report_data = []
            for awb, cnt in st.session_state.scanned_counts.items():
                row = unique_df[unique_df[awb_col].str.upper() == awb]
                courier = row[courier_col].iloc[0] if len(row)>0 else "?"
                report_data.append([courier, awb, cnt])
            
            report_df = pd.DataFrame(report_data, columns=['Courier','AWB','Scan_Count'])
            csv = report_df.to_csv(index=False)
            st.download_button("📥 Download CSV", csv, "scan_report.csv", "text/csv")

else:
    st.info("""
    🔄 **Setup:**
    1. Meesho CSV upload
    2. Scanner plug-in → Auto-focus hoga
    3. **Scan → Enter/Tab** = Instant match!
    """)
