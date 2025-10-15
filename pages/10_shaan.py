# Meesho_PDF_Sorter_v7_2.py
# Final v7.2 — OCR fallback + full grouping fixes (Courier -> Style -> Size)
# Run:
#  pip install streamlit pdfplumber PyPDF2 pymupdf pytesseract pillow
# Also install system Tesseract OCR (see notes above).
# streamlit run Meesho_PDF_Sorter_v7_2.py

import streamlit as st
import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
import fitz   # PyMuPDF
import pytesseract
from PIL import Image
import re
from io import BytesIO
from collections import defaultdict, OrderedDict

st.set_page_config(page_title="Meesho PDF Auto Sorter v7.2", layout="wide")
st.title("📦 Meesho Invoice Auto Sourcing – Final v7.2 (OCR + Full Group Fix)")
st.caption("Courier → Style → Size. Robust text normalization + OCR fallback. (For Bilal Sir)")

# ---------------- CONFIG ----------------
COURIER_PRIORITY = ["Shadowfax", "Xpress Bees", "Delhivery", "Valmo"]
SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]

# STYLE groups: each entry = (list_of_regex_patterns, display_name)
STYLE_GROUPS = [
    # Jumpsuit / ZEME / 2-PC family
    ([
        r"zeme[- ]?0?1", r"\bzeme01\b", r"\b2[- ]?pc[s]?\b", r"\b2 ?pc\b", r"\b2pcs?\b",
        r"\b2[- ]?pcs?[-_ ]?jumpsuit\b", r"\b2pc[-_ ]?jumpsuit\b"
    ], "Jumpsuit"),

    # 2-Tape family
    ([r"\b2[- ]?tape\b", r"\b2[- ]?strip\b", r"\b2tape\b", r"\b2strip\b"], "2-Tape"),

    # Combo / OF / set-of-2 family
    ([r"-2-s\b", r"\bset of 2\b", r"\bof 2\b", r"\bof\b"], "Combo 2-Tape"),

    # Fruit
    ([r"\bfruit\b"], "Fruit"),

    # Crop — FIXED: use exact word boundary
    ([r"\bcrop\b"], "Crop Hoodie"),

    # Plain Trouser
    ([r"\bplain\b", r"\bplain[-_ ]?trouser\b"], "Plain Trouser"),
]

# ---------------- Utilities ----------------
def normalize_text_for_matching(raw):
    """Normalize text so scattered letters/hyphens/odd chars become searchable words."""
    if not raw:
        return ""
    t = raw

    # Replace common OCR/typo variants
    t = t.replace("0", "O")  # sometimes 'O' and zero confuse — bring to letter O
    # Collapse spaced letters like "C R O P" -> "C R O P" -> "CROP"
    t = re.sub(r'(?:(?<=\s)|^)([A-Za-z])(?=\s)(?:\s+)(?=[A-Za-z])', r'\1', t)  # try reduce spaces between single letters
    # Remove weird repeated spacing and control chars
    t = re.sub(r'[\r\n]+', ' ', t)
    t = re.sub(r'[-_]{2,}', '-', t)
    # remove multiple spaces
    t = re.sub(r'\s+', ' ', t)
    # trim
    t = t.strip()
    # uppercase for size detection convenience in other funcs
    return t

def force_compact_token(t):
    """Aggressively join single-letter spaced tokens: 'C R O P' -> 'CROP'"""
    # join sequences of single letters separated by spaces
    def join_letters(match):
        letters = match.group(0)
        return letters.replace(" ", "")
    return re.sub(r'(?:\b[A-Za-z](?:\s+|$)){2,}', join_letters, t)

# Detect courier by literal matching of courier names
def detect_courier(text):
    if not text:
        return "UNKNOWN"
    for courier in COURIER_PRIORITY:
        if re.search(re.escape(courier), text, re.IGNORECASE):
            return courier
    return "UNKNOWN"

# Detect style using compiled regex patterns (patterns are lower-case / regex)
compiled_style_patterns = []
for patterns, name in STYLE_GROUPS:
    compiled = [re.compile(pat, re.IGNORECASE) for pat in patterns]
    compiled_style_patterns.append((compiled, name))

def detect_style(text):
    t = (text or "")
    # Try a compacted variant to catch spaced letters
    t_compact = force_compact_token(t)
    for compiled_list, display in compiled_style_patterns:
        for cre in compiled_list:
            if cre.search(t) or cre.search(t_compact):
                return display
    return "Other"

def detect_size(text):
    if not text:
        return "NA"
    t = text.upper()
    found = []
    for s in SIZE_ORDER:
        # match token boundaries, accept parentheses like (M) or M, /M/
        if re.search(rf"(?<![A-Z0-9]){re.escape(s)}(?![A-Z0-9])", t):
            found.append(s)
    # return first by priority
    for s in SIZE_ORDER:
        if s in found:
            return s
    return "NA"

# OCR extraction using PyMuPDF + pytesseract
def ocr_page_to_text(pdf_path_or_doc, page_number):
    try:
        # pdf_path_or_doc is a fitz.Document or filename
        if isinstance(pdf_path_or_doc, fitz.Document):
            doc = pdf_path_or_doc
        else:
            doc = fitz.open(pdf_path_or_doc)
        page = doc.load_page(page_number)
        pix = page.get_pixmap(dpi=200)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        text = pytesseract.image_to_string(img)
        return text
    except Exception as e:
        return ""

# ---------------- STREAMLIT UI ----------------
uploaded_file = st.file_uploader("📤 Upload Meesho Invoice PDF (original)", type=["pdf"])
if not uploaded_file:
    st.info("Upload a Meesho invoice PDF to begin. (v7.2 includes OCR fallback for scanned pages.)")
    st.stop()

# optional: allow user to set tesseract cmd path if on Windows
tess_override = st.text_input("Optional: Tesseract executable path (leave empty if tesseract is in PATH)", value="")
if tess_override:
    pytesseract.pytesseract.tesseract_cmd = tess_override

reader = PdfReader(uploaded_file)
total_pages = len(reader.pages)
st.success(f"📄 Loaded PDF — {total_pages} pages detected.")

# debug toggle
show_extracted_preview = st.checkbox("🔎 Show extracted text preview for pages (Debug)", value=False)
use_ocr_for_short_text = st.checkbox("🛠 Use OCR fallback on pages with very little text (recommended)", value=True)
ocr_min_chars = st.number_input("OCR threshold (if extracted text chars < this → run OCR)", min_value=5, max_value=500, value=30)

# Build hierarchy: courier -> style -> size -> [page_indexes]
hierarchy = defaultdict(lambda: OrderedDict())
hierarchy["UNKNOWN"] = OrderedDict()
unparsed_pages = []

# open with pdfplumber and also fitz doc for OCR if needed
with pdfplumber.open(uploaded_file) as pdf:
    fitz_doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    # we used read() above so need to reopen pdfplumber with bytes - reopen
    # (stream already consumed) => reopen using bytes
# reopen pdfplumber properly with saved bytes
uploaded_file.seek(0)
pdf_bytes = uploaded_file.read()
with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
    fitz_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for i, page in enumerate(pdf.pages):
        raw_text = page.extract_text() or ""
        text_for_match = raw_text

        # If text too short and OCR enabled -> run OCR
        if use_ocr_for_short_text and (len(raw_text.strip()) < ocr_min_chars):
            try:
                ocr_text = ocr_page_to_text(fitz_doc, i)
                if ocr_text and len(ocr_text.strip()) > len(raw_text.strip()):
                    text_for_match = ocr_text
            except Exception:
                # fall back to raw_text
                text_for_match = raw_text

        # Normalize & compact
        norm = normalize_text_for_matching(text_for_match)
        norm = force_compact_token(norm)
        # final text used for detection
        detection_text = norm

        # Detect
        courier = detect_courier(detection_text)
        style = detect_style(detection_text)
        size = detect_size(detection_text)

        # Ensure dict paths exist
        if style not in hierarchy[courier]:
            hierarchy[courier][style] = OrderedDict()
        if size not in hierarchy[courier][style]:
            hierarchy[courier][style][size] = []
        if i not in hierarchy[courier][style][size]:
            hierarchy[courier][style][size].append(i)

        if courier == "UNKNOWN" and style == "Other" and size == "NA":
            unparsed_pages.append(i)

        # Optional preview listing
        if show_extracted_preview:
            st.write(f"--- Page {i} ---")
            st.text(detection_text[:1000])

# Preview table of groups
st.subheader("Detected groups (preview)")
preview_rows = []
for c in COURIER_PRIORITY + ["UNKNOWN"]:
    if c not in hierarchy:
        continue
    for style, sizes in hierarchy[c].items():
        total = sum(len(pages) for pages in sizes.values())
        preview_rows.append({"Courier": c, "Style": style, "TotalPages": total})
st.dataframe(preview_rows)

if unparsed_pages:
    st.warning(f"⚠ {len(unparsed_pages)} pages couldn't be parsed/detected: sample indices {unparsed_pages[:10]}")

# Download UI: courier -> style -> choose sizes
st.header("📦 Download: Courier → Style → (choose sizes)")

for courier in COURIER_PRIORITY:
    styles = hierarchy.get(courier, {})
    if not styles:
        st.info(f"❌ No pages detected for {courier}")
        continue

    st.subheader(f"🚚 {courier}")
    for style_name, sizes_dict in styles.items():
        total_pages_style = sum(len(v) for v in sizes_dict.values())
        with st.expander(f"Style: {style_name}  —  Pages: {total_pages_style}", expanded=False):
            # collect available sizes in stable order
            available_sizes = [s for s in SIZE_ORDER if s in sizes_dict and sizes_dict[s]]
            if "NA" in sizes_dict and sizes_dict["NA"]:
                available_sizes.append("NA")
            st.write(f"Available sizes: {', '.join(available_sizes) if available_sizes else 'None detected'}")

            sizes_selected = st.multiselect(f"Select sizes to include — {courier} • {style_name}", options=available_sizes, default=available_sizes)

            col1, col2 = st.columns([1,1])
            with col1:
                if st.button(f"⬇️ Download Full — {courier} • {style_name}", key=f"full_{courier}_{style_name}"):
                    writer = PdfWriter()
                    for s in SIZE_ORDER + ["NA"]:
                        pages = sizes_dict.get(s, [])
                        for pindex in pages:
                            writer.add_page(PdfReader(BytesIO(pdf_bytes)).pages[pindex])
                    buf = BytesIO()
                    writer.write(buf)
                    buf.seek(0)
                    st.download_button(label=f"Save {courier}_{style_name}.pdf", data=buf, file_name=f"{courier}_{style_name.replace(' ', '_')}.pdf", mime="application/pdf")
            with col2:
                if st.button(f"⬇️ Download Filtered — {courier} • {style_name}", key=f"filt_{courier}_{style_name}"):
                    if not sizes_selected:
                        st.error("Select at least one size to download filtered PDF.")
                    else:
                        writer = PdfWriter()
                        for s in SIZE_ORDER + ["NA"]:
                            if s in sizes_selected:
                                pages = sizes_dict.get(s, [])
                                for pindex in pages:
                                    writer.add_page(PdfReader(BytesIO(pdf_bytes)).pages[pindex])
                        buf = BytesIO()
                        writer.write(buf)
                        buf.seek(0)
                        sel_label = "_".join(sizes_selected)
                        st.download_button(label=f"Save {courier}_{style_name}_{sel_label}.pdf", data=buf, file_name=f"{courier}_{style_name.replace(' ', '_')}_{sel_label}.pdf", mime="application/pdf")

st.success("✅ Done — use the buttons above to download courier+style full or size-filtered PDFs. If any group still misses pages, share a sample page index shown in the preview and I will fine-tune the rules.")
