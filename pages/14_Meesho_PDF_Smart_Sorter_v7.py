
# --------------------------------------------------------------
# 📦 Meesho Invoice Auto Sourcing Sorter (v7 - MultiPDF + Custom Styles + Courier+Style Selection)
# --------------------------------------------------------------
# Required:
# pip install streamlit PyPDF2 pdfplumber
# Run:
# streamlit run Meesho_PDF_Smart_Sorter_v7.py

import streamlit as st
import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
import re
from io import BytesIO
from collections import OrderedDict

st.set_page_config(page_title="Meesho PDF Smart Sorter v7", layout="centered")

st.title("📦 Meesho Invoice Auto Sourcing – v7 (MultiPDF + Custom Styles + Selection)")
st.caption("Features: Multi-PDF merge, custom style order, courier+style selection, combined download")

# ----------------------------------------------------
# Configuration
# ----------------------------------------------------
COURIER_PRIORITY = ["Shadowfax", "Xpress Bees", "Delhivery", "Valmo"]
SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]

DEFAULT_STYLE_CANONICAL = [
    (r"zeme[- ]?0?1", "ZEME-01"),
    (r"2[- ]?pc[s]?", "2-PC"),
    (r"2[- ]?(tape|strip)", "2-TAPE"),
    (r"\\bfruit\\b", "FRUIT"),
    (r"\\bcrop\\b", "CROP"),
    (r"-2-s\\b", "OF"),
    (r"\\bof\\b", "OF")
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
    # First check canonical patterns (regex)
    for pat, canon in canonical_patterns:
        try:
            if re.search(pat, t):
                return canon
        except re.error:
            # fallback to simple substring match if pattern invalid
            if pat in t:
                return canon
    # If not matched using patterns, return OTHER
    return "OTHER"

def detect_size(text):
    for s in SIZE_ORDER:
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(s)}(?![A-Za-z0-9])", text, re.IGNORECASE):
            return s
    return "NA"

def make_download_bytes(page_indices, reader):
    """Given list of page indices (relative to merged reader), return BytesIO of PDF"""
    writer = PdfWriter()
    added = set()
    for idx in page_indices:
        if idx in added:
            continue
        writer.add_page(reader.pages[idx])
        added.add(idx)
    buf = BytesIO()
    writer.write(buf)
    buf.seek(0)
    return buf

# ----------------------------------------------------
# UI Inputs
# ----------------------------------------------------
uploaded_files = st.file_uploader("📤 Upload one or more Meesho Invoice PDFs", type=["pdf"], accept_multiple_files=True)

custom_style_input = st.text_input("✏️ Enter your custom style names (comma separated)", placeholder="e.g. 77-KJR, 8-PATTI, SIMPLE, 3 CHECK")
st.caption("These styles (in the same order) will be used for sorting and will appear as selectable style names per courier. Leave empty to use default canonical patterns.")

# Option: download merged raw PDF
download_merged_raw = st.checkbox("Provide 'Download Raw Merged PDF' button", value=True)

if uploaded_files:
    # Merge PDFs if multiple
    writer_merge = PdfWriter()
    for uf in uploaded_files:
        try:
            reader_temp = PdfReader(uf)
            for p in reader_temp.pages:
                writer_merge.add_page(p)
        except Exception as e:
            st.error(f"Error reading one of the uploaded PDFs: {e}")
            st.stop()
    merged_buf = BytesIO()
    writer_merge.write(merged_buf)
    merged_buf.seek(0)

    reader = PdfReader(merged_buf)
    total_pages = len(reader.pages)
    st.info(f"📄 Total combined pages detected: {total_pages}")

    # Define canonical list
    if custom_style_input.strip():
        # build canonical_patterns from user input; match substrings case-insensitively
        custom_styles = [s.strip() for s in custom_style_input.split(",") if s.strip()]
        # create simple patterns that match the style text inside the page text
        canonical_patterns = []
        for s in custom_styles:
            # use escaped lowercased token for simple search; pattern tries word-like match but allows hyphens/numbers
            pat = re.escape(s.lower())
            canonical_patterns.append((pat, s.upper()))
    else:
        canonical_patterns = DEFAULT_STYLE_CANONICAL

    # Build hierarchy
    hierarchy = {c: OrderedDict() for c in COURIER_PRIORITY}
    hierarchy["UNKNOWN"] = OrderedDict()
    unparsed_pages = []

    with pdfplumber.open(merged_buf) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            courier = detect_courier(text)
            style = detect_canonical_style(text, canonical_patterns)
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
    st.dataframe(preview[:120])

    if unparsed_pages:
        st.warning(f"{len(unparsed_pages)} pages could not be parsed. (e.g. pages: {unparsed_pages[:10]})")

    # Optional: raw merged download
    if download_merged_raw:
        merged_buf.seek(0)
        st.download_button("⬇️ Download Raw Merged PDF", data=merged_buf, file_name="Merged_Raw.pdf", mime="application/pdf")

    # ----------------------------------------------------
    # Courier-wise output with per-courier style selection
    # ----------------------------------------------------
    st.subheader("📦 Courier-wise: select styles to include per courier")

    # store selections here
    selections_by_courier = {}

    for courier in COURIER_PRIORITY:
        st.markdown(f"**{courier}**")
        styles_dict = hierarchy.get(courier, {})
        if not styles_dict:
            st.write(f"❌ No pages found for {courier}")
            continue

        observed_styles = list(styles_dict.keys())
        # Present multiselect of observed styles (show in canonical order if possible)
        # Determine order: first follow canonical_patterns order, then append others
        canonical_order = [canon for _, canon in canonical_patterns]
        ordered_styles = []
        for ccanon in canonical_order:
            if ccanon in observed_styles and ccanon not in ordered_styles:
                ordered_styles.append(ccanon)
        for s in observed_styles:
            if s not in ordered_styles:
                ordered_styles.append(s)

        sel_key = f"sel_{courier.replace(' ', '_')}"
        selected = st.multiselect(f"Select styles for {courier} (leave empty for ALL styles)", options=ordered_styles, key=sel_key)
        selections_by_courier[courier] = selected

        # Create per-courier download button
        # If selected empty -> include all styles for courier
        include_styles = selected if selected else ordered_styles

        # gather page indices matching include_styles
        pages_to_write = []
        for style in include_styles:
            sizes_map = styles_dict.get(style, {})
            for s in SIZE_ORDER + ["NA"]:
                pages = sizes_map.get(s, [])
                for p in pages:
                    if p not in pages_to_write:
                        pages_to_write.append(p)

        if pages_to_write:
            buf = make_download_bytes(pages_to_write, reader)
            st.download_button(label=f"⬇️ Download {courier} – Selected Styles ({len(pages_to_write)} pages)",
                               data=buf,
                               file_name=f"{courier}_Selected_Styles.pdf",
                               mime="application/pdf")
        else:
            st.info("No pages found for the selected styles for this courier.")

    # ----------------------------------------------------
    # Combined Download: All selected styles across couriers
    # ----------------------------------------------------
    st.subheader("📥 Combined Download — all selected styles across couriers")

    # Collect all selected page indices
    combined_pages = []
    for courier, selected in selections_by_courier.items():
        styles_dict = hierarchy.get(courier, {})
        if not styles_dict:
            continue
        # if user left selection empty for a courier, treat as 'all styles' for that courier
        observed_styles = list(styles_dict.keys())
        canonical_order = [canon for _, canon in canonical_patterns]
        ordered_styles = []
        for ccanon in canonical_order:
            if ccanon in observed_styles and ccanon not in ordered_styles:
                ordered_styles.append(ccanon)
        for s in observed_styles:
            if s not in ordered_styles:
                ordered_styles.append(s)
        include_styles = selected if selected else ordered_styles

        for style in include_styles:
            sizes_map = styles_dict.get(style, {})
            for s in SIZE_ORDER + ["NA"]:
                pages = sizes_map.get(s, [])
                for p in pages:
                    if p not in combined_pages:
                        combined_pages.append(p)

    if combined_pages:
        combined_buf = make_download_bytes(combined_pages, reader)
        st.download_button(label=f"⬇️ Download All Selected Styles (Combined) — {len(combined_pages)} pages",
                           data=combined_buf,
                           file_name="All_Couriers_Selected_Styles_Combined.pdf",
                           mime="application/pdf")
    else:
        st.info("No pages selected across couriers yet. Use the multiselects above to choose styles to include.")

    st.success("🎉 Done — courier+style selection enabled. Use the downloads for packing.")
else:
    st.info("Please upload one or more Meesho Invoice PDFs to start sorting.")
