import streamlit as st
import pdfplumber, hashlib
from PyPDF2 import PdfReader, PdfWriter
import re
from io import BytesIO
from collections import defaultdict

st.set_page_config(page_title="Meesho PDF Auto Sorter v6", layout="wide")
st.title("📦 Meesho Invoice Auto Sourcing – Final v6")
st.caption("Developed for Bilal Sir — Courier ➜ Style ➜ Size")

COURIER_PRIORITY = ["Shadowfax", "Xpress Bees", "Delhivery", "Valmo"]
SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]
STYLE_GROUPS = [
    (["zeme-01","zeme01","2-pc","2pcs","2 pcs","2pcs jumpsuit","2-pcs jumpsuit"], "Jumpsuit"),
    (["2 tape","2 strip","2-tape","2-strip"], "2-Tape"),
    (["of","-2-s"], "Combo 2-Tape"),
    (["fruit"], "Fruit"),
    (["crop"], "Crop Hoodie"),
    (["plain"], "Plain Trouser"),
]

def detect_courier(t):
    for c in COURIER_PRIORITY:
        if re.search(re.escape(c), t, re.IGNORECASE): return c
    return "UNKNOWN"
def detect_style(t):
    t=t.lower()
    for pats,name in STYLE_GROUPS:
        for p in pats:
            if re.search(rf"\b{re.escape(p)}\b", t): return name
    return "Other"
def detect_size(t):
    for s in SIZE_ORDER:
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(s)}(?![A-Za-z0-9])", t, re.IGNORECASE):
            return s
    return "NA"

# --- State init ---
if "buffers" not in st.session_state: st.session_state.buffers = {}
if "meta" not in st.session_state: st.session_state.meta = {}
if "ready" not in st.session_state: st.session_state.ready = False
if "file_key" not in st.session_state: st.session_state.file_key = None

@st.cache_data(show_spinner=False)
def build_cached(pdf_bytes: bytes):
    reader = PdfReader(BytesIO(pdf_bytes))
    total_pages = len(reader.pages)
    hierarchy = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    unparsed = []
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for i,p in enumerate(pdf.pages):
            text = p.extract_text() or ""
            c = detect_courier(text); s = detect_style(text); z = detect_size(text)
            hierarchy[c][s][z].append(i)
            if c=="UNKNOWN" and s=="Other" and z=="NA": unparsed.append(i)
    # pre-merge buffers
    buffers = {}
    for c in COURIER_PRIORITY:
        styles = hierarchy.get(c,{})
        for style_name, sizes_dict in styles.items():
            if not any(sizes_dict.values()): continue
            w = PdfWriter(); added=set()
            for z in SIZE_ORDER+["NA"]:
                for p in sizes_dict.get(z, []):
                    if p not in added:
                        w.add_page(reader.pages[p]); added.add(p)
            buf = BytesIO(); w.write(buf); buf.seek(0)
            buffers[(c,style_name)] = buf
    return buffers, {"pages": total_pages, "unparsed": unparsed}

uploaded = st.file_uploader("📤 Upload Meesho Invoice PDF", type=["pdf"])

# Build once per unique file
if uploaded and not st.session_state.ready:
    file_bytes = uploaded.read()
    file_key = hashlib.md5(file_bytes).hexdigest()
    if st.session_state.file_key != file_key:
        buffers, meta = build_cached(file_bytes)
        st.session_state.buffers = buffers
        st.session_state.meta = meta
        st.session_state.file_key = file_key
    st.session_state.ready = True

# Static info (no spinner on rerun)
if st.session_state.ready:
    m = st.session_state.meta
    st.info(f"📄 Total pages detected: {m.get('pages',0)}")
    if m.get("unparsed"): st.warning(f"⚠️ {len(m['unparsed'])} pages could not be identified. Example: {m['unparsed'][:10]}")
    st.header("📦 Download Courier + Style-wise Sorted PDFs")

    # Pure download fragment: no processing, just buttons
    with st.container():
        for courier in COURIER_PRIORITY:
            has_any = any(k[0]==courier for k in st.session_state.buffers)
            if not has_any: continue
            st.subheader(f"🚚 {courier}")
            for (c, style), buf in st.session_state.buffers.items():
                if c!=courier: continue
                st.download_button(
                    label=f"⬇️ Download {courier} – {style}",
                    data=buf,
                    file_name=f"{courier}_{style.replace(' ','_')}.pdf",
                    mime="application/pdf",
                    use_container_width=False
                )
    st.success("🎉 All files ready! Download courier + style-wise sorted PDFs above.")
else:
    st.info("Please upload a Meesho Invoice PDF file to start sorting.")
