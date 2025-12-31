import streamlit as st
import pandas as pd
import io
import time
import streamlit.components.v1 as components

st.set_page_config(page_title="Auto Clear Scanner", layout="wide", page_icon="🔍")

st.title("⚡ **AUTO-CLEAR SCANNER**")
st.markdown("**Scan → Process → AUTO CLEAR → Ready for Next!**")

# Session state
if "scanned_counts" not in st.session_state:
    st.session_state.scanned_counts = {}
if "data_loaded" not in st.session_state:
    st.session_state.data_loaded = False
if "selected_courier" not in st.session_state:
    st.session_state.selected_courier = "ALL"

COURIER_MAP = {"PocketShip": "Valmo", "pocketship": "Valmo"}

def normalize_courier(name):
    if pd.isna(name): return "Unknown"
    return COURIER_MAP.get(str(name).strip().lower(), str(name).strip())

def load_file(file):
    file_bytes = file.read()
    file.seek(0)
    text = file_bytes.decode('utf-8', errors='ignore')
    lines = text.split('\n')[6:]
    df = pd.read_csv(io.StringIO('\n'.join(lines)), engine='python')
    return df

# File upload
uploaded_file = st.file_uploader("📁 CSV", type=["csv"])

if uploaded_file is not None and not st.session_state.data_loaded:
    df = load_file(uploaded_file)
    if df is not None:
        courier_col = next((col for col in df.columns if 'courier' in str(col).lower()), 'Courier Partner')
        awb_col = next((col for col in df.columns if 'awb' in str(col).lower()), 'AWB Number')
        
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

if st.session_state.get("data_loaded"):
    unique_df = st.session_state.unique_df
    courier_col = st.session_state.courier_col
    awb_col = st.session_state.awb_col
    
    # Courier selector
    col1, col2, col3 = st.columns([1,2,2])
    with col1:
        all_couriers = sorted(unique_df[courier_col].unique())
        selected_courier = st.selectbox("🎯 Courier:", ["ALL"] + list(all_couriers), key="courier_select")
        st.session_state.selected_courier = selected_courier
    
    filtered_df = unique_df if selected_courier == "ALL" else unique_df[unique_df[courier_col] == selected_courier]
    
    # Metrics
    total = len(filtered_df)
    scanned_total = sum(1 for awb in st.session_state.scanned_counts if awb in filtered_df[awb_col].str.upper())
    col2.metric("📦 Total", total)
    col3.metric("✅ Scanned", scanned_total, f"{scanned_total}/{total}")
    
    st.markdown("---")
    
    # 🔥 **AUTO-CLEAR SCANNER** - MAIN FEATURE!
    st.subheader("⚡ **AUTO-CLEAR SCANNER**")
    st.markdown("**Scan → Match → AUTO CLEAR → Next Ready!**")
    
    # **SUPER LARGE FOCUSED BOX + AUTO-CLEAR JS**
    components.html("""
    <style>
    .scanner-container {
        border: 4px solid #10b981 !important;
        border-radius: 20px !important;
        background: linear-gradient(135deg, #f0fdf4, #dcfce7) !important;
        padding: 25px !important;
        text-align: center !important;
        font-family: 'Courier New', monospace !important;
    }
    #scanner-input {
        width: 100% !important;
        height: 80px !important;
        font-size: 28px !important;
        font-family: 'Courier New', monospace !important;
        border: 3px solid #10b981 !important;
        border-radius: 15px !important;
        text-align: center !important;
        background: white !important;
        color: #059669 !important;
        outline: none !important;
        caret-color: #059669 !important;
    }
    #scanner-input:focus {
        box-shadow: 0 0 20px rgba(16, 185, 129, 0.5) !important;
        border-color: #059669 !important;
    }
    </style>
    
    <div class="scanner-container">
        <div style="font-size: 24px; font-weight: bold; color: #059669; margin-bottom: 15px;">
            🎯 **AUTO-CLEAR ZONE**
        </div>
        <input type="text" 
               id="scanner-input" 
               placeholder="🔍 Scanner yahan focus karega... SCAN!"
               autocomplete="off"
               autocorrect="off"
               autocapitalize="off"
               spellcheck="false">
        <div style="margin-top: 10px; font-size: 14px; color: #666;">
            📱 Scanner plug → **AUTO FOCUS** → Scan → **AUTO CLEAR**
        </div>
        <input type="hidden" id="awb-result">
    </div>
    
    <script>
    const scannerInput = document.getElementById('scanner-input');
    const awbResult = document.getElementById('awb-result');
    
    // AUTO-FOCUS (always ready)
    scannerInput.focus();
    
    let debounceTimer;
    let lastAWB = '';
    
    scannerInput.addEventListener('input', function(e) {
        const awb = e.target.value.trim().toUpperCase();
        
        // Only process if valid AWB length
        if (awb.length >= 12) {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                if (awb !== lastAWB && awb.length >= 12) {
                    awbResult.value = awb;
                    lastAWB = awb;
                    
                    // AUTO-CLEAR MAGIC! ✅
                    e.target.value = '';
                    
                    // Trigger Streamlit
                    window.parent.streamlit.setComponentValue(awb);
                }
            }, 200); // 200ms debounce
        }
    });
    
    // Keep focus after clear
    scannerInput.addEventListener('blur', () => {
        setTimeout(() => scannerInput.focus(), 50);
    });
    
    </script>
    """, height=250)
    
    # Receive from JS
    awb_scanned = st.text_input("", key="awb_from_scanner", label_visibility="hidden")
    
    # **INSTANT PROCESS + AUTO-CLEAR**
    if awb_scanned:
        awb = awb_scanned.strip().upper()
        all_awbs = filtered_df[awb_col].astype(str).str.strip().str.upper()
        
        if awb in all_awbs.values:
            st.session_state.scanned_counts[awb] = st.session_state.scanned_counts.get(awb, 0) + 1
            courier = filtered_df[all_awbs == awb][courier_col].iloc[0]
            st.balloons()
            st.success(f"✅ **{courier}** | {awb} | **#{st.session_state.scanned_counts[awb]}**")
            st.rerun()
        else:
            st.error(f"❌ **{awb}** Not Found!")
    
    st.markdown("---")
    
    # Results
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("✅ SCANNED")
        scanned_list = []
        for awb, cnt in st.session_state.scanned_counts.items():
            if awb in filtered_df[awb_col].str.upper():
                row = filtered_df[filtered_df[awb_col].str.upper() == awb]
                courier = row[courier_col].iloc[0]
                scanned_list.append([courier, awb, cnt])
        if scanned_list:
            st.dataframe(pd.DataFrame(scanned_list, columns=['Courier','AWB','Count']))
    
    with col2:
        st.subheader("❌ MISSING")
        scanned_set = set(awb for awb in st.session_state.scanned_counts if awb in filtered_df[awb_col].str.upper())
        missing = set(filtered_df[awb_col].str.strip().str.upper()) - scanned_set
        if missing:
            missing_df = filtered_df[filtered_df[awb_col].str.upper().isin(missing)]
            st.dataframe(missing_df[[courier_col, awb_col]])
        else:
            st.success("🎉 COMPLETE!")
    
    if st.button("🔄 RESET", use_container_width=True):
        st.session_state.scanned_counts = {}
        st.rerun()

else:
    st.info("📤 CSV upload first!")
