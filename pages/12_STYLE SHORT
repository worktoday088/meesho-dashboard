# --------------------------------------------------------------
# 📦 Meesho Invoice Auto Sourcing Sorter (v6 - Stable Pro Version)
# --------------------------------------------------------------
# Run command:
# streamlit run Meesho_PDF_Sorter_v6.py
# Requirements:
# pip install streamlit PyPDF2 pdfplumber

import streamlit as st
import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
import re
from io import BytesIO
from collections import defaultdict, OrderedDict

st.set_page_config(page_title="Meesho PDF Auto Sorter v6", layout="wide")

st.title("📦 Meesho Invoice Auto Sourcing – Final v6")
st.caption("Developed for Bilal Sir — Courier ➜ Style ➜ Size (Stable Version with Smart Grouping)")

# ----------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------
COURIER_PRIORITY = ["Shadowfax", "Xpress Bees", "Delhivery", "Valmo"]
SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]

STYLE_GROUPS = [
    # (pattern list, canonical display name)
    (["zeme-01", "zeme01", "2-pc", "2pcs", "2 pcs", "2pcs jumpsuit", "2-pcs jumpsuit"], "Jumpsuit"),
    (["2 tape", "2 strip", "2-tape", "2-strip"], "2-Tape"),
    (["of", "-2-s"], "Combo 2-Tape"),
    (["fruit"], "Fruit"),
    (["crop"], "Crop Hoodie"),
    (["plain"], "Plain Trouser"),
]

# ----------------------------------------------------
# Helper Functions
# ----------------------------------------------------
def detect_courier(text):
    for courier in COURIER_PRIORITY:
        if re.search(re.escape(courier), text, re.IGNORECASE):
            return courier
    return "UNKNOWN"

def detect_style(text):
    t = text.lower()
    for patterns, style_name in STYLE_GROUPS:
        for pat in patterns:
            if re.search(rf"\b{re.escape(pat)}\b", t):
                return style_name
    return "Other"

def detect_size(text):
    for s in SIZE_ORDER:
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(s)}(?![A-Za-z0-9])", text, re.IGNORECASE):
            return s
    return "NA"

# ----------------------------------------------------
# Streamlit UI
# ----------------------------------------------------
uploaded_file = st.file_uploader("📤 Upload Meesho Invoice PDF", type=["pdf"])

if uploaded_file:
    reader = PdfReader(uploaded_file)
    total_pages = len(reader.pages)
    st.info(f"📄 Total pages detected: {total_pages}")

    # hierarchy: courier -> style -> size -> [pages]
    hierarchy = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    unparsed_pages = []

    with pdfplumber.open(uploaded_file) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            courier = detect_courier(text)
            style = detect_style(text)
            size = detect_size(text)

            hierarchy[courier][style][size].append(i)
            if courier == "UNKNOWN" and style == "Other" and size == "NA":
                unparsed_pages.append(i)

    st.success("✅ PDF scanned and grouped successfully!")

    if unparsed_pages:
        st.warning(f"⚠️ {len(unparsed_pages)} pages could not be identified. Example: {unparsed_pages[:10]}")

    # ----------------------------------------------------
    # DOWNLOAD SECTION
    # ----------------------------------------------------
    st.header("📦 Download Courier + Style-wise Sorted PDFs")

    for courier in COURIER_PRIORITY:
        styles = hierarchy.get(courier, {})
        if not styles:
            continue

        st.subheader(f"🚚 {courier}")

        for style_name, sizes_dict in styles.items():
            if not any(sizes_dict.values()):
                continue

            writer = PdfWriter()
            for s in SIZE_ORDER + ["NA"]:
                pages = sizes_dict.get(s, [])
                added = set()
                for p in pages:
                    if p not in added:
                        writer.add_page(reader.pages[p])
                        added.add(p)

            buf = BytesIO()
            writer.write(buf)
            buf.seek(0)

            file_label = f"⬇️ Download {courier} – {style_name}"
            file_name = f"{courier}_{style_name.replace(' ', '_')}.pdf"

            st.download_button(
                label=file_label,
                data=buf,
                file_name=file_name,
                mime="application/pdf"
            )

    st.success("🎉 All files ready! Download courier + style-wise sorted PDFs above.")

else:
    st.info("Please upload a Meesho Invoice PDF file to start sorting.")
