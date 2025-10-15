# --------------------------------------------------------------
# 📦 Meesho Invoice Auto Sourcing Sorter (v5 - Stable Version)
# --------------------------------------------------------------
# Required:
# pip install streamlit PyPDF2 pdfplumber
# Run:
# streamlit run Meesho_PDF_Sorter_v5.py

import streamlit as st
import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
import re
from io import BytesIO
from collections import defaultdict, OrderedDict

st.set_page_config(page_title="Meesho PDF Smart Sorter v5", layout="centered")

st.title("📦 Meesho Invoice Auto Sourcing – Final v5")
st.caption("Developed for Bilal Sir — Fully stable version (courier → style → size with duplicate fix)")

# ----------------------------------------------------
# Configuration
# ----------------------------------------------------
COURIER_PRIORITY = ["Shadowfax", "Xpress Bees", "Delhivery", "Valmo"]
SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]

STYLE_CANONICAL = [
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

def detect_canonical_style(text):
    t = text.lower()
    for pat, canon in STYLE_CANONICAL:
        if re.search(pat, t):
            return canon
    return "OTHER"

def detect_size(text):
    """Detect only first valid size from XS,S,M,L,XL,XXL in page text"""
    found = []
    for s in SIZE_ORDER:
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(s)}(?![A-Za-z0-9])", text, re.IGNORECASE):
            found.append(s)
    if found:
        # unique sizes, keep first in order of SIZE_ORDER
        for s in SIZE_ORDER:
            if s in found:
                return s
    return "NA"

# ----------------------------------------------------
# Main Streamlit UI
# ----------------------------------------------------
uploaded_file = st.file_uploader("📤 Upload Meesho Invoice PDF", type=["pdf"])

if uploaded_file:
    reader = PdfReader(uploaded_file)
    total_pages = len(reader.pages)
    st.info(f"Total pages detected: {total_pages}")

    # courier -> style -> size -> list of page indexes
    hierarchy = {c: OrderedDict() for c in COURIER_PRIORITY}
    hierarchy["UNKNOWN"] = OrderedDict()
    unparsed_pages = []

    with pdfplumber.open(uploaded_file) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            courier = detect_courier(text)
            style = detect_canonical_style(text)
            size = detect_size(text)

            # initialize dict structure
            if style not in hierarchy.setdefault(courier, OrderedDict()):
                hierarchy[courier][style] = OrderedDict()
            hierarchy[courier][style].setdefault(size, [])

            # Prevent duplicates: add only if page not already in same style-size list
            if i not in hierarchy[courier][style][size]:
                hierarchy[courier][style][size].append(i)

            if courier == "UNKNOWN" and style == "OTHER" and size == "NA":
                unparsed_pages.append(i)

    st.success("✅ PDF processed successfully!")

    # Quick preview
    preview = []
    for c in COURIER_PRIORITY + ["UNKNOWN"]:
        if c not in hierarchy:
            continue
        for style, sizes in hierarchy[c].items():
            for size, pages in sizes.items():
                preview.append({"Courier": c, "Style": style, "Size": size, "Pages": len(pages)})
    st.dataframe(preview[:40])

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

        # determine fixed style order (canonical)
        canon_order = [canon for _, canon in STYLE_CANONICAL]
        observed_styles = list(styles_dict.keys())
        ordered_styles = []
        for ccanon in canon_order:
            if ccanon in observed_styles and ccanon not in ordered_styles:
                ordered_styles.append(ccanon)
        for s in observed_styles:
            if s not in ordered_styles:
                ordered_styles.append(s)

        # write pages
        for style in ordered_styles:
            sizes_map = styles_dict.get(style, {})
            # size order stable
            for s in SIZE_ORDER + ["NA"]:
                pages_for_size = sizes_map.get(s, [])
                # avoid repeats (if duplicate sizes exist)
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
            file_name=f"{courier}_Sorted_v5.pdf",
            mime="application/pdf"
        )

    st.success("🎉 Done! Each courier's PDF is now size-wise sorted and duplicates are fixed.")
else:
    st.info("Please upload a Meesho Invoice PDF to start sorting.")
