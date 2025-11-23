import streamlit as st
import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
import re
from io import BytesIO
from collections import OrderedDict

st.set_page_config(page_title="Meesho PDF Smart Sorter", layout="centered")
st.title("Meesho PDF Smart Sorter — Exact, Ordered, Status, Fast")

COURIERPRIORITY = ["Shadowfax", "Xpress Bees", "Delhivery", "Valmo"]

if 'style_groups' not in st.session_state:
    st.session_state.style_groups = []
if 'pdf_cache' not in st.session_state:
    st.session_state.pdf_cache = {}
if 'status_map' not in st.session_state:
    st.session_state.status_map = {}
if 'final_total_pages' not in st.session_state:
    st.session_state.final_total_pages = {}

def add_group():
    st.session_state.style_groups.append({'synonyms': '', 'style_name': ''})

def clear_groups():
    st.session_state.style_groups = []

st.button("Add Synonym Group", on_click=add_group)
st.button("Clear All Groups", on_click=clear_groups)

for i, group in enumerate(st.session_state.style_groups):
    cols = st.columns([2,2,1])
    group['synonyms'] = cols[0].text_input("Synonyms (comma separated)", value=group['synonyms'], key=f"syn_{i}")
    group['style_name'] = cols[1].text_input("Unified Style Name", value=group['style_name'], key=f"name_{i}")
    if cols[2].button("Remove", key=f"del_{i}"):
        st.session_state.style_groups.pop(i)
        st.experimental_rerun()

# Collapsible summary of group patterns
if st.session_state.style_groups:
    with st.expander("Show/Hide Synonym Regex Patterns Summary"):
        regex_list = []
        for group in st.session_state.style_groups:
            name = group['style_name'].strip().upper()
            for syn in group['synonyms'].split(','):
                syn=syn.strip()
                if syn:
                    pat = r"\b" + re.escape(syn) + r"\b"
                    regex_list.append({"synonym": syn, "regex": pat, "style_name": name})
        st.write(regex_list)

with st.expander("Show/Hide PDF Upload Area", expanded=True):
    uploaded_files = st.file_uploader("Upload one or more PDF files", type="pdf", accept_multiple_files=True)
    
def detect_courier(text):
    for c in COURIERPRIORITY:
        if re.search(re.escape(c), text, re.IGNORECASE):
            return c
    return "OTHER"

def reset_cache():
    st.session_state.pdf_cache = {}
    st.session_state.status_map = {}
    st.session_state.final_total_pages = {}

def guess_style(text, known_styles):
    candidates = set()
    patt = re.compile(r"\b[A-Z0-9\-]{4,}\b")
    for m in patt.findall(text.upper()):
        word = m.strip()
        if word and word not in known_styles:
            candidates.add(word)
    return candidates

if uploaded_files and st.session_state.style_groups:
    reset_cache()

    st.session_state.status_map['step'] = 'Merging PDFs...'
    st.info("Merging all PDF files...")

    patterns = []
    style_set = set()
    for group in st.session_state.style_groups:
        name = group['style_name'].strip().upper()
        style_set.add(name)
        for syn in group['synonyms'].split(','):
            syn = syn.strip()
            if syn:
                pat = r"\b" + re.escape(syn) + r"\b"
                patterns.append((pat, name))

    writer_merge = PdfWriter()
    for uf in uploaded_files:
        try:
            temp_reader = PdfReader(uf)
            for p in temp_reader.pages:
                writer_merge.add_page(p)
        except Exception as e:
            st.session_state.status_map['error'] = f"PDF reading error: {e}"
            st.error(st.session_state.status_map['error'])
            st.stop()

    merged_buf = BytesIO()
    writer_merge.write(merged_buf)
    merged_buf.seek(0)
    reader = PdfReader(merged_buf)
    st.success(f"Total merged pages: {len(reader.pages)}")

    courier_map = OrderedDict()
    st.session_state.status_map['step'] = 'Extracting pages by courier and style groups...'
    st.info("Processing PDF for courier and style grouping ...")

    with pdfplumber.open(merged_buf) as pdf:
        for idx, page in enumerate(pdf.pages):
            text = (page.extract_text() or "")
            courier = detect_courier(text)
            match_found = None
            for pat, style_name in patterns:
                if re.search(pat, text, re.IGNORECASE):
                    match_found = style_name
                    break
            if courier not in courier_map:
                courier_map[courier] = {'manual': OrderedDict(), 'auto': set()}
            if match_found:
                if match_found not in courier_map[courier]['manual']:
                    courier_map[courier]['manual'][match_found] = []
                courier_map[courier]['manual'][match_found].append(idx)
            else:
                auto_found = guess_style(text, style_set)
                for af in auto_found:
                    courier_map[courier]['auto'].add(idx)
    st.session_state.status_map['step'] = 'Splitting pages and preparing final PDFs...'
    st.info("Splitting and caching PDFs for download...")

    success_processed = True
    for courier, data in courier_map.items():
        try:
            ordered_pages = []
            used = set()
            # Process manual groups by UI order
            for group in st.session_state.style_groups:
                style_name = group['style_name'].strip().upper()
                manual_pages = data['manual'].get(style_name, [])
                for idx in sorted(manual_pages):
                    if idx not in used:
                        ordered_pages.append(idx)
                        used.add(idx)
            # Add auto pages at the end
            for idx in sorted(data['auto']):
                if idx not in used:
                    ordered_pages.append(idx)
                    used.add(idx)

            # Store total page count for combined!
            st.session_state.final_total_pages[courier] = len(ordered_pages)

            # Individual style group PDF cache
            for style, pages in data['manual'].items():
                key = (courier, style)
                if pages:
                    if key not in st.session_state.pdf_cache:
                        writer = PdfWriter()
                        for idx in sorted(set(pages)):
                            writer.add_page(reader.pages[idx])
                        buf = BytesIO()
                        writer.write(buf)
                        buf.seek(0)
                        st.session_state.pdf_cache[key] = buf.getvalue()
            key_auto = (courier, "AUTO")
            auto_pages = sorted(data['auto'])
            if auto_pages and key_auto not in st.session_state.pdf_cache:
                writer = PdfWriter()
                for idx in auto_pages:
                    writer.add_page(reader.pages[idx])
                buf = BytesIO()
                writer.write(buf)
                buf.seek(0)
                st.session_state.pdf_cache[key_auto] = buf.getvalue()
            key_comb = (courier, "COMBINED")
            if ordered_pages and key_comb not in st.session_state.pdf_cache:
                writer = PdfWriter()
                for idx in ordered_pages:
                    writer.add_page(reader.pages[idx])
                buf = BytesIO()
                writer.write(buf)
                buf.seek(0)
                st.session_state.pdf_cache[key_comb] = buf.getvalue()
        except Exception as e:
            success_processed = False
            st.session_state.status_map['error'] = f"PDF splitting error: {e}"
            st.error(st.session_state.status_map['error'])

    if success_processed:
        st.session_state.status_map['step'] = 'Ready to download!'
        for courier, data in courier_map.items():
            st.subheader(f"Courier: {courier}")
            for style, pages in data['manual'].items():
                key = (courier, style)
                if key in st.session_state.pdf_cache:
                    st.download_button(
                        label=f"{courier} • Style PDF: {style} ({len(pages)} pages)",
                        data=st.session_state.pdf_cache[key],
                        file_name=f"{courier}_{style.replace(' ','_')}.pdf",
                        mime="application/pdf"
                    )
            key_auto = (courier, "AUTO")
            auto_pages = sorted(data['auto'])
            if key_auto in st.session_state.pdf_cache:
                st.download_button(
                    label=f"{courier} • AUTO Detected Styles PDF ({len(auto_pages)} pages)",
                    data=st.session_state.pdf_cache[key_auto],
                    file_name=f"{courier}_AUTO_DETECTED.pdf",
                    mime="application/pdf"
                )
            key_comb = (courier, "COMBINED")
            if key_comb in st.session_state.pdf_cache:
                total_pages = st.session_state.final_total_pages.get(courier, 0)
                st.download_button(
                    label=f"{courier} • COMBINED Ordered PDF ({total_pages} pages)",
                    data=st.session_state.pdf_cache[key_comb],
                    file_name=f"{courier}_COMBINED_ALL.pdf",
                    mime="application/pdf"
                )
        st.success("All PDF files are ready! Please download.")
    else:
        st.warning("Error occurred during PDF processing. Please check your keywords, files, or try again.")
else:
    st.info("Define synonym groups and upload PDF(s) (all steps/status/buttons will appear here).")
