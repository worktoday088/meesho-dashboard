import streamlit as st
import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
import re
from io import BytesIO
from collections import OrderedDict

st.set_page_config(page_title="Meesho PDF Smart Sorter v12 (Cache & Group)", layout="centered")
st.title("Meesho Auto PDF Sourcing — Courierwise, Synonym Groups, AUTO, Fast Caching")

COURIERPRIORITY = ["Shadowfax", "Xpress Bees", "Delhivery", "Valmo"]

# --- User-defined style grouping ---
if 'style_groups' not in st.session_state:
    st.session_state.style_groups = []
if 'pdf_cache' not in st.session_state:
    st.session_state.pdf_cache = {}

def add_group():
    st.session_state.style_groups.append({'synonyms': '', 'style_name': ''})

def clear_groups():
    st.session_state.style_groups = []

st.button("नया Synonym Group जोड़ें", on_click=add_group)
st.button("सभी Groups हटाएँ", on_click=clear_groups)

for i, group in enumerate(st.session_state.style_groups):
    cols = st.columns([2,2,1])
    group['synonyms'] = cols[0].text_input("Synonyms (comma separated)", value=group['synonyms'], key=f"syn_{i}")
    group['style_name'] = cols[1].text_input("Style Name (Unified)", value=group['style_name'], key=f"name_{i}")
    if cols[2].button("Remove", key=f"del_{i}"):
        st.session_state.style_groups.pop(i)
        st.experimental_rerun()

if st.session_state.style_groups:
    st.markdown("##### आपके Synonym Groups:")
    st.write([
        {"Synonyms": g['synonyms'], "Style Name": g['style_name']} 
        for g in st.session_state.style_groups if g['synonyms'] and g['style_name']
    ])

uploaded_files = st.file_uploader("PDF फाइल अपलोड करें (एक या कई)", type="pdf", accept_multiple_files=True)

def detect_courier(text):
    for c in COURIERPRIORITY:
        if re.search(re.escape(c), text, re.IGNORECASE):
            return c
    return "OTHER"

def guess_style(text, known_styles):
    candidates = set()
    patt = re.compile(r"[A-Z0-9\-]{4,}|[A-Z][^\n]{2,26}")  # अपने इनवॉइस के हिसाब से सुधारें
    for m in patt.findall(text):
        word = m.strip().upper()
        if word and not any(ks in word for ks in known_styles):
            candidates.add(word)
    return candidates

def reset_cache():
    st.session_state.pdf_cache = {}

if uploaded_files and st.session_state.style_groups:
    # Cache PDF only when new file/group input
    reset_cache()

    synonym_map = {}
    style_set = set()
    for group in st.session_state.style_groups:
        name = group['style_name'].strip().upper()
        style_set.add(name)
        for syn in group['synonyms'].split(','):
            if syn.strip():
                synonym_map[syn.strip().lower()] = name

    writer_merge = PdfWriter()
    for uf in uploaded_files:
        try:
            temp_reader = PdfReader(uf)
            for p in temp_reader.pages:
                writer_merge.add_page(p)
        except Exception as e:
            st.error(f"PDF पढ़ने में समस्या: {e}")
            st.stop()

    merged_buf = BytesIO()
    writer_merge.write(merged_buf)
    merged_buf.seek(0)
    reader = PdfReader(merged_buf)
    st.success(f"कुल पेज: {len(reader.pages)}")

    courier_map = OrderedDict()
    # --- FAST: process all pages only once ---
    with pdfplumber.open(merged_buf) as pdf:
        for idx, page in enumerate(pdf.pages):
            text = (page.extract_text() or "").lower()
            courier = detect_courier(text)
            matched_style = None
            for syn, style_name in synonym_map.items():
                if syn in text:
                    matched_style = style_name
                    break
            if courier not in courier_map:
                courier_map[courier] = {'manual': OrderedDict(), 'auto': set()}
            if matched_style:
                if matched_style not in courier_map[courier]['manual']:
                    courier_map[courier]['manual'][matched_style] = []
                courier_map[courier]['manual'][matched_style].append(idx)
            else:
                auto_found = guess_style(text, style_set)
                for af in auto_found:
                    courier_map[courier]['auto'].add(idx)

    # --- PDF RAM Caching & UI Download Buttons ---
    for courier, data in courier_map.items():
        st.subheader(f"Courier: {courier}")
        # 1) MANUAL GROUPS
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
                st.download_button(
                    label=f"{courier} • Style PDF: {style} ({len(pages)} pages)",
                    data=st.session_state.pdf_cache[key],
                    file_name=f"{courier}_{style.replace(' ','_')}.pdf",
                    mime="application/pdf"
                )
        # 2) AUTO (Only one button for all auto-detected, all pages in one PDF!)
        key_auto = (courier, "AUTO")
        auto_pages = sorted(data['auto'])
        if auto_pages:
            if key_auto not in st.session_state.pdf_cache:
                writer = PdfWriter()
                for idx in auto_pages:
                    writer.add_page(reader.pages[idx])
                buf = BytesIO()
                writer.write(buf)
                buf.seek(0)
                st.session_state.pdf_cache[key_auto] = buf.getvalue()
            st.download_button(
                label=f"{courier} • AUTO Detected Styles PDF ({len(auto_pages)} pages)",
                data=st.session_state.pdf_cache[key_auto],
                file_name=f"{courier}_AUTO_DETECTED.pdf",
                mime="application/pdf"
            )
else:
    st.info("Synonym group बनाएँ (manual), PDF फाइल अपलोड करें—फिर auto & group दोनों में sorting खुद-ब-खुद!")

