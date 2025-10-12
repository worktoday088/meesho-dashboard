# --------------------------------------------------------------
# 📦 Streamlit App: Meesho PDF Auto Sourcing Sorter (by Bilal)
# --------------------------------------------------------------
# Required libraries:
# pip install streamlit PyPDF2 pdfplumber

import streamlit as st
import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
import re
from io import BytesIO

st.set_page_config(page_title="Meesho PDF Auto Sorter", layout="centered")

st.title("📦 Meesho Invoice Auto Sourcing (PDF Sorter)")
st.caption("Developed for Bilal Sir — Auto-arrange invoices by Courier, Style & Size order")

# -----------------------------
# Define fixed sorting priorities
# -----------------------------
COURIER_PRIORITY = ["Shadowfax", "Xpress Bees", "Delhivery", "Valmo"]
SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]

# Style groups (patterns treated as same)
STYLE_GROUPS = {
    "FRUIT": [r"\\bFRUIT\\b"],
    "CROP": [r"\\bCROP\\b"],
    "2-PC_GROUP": [r"\\b2[- ]?PC\\b", r"\\bZEME[- ]?01\\b"],
    "2-TAPE_GROUP": [r"\\b2[- ]?(TAPE|STRIP)\\b"],
    "OF_GROUP": [r"\\b-2-S\\b", r"\\bOF\\b"]
}

# -----------------------------
# Helper: detect courier name
# -----------------------------
def detect_courier(text):
    for courier in COURIER_PRIORITY:
        if re.search(courier, text, re.IGNORECASE):
            return courier
    return "UNKNOWN"

# -----------------------------
# Helper: detect style group
# -----------------------------
def detect_style(text):
    for group, patterns in STYLE_GROUPS.items():
        for pat in patterns:
            if re.search(pat, text, re.IGNORECASE):
                return group
    return "OTHER"

# -----------------------------
# Helper: detect size
# -----------------------------
def detect_size(text):
    for size in SIZE_ORDER:
        if re.search(rf"\\b{size}\\b", text, re.IGNORECASE):
            return size
    return "NA"

# -----------------------------
# Upload and process PDF
# -----------------------------
uploaded_file = st.file_uploader("📤 Upload Meesho Invoice PDF", type=["pdf"])

if uploaded_file is not None:
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

    st.success("✅ Sourcing info extracted successfully!")

    # Sorting logic
    def sort_key(p):
        courier_rank = COURIER_PRIORITY.index(p["courier"]) if p["courier"] in COURIER_PRIORITY else 999
        style_rank = list(STYLE_GROUPS.keys()).index(p["style"]) if p["style"] in STYLE_GROUPS else 999
        size_rank = SIZE_ORDER.index(p["size"]) if p["size"] in SIZE_ORDER else 999
        return (courier_rank, style_rank, size_rank)

    sorted_pages = sorted(page_data, key=sort_key)

    # Show preview
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
        file_name="Sorted_Meesho_Invoices.pdf",
        mime="application/pdf"
    )

    st.success("🎉 Done! Your sorted Meesho PDF is ready to download.")
else:
    st.warning("Please upload a Meesho Invoice PDF to start sorting.")
