import streamlit as st
import pandas as pd

# --- MASTER LIST OF COLORS ---
COLOR_LIST = [
    'BLACK', 'WHITE', 'GREY', 'PINK', 'PURPLE', 'WINE', 'BOTTLE GREEN', 'CREAM', 'PEACH', 'BLUE', 'RED', 'YELLOW', 'FRUIT', 'JACKET'
]

def extract_color(sku):
    found_colors = [col for col in COLOR_LIST if col.lower() in sku.lower()]
    return ', '.join(found_colors) if found_colors else ''

st.title('SKU Color Extractor')

uploaded_file = st.file_uploader('Upload your Excel/CSV file', type=['xlsx', 'csv'])

if uploaded_file:
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
    sku_col = st.selectbox('Select SKU column:', df.columns)
    
    df['Color'] = df[sku_col].apply(extract_color)
    st.write('Extracted Colors:')
    st.dataframe(df)
    
    st.download_button('Download Result (Excel)', df.to_excel(index=False), file_name='ExtractedColors.xlsx')
    st.download_button('Download Result (CSV)', df.to_csv(index=False), file_name='ExtractedColors.csv')
    
    st.success('Color column created! You can filter and download.')
