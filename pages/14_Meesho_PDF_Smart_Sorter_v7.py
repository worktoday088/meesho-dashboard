# --------------------------------------------------------------
# 📦 Meesho Invoice Auto Sourcing Sorter (v8 - with Page Ranges)
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

st.set_page_config(page_title="Meesho PDF Smart Sorter v8", layout="centered")
st.title("📦 Meesho Invoice Auto Sourcing – v8 (with Page Ranges)")
st.caption("Features: Multi-PDF merge, custom style order, courier+style selection, page range display")

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
        if re.search(rf"(?<!\w){re.escape(s)}(?!\w)", text, re.IGNORECASE):
            return s
    return "NA"

def make_download_bytes(page_indices, reader):
    writer = PdfWriter()
    for idx in page_indices:
        writer.add_page(reader.pages[idx])
    buf = BytesIO()
    writer.write(buf)
    buf.seek(0)
    return buf

# ----------------------------------------------------
# Streamlit UI
# ----------------------------------------------------

# Sidebar: Custom style patterns
st.sidebar.header("⚙️ Custom Style Patterns")
st.sidebar.caption("Define regex patterns to identify and canonicalize style names.")
user_patterns = []
for i, (default_pat, default_canon) in enumerate(DEFAULT_STYLE_CANONICAL):
    with st.sidebar.expander(f"Pattern {i+1}", expanded=False):
        pat = st.text_input(f"Regex pattern {i+1}", value=default_pat, key=f"pat_{i}")
        canon = st.text_input(f"Canonical name {i+1}", value=default_canon, key=f"canon_{i}")
        if pat.strip() and canon.strip():
            user_patterns.append((pat.strip(), canon.strip()))

# Allow user to add more patterns
extra_count = st.sidebar.number_input("Add extra patterns", min_value=0, max_value=10, value=0)
for j in range(extra_count):
    idx = len(DEFAULT_STYLE_CANONICAL) + j
    with st.sidebar.expander(f"Extra Pattern {j+1}", expanded=False):
        pat = st.text_input(f"Regex pattern (extra {j+1})", key=f"extra_pat_{j}")
        canon = st.text_input(f"Canonical name (extra {j+1})", key=f"extra_canon_{j}")
        if pat.strip() and canon.strip():
            user_patterns.append((pat.strip(), canon.strip()))

canonical_patterns = user_patterns if user_patterns else DEFAULT_STYLE_CANONICAL

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
    
    # Parse with pdfplumber
    merged_buf.seek(0)
    hierarchy = OrderedDict()  # {courier: {style: {size: [page_indices]}}}
    
    with pdfplumber.open(merged_buf) as pdf:
        for idx, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            courier = detect_courier(text)
            style = detect_canonical_style(text, canonical_patterns)
            size = detect_size(text)
            
            if courier not in hierarchy:
                hierarchy[courier] = {}
            if style not in hierarchy[courier]:
                hierarchy[courier][style] = {}
            if size not in hierarchy[courier][style]:
                hierarchy[courier][style][size] = []
            hierarchy[courier][style][size].append(idx)
    
    # Build style_pages_map: {courier: {style: [all_pages_for_that_style]}}
    style_pages_map = {}
    for courier, styles_dict in hierarchy.items():
        style_pages_map[courier] = {}
        for style, sizes_map in styles_dict.items():
            all_pages = []
            for s in SIZE_ORDER + ["NA"]:
                for p in sizes_map.get(s, []):
                    if p not in all_pages:
                        all_pages.append(p)
            style_pages_map[courier][style] = sorted(set(all_pages))
    
    # Display summary
    st.subheader("📊 Summary by Courier & Style")
    for courier in COURIER_PRIORITY + ["UNKNOWN"]:
        if courier not in hierarchy:
            continue
        styles_dict = hierarchy[courier]
        total_courier_pages = sum(len(style_pages_map[courier][st]) for st in styles_dict.keys())
        st.markdown(f"### 🚚 {courier} ({total_courier_pages} pages)")
        
        # Sort styles by canonical order
        observed_styles = list(styles_dict.keys())
        canonical_order = [canon for _, canon in canonical_patterns]
        ordered_styles = []
        for ccanon in canonical_order:
            if ccanon in observed_styles and ccanon not in ordered_styles:
                ordered_styles.append(ccanon)
        for s in observed_styles:
            if s not in ordered_styles:
                ordered_styles.append(s)
        
        # Show count table
        rows = []
        for style in ordered_styles:
            sizes_map = styles_dict[style]
            row = {"Style": style}
            for sz in SIZE_ORDER:
                row[sz] = len(sizes_map.get(sz, []))
            row["NA"] = len(sizes_map.get("NA", []))
            row["Total"] = sum(len(sizes_map.get(s, [])) for s in SIZE_ORDER + ["NA"])
            rows.append(row)
        
        st.table(rows)
    
    # ----------------------------------------------------
    # Per-Courier Selection
    # ----------------------------------------------------
    st.subheader("🎯 Select Styles per Courier")
    selections_by_courier = {}
    for courier in COURIER_PRIORITY + ["UNKNOWN"]:
        if courier not in hierarchy:
            continue
        styles_dict = hierarchy[courier]
        
        # Sort styles
        observed_styles = list(styles_dict.keys())
        canonical_order = [canon for _, canon in canonical_patterns]
        ordered_styles = []
        for ccanon in canonical_order:
            if ccanon in observed_styles and ccanon not in ordered_styles:
                ordered_styles.append(ccanon)
        for s in observed_styles:
            if s not in ordered_styles:
                ordered_styles.append(s)
        
        with st.expander(f"🚚 {courier} — Select Styles"):
            selected = st.multiselect(f"Choose styles for {courier} (leave empty = all)",
                                      options=ordered_styles,
                                      default=[],
                                      key=f"select_{courier}")
            selections_by_courier[courier] = selected
            
            # Determine which styles to include
            include_styles = selected if selected else ordered_styles
            
            # Show page ranges for each included style
            if include_styles:
                st.markdown("**📄 Page Ranges for Selected Styles:**")
                for sty in include_styles:
                    pages = style_pages_map[courier].get(sty, [])
                    if pages:
                        ranges = page_ranges_from_list(pages)
                        human = format_ranges_human(ranges, one_indexed=True)
                        cmd = format_ranges_printer(ranges, one_indexed=True)
                        st.caption(f"**{sty}**: p. {human} | 🖨️ Print: `{cmd}`")
            
            # Gather pages for download
            pages_to_write = []
            for style in include_styles:
                sizes_map = styles_dict.get(style, {})
                for s in SIZE_ORDER + ["NA"]:
                    pages = sizes_map.get(s, [])
                    for p in pages:
                        if p not in pages_to_write:
                            pages_to_write.append(p)
            
            if pages_to_write:
                # Show combined range for this courier
                pages_to_write_sorted = sorted(set(pages_to_write))
                courier_ranges = page_ranges_from_list(pages_to_write_sorted)
                courier_human = format_ranges_human(courier_ranges, one_indexed=True)
                courier_cmd = format_ranges_printer(courier_ranges, one_indexed=True)
                st.info(f"📦 **{courier} Total Range**: p. {courier_human} | 🖨️ `{courier_cmd}`")
                
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
    
    combined_pages = []
    for courier, selected in selections_by_courier.items():
        styles_dict = hierarchy.get(courier, {})
        if not styles_dict:
            continue
        
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
        combined_pages_sorted = sorted(set(combined_pages))
        cranges = page_ranges_from_list(combined_pages_sorted)
        chuman = format_ranges_human(cranges, one_indexed=True)
        ccmd = format_ranges_printer(cranges, one_indexed=True)
        st.info(f"📄 **Combined Range**: p. {chuman} | 🖨️ Print: `{ccmd}`")
        
        combined_buf = make_download_bytes(combined_pages, reader)
        st.download_button(label=f"⬇️ Download All Selected Styles (Combined) — {len(combined_pages)} pages",
                           data=combined_buf,
                           file_name="All_Couriers_Selected_Styles_Combined.pdf",
                           mime="application/pdf")
    else:
        st.info("No pages selected across couriers yet. Use the multiselects above to choose styles to include.")
    
    st.success("🎉 Done — courier+style selection with page ranges enabled. Use the downloads for packing.")
else:
    st.info("Please upload one or more Meesho Invoice PDFs to start sorting.")
