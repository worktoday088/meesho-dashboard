import streamlit as st
import pandas as pd
import io
import time

# ================= CONFIG =================
st.set_page_config(
    page_title="Return Packet Scanner PRO",
    layout="wide",
    page_icon="📦"
)

CLEAR_DELAY = 1.0   # 🔥 EXACT 1 SECOND (as requested)

# ================= CSS + VOICE =================
st.markdown("""
<style>
.scan-box input {
    font-size: 28px !important;
    height: 60px;
}
</style>

<script>
function speak(text){
    const msg = new SpeechSynthesisUtterance(text);
    msg.rate = 1;
    msg.pitch = 1;
    window.speechSynthesis.speak(msg);
}
</script>
""", unsafe_allow_html=True)

# ================= TITLE =================
st.title("📦 RETURN PACKET SCANNER – PRO")
st.markdown("### 🔦 Fast Barcode Scanner | Voice Alert | Auto Clear (1s)")

# ================= SESSION =================
for k, v in {
    "scanned": set(),
    "data_loaded": False,
    "selected_courier": "ALL"
}.items():
    st.session_state.setdefault(k, v)

# ================= CSV LOADER =================
def load_csv(file, header=None):
    raw = file.read().decode("utf-8", errors="ignore")
    lines = raw.split("\n")[6:]  # skip metadata
    df = pd.read_csv(io.StringIO("\n".join(lines)), engine="python", on_bad_lines="skip")
    if header is not None:
        df.columns = header
    return df

# ================= UPLOAD =================
st.subheader("📁 Upload CSV Files")

files = st.file_uploader(
    "Select one or more CSV files",
    type=["csv"],
    accept_multiple_files=True
)

if files and not st.session_state.data_loaded:
    base_df = None
    headers = None

    for i, f in enumerate(files):
        df = load_csv(f, headers)
        if i == 0:
            headers = df.columns
            base_df = df
        else:
            base_df = pd.concat([base_df, df], ignore_index=True)

    courier_col = next(c for c in base_df.columns if "courier" in c.lower())
    awb_col = next(c for c in base_df.columns if "awb" in c.lower())

    base_df[awb_col] = base_df[awb_col].astype(str).str.strip()
    base_df = base_df.drop_duplicates(subset=[awb_col])

    st.session_state.df = base_df
    st.session_state.courier_col = courier_col
    st.session_state.awb_col = awb_col
    st.session_state.data_loaded = True
    st.rerun()

# ================= SCAN HANDLER =================
def handle_scan():
    raw = st.session_state.SCANBOX.strip().upper()

    # 👉 LAST AWB ONLY (concat-proof)
    awb = raw[-18:]

    df = st.session_state.df
    courier_col = st.session_state.courier_col
    awb_col = st.session_state.awb_col
    sel = st.session_state.selected_courier

    filtered = df if sel == "ALL" else df[df[courier_col] == sel]
    all_awbs = filtered[awb_col].str.upper().values

    if awb in st.session_state.scanned:
        st.warning(f"⚠ DUPLICATE | {awb}")
        st.components.v1.html("<script>speak('Duplicate')</script>", height=0)

    elif awb in all_awbs:
        st.success(f"✅ SCANNED | {awb}")
        st.session_state.scanned.add(awb)
        st.components.v1.html("<script>speak('Scanned')</script>", height=0)

    else:
        st.error(f"❌ NOT FOUND | {awb}")
        st.components.v1.html("<script>speak('Not Found')</script>", height=0)

    # 🔥 EXACT 1 SECOND DELAY
    time.sleep(CLEAR_DELAY)

    # 🔥 CLEAR INPUT
    st.session_state.SCANBOX = ""

# ================= MAIN DASHBOARD =================
if st.session_state.data_loaded:
    df = st.session_state.df
    courier_col = st.session_state.courier_col
    awb_col = st.session_state.awb_col

    couriers = sorted(df[courier_col].dropna().unique())

    col1, col2 = st.columns([1, 2])
    with col1:
        st.session_state.selected_courier = st.selectbox(
            "🎯 Select Courier",
            ["ALL"] + couriers
        )

    filtered = df if st.session_state.selected_courier == "ALL" else df[df[courier_col] == st.session_state.selected_courier]

    with col2:
        st.metric("📦 TOTAL", len(filtered))
        st.metric("✅ SCANNED", len(st.session_state.scanned))
        st.metric("❌ PENDING", len(filtered) - len(st.session_state.scanned))

    st.markdown("---")

    # ================= SCANNER =================
    st.subheader("🔦 AUTO SCAN AREA")

    st.text_input(
        "SCAN AWB HERE",
        key="SCANBOX",
        placeholder="Scan packet…",
        on_change=handle_scan,
        label_visibility="collapsed"
    )

    st.markdown("---")

    # ================= TABLES =================
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("✅ SCANNED")
        st.dataframe(
            filtered[filtered[awb_col].str.upper().isin(st.session_state.scanned)][[courier_col, awb_col]]
        )

    with c2:
        st.subheader("❌ MISSING")
        missing = set(filtered[awb_col].str.upper()) - st.session_state.scanned
        st.dataframe(
            filtered[filtered[awb_col].str.upper().isin(missing)][[courier_col, awb_col]]
        )

else:
    st.info("⬆ Upload CSV to start scanning")
