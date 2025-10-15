# Meesho_PDF_Sorter_v7_1.py
# Final v7.1 — Crop fix + stable Courier->Style->Size grouping & per-style size-filtered downloads
# Run:
# pip install streamlit pdfplumber PyPDF2
# streamlit run Meesho_PDF_Sorter_v7_1.py

import streamlit as st
import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
import re
from io import BytesIO
from collections import defaultdict, OrderedDict

st.set_page_config(page_title="Meesho PDF Auto Sorter v7.1", layout="wide")
st.title("📦 Meesho Invoice Auto Sourcing – Final v7.1")
st.caption("Crop fixed — Courier → Style → Size. Per-style and size-filtered downloads.")

# --------- CONFIG ----------
COURIER_PRIORITY = ["Shadowfax", "Xpress Bees", "Delhivery", "Valmo"]
SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]

# STYLE_GROUPS: each item is (list_of_regex_patterns, display_name)
# Patterns are regular expressions (lowercase matching will be used in detect)
STYLE_GROUPS = [
    # Jumpsuit / ZEME / 2-PC family
    ([
        r"zeme[- ]?0?1", r"zeme01", r"\b2[- ]?pc[s]?\b", r"\b2 ?pc\b", r"\b2pcs?\b",
        r"2[- ]?pcs? jumpsuit", r"2pc jumpsuit"
     ], "Jumpsuit"),

    # 2-Tape family
    ([r"\b2[- ]?tape\b", r"\b2[- ]?strip\b", r"\b2tape\b", r"\b2strip\b"], "2-Tape"),

    # Combo / OF / set-of-2 family (use word boundaries where appropriate)
    ([r"-2-s\b", r"\bset of 2\b", r"\bof 2\b", r"\bof\b"], "Combo 2-Tape"),

    # Fruit
    ([r"\bfruit\b"], "Fruit"),

    # Crop — FIXED: use exact word boundary so '2-crop' or 'cropper' don't match
    ([r"\bcrop\b"], "Crop Hoodie"),

    # Plain Trouser
    ([r"\bplain\b", r"\bplain[-_ ]?trouser\b"], "Plain Trouser"),
]

# ---------- Helpers ----------
def detect_courier(text):
    if not text:
        return "UNKNOWN"
    for courier in COURIER_PRIORITY:
        if re.search(re.escape(courier), text, re.IGNORECASE):
            return courier
    return "UNKNOWN"

def detect_style(text):
    t = (text or "").lower()
    for patterns, display in STYLE_GROUPS:
        for pat in patterns:
            try:
                if re.search(pat, t, re.IGNORECASE):
                    return display
            except re.error:
                # fallback: literal substring if regex invalid
                if pat in t:
                    return display
    return "Other"

def detect_size(text):
    if not text:
        return "NA"
    t = (text or "").upper()
    found = []
    for s in SIZE_ORDER:
        # match size as separate token or in parentheses etc.
        if re.search(rf"(?<![A-Z0-9]){re.escape(s)}(?![A-Z0-9])", t):
            found.append(s)
    # choose the highest-priority size found (XS first ...)
    for s in SIZE_ORDER:
        if s in found:
            return s
    return "NA"

# --------- Upload and parse ----------
uploaded_file = st.file_uploader("📤 Upload Meesho Invoice PDF (original)", type=["pdf"])
if not uploaded_file:
    st.info("Upload a Meesho invoice PDF to begin.")
    st.stop()

reader = PdfReader(uploaded_file)
total_pages = len(reader.pages)
st.success(f"📄 Loaded PDF — {total_pages} pages detected.")

# Build hierarchy: courier -> style -> size -> [page_indexes]
hierarchy = defaultdict(lambda: OrderedDict())
hierarchy["UNKNOWN"] = OrderedDict()
unparsed = []

with pdfplumber.open(uploaded_file) as pdf:
    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        courier = detect_courier(text)
        style = detect_style(text)
        size = detect_size(text)

        # ensure nested maps exist
        if style not in hierarchy[courier]:
            hierarchy[courier][style] = OrderedDict()
        if size not in hierarchy[courier][style]:
            hierarchy[courier][style][size] = []
        # add page index if not duplicate
        if i not in hierarchy[courier][style][size]:
            hierarchy[courier][style][size].append(i)

        if courier == "UNKNOWN" and style == "Other" and size == "NA":
            unparsed.append(i)

# Preview
st.subheader("Detected groups (preview)")
preview_rows = []
for c in COURIER_PRIORITY + ["UNKNOWN"]:
    if c not in hierarchy:
        continue
    for style, sizes in hierarchy[c].items():
        total = sum(len(pages) for pages in sizes.values())
        preview_rows.append({"Courier": c, "Style": style, "TotalPages": total})
st.dataframe(preview_rows)

if unparsed:
    st.warning(f"⚠ {len(unparsed)} pages seem unparsed (example indices): {unparsed[:10]}")

# --------- Download UI ----------
st.header("📦 Download: Courier → Style → (select sizes)")

for courier in COURIER_PRIORITY:
    styles = hierarchy.get(courier, {})
    if not styles:
        st.info(f"❌ No pages detected for {courier}")
        continue

    st.subheader(f"🚚 {courier}")
    for style_name, sizes_dict in styles.items():
        available_sizes = [s for s in SIZE_ORDER if s in sizes_dict and sizes_dict[s]]
        if "NA" in sizes_dict and sizes_dict["NA"]:
            available_sizes.append("NA")

        with st.expander(f"Style: {style_name}  —  Pages: {sum(len(v) for v in sizes_dict.values())}", expanded=False):
            st.write(f"Available sizes: {', '.join(available_sizes) if available_sizes else 'None detected'}")
            sizes_selected = st.multiselect(f"Select sizes — {courier} • {style_name}", options=available_sizes, default=available_sizes)
            col1, col2 = st.columns([1,1])
            with col1:
                if st.button(f"⬇️ Download Full — {courier} • {style_name}", key=f"full_{courier}_{style_name}"):
                    writer = PdfWriter()
                    for s in SIZE_ORDER + ["NA"]:
                        pages = sizes_dict.get(s, [])
                        for pindex in pages:
                            writer.add_page(reader.pages[pindex])
                    buf = BytesIO()
                    writer.write(buf)
                    buf.seek(0)
                    st.download_button(label=f"Save {courier}_{style_name}.pdf", data=buf, file_name=f"{courier}_{style_name.replace(' ', '_')}.pdf", mime="application/pdf")
            with col2:
                if st.button(f"⬇️ Download Filtered — {courier} • {style_name}", key=f"filt_{courier}_{style_name}"):
                    if not sizes_selected:
                        st.error("Select at least one size to download filtered PDF.")
                    else:
                        writer = PdfWriter()
                        for s in SIZE_ORDER + ["NA"]:
                            if s in sizes_selected:
                                pages = sizes_dict.get(s, [])
                                for pindex in pages:
                                    writer.add_page(reader.pages[pindex])
                        buf = BytesIO()
                        writer.write(buf)
                        buf.seek(0)
                        sel_label = "_".join(sizes_selected)
                        st.download_button(label=f"Save {courier}_{style_name}_{sel_label}.pdf", data=buf, file_name=f"{courier}_{style_name.replace(' ', '_')}_{sel_label}.pdf", mime="application/pdf")

st.success("✅ Crop grouping fixed. Use the download buttons above to get courier+style (and size-filtered) PDFs.")
