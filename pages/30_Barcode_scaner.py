import streamlit as st
import pandas as pd
import streamlit.components.v1 as components

st.set_page_config(page_title="Return Packet Scanner", layout="wide")

st.title("🔍 Return Packet Scanner - Meesho OFD Reverse")
st.markdown("---")

# Session state initialization
if "scanned_counts" not in st.session_state:
    st.session_state.scanned_counts = {}
if "data_loaded" not in st.session_state:
    st.session_state.data_loaded = False
if "total_packets" not in st.session_state:
    st.session_state.total_packets = 0

HEADER_ROW_INDEX = 0  # CSV mein header top par hai [file:1]

@st.cache_data
def load_file(file):
    if file.name.lower().endswith(".csv"):
        return pd.read_csv(file, header=HEADER_ROW_INDEX)
    else:
        return pd.read_excel(file, header=HEADER_ROW_INDEX)

# File upload
uploaded_file = st.file_uploader("📁 CSV/Excel upload karein", type=["csv", "xlsx"])

if uploaded_file is not None and not st.session_state.data_loaded:
    with st.spinner("File load ho rahi hai..."):
        df = load_file(uploaded_file)
        st.session_state.df = df
        st.session_state.data_loaded = True
        
        # Columns identify karo
        courier_col = "Courier Partner" if "Courier Partner" in df.columns else None
        awb_col = "AWB Number" if "AWB Number" in df.columns else None
        
        if courier_col and awb_col:
            # Clean data
            df[courier_col] = df[courier_col].astype(str).str.strip()
            df[awb_col] = df[awb_col].astype(str).str.strip()
            
            # Unique AWB per courier
            unique_df = df.drop_duplicates(subset=[awb_col])
            st.session_state.unique_df = unique_df
            st.session_state.courier_col = courier_col
            st.session_state.awb_col = awb_col
            st.session_state.total_packets = len(unique_df)
            
            st.success(f"✅ File load ho gayi! Total unique packets: {st.session_state.total_packets}")
        else:
            st.error("❌ Courier Partner ya AWB Number column nahi mila!")

# Main dashboard
if st.session_state.get("data_loaded", False):
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📊 Courier-wise Packet Summary")
        unique_df = st.session_state.unique_df
        courier_counts = (
            unique_df.groupby(st.session_state.courier_col)[st.session_state.awb_col]
            .nunique()
            .reset_index()
            .rename(columns={st.session_state.awb_col: "Total Packets"})
        )
        st.dataframe(courier_counts, use_container_width=True)
    
    with col2:
        st.metric("Total Expected", st.session_state.total_packets)
        scanned_total = len(st.session_state.scanned_counts)
        st.metric("Scanned", scanned_total, delta=f"{scanned_total}/{st.session_state.total_packets}")

    st.markdown("---")
    
    # Scanning Section
    st.subheader("🔦 Live Scanning")
    scan_col1, scan_col2 = st.columns([1, 3])
    
    with scan_col1:
        scan_mode = st.radio("Scan Mode:", ["Barcode Scanner", "Mobile Camera"])
    
    with scan_col2:
        if scan_mode == "Barcode Scanner":
            awb_input = st.text_input("AWB scan karein (Enter dabaayein)", key="awb_input")
        else:
            # Mobile Camera Scanner (HTML/JS)
            st.markdown("""
            <div id="scanner-container" style="width: 100%; height: 300px; border: 2px dashed #ddd; 
            display: flex; align-items: center; justify-content: center; 
            background: #f8f9fa; border-radius: 10px;">
                <p style="color: #666; text-align: center;">📱 Camera se scan karein<br>
                (Mobile Chrome browser use karein)</p>
            </div>
            <input type="text" id="camera-result" style="display: none;">
            """, unsafe_allow_html=True)
            
            components.html("""
            <script src="https://unpkg.com/@zxing/library@latest/umd/index.min.js"></script>
            <script>
            let codeReader;
            if (window ZXing) {
                codeReader = new ZXing.BrowserMultiFormatReader();
            }
            
            document.getElementById('scanner-container').onclick = function() {
                codeReader.decodeFromVideoDevice(null, 'scanner-container', function(result, err) {
                    if (result) {
                        document.getElementById('camera-result').value = result.text;
                        parent.document.querySelector('[data-testid="stTextInput"]').value = result.text;
                        parent.document.querySelector('[data-testid="stTextInput"]').dispatchEvent(new Event('input', { bubbles: true }));
                        codeReader.reset();
                    }
                });
            };
            </script>
            """, height=350)
            awb_input = st.text_input("Camera scan result:", key="camera_awb")

    # Process scanned AWB
    if awb_input:
        awb = awb_input.strip()
        if awb:
            awb_key = awb.upper()  # Normalize
            unique_df = st.session_state.unique_df
            
            if awb_key in unique_df[st.session_state.awb_col].astype(str).str.upper().values:
                st.session_state.scanned_counts[awb_key] = st.session_state.scanned_counts.get(awb_key, 0) + 1
                courier = unique_df[unique_df[st.session_state.awb_col].astype(str).str.upper() == awb_key][st.session_state.courier_col].iloc[0]
                st.success(f"✅ {courier} ka packet scan ho gaya! Count: {st.session_state.scanned_counts[awb_key]}")
                st.rerun()
            else:
                st.error(f"❌ AWB {awb} file mein nahi mila!")

    # Results
    st.markdown("---")
    
    col3, col4 = st.columns(2)
    
    with col3:
        st.subheader("✅ Scanned Packets")
        if st.session_state.scanned_counts:
            scanned_list = []
            for awb, cnt in st.session_state.scanned_counts.items():
                row = unique_df[
                    unique_df[st.session_state.awb_col].astype(str).str.upper() == awb
                ]
                courier = row[st.session_state.courier_col].iloc[0] if not row.empty else "NA"
                scanned_list.append({
                    "Courier": courier,
                    "AWB": awb,
                    "Scans": cnt
                })
            scanned_df = pd.DataFrame(scanned_list)
            st.dataframe(scanned_df, use_container_width=True)
        else:
            st.info("Koi packet scan nahi hua abhi.")
    
    with col4:
        st.subheader("❌ Missing Packets (Highlight)")
        all_awb = set(unique_df[st.session_state.awb_col].astype(str).str.upper())
        scanned_set = set(st.session_state.scanned_counts.keys())
        missing_awb = all_awb - scanned_set
        
        if missing_awb:
            missing_df = unique_df[
                unique_df[st.session_state.awb_col].astype(str).str.upper().isin(missing_awb)
            ][[st.session_state.courier_col, st.session_state.awb_col]].reset_index(drop=True)
            
            # Highlight table
            st.markdown(missing_df.style.apply(
                lambda x: ['background-color: #ffebee' for _ in x], axis=1
            ).to_html(), unsafe_allow_html=True)
        else:
            st.success("🎉 Saare packets scan ho gaye!")

    # Reset button
    if st.button("🔄 Reset All Scans", type="secondary"):
        st.session_state.scanned_counts = {}
        st.rerun()
