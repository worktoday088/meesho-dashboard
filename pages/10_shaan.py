import streamlit as st
import pandas as pd
import re
import unicodedata
from io import BytesIO
from typing import List

# ------------------ MASTER COLOR LIST (Comprehensive) ------------------
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

# ------------------ TEXT CLEANING & COLOR EXTRACTION ------------------
def clean_text(text: str) -> str:
    """Remove unicode noise, special chars, normalize case & spaces."""
    if pd.isnull(text):
        return ''
    s = str(text)
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')  # remove unicode noise
    s = s.replace('_', ' ').replace('-', ' ')  # normalize separators
    s = re.sub(r'[^A-Za-z0-9\s]', ' ', s)     # keep only alnum + space
    s = ' '.join(s.split()).lower()            # collapse spaces, lowercase
    return s

def extract_color(sku: str) -> str:
    sku_norm = clean_text(sku).replace(' ', '')
    found = []
    for col in COLOR_LIST:
        c_norm = clean_text(col).replace(' ', '')
        if c_norm and c_norm in sku_norm:
            found.append(col)
    # deduplicate while preserving order
    seen = set()
    unique_found = [x for x in found if not (x in seen or seen.add(x))]
    return ', '.join(unique_found)

# ------------------ FILE READ HELPERS ------------------
def read_any(uploaded_file) -> pd.DataFrame:
    """Robust reader: tries multiple encodings & handles bad lines."""
    name = uploaded_file.name.lower()
    if name.endswith('.xlsx') or name.endswith('.xls'):
        return pd.read_excel(uploaded_file)
    # CSV: try utf-8, then latin1 fallback
    try:
        return pd.read_csv(uploaded_file, encoding='utf-8', on_bad_lines='skip')
    except Exception:
        uploaded_file.seek(0)
        return pd.read_csv(uploaded_file, encoding='latin1', on_bad_lines='skip')

def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    """Return Excel bytes using openpyxl."""
    buffer = BytesIO()
    try:
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
        return buffer.getvalue()
    finally:
        buffer.close()

# ------------------ STREAMLIT APP ------------------
def main():
    st.title('SKU Color Extractor • CSV/Excel Cleaner')

    uploaded = st.file_uploader('Upload your file (CSV or Excel)', type=['csv', 'xlsx', 'xls'])
    if not uploaded:
        st.info('Upload a CSV/XLSX to start')
        return

    # Read file robustly
    try:
        df = read_any(uploaded)
    except Exception as e:
        st.error(f'File read error: {e}')
        return

    # Clean column names
    df.columns = df.columns.astype(str).str.strip()

    # Choose SKU column
    default_sku_col = 'SKU' if 'SKU' in df.columns else None
    sku_col = st.selectbox('Select SKU column', df.columns, index=(list(df.columns).index(default_sku_col) if default_sku_col in df.columns else 0))

    # Clean SKU text and extract colors
    df['SKU_CLEAN'] = df[sku_col].apply(clean_text)
    df['Color'] = df['SKU_CLEAN'].apply(lambda s: extract_color(s))

    # Optional: show unmatched rows for review
    show_unmatched = st.checkbox('Show only rows where Color not found', value=False)
    view_df = df[df['Color'].eq('')] if show_unmatched else df

    st.subheader('Preview')
    st.dataframe(view_df, use_container_width=True)

    # Downloads
    excel_bytes = df_to_excel_bytes(df)
    csv_bytes = df.to_csv(index=False).encode('utf-8')

    st.download_button('Download Excel (clean + colors)', data=excel_bytes,
                       file_name='Cleaned_ExtractedColors.xlsx',
                       mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    st.download_button('Download CSV (clean + colors)', data=csv_bytes,
                       file_name='Cleaned_ExtractedColors.csv',
                       mime='text/csv')

    st.success('Completed: file cleaned and colors extracted')

if __name__ == '__main__':
    main()
