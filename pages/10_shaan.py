import streamlit as st
import pandas as pd
import unicodedata, re
from io import BytesIO
from typing import List

# ---------------- Master Lists ----------------
# Compound colors that must remain as-is in output
COMPOUND_COLORS: List[str] = [
    'WHITE-RED', 'WHITE-BLUE', 'BLACK-YELLOW'
    # जरूरत के हिसाब से और जोड़ते रहें: 'RED-BLACK', 'BLUE-WHITE', ...
]

# All colors including multi-word single colors
COLOR_LIST: List[str] = [
    'BLACK', 'WHITE', 'GREY', 'PINK', 'PURPLE', 'WINE', 'BOTTLE GREEN', 'PEACH',
    'CREAM', 'BROWN', 'BLUE', 'RED', 'YELLOW', 'NAVY', 'NAVY BLUE', 'PETROL',
    'MUSTARD', 'WHITE-RED', 'WHITE-BLUE', 'BLACK-YELLOW',
    'MAROON', 'OLIVE', 'SKY BLUE', 'ORANGE', 'BEIGE', 'FUCHSIA', 'MAGENTA',
    'SEA GREEN', 'TEAL', 'TURQUOISE', 'VIOLET', 'OFF WHITE', 'GOLD', 'SILVER',
    'CHARCOAL', 'RUST', 'MINT', 'LAVENDER', 'BURGUNDY', 'KHAKI', 'CAMEL',
    'IVORY', 'CORAL', 'COPPER', 'MULTICOLOR', 'GREEN', 'DARK GREEN', 'LIGHT GREEN',
    'DARK BLUE', 'LIGHT BLUE', 'DARK GREY', 'LIGHT GREY', 'SKIN', 'STONE'
]

# -------------- Normalization Helpers --------------
def normalize(s: str) -> str:
    if pd.isna(s): return ''
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii','ignore').decode('ascii')
    s = s.replace('\u200b',' ')
    s = s.replace('_',' ').replace('-',' ')
    s = re.sub(r'[^A-Za-z0-9\s]',' ', s)
    s = ' '.join(s.split()).lower()
    return s

def key(s: str) -> str:
    return normalize(s).replace(' ', '')  # space-less for robust contains

# -------------- Extraction Logic --------------
def extract_color_from_row(row: pd.Series) -> str:
    # Search across SKU + Product Name together
    all_text = f"{row.get('SKU','')} {row.get('Product Name','')}"
    t = key(all_text)

    found = []

    # 1) Priority: detect compound colors first (keep as-is)
    for comp in COMPOUND_COLORS:
        if key(comp) in t:
            found.append(comp)

    # Build component set from compounds to avoid duplicates like WHITE, RED
    compound_components = set()
    for comp in found:
        for p in comp.split('-'):
            compound_components.add(p.strip().upper())

    # 2) Detect other colors (single or multi-word), but skip components of found compounds
    for col in COLOR_LIST:
        if col in COMPOUND_COLORS:
            continue  # compounds already handled
        if key(col) in t:
            if col.upper() in compound_components:
                continue
            found.append(col)

    # Unique preserve order
    seen = set(); unique = []
    for c in found:
        if c not in seen:
            unique.append(c); seen.add(c)

    return ', '.join(unique)

# -------------- File IO --------------
def read_any(upload) -> pd.DataFrame:
    try:
        if upload.name.lower().endswith(('.xlsx','.xls')):
            return pd.read_excel(upload)
        return pd.read_csv(upload, encoding='utf-8', on_bad_lines='skip')
    except Exception:
        upload.seek(0)
        return pd.read_csv(upload, encoding='latin1', on_bad_lines='skip')

def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return buffer.getvalue()

# -------------- Streamlit App --------------
def main():
    st.title('SKU Color Extractor • Compound-Priority • Cleaner')

    uploaded = st.file_uploader('Upload CSV/XLSX', type=['csv','xlsx','xls'])
    if not uploaded:
        st.info('Upload a file to start')
        return

    try:
        df = read_any(uploaded)
    except Exception as e:
        st.error(f'File read error: {e}')
        return

    # Clean column names
    df.columns = df.columns.astype(str).str.strip()

    # Ensure columns exist; if missing, create blanks so logic works
    if 'SKU' not in df.columns: df['SKU'] = ''
    if 'Product Name' not in df.columns: df['Product Name'] = ''

    # Extract Color
    df['Color'] = df.apply(extract_color_from_row, axis=1)

    st.subheader('Preview')
    st.dataframe(df.head(200), use_container_width=True)

    with st.expander('Rows with NO color match'):
        st.dataframe(df[df['Color'].eq('')].head(200), use_container_width=True)

    excel_bytes = to_excel_bytes(df)
    csv_bytes = df.to_csv(index=False).encode('utf-8')

    st.download_button('Download Excel (with Color)', data=excel_bytes,
                       file_name='Cleaned_ExtractedColors.xlsx',
                       mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    st.download_button('Download CSV (with Color)', data=csv_bytes,
                       file_name='Cleaned_ExtractedColors.csv', mime='text/csv')

    st.success('Done! Compound colors kept as-is (e.g., WHITE-RED).')

if __name__ == '__main__':
    main()
