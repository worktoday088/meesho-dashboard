# Meesho_PDF_Sorter_v7.py
# Final v7 — Courier -> Style -> Size filtering + per-style & filtered downloads
# Requirements:
# pip install streamlit pdfplumber PyPDF2

import streamlit as st
import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
import re
from io import BytesIO
from collections import defaultdict, OrderedDict

st.set_page_config(page_title="Meesho PDF Auto Sorter v7", layout="wide")
st.title("📦 Meesho Invoice Auto Sourcing – Final v7")
st.caption("Courier → Style → Size. Per-style and size-filtered downloads (for Bilal Sir)")

# --------- CONFIG ----------
COURIER_PRIORITY = ["Shadowfax", "Xpress Bees", "Delhivery", "Valmo"]
SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]

# style groups: list of keywords (lowercase substrings) → display name
STYLE_GROUPS = [
    (["zeme-01", "zeme01", "zeme", "2-pc", "2 pc", "2pc", "2pcs", "2-pcs", "2pcs jumpsuit", "2-pcs jumpsuit", "2 pc jumpsuit"], "Jumpsuit"),
    (["2 tape", "2-tape", "2 strip", "2-strip", "2strip", "2tape"], "2-Tape"),
    (["-2-s", " set of 2", " of 2", " of2", " of-2", r"\bof\b"], "Combo 2-Tape"),
    (["fruit"], "Fruit"),
    (["crop"], "Crop Hoodie"),
    (["plain", "plain trouser", "plain-trouser", "plain_trouser"], "Plain Trouser"),
]

def detect_courier(text):
    if not text:
        return "UNKNOWN"
    for c in COURIER_PRIORITY:
        if re.search(re.escape(c), text, re.IGNORECASE):
            return c
    return "UNKNOWN"

def detect_style(text):
    t = (text or "").lower()
    for patterns, name in STYLE_GROUPS:
        for pat in patterns:
            # treat pat as literal substring unless contains regex-like chars
            if re.search(re.escape(pat), t) or (pat.startswith("\\b") and re.search(pat, t)):
                return name
    return "Other"

def detect_size(text):
    """Return first matching size in SIZE_ORDER found on page text (stable)."""
    if not text:
        return "NA"
    t = text.upper()
    found = []
    for s in SIZE_ORDER:
        # match as token or inside parentheses etc.
        if re.search(rf"(?<![A-Z0-9]){re.escape(s)}(?![A-Z0-9])", t):
            found.append(s)
    # if multiple found, return the one with smallest index in SIZE_ORDER (priority)
    for s in SIZE_ORDER:
        if s in found:
            return s
    return "NA"

# --------- Upload PDF ----------
uploaded_file = st.file_uploader("📤 Upload Meesho Invoice PDF (original)", type=["pdf"])

if not uploaded_file:
    st.info("Upload a Meesho invoice PDF to begin (app will group by courier → style → size).")
    st.stop()

reader = PdfReader(uploaded_file)
total_pages = len(reader.pages)
st.success(f"📄 Loaded PDF — {total_pages} pages detected.")

# --------- Parse PDF into hierarchy ----------
# hierarchy: courier -> style -> size -> [page_indexes]
hierarchy = defaultdict(lambda: OrderedDict())
hierarchy["UNKNOWN"] = OrderedDict()
unparsed = []

with pdfplumber.open(uploaded_file) as pdf:
    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        courier = detect_courier(text)
        style = detect_style(text)
        size = detect_size(text)

        # ensure dict structure exists
        if style not in hierarchy[courier]:
            hierarchy[courier][style] = OrderedDict()
        if size not in hierarchy[courier][style]:
            hierarchy[courier][style][size] = []
        # avoid duplicate page index
        if i not in hierarchy[courier][style][size]:
            hierarchy[courier][style][size].append(i)

        if courier == "UNKNOWN" and style == "Other" and size == "NA":
            unparsed.append(i)

# Preview summary
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

# --------- Download UI: Courier → Style → size-filter ----------
st.header("📦 Download: Courier → Style → (choose sizes)")

for courier in COURIER_PRIORITY:
    styles = hierarchy.get(courier, {})
    if not styles:
        st.info(f"❌ No pages detected for {courier}")
        continue

    st.subheader(f"🚚 {courier}")
    cols = st.columns(3)
    # For each style show a card with multiselect sizes and two buttons (Full style, Filtered)
    for style_name, sizes_dict in styles.items():
        # collect available sizes present for this style, in SIZE_ORDER order
        available_sizes = [s for s in SIZE_ORDER if s in sizes_dict and sizes_dict[s]]
        # include 'NA' only if present
        if "NA" in sizes_dict and sizes_dict["NA"]:
            available_sizes.append("NA")

        with st.expander(f"Style: {style_name}  —  Pages: {sum(len(v) for v in sizes_dict.values())}", expanded=False):
            st.write(f"Available sizes for this style: {', '.join(available_sizes) if available_sizes else 'None detected'}")
            sizes_selected = st.multiselect(f"Select sizes to include — {courier} • {style_name}", options=available_sizes, default=available_sizes)
            # Buttons: download full style and download filtered
            col1, col2 = st.columns([1,1])
            with col1:
                if st.button(f"⬇️ Download Full — {courier} • {style_name}", key=f"full_{courier}_{style_name}"):
                    # build PDF with all pages for this style (size-order stable)
                    writer = PdfWriter()
                    # add pages in SIZE_ORDER then NA then any others
                    for s in SIZE_ORDER + ["NA"]:
                        pages = sizes_dict.get(s, [])
                        for pindex in pages:
                            writer.add_page(reader.pages[pindex])
                    buf = BytesIO()
                    writer.write(buf)
                    buf.seek(0)
                    st.download_button(label=f"Click to save {courier}_{style_name}.pdf",
                                       data=buf,
                                       file_name=f"{courier}_{style_name.replace(' ', '_')}.pdf",
                                       mime="application/pdf")
            with col2:
                if st.button(f"⬇️ Download Filtered — {courier} • {style_name}", key=f"filt_{courier}_{style_name}"):
                    if not sizes_selected:
                        st.error("No sizes selected — choose at least one size to download filtered PDF.")
                    else:
                        writer = PdfWriter()
                        # add pages only for selected sizes in stable order
                        for s in SIZE_ORDER + ["NA"]:
                            if s in sizes_selected:
                                pages = sizes_dict.get(s, [])
                                for pindex in pages:
                                    writer.add_page(reader.pages[pindex])
                        buf = BytesIO()
                        writer.write(buf)
                        buf.seek(0)
                        sel_label = "_".join(sizes_selected)
                        st.download_button(label=f"Click to save {courier}_{style_name}_{sel_label}.pdf",
                                           data=buf,
                                           file_name=f"{courier}_{style_name.replace(' ', '_')}_{sel_label}.pdf",
                                           mime="application/pdf")

st.success("Done — use the buttons above to download full-style PDFs or size-filtered PDFs. If some pages are not parsed correctly, share a sample page and I will tune detection rules.")
