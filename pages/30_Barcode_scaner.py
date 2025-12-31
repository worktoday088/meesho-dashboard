import streamlit as st
import pandas as pd
import io

# ================= CONFIG =================
st.set_page_config(
    page_title="Return Packet Scanner PRO",
    layout="wide",
    page_icon="📦"
)

# ================= COURIER ALIAS =================
COURIER_MAP = {
    "POCKETSHIP": "VALMO",
    "VALMO": "VALMO"
}

def normalize_courier(name):
    if pd.isna(name):
        return name
    name = str(name).upper().strip()
    return COURIER_MAP.get(name, name)

# ================= CSS + JS =================
st.markdown("""
<style>
input {
    font-size: 30px !important;
    height: 65px !important;
}
</style>

<script>
function speak(text){
    const msg = new SpeechSynthesisUtterance(text);
    msg.rate = 1;
    window.speechSynthesis.speak(msg);
}

function clearAndFocus(){
    const inp = parent.document.querySelector('input');
    if(inp){
        inp.value = "";
        inp.focus();
    }
}
</script>
""", unsafe_allow_html=True)

# ================= SESSION =================
st.session_state.setdefault("scanned", set())
st.session_state.setdefault("loaded", False)

# ================= CSV LOAD =================
def load_csv(file):
    raw = file.read().decode("utf-8", errors="ignore")
    lines = raw.split("\n")[6:]
    return pd.read_csv(io.StringIO("\n".join(lines)), engine="python", on_bad_lines="skip")

# ================= UPLOAD =================
files = st.file_uploader("Upload CSV", type=["csv"], accept_multiple_files=True)

if files and not st.session_state.loaded:
    dfs = []
    for f in files:
        dfs.append(load_csv(f))

    df = pd.concat(dfs, ignore_index=True)

    courier_col = next(c for c in df.columns if "courier" in c.lower())
    awb_col = next(c for c in df.columns if "awb" in c.lower())

    df[courier_col] = df[courier_col].apply(normalize_courier)
    df[awb_col] = df[awb_col].astype(str).str.strip()

    df = df.drop_duplicates(subset=[awb_col])

    st.session_state.df = df
    st.session_state.courier_col = courier_col
    st.session_state.awb_col = awb_col
    st.session_state.loaded = True
    st.rerun()

# ================= SCAN HANDLER =================
def on_scan():
    raw = st.session_state.SCAN.strip().upper()
    awb = raw[-18:]  # last AWB only

    df = st.session_state.df
    awbs = df[st.session_state.awb_col].str.upper().values

    if awb in st.session_state.scanned:
        st.warning(f"⚠ DUPLICATE | {awb}")
        st.components.v1.html("<script>speak('Duplicate');clearAndFocus()</script>", height=0)

    elif awb in awbs:
        st.success(f"✅ SCANNED | {awb}")
        st.session_state.scanned.add(awb)
        st.components.v1.html("<script>speak('Scanned');clearAndFocus()</script>", height=0)

    else:
        st.error(f"❌ NOT FOUND | {awb}")
        st.components.v1.html("<script>speak('Not Found');clearAndFocus()</script>", height=0)

    st.session_state.SCAN = ""

# ================= UI =================
st.title("📦 RETURN SCANNER – FINAL (VIDEO STYLE)")

if st.session_state.loaded:
    st.text_input(
        "Scan AWB",
        key="SCAN",
        on_change=on_scan,
        placeholder="Scan packet…",
        label_visibility="collapsed"
    )

    df = st.session_state.df
    total = len(df)
    scanned = len(st.session_state.scanned)

    c1, c2, c3 = st.columns(3)
    c1.metric("TOTAL", total)
    c2.metric("SCANNED", scanned)
    c3.metric("PENDING", total - scanned)
else:
    st.info("Upload CSV to start")
