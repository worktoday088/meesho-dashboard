import streamlit as st
import pandas as pd
import io, time

# ================== PAGE CONFIG ==================
st.set_page_config(
    page_title="Return Packet Scanner PRO",
    layout="wide",
    page_icon="📦"
)

# ================== CSS + SOUND ==================
st.markdown("""
<style>
.upload-box {
    border: 3px dashed #fb923c;
    padding: 20px;
    background: #fff7ed;
    border-radius: 14px;
    position: relative;
    margin-bottom: 10px;
}
.upload-box::before {
    content: "▲";
    position: absolute;
    top: -22px;
    left: 20px;
    font-size: 34px;
    color: #fb923c;
}
.scan-box input {
    font-size: 28px !important;
    height: 60px;
}
</style>

<script>
function beep(freq){
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    osc.frequency.value = freq;
    osc.connect(ctx.destination);
    osc.start();
    setTimeout(()=>osc.stop(),150);
}
</script>
""", unsafe_allow_html=True)

# ================== TITLE ==================
st.title("📦 RETURN PACKET SCANNER – PRO")
st.markdown("### 🔺 High-Speed Warehouse Scanner | Duplicate Block | Multi CSV Merge")

# ================== SESSION ==================
for k, v in {
    "scanned": set(),
    "data_loaded": False,
    "selected_courier": "ALL",
    "last_scan": 0
}.items():
    st.session_state.setdefault(k, v)

# ================== HELPERS ==================
def load_csv(file, header=None):
    raw = file.read().decode("utf-8", errors="ignore")
    lines = raw.split("\n")[6:]
    df = pd.read_csv(io.StringIO("\n".join(lines)), engine="python", on_bad_lines="skip")
    if header is not None:
        df.columns = header
    return df

# ================== UPLOAD UI ==================
st.markdown("""
<div class="upload-box">
<h3>🔺 UPLOAD CSV FILES</h3>
<b>Select one or more CSV files</b>
</div>
""", unsafe_allow_html=True)

files = st.file_uploader(
    "",
    type=["csv"],
    accept_multiple_files=True
)

if files and not st.session_state.data_loaded:
    with st.spinner("Merging files..."):
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

        st.session_state.update({
            "df": base_df,
            "courier_col": courier_col,
            "awb_col": awb_col,
            "data_loaded": True
        })
        st.rerun()

# ================== DASHBOARD ==================
if st.session_state.data_loaded:
    df = st.session_state.df
    courier_col = st.session_state.courier_col
    awb_col = st.session_state.awb_col

    couriers = sorted(df[courier_col].dropna().unique())
    col1, col2 = st.columns([1,2])

    with col1:
        sel = st.selectbox("🎯 Select Courier", ["ALL"] + couriers)
        st.session_state.selected_courier = sel

    filtered = df if sel == "ALL" else df[df[courier_col] == sel]

    with col2:
        st.metric("📦 TOTAL", len(filtered))
        st.metric("✅ SCANNED", len(st.session_state.scanned))
        st.metric("❌ PENDING", len(filtered) - len(st.session_state.scanned))

    st.markdown("---")

    # ================== SCANNER ==================
    st.subheader("🔦 AUTO SCAN AREA")

    awb = st.text_input(
        "SCAN AWB HERE",
        key="SCANBOX",
        placeholder="Scanner auto input...",
        label_visibility="collapsed"
    )

    now = time.time()
    if awb and now - st.session_state.last_scan > 0.4:
        awb = awb.strip().upper()
        all_awb = filtered[awb_col].str.upper().values

        if awb in st.session_state.scanned:
            st.warning(f"⚠ DUPLICATE | {awb}")
            st.components.v1.html("<script>beep(400)</script>", height=0)

        elif awb in all_awb:
            st.success(f"✅ SCANNED | {awb}")
            st.session_state.scanned.add(awb)
            st.components.v1.html("<script>beep(900)</script>", height=0)

        else:
            st.error(f"❌ NOT FOUND | {awb}")
            st.components.v1.html("<script>beep(200)</script>", height=0)

        if "SCANBOX" in st.session_state:
            del st.session_state["SCANBOX"]

        st.session_state.last_scan = now
        st.rerun()

    st.markdown("---")

    # ================== TABLES ==================
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("✅ SCANNED")
        st.dataframe(
            filtered[filtered[awb_col].str.upper().isin(st.session_state.scanned)][[courier_col, awb_col]]
        )

    with c2:
        st.subheader("❌ MISSING")
        missing = set(filtered[awb_col].str.upper()) - st.session_state.scanned
        st.dataframe(filtered[filtered[awb_col].str.upper().isin(missing)][[courier_col, awb_col]])

    if st.button("🔄 RESET ALL", use_container_width=True):
        st.session_state.scanned.clear()
        st.rerun()

else:
    st.info("⬆ Upload CSV files to start scanning")
