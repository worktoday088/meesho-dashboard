# --------------------------------------------------------------
# 📦 Meesho Invoice Smart Search & Export by Style (v8)
# --------------------------------------------------------------
# Required:
#   pip install streamlit PyPDF2 pdfplumber
# Run:
#   streamlit run Meesho_PDF_Smart_Sorter_v8.py

import streamlit as st
import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
import re
from io import BytesIO
from collections import OrderedDict

st.set_page_config(page_title="Meesho PDF Smart Search v8", layout="centered")
st.title("📦 Meesho Invoice Smart Search & Export by Style – v8")
st.caption("Search for any style keyword and get matching pages with page ranges")

# ----------------------------------------------------
# Configuration
# ----------------------------------------------------
COURIER_PRIORITY = ["Shadowfax", "Xpress Bees", "Delhivery", "Valmo"]
SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]

# ----------------------------------------------------
# Helper functions - Page Range Formatting
# ----------------------------------------------------
def page_ranges_from_list(pages):
    """Convert sorted list of page numbers to list of (start, end) tuples."""
    if not pages:
        return []
    pages = sorted(set(pages))
    ranges = []
    start = prev = pages[0]
    for p in pages[1:]:
        if p == prev + 1:
            prev = p
        else:
            ranges.append((start, prev))
            start = prev = p
    ranges.append((start, prev))
    return ranges

def format_ranges_human(ranges, one_indexed=True):
    """Format ranges for human reading: e.g., '12–14, 17–18'"""
    parts = []
    for a, b in ranges:
        a1 = a + 1 if one_indexed else a
        b1 = b + 1 if one_indexed else b
        if a == b:
            parts.append(f"{a1}")
        else:
            parts.append(f"{a1}–{b1}")
    return ", ".join(parts)

def format_ranges_printer(ranges, one_indexed=True):
    """Format ranges for printer/PDF viewer: e.g., '12-14,17-18'"""
    parts = []
    for a, b in ranges:
        a1 = a + 1 if one_indexed else a
        b1 = b + 1 if one_indexed else b
        if a == b:
            parts.append(f"{a1}")
        else:
            parts.append(f"{a1}-{b1}")
    return ",".join(parts)

# ----------------------------------------------------
# Helper functions - Detection
# ----------------------------------------------------
def detect_courier(text):
    for c in COURIER_PRIORITY:
        if re.search(re.escape(c), text, re.IGNORECASE):
            return c
    return "UNKNOWN"

def detect_size(text):
    for s in SIZE_ORDER:
        if re.search(rf"(?<!\w){re.escape(s)}(?!\w)", text, re.IGNORECASE):
            return s
    return "NA"

def make_download_bytes(page_indices, reader):
    writer = PdfWriter()
    for idx in sorted(page_indices):
        writer.add_page(reader.pages[idx])
    buf = BytesIO()
    writer.write(buf)
    buf.seek(0)
    return buf

# ----------------------------------------------------
# Streamlit UI
# ----------------------------------------------------

# Main: File uploader
uploaded_files = st.file_uploader("Upload Meesho Invoice PDF(s)", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    # Merge all PDFs
    all_bytes = []
    for uf in uploaded_files:
        all_bytes.append(uf.read())
    
    # Create a single merged PDF in memory
    merger_writer = PdfWriter()
    for file_bytes in all_bytes:
        temp_reader = PdfReader(BytesIO(file_bytes))
        for page in temp_reader.pages:
            merger_writer.add_page(page)
    
    merged_buf = BytesIO()
    merger_writer.write(merged_buf)
    merged_buf.seek(0)
    
    reader = PdfReader(merged_buf)
    total_pages = len(reader.pages)
    st.success(f"✅ Merged {len(uploaded_files)} PDF(s) into {total_pages} pages.")
    
    # Parse with pdfplumber to extract text from each page
    merged_buf.seek(0)
    page_data = []  # [{page_idx, text, courier, size}, ...]
    
    with pdfplumber.open(merged_buf) as pdf:
        for idx, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            courier = detect_courier(text)
            size = detect_size(text)
            page_data.append({
                "page_idx": idx,
                "text": text,
                "courier": courier,
                "size": size
            })
    
    st.success(f"✅ Parsed {len(page_data)} pages with text extraction.")
    
    # ----------------------------------------------------
    # Style Search Text Box
    # ----------------------------------------------------
    st.subheader("🔍 Search for Style Keyword")
    st.caption("Enter any style keyword (e.g., FRUIT, 2-PC, ZEME-01, CROP) to find matching pages.")
    
    search_query = st.text_input("Enter style keyword to search:", value="", placeholder="e.g., FRUIT")
    
    if search_query.strip():
        query_lower = search_query.strip().lower()
        
        # Find all pages that contain the query in their text
        matched_pages = []
        matched_details = []
        
        for item in page_data:
            if query_lower in item["text"].lower():
                matched_pages.append(item["page_idx"])
                matched_details.append({
                    "Page": item["page_idx"] + 1,  # 1-indexed for display
                    "Courier": item["courier"],
                    "Size": item["size"]
                })
        
        if matched_pages:
            matched_pages = sorted(set(matched_pages))
            
            # Calculate page ranges
            ranges = page_ranges_from_list(matched_pages)
            human_range = format_ranges_human(ranges, one_indexed=True)
            printer_range = format_ranges_printer(ranges, one_indexed=True)
            
            # Display results
            st.success(f"✅ Found **{len(matched_pages)} pages** matching '**{search_query}**'")
            st.info(f"📄 **Page Range**: p. {human_range}")
            st.info(f"🖨️ **Print Command**: `{printer_range}`")
            
            # Show table of matched pages
            st.markdown("### 📋 Matched Pages Details:")
            st.table(matched_details)
            
            # Download button for matched pages
            buf = make_download_bytes(matched_pages, reader)
            st.download_button(
                label=f"⬇️ Download '{search_query}' Pages ({len(matched_pages)} pages)",
                data=buf,
                file_name=f"{search_query.replace(' ', '_')}_Pages.pdf",
                mime="application/pdf"
            )
            
            # Show courier-wise breakdown
            st.markdown("### 🚚 Courier-wise Breakdown:")
            courier_breakdown = {}
            for item in matched_details:
                c = item["Courier"]
                if c not in courier_breakdown:
                    courier_breakdown[c] = []
                courier_breakdown[c].append(item["Page"])
            
            for courier, pages in courier_breakdown.items():
                pages_sorted = sorted(set(pages))
                cranges = page_ranges_from_list([p-1 for p in pages_sorted])  # Convert back to 0-indexed
                chuman = format_ranges_human(cranges, one_indexed=True)
                st.caption(f"**{courier}**: {len(pages_sorted)} pages | p. {chuman}")
        
        else:
            st.warning(f"⚠️ No pages found matching '**{search_query}**'. Try a different keyword.")
    
    else:
        st.info("👆 Enter a style keyword in the search box above to find matching pages.")

else:
    st.info("Please upload one or more Meesho Invoice PDFs to start searching.")
