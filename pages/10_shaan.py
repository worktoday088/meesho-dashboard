# Meesho_PDF_Sorter_v4.py
# Smart, stable grouping: courier -> canonical-style -> size -> pages
# pip install streamlit PyPDF2 pdfplumber

import streamlit as st
import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
import re
from io import BytesIO
from collections import defaultdict, OrderedDict

st.set_page_config(page_title="Meesho PDF Smart Sorter v4", layout="centered")
st.title("📦 Meesho Invoice Auto Sourcing – Advanced v4")
st.caption("Stable grouping: courier → canonical-style → sizes (no repeated size blocks)")

# Configuration
COURIER_PRIORITY = ["Shadowfax", "Xpress Bees", "Delhivery", "Valmo"]
SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]

# base style patterns -> canonical name (order here defines preferred style order inside each courier)
STYLE_CANONICAL = [
    (r"zeme[- ]?0?1", "ZEME-01"),
    (r"2[- ]?pc[s]?", "2-PC"),
    (r"2[- ]?(tape|strip)", "2-TAPE"),
    (r"\bfruit\b", "FRUIT"),
    (r"\bcrop\b", "CROP"),
    (r"-2-s\b", "OF"),
    (r"\bof\b", "OF")
]

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
    for s in SIZE_ORDER:
        # match whole token like " M " or "(M)" etc.
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(s)}(?![A-Za-z0-9])", text, re.IGNORECASE):
            return s
    return "NA"

uploaded_file = st.file_uploader("📤 Upload Meesho Invoice PDF", type=["pdf"])

if uploaded_file:
    reader = PdfReader(uploaded_file)
    total_pages = len(reader.pages)
    st.info(f"Total pages: {total_pages}")

    # Build nested structure: courier -> style -> size -> list(page_indexes)
    hierarchy = {c: OrderedDict() for c in COURIER_PRIORITY}
    hierarchy["UNKNOWN"] = OrderedDict()  # for uncategorized pages

    # keep a list of pages that couldn't be parsed for quick debug
    unparsed_pages = []

    with pdfplumber.open(uploaded_file) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            courier = detect_courier(text)
            style = detect_canonical_style(text)
            size = detect_size(text)

            # ensure style entry exists
            if style not in hierarchy.get(courier, {}):
                hierarchy.setdefault(courier, OrderedDict())[style] = OrderedDict()
            # ensure size list exists
            hierarchy[courier][style].setdefault(size, []).append(i)

            # debug mark if nothing found
            if courier == "UNKNOWN" and style == "OTHER" and size == "NA":
                unparsed_pages.append(i)

    st.write("Detected summary (sample):")
    # show small preview: for each courier list first few styles/sizes
    preview = []
    for c in COURIER_PRIORITY + ["UNKNOWN"]:
        if c not in hierarchy:
            continue
        for style, sizes in hierarchy[c].items():
            for size, pages in sizes.items():
                preview.append({"courier": c, "style": style, "size": size, "pages_count": len(pages)})
    st.dataframe(preview[:50])

    if unparsed_pages:
        st.warning(f"Warning: {len(unparsed_pages)} pages could not be parsed (pages: {unparsed_pages[:10]}...)")

    # Now create courier-wise PDF files using stable ordering:
    st.subheader("📦 Download Per-Courier Sorted PDFs")
    for courier in COURIER_PRIORITY:
        # if no pages for this courier, show message
        styles_dict = hierarchy.get(courier, {})
        if not styles_dict:
            st.write(f"❌ No pages found for {courier}")
            continue

        writer = PdfWriter()

        # Determine style iteration order:
        # 1) use canonical order defined in STYLE_CANONICAL
        # 2) then any other styles (OTHER or unexpected) in alphabetical order
        canon_order = [canon for _, canon in STYLE_CANONICAL]
        observed_styles = list(styles_dict.keys())
        # keep unique preserving order: first canon that occur, then others
        ordered_styles = []
        for ccanon in canon_order:
            if ccanon in observed_styles and ccanon not in ordered_styles:
                ordered_styles.append(ccanon)
        # append remaining observed styles
        for s in observed_styles:
            if s not in ordered_styles:
                ordered_styles.append(s)

        # For each style, append pages in SIZE_ORDER order (sizes with page lists)
        for style in ordered_styles:
            sizes_map = styles_dict.get(style, {})
            # for sizes in SIZE_ORDER, then NA, then any others
            for s in SIZE_ORDER + ["NA"]:
                pages_for_size = sizes_map.get(s, [])
                for page_index in pages_for_size:
                    writer.add_page(reader.pages[page_index])
            # append any unexpected sizes (keys not in SIZE_ORDER and not "NA")
            for s_unexp in [k for k in sizes_map.keys() if k not in SIZE_ORDER and k != "NA"]:
                for page_index in sizes_map[s_unexp]:
                    writer.add_page(reader.pages[page_index])

        # write buffer and provide download
        buf = BytesIO()
        writer.write(buf)
        buf.seek(0)
        st.download_button(
            label=f"⬇️ Download {courier} PDF",
            data=buf,
            file_name=f"{courier}_Sorted_v4.pdf",
            mime="application/pdf"
        )

    st.success("Finished: courier-wise PDFs are ready. Each style's sizes appear as one contiguous block.")
else:
    st.info("Upload a Meesho PDF to process.")
