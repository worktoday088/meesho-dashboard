# --------------------------------------------------------------
# 📦 Streamlit App: Meesho PDF Auto Sourcing Sorter (Advanced v3)
# --------------------------------------------------------------
# Required:
# pip install streamlit PyPDF2 pdfplumber
# Run: streamlit run Meesho_PDF_Sorter_v3.py

import streamlit as st
import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
import re
from io import BytesIO

st.set_page_config(page_title="Meesho PDF Smart Sorter v3", layout="centered")

st.title("📦 Meesho Invoice Auto Sourcing – Advanced v3")
st.caption("Developed for Bilal Sir – Smart PDF sorter with base-style grouping & courier-wise downloads")

# ----------------------------------------------------
# Configuration
# ----------------------------------------------------
COURIER_PRIORITY = ["Shadowfax", "Xpress Bees", "Delhivery", "Valmo"]
SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]

BASE_STYLE_PATTERNS = [
    r"zeme[- ]?0?1",           # ZEME-01 and variants
    r"2[- ]?pc[s]?",           # 2-PC, 2-PCS, 2 PC, etc.
    r"2[- ]?(tape|strip)",     # 2-TAPE, 2-STRIP
    r"fruit",                  # FRUIT
    r"crop",                   # CROP
    r"of", r"-2-s"             # OF group
]

# ----------------------------------------------------
# Detection Helpers
# ----------------------------------------------------
def detect_courier(text):
    for c in COURIER_PRIORITY:
        if re.search(c, text, re.IGNORECASE):
            return c
    return "UNKNOWN"

def detect_base_style(text):
    """Detect base keyword ignoring suffixes like color/number."""
    text_lower = text.lower()
    for pat in BASE_STYLE_PATTERNS:
        match = re.search(pat, text_lower)
        if match:
            base = match.group(0)
            # Normalize for grouping
            if "zeme" in base: return "ZEME-01"
            if "2-pc" in base or "2 pc" in base: return "2-PC"
            if "tape" in base or "strip" in base: return "2-TAPE"
            if "fruit" in base: return "FRUIT"
            if "crop" in base: return "CROP"
            if "of" in base or "-2-s" in base: return "OF"
    return "OTHER"

def detect_size(text):
    for s in SIZE_ORDER:
        if re.search(rf"\b{s}\b", text, re.IGNORECASE):
            return s
    return "NA"

# ----------------------------------------------------
# PDF Processing
# ----------------------------------------------------
uploaded_file = st.file_uploader("📤 Upload Meesho Invoice PDF", type=["pdf"])

if uploaded_file:
    reader = PdfReader(uploaded_file)
    total_pages = len(reader.pages)
    st.info(f"Total pages detected: {total_pages}")

    page_data = []
    with pdfplumber.open(uploaded_file) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            courier = detect_courier(text)
            style = detect_base_style(text)
            size = detect_size(text)
            page_data.append({
                "index": i,
                "courier": courier,
                "style": style,
                "size": size
            })

    st.success("✅ All pages analyzed successfully!")

    # Sorting key
    def sort_key(p):
        courier_rank = COURIER_PRIORITY.index(p["courier"]) if p["courier"] in COURIER_PRIORITY else 999
        style_rank = sorted(list(set([d["style"] for d in page_data]))).index(p["style"]) if p["style"] != "OTHER" else 999
        size_rank = SIZE_ORDER.index(p["size"]) if p["size"] in SIZE_ORDER else 999
        return (courier_rank, style_rank, size_rank)

    sorted_pages = sorted(page_data, key=sort_key)

    st.subheader("📋 Sourcing Summary (Preview)")
    st.dataframe(sorted_pages[:20])

    # ----------------------------------------------------
    # Create Separate PDFs for Each Courier
    # ----------------------------------------------------
    st.subheader("📦 Download Sorted PDFs (Courier-wise)")
    for courier in COURIER_PRIORITY:
        courier_pages = [p for p in sorted_pages if p["courier"] == courier]
        if not courier_pages:
            st.write(f"❌ No pages found for {courier}")
            continue

        writer = PdfWriter()
        for item in courier_pages:
            writer.add_page(reader.pages[item["index"]])

        buffer = BytesIO()
        writer.write(buffer)
        buffer.seek(0)

        st.download_button(
            label=f"⬇️ Download {courier} PDF",
            data=buffer,
            file_name=f"{courier}_Sorted_Invoices.pdf",
            mime="application/pdf"
        )

    st.success("🎉 All courier-wise sorted PDFs ready for download!")
else:
    st.warning("Please upload a Meesho Invoice PDF to start sorting.")
