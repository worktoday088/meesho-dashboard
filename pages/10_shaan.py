import streamlit as st
import pandas as pd

# Master Color List with popular Indian and international fashion shades
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
    # Normalize text: strip spaces, remove underscores/dashes, lowercase
    if pd.isnull(text):
        return ''
    text = str(text).strip().replace('_', ' ').replace('-', ' ')
    return ' '.join(text.split()).lower()  # also removes extra inner spaces

def extract_color(sku):
    sku_clean = clean_text(sku).replace(' ', '')
    found_colors = [col for col in COLOR_LIST if col.replace(' ', '').lower() in sku_clean]
    return ', '.join(found_colors) if found_colors else ''

def main():
    st.title('Full Featured SKU Color Extractor & CSV/Excel Cleaner')

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

        # Clean columns names too
        df.columns = df.columns.str.strip()

        # Choose SKU column
        sku_col = 'SKU' if 'SKU' in df.columns else st.selectbox('Select SKU column:', df.columns)

        # Clean SKU column text
        df[sku_col] = df[sku_col].apply(clean_text)

        # Extract colors
        df['Color'] = df[sku_col].apply(extract_color)

        st.subheader('Cleaned Data with Extracted Colors')
        st.dataframe(df)

        # Download buttons
        to_excel = df.to_excel(index=False)
        to_csv = df.to_csv(index=False)

        st.download_button(label='Download as Excel', data=to_excel, file_name='Cleaned_ExtractedColors.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        st.download_button(label='Download as CSV', data=to_csv, file_name='Cleaned_ExtractedColors.csv', mime='text/csv')

        st.success('File cleaned and colors extracted successfully!')

if __name__ == '__main__':
    main()
