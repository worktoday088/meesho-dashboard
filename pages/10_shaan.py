import streamlit as st
import pandas as pd
import unicodedata
import re
from io import BytesIO
from typing import List

COLOR_LIST: List[str] = [
    'BLACK', 'WHITE', 'GREY', 'PINK', 'PURPLE', 'WINE', 'BOTTLE GREEN', 'PEACH',
    'CREAM', 'BROWN', 'BLUE', 'RED', 'YELLOW', 'NAVY', 'NAVY BLUE', 'PETROL',
    'MUSTARD', 'WHITE-RED', 'WHITE-BLUE', 'BLACK-YELLOW', 'MAROON', 'OLIVE', 'SKY BLUE',
    'ORANGE', 'BEIGE', 'FUCHSIA', 'MAGENTA', 'SEA GREEN', 'TEAL', 'TURQUOISE',
    'VIOLET', 'OFF WHITE', 'GOLD', 'SILVER', 'CHARCOAL', 'RUST', 'MINT', 'LAVENDER',
    'BURGUNDY', 'KHAKI', 'CAMEL', 'IVORY', 'CORAL', 'COPPER', 'MULTICOLOR', 'GREEN',
    'DARK GREEN', 'LIGHT GREEN', 'DARK BLUE', 'LIGHT BLUE', 'DARK GREY',
    'LIGHT GREY', 'SKIN', 'STONE'
]

def clean_text(text: str) -> str:
    if pd.isnull(text):
        return ''
    s = str(text)
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
    s = s.replace('_', ' ').replace('-', ' ')
    s = re.sub(r'[^A-Za-z0-9\s]', ' ', s)
    s = ' '.join(s.split()).lower()
    return s

def extract_color(row):
    all_text = f"{row.get('SKU','')} {row.get('Product Name','')}"
    sku_norm = clean_text(all_text).replace(' ', '')
    found = []
    for col in COLOR_LIST:
        c_norm = clean_text(col).replace(' ', '')
        if c_norm and c_norm in sku_norm:
            found.append(col)
    seen = set()
    unique_found = [x for x in found if not (x in seen or seen.add(x))]
    return ', '.join(unique_found)

def df_to_excel_bytes(df: pd.DataFrame):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return buffer.getvalue()

def main():
    st.title('SKU Color Extractor • CSV/Excel Cleaner (Robust Version)')
    uploaded = st.file_uploader('Upload file (CSV/XLSX)', type=['csv', 'xlsx', 'xls'])
    if not uploaded:
        st.info('Upload a file to begin')
        return

    try:
        if uploaded.name.lower().endswith('.csv'):
            df = pd.read_csv(uploaded, encoding='utf-8', on_bad_lines='skip')
        else:
            df = pd.read_excel(uploaded)
    except Exception:
        uploaded.seek(0)
        df = pd.read_csv(uploaded, encoding='latin1', on_bad_lines='skip')

    df.columns = df.columns.astype(str).str.strip()

    # दोनों कॉलम clean करें+combine करें वरना दोनों का नाम अलग हो सकता है
    for col in ['SKU', 'Product Name']:
        if col in df.columns:
            df[col] = df[col].fillna('').astype(str)

    df['Color'] = df.apply(extract_color, axis=1)

    st.dataframe(df)

    excel_data = df_to_excel_bytes(df)
    csv_data = df.to_csv(index=False).encode('utf-8')

    st.download_button('Download Excel', data=excel_data, file_name='Cleaned_ExtractedColors.xlsx')
    st.download_button('Download CSV', data=csv_data, file_name='Cleaned_ExtractedColors.csv')

    st.success('Extraction complete! Check the output below.')

if __name__ == "__main__":
    main()
