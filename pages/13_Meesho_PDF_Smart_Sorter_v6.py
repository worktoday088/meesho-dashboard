
# --------------------------------------------------------------
# 📦 Meesho Invoice Auto Sourcing Sorter (v6 - MultiPDF + Custom Styles)
# --------------------------------------------------------------
# Required:
# pip install streamlit PyPDF2 pdfplumber
# Run:
# streamlit run Meesho_PDF_Smart_Sorter_v6.py

import streamlit as st
import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
import re
from io import BytesIO
from collections import OrderedDict

st.set_page_config(page_title="Meesho PDF Smart Sorter v6", layout="centered")

st.title("📦 Meesho Invoice Auto Sourcing – v6 (Multi PDF + Custom Style Input)")
st.caption("Developed for Bilal Sir — Auto merge & client-specific style order supported")

# ----------------------------------------------------
# Configuration
# ----------------------------------------------------
COURIER_PRIORITY = ["Shadowfax", "Xpress Bees", "Delhivery", "Valmo"]
SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]

DEFAULT_STYLE_CANONICAL = [
    (r"zeme[- ]?0?1", "ZEME-01"),
    (r"2[- ]?pc[s]?", "2-PC"),
    (r"2[- ]?(tape|strip)", "2-TAPE"),
    (r"\bfruit\b", "FRUIT"),
    (r"\bcrop\b", "CROP"),
    (r"-2-s\b", "OF"),
    (r"\bof\b", "OF")
]

# ----------------------------------------------------
# Helper functions
# ----------------------------------------------------
def detect_courier(text):
    for c in COURIER_PRIORITY:
        if re.search(re.escape(c), text, re.IGNORECASE):
            return c
    return "UNKNOWN"

def detect_canonical_style(text, canonical_patterns):
    t = text.lower()
    for pat, canon in canonical_patterns:
        if re.search(pat, t):
            return canon
    return "OTHER"

def detect_size(text):
    for s in SIZE_ORDER:
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(s)}(?![A-Za-z0-9])", text, re.IGNORECASE):
            return s
    return "NA"

# ----------------------------------------------------
# UI Inputs
# ----------------------------------------------------
uploaded_files = st.file_uploader("📤 Upload one or more Meesho Invoice PDFs", type=["pdf"], accept_multiple_files=True)

custom_style_input = st.text_input("✏️ Enter your custom style names (comma separated)", placeholder="e.g. A1, A2, FRUIT, CROP")
st.caption("These styles will be used in the same order for sorting. Leave empty for default pattern matching.")

if uploaded_files:
    # Merge PDFs if multiple
    writer_merge = PdfWriter()
    for uf in uploaded_files:
        reader_temp = PdfReader(uf)
        for p in reader_temp.pages:
            writer_merge.add_page(p)
    merged_buf = BytesIO()
    writer_merge.write(merged_buf)
    merged_buf.seek(0)

    reader = PdfReader(merged_buf)
    total_pages = len(reader.pages)
    st.info(f"📄 Total combined pages detected: {total_pages}")

    # Define canonical list
    if custom_style_input.strip():
        custom_styles = [s.strip() for s in custom_style_input.split(",") if s.strip()]
        STYLE_CANONICAL = [(rf"\b{s.lower()}\b", s.upper()) for s in custom_styles]
    else:
        STYLE_CANONICAL = DEFAULT_STYLE_CANONICAL

    # Build hierarchy
    hierarchy = {c: OrderedDict() for c in COURIER_PRIORITY}
    hierarchy["UNKNOWN"] = OrderedDict()
    unparsed_pages = []

    with pdfplumber.open(merged_buf) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            courier = detect_courier(text)
            style = detect_canonical_style(text, STYLE_CANONICAL)
            size = detect_size(text)

            if style not in hierarchy.setdefault(courier, OrderedDict()):
                hierarchy[courier][style] = OrderedDict()
            hierarchy[courier][style].setdefault(size, [])

            if i not in hierarchy[courier][style][size]:
                hierarchy[courier][style][size].append(i)

            if courier == "UNKNOWN" and style == "OTHER" and size == "NA":
                unparsed_pages.append(i)

    st.success("✅ All PDFs processed successfully!")

    # Preview Table
    preview = []
    for c in COURIER_PRIORITY + ["UNKNOWN"]:
        if c not in hierarchy:
            continue
        for style, sizes in hierarchy[c].items():
            for size, pages in sizes.items():
                preview.append({"Courier": c, "Style": style, "Size": size, "Pages": len(pages)})
    st.dataframe(preview[:60])

    if unparsed_pages:
        st.warning(f"{len(unparsed_pages)} pages could not be parsed. (e.g. pages: {unparsed_pages[:10]})")

    # ----------------------------------------------------
    # Courier-wise output
    # ----------------------------------------------------
    st.subheader("📦 Download Sorted PDFs (Courier-wise)")

    for courier in COURIER_PRIORITY:
        styles_dict = hierarchy.get(courier, {})
        if not styles_dict:
            st.write(f"❌ No pages found for {courier}")
            continue

        writer = PdfWriter()

        # determine style order
        canon_order = [canon for _, canon in STYLE_CANONICAL]
        observed_styles = list(styles_dict.keys())
        ordered_styles = []
        for ccanon in canon_order:
            if ccanon in observed_styles and ccanon not in ordered_styles:
                ordered_styles.append(ccanon)
        for s in observed_styles:
            if s not in ordered_styles:
                ordered_styles.append(s)

        for style in ordered_styles:
            sizes_map = styles_dict.get(style, {})
            for s in SIZE_ORDER + ["NA"]:
                pages_for_size = sizes_map.get(s, [])
                added = set()
                for page_index in pages_for_size:
                    if page_index not in added:
                        writer.add_page(reader.pages[page_index])
                        added.add(page_index)

        buf = BytesIO()
        writer.write(buf)
        buf.seek(0)
        st.download_button(
            label=f"⬇️ Download {courier} PDF",
            data=buf,
            file_name=f"{courier}_Sorted_v6.pdf",
            mime="application/pdf"
        )

    st.success("🎉 All PDFs merged and sorted successfully!")
else:
    st.info("Please upload one or more Meesho Invoice PDFs to start sorting.")
