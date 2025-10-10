import streamlit as st
import pandas as pd

# MASTER COLOR LIST — सभी संभावित रंग जोड़ दिए हैं
COLOR_LIST = [
    'BLACK', 'WHITE', 'GREY', 'PINK', 'PURPLE', 'WINE', 'BOTTLE GREEN', 'PEACH',
    'CREAM', 'BROWN', 'BLUE', 'RED', 'YELLOW', 'NAVY', 'NAVY BLUE', 'PETROL',
    'MUSTARD', 'WHITE-RED', 'WHITE-BLUE', 'BLACK-YELLOW',
    'MAROON', 'OLIVE', 'SKY BLUE', 'ORANGE', 'BEIGE', 'FUCHSIA', 'MAGENTA',
    'SEA GREEN', 'TEAL', 'TURQUOISE', 'VIOLET', 'OFF WHITE', 'GOLD', 'SILVER',
    'CHARCOAL', 'RUST', 'MINT', 'LAVENDER', 'BURGUNDY', 'KHAKI', 'CAMEL',
    'IVORY', 'CORAL', 'COPPER', 'MULTICOLOR', 'GREEN', 'DARK GREEN', 'LIGHT GREEN',
    'DARK BLUE', 'LIGHT BLUE', 'DARK GREY', 'LIGHT GREY', 'SKIN', 'STONE'
]

def extract_color(sku):
    norm = lambda t: t.replace('-', '').replace(' ', '').lower()
    sku_norm = norm(str(sku))
    found_colors = [col for col in COLOR_LIST if norm(col) in sku_norm]
    return ', '.join(found_colors) if found_colors else ''

st.title('SKU Color Extractor')

uploaded_file = st.file_uploader('Upload your Excel/CSV file', type=['xlsx', 'csv'])
if uploaded_file:
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file, encoding='utf-8')
    else:
        df = pd.read_excel(uploaded_file)
    sku_col = 'SKU' if 'SKU' in df.columns else st.selectbox('Select SKU column:', df.columns)
    df['Color'] = df[sku_col].astype(str).apply(extract_color)
    st.write('Extracted Colors:')
    st.dataframe(df)
    st.download_button('Download Result (Excel)', df.to_excel(index=False), file_name='ExtractedColors.xlsx')
    st.download_button('Download Result (CSV)', df.to_csv(index=False), file_name='ExtractedColors.csv')
    st.success('Color column created! You can filter and download.')
