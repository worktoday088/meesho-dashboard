import streamlit as st
import pandas as pd
from io import BytesIO
from openpyxl.utils import column_index_from_string, get_column_letter

st.set_page_config(
    page_title="Meesho Column Letter Image Tool",
    layout="wide"
)

st.title("🧵 Meesho Template – Column Letter Based Image Filler")
st.write("No column name issues • You select column letters • 100% reliable")

# ================= UPLOAD =================
uploaded_file = st.file_uploader(
    "📤 Original Meesho Excel Template Upload करें",
    type=["xlsx"]
)

if uploaded_file:
    xls = pd.ExcelFile(uploaded_file)

    sheet_name = st.selectbox(
        "📄 Image links वाली Sheet select करें",
        xls.sheet_names
    )

    # Fixed as per your template
    HEADER_ROW = 3      # Excel row number
    DATA_START_ROW = 5 # Excel row number

    df = pd.read_excel(
        uploaded_file,
        sheet_name=sheet_name,
        header=HEADER_ROW - 1
    )

    st.markdown("## ⚙️ Column Settings")

    image_start_col_letter = st.text_input(
        "Image 1 (Front) का Column Letter लिखें",
        value="AH"
    ).upper()

    images_per_style = st.number_input(
        "एक Style में कितनी Images होंगी?",
        min_value=1,
        max_value=20,
        value=5
    )

    style_id_col_letter = st.text_input(
        "Product ID / Style ID का Column Letter लिखें",
        value="AL"
    ).upper()

    repeat_rows = st.number_input(
        "एक Style को कितनी Rows में Repeat करना है? (Ctrl + D)",
        min_value=1,
        max_value=20,
        value=4
    )

    if st.button("✅ Fill Meesho Template"):
        try:
            # Convert column letters to indexes
            image_start_idx = column_index_from_string(image_start_col_letter) - 1
            style_id_idx = column_index_from_string(style_id_col_letter) - 1

            # Image column indexes
            image_col_indexes = list(
                range(image_start_idx, image_start_idx + images_per_style)
            )

            # Data rows (Row 5 onwards)
            data_df = df.iloc[DATA_START_ROW - 1:].copy()

            # Collect image links sequentially
            links = []
            for _, row in data_df.iterrows():
                for col_idx in image_col_indexes:
                    if col_idx < len(df.columns):
                        val = row.iloc[col_idx]
                        if pd.notna(val):
                            links.append(val)

            total_styles = len(links) // images_per_style

            if total_styles == 0:
                st.error("❌ Selected columns में कोई valid image link नहीं मिला.")
                st.stop()

            st.markdown("## ✏️ हर Style के लिए Product ID / Style ID लिखें")

            style_ids = []
            for i in range(total_styles):
                sid = st.text_input(
                    f"Style {i+1} – Product ID / Style ID",
                    key=f"sid_{i}"
                )
                style_ids.append(sid)

            # Fill template
            current_row = DATA_START_ROW - 1

            for i in range(total_styles):
                style_images = links[
                    i * images_per_style:(i + 1) * images_per_style
                ]

                for _ in range(repeat_rows):
                    for j, col_idx in enumerate(image_col_indexes):
                        if col_idx < len(df.columns):
                            df.iat[current_row, col_idx] = style_images[j]

                    df.iat[current_row, style_id_idx] = style_ids[i]
                    current_row += 1

            st.success("✅ Meesho Template Successfully Filled!")

            st.markdown("## 📋 Preview (Exact Meesho Format)")
            st.dataframe(df.iloc[:current_row], use_container_width=True)

            # Download
            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df.to_excel(
                    writer,
                    index=False,
                    sheet_name=sheet_name,
                    startrow=HEADER_ROW - 1
                )

            st.download_button(
                "⬇️ Download Filled Meesho Excel",
                data=output.getvalue(),
                file_name="meesho_column_letter_filled.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        except Exception as e:
            st.error(f"❌ Error: {e}")
