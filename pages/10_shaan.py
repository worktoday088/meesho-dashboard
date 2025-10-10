import streamlit as st
import pandas as pd
from io import BytesIO, StringIO

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

def clean_text(text):
    if pd.isnull(text):
        return ''
    text = str(text).strip().replace('_', ' ').replace('-', ' ')
    return ' '.join(text.split()).lower()

def extract_color(sku):
    sku_clean = clean_text(sku).replace(' ', '')
    found_colors = [col for col in COLOR_LIST if col.replace(' ', '').lower() in sku_clean]
    return ', '.join(found_colors) if found_colors else ''

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    processed_data = output.getvalue()
    return processed_data

def to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

def main():
    st.title('SKU Color Extractor & CSV/Excel Cleaner')

    uploaded_file = st.file_uploader('Upload your Excel/CSV file', type=['xlsx', 'csv'])
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file, encoding='utf-8', on_bad_lines='skip')
            else:
                df = pd.read_excel(uploaded_file)
        except Exception as e:
            st.error(f"Error reading file: {e}")
            return

        df.columns = df.columns.str.strip()
        sku_col = 'SKU' if 'SKU' in df.columns else st.selectbox('Select SKU column:', df.columns)
        df[sku_col] = df[sku_col].apply(clean_text)
        df['Color'] = df[sku_col].apply(extract_color)

        st.subheader('Cleaned Data with Extracted Colors')
        st.dataframe(df)

        st.download_button(label='Download as Excel', data=to_excel(df), file_name='Cleaned_ExtractedColors.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        st.download_button(label='Download as CSV', data=to_csv(df), file_name='Cleaned_ExtractedColors.csv', mime='text/csv')

        st.success('File cleaned and colors extracted successfully!')

if __name__ == '__main__':
    main()
