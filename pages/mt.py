import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Meesho Image Fill Tool", layout="wide")

st.title("🧵 Meesho Excel – Manual Column Select Tool")
st.write("No auto-detect issues • You select columns • 100% reliable")

uploaded_file = st.file_uploader("📤 Meesho Excel Template Upload करें", type=["xlsx"])

if uploaded_file:
    xls = pd.ExcelFile(uploaded_file)

    sheet_name = st.selectbox("📄 Image links वाली Sheet select करें", xls.sheet_names)

    df = pd.read_excel(uploaded_file, sheet_name=sheet_name, header=2)

    st.markdown("## 🖼️ Image Columns Select करें")

    all_columns = list(df.columns)

    images_per_style = st.number_input(
        "एक Style में कितनी Images होंगी?",
        min_value=1, max_value=20, value=5
    )

    image_columns = st.multiselect(
        "Image columns select करें (order important है)",
        options=all_columns,
        max_selections=images_per_style
    )

    style_col = st.selectbox(
        "Product ID / Style ID वाला column select करें",
        options=all_columns
    )

    repeat_rows = st.number_input(
        "एक Style को कितनी Rows में Repeat करना है? (Ctrl + D)",
        min_value=1, max_value=20, value=4
    )

    if st.button("✅ Generate & Fill Template"):
        if len(image_columns) != images_per_style:
            st.error("❌ जितनी images per style चुनी हैं, उतने image columns select करें.")
            st.stop()

        data_df = df.iloc[4:].copy()

        links = []
        for _, row in data_df.iterrows():
            for col in image_columns:
                if pd.notna(row[col]):
                    links.append(row[col])

        total_styles = len(links) // images_per_style

        if total_styles == 0:
            st.error("❌ Selected columns में कोई valid image link नहीं मिला.")
            st.stop()

        st.markdown("## ✏️ हर Style के लिए Product ID / Style ID लिखें")

        style_ids = []
        for i in range(total_styles):
            sid = st.text_input(f"Style {i+1} – Product ID / Style ID", key=i)
            style_ids.append(sid)

        start_row = 4
        current_row = start_row

        for i in range(total_styles):
            style_images = links[i*images_per_style:(i+1)*images_per_style]

            for _ in range(repeat_rows):
                for j, col in enumerate(image_columns):
                    df.at[current_row, col] = style_images[j]

                df.at[current_row, style_col] = style_ids[i]
                current_row += 1

        st.success("✅ Template Successfully Filled!")

        st.dataframe(df.iloc[:current_row], use_container_width=True)

        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name, startrow=2)

        st.download_button(
            "⬇️ Download Filled Excel",
            output.getvalue(),
            file_name="meesho_filled_final.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
