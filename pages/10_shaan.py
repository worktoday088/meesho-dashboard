# --------------------------------------------------------------
# 📦 Streamlit App: Meesho PDF Auto Sourcing Sorter (Smart v2)
# --------------------------------------------------------------
# Required:
# pip install streamlit PyPDF2 pdfplumber
# Run: streamlit run Meesho_PDF_Sorter_v2.py

import streamlit as st
import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
import re
from io import BytesIO

st.set_page_config(page_title="Meesho PDF Smart Sorter", layout="centered")

st.title("📦 Meesho Invoice Auto Sourcing – Smart v2")
st.caption("Developed for Bilal Sir – Smart PDF sorter (Courier + Style + Size)")

# ----------------------------------------------------
# Fixed priorities & lists
# ----------------------------------------------------
COURIER_PRIORITY = ["Shadowfax", "Xpress Bees", "Delhivery", "Valmo"]
SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]

# Flexible style patterns (matches anywhere inside text)
STYLE_GROUPS = {
    "FRUIT": [r"fruit"],
    "CROP": [r"crop"],
    "2-PC_GROUP": [r"2[- ]?pc", r"zeme[- ]?0?1"],
    "2-TAPE_GROUP": [r"2[- ]?(tape|strip)", r"strip2"],
    "OF_GROUP": [r"-2-s", r"of"]
}

# ----------------------------------------------------
# Detect Courier
# ----------------------------------------------------
def detect_courier(text):
    for c in COURIER_PRIORITY:
        if re.search(c, text, re.IGNORECASE):
            return c
    return "UNKNOWN"

# ----------------------------------------------------
# Detect Style (contains based, smart)
# ----------------------------------------------------
def detect_style(text):
    text_lower = text.lower()
    for group, patterns in STYLE_GROUPS.items():
        for pat in patterns:
            if re.search(pat, text_lower):
                return group
    return "OTHER"

# ----------------------------------------------------
# Detect Size
# ----------------------------------------------------
def detect_size(text):
    for s in SIZE_ORDER:
        if re.search(rf"\\b{s}\\b", text, re.IGNORECASE):
            return s
    return "NA"

# ----------------------------------------------------
# Streamlit UI
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
            style = detect_style(text)
            size = detect_size(text)
            page_data.append({
                "index": i,
                "courier": courier,
                "style": style,
                "size": size
            })

    st.success("✅ Detected all pages and matched styles successfully!")

    # Sorting key
    def sort_key(p):
        courier_rank = COURIER_PRIORITY.index(p["courier"]) if p["courier"] in COURIER_PRIORITY else 999
        style_rank = list(STYLE_GROUPS.keys()).index(p["style"]) if p["style"] in STYLE_GROUPS else 999
        size_rank = SIZE_ORDER.index(p["size"]) if p["size"] in SIZE_ORDER else 999
        return (courier_rank, style_rank, size_rank)

    sorted_pages = sorted(page_data, key=sort_key)

    st.subheader("📋 Detected Summary (First 20 Pages Preview)")
    st.dataframe(sorted_pages[:20])

    # Create new sorted PDF
    writer = PdfWriter()
    for item in sorted_pages:
        writer.add_page(reader.pages[item["index"]])

    buffer = BytesIO()
    writer.write(buffer)
    buffer.seek(0)

    st.download_button(
        label="⬇️ Download Sorted PDF",
        data=buffer,
        file_name="Sorted_Meesho_Invoices_v2.pdf",
        mime="application/pdf"
    )

    st.success("🎉 Sorting completed successfully! Your Smart Sorted PDF is ready to download.")
else:
    st.warning("Please upload a Meesho Invoice PDF to start sorting.")
