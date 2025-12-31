import streamlit as st
import pandas as pd
import io
import time

st.set_page_config(page_title="Return Packet Scanner", layout="wide", page_icon="🔍")

st.title("🔍 **AUTO-SCAN Courier Tracker**")
st.markdown("**PocketShip=Valmo merged | Instant scan | Single courier mode**")

# Session state
if "scanned_counts" not in st.session_state:
    st.session_state.scanned_counts = {}
if "data_loaded" not in st.session_state:
    st.session_state.data_loaded = False
if "selected_courier" not in st.session_state:
    st.session_state.selected_courier = "ALL"
if "last_scan_time" not in st.session_state:
    st.session_state.last_scan_time = 0

# COURIER MAPPING (PocketShip = Valmo)
COURIER_MAP = {
    "PocketShip": "Valmo",
    "pocketship": "Valmo"
}

def normalize_courier(courier_name):
    """PocketShip ko Valmo bana do"""
    if pd.isna(courier_name):
        return "Unknown"
    name = str(courier_name).strip().lower()
    return COURIER_MAP.get(name, courier_name)

def load_file_safe(file):
    file_bytes = file.read()
    file.seek(0)
    text_content = file_bytes.decode('utf-8', errors='ignore')
    
    # Skip Meesho metadata [file:1]
    lines = text_content.split('\n')[6:]
    csv_buffer = io.StringIO('\n'.join(lines))
    df = pd.read_csv(csv_buffer, engine='python', sep=',', quotechar='"', on_bad_lines='skip')
    return df

# File upload
st.subheader("📁 Upload Meesho CSV")
uploaded_file = st.file_uploader("CSV", type=["csv"])

if uploaded_file is not None and not st.session_state.data_loaded:
    with st.spinner("Loading..."):
        df = load_file_safe(uploaded_file)
        if df is not None:
            courier_col = next((col for col in df.columns if 'courier' in str(col).lower()), 'Courier Partner')
            awb_col = next((col for col in df.columns if 'awb' in str(col).lower()), 'AWB Number')
            
            # NORMALIZE COURIERS
            df[courier_col] = df[courier_col].apply(normalize_courier)
            df[awb_col] = df[awb_col].astype(str).str.strip()
            
            unique_df = df.drop_duplicates(subset=[awb_col]).dropna(subset=[awb_col])
            
            st.session_state.df = df
            st.session_state.unique_df = unique_df
            st.session_state.courier_col = courier_col
            st.session_state.awb_col = awb_col
            st.session_state.total_packets = len(unique_df)
            st.session_state.data_loaded = True
            st.rerun()

# MAIN DASHBOARD
if st.session_state.get("data_loaded"):
    unique_df = st.session_state.unique_df
    courier_col = st.session_state.courier_col
    awb_col = st.session_state.awb_col
    
    # AVAILABLE COURIERS (merged)
    all_couriers = sorted(unique_df[courier_col].unique())
    
    # FILTER SELECTOR
    col_filter, col_metrics = st.columns([1, 2])
    with col_filter:
        st.subheader("🎯 **Select Courier**")
        selected_courier = st.selectbox(
            "Choose courier (or ALL):",
            ["ALL"] + list(all_couriers),
            index=0 if st.session_state.selected_courier == "ALL" else all_couriers.index(st.session_state.selected_courier)+1,
            key="courier_selector"
        )
        if selected_courier != st.session_state.selected_courier:
            st.session_state.selected_courier = selected_courier
            st.rerun()
    
    # METRICS (filtered)
    filtered_df = unique_df if selected_courier == "ALL" else unique_df[unique_df[courier_col] == selected_courier]
    total = len(filtered_df)
    scanned_total = sum(1 for awb in st.session_state.scanned_counts if awb in filtered_df[awb_col].str.upper().values)
    pending_total = total - scanned_total
    
    with col_metrics:
        col1, col2, col3 = st.columns(3)
        col1.metric("📦 Total", total)
        col2.metric("✅ Scanned", scanned_total, f"{scanned_total}/{total}")
        col3.metric("❌ Pending", pending_total, delta=f"-{pending_total}")
    
    st.markdown("---")
    
    # **COURIER SUMMARY** (sirf selected ya sab)
    st.subheader("📊 **Summary**")
    if selected_courier == "ALL":
        courier_stats = filtered_df.groupby(courier_col)[awb_col].nunique().reset_index(name="Total")
        scanned_per_courier = {}
        for awb in st.session_state.scanned_counts:
            row = unique_df[unique_df[awb_col].str.upper() == awb]
            if not row.empty:
                courier = row[courier_col].iloc[0]
                scanned_per_courier[courier] = scanned_per_courier.get(courier, 0) + 1
        
        courier_stats['Scanned'] = courier_stats[courier_col].map(scanned_per_courier).fillna(0)
        courier_stats['Pending'] = courier_stats['Total'] - courier_stats['Scanned']
        
        def highlight_pending(val):
            return 'background-color: #fee2e2; color: #dc2626' if val > 0 else ''
        
        styled = courier_stats.style.applymap(highlight_pending, subset=['Pending'])
        st.dataframe(styled, use_container_width=True)
    else:
        st.info(f"**🎯 Selected: {selected_courier}**")
    
    st.markdown("---")
    
    # **🔥 INSTANT AUTO-SCANNER**
    st.subheader("🔦 **INSTANT SCANNER** - No Enter needed!")
    
    # GIANT FOCUSED INPUT BOX
    awb_input = st.text_input(
        "🎯 **AUTO SCAN HERE**",
        placeholder="Scanner will instantly process...",
        key="AUTO_SCANNER_BOX",
        help="Scanner scan → INSTANT match! No click/Enter"
    )
    
    # **INSTANT PROCESSING** (0.5 sec debounce)
    current_time = time.time()
    if awb_input and (current_time - st.session_state.last_scan_time > 0.5):
        awb = str(awb_input).strip().upper()
        if len(awb) > 8:
            all_awbs = filtered_df[awb_col].astype(str).str.strip().str.upper()
            
            if awb in all_awbs.values:
                st.session_state.scanned_counts[awb] = st.session_state.scanned_counts.get(awb, 0) + 1
                courier = filtered_df[all_awbs == awb][courier_col].iloc[0]
                st.success(f"✅ **{courier}** | {awb} | **#{st.session_state.scanned_counts[awb]}**")
                st.session_state.last_scan_time = current_time
                st.rerun()
            else:
                st.warning(f"❌ **{awb}** - Not in selected courier!")
                st.session_state.last_scan_time = current_time
    
    st.markdown("---")
    
    # RESULTS
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("✅ **SCANNED**")
        scanned_list = []
        for awb, cnt in st.session_state.scanned_counts.items():
            if awb in filtered_df[awb_col].str.upper().values:
                row = filtered_df[filtered_df[awb_col].str.upper() == awb]
                courier = row[courier_col].iloc[0]
                scanned_list.append([courier, awb, cnt])
        
        if scanned_list:
            st.dataframe(pd.DataFrame(scanned_list, columns=['Courier','AWB','Count']))
        else:
            st.info("No scans yet")
    
    with col2:
        st.subheader("❌ **MISSING**")
        scanned_set = set(awb for awb, _ in st.session_state.scanned_counts.items() if awb in filtered_df[awb_col].str.upper().values)
        all_awbs_set = set(filtered_df[awb_col].str.strip().str.upper())
        missing = all_awbs_set - scanned_set
        
        if missing:
            missing_df = filtered_df[filtered_df[awb_col].str.upper().isin(missing)]
            st.dataframe(missing_df[[courier_col, awb_col]])
        else:
            st.success("🎉 **COMPLETE!**")
    
    # CONTROLS
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🔄 RESET", use_container_width=True):
            st.session_state.scanned_counts = {}
            st.rerun()
    with col_btn2:
        if st.button("💾 EXPORT", use_container_width=True):
            report = pd.DataFrame(scanned_list, columns=['Courier','AWB','Count'])
            csv = report.to_csv(index=False)
            st.download_button("Download", csv, "report.csv", "text/csv")

else:
    st.info("📤 Upload CSV to start!")
