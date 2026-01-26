import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(
    page_title="Meesho Template Image Filler",
    layout="wide"
)

st.title("🧵 Meesho Template – Image & Style ID Automation (Streamlit)")
st.write("Upload Meesho Excel → Auto fill images + Product ID → Direct Upload Ready")

# ================= USER INPUTS =================

sheet_name = st.text_input(
    "📄 Image links वाली Sheet का exact नाम लिखें",
    placeholder="Example: Catalog Upload"
)

images_per_style = st.number_input(
    "एक Style में कितनी Images होंगी?",
    min_value=1,
    max_value=20,
    value=5
)

repeat_rows = st.number_input(
    "एक Style को कितनी Rows में Repeat करना है? (Ctrl + D जैसा)",
    min_value=1,
    max_value=20,
    value=4
)

uploaded_file = st.file_uploader(
    "📤 Meesho Excel Template Upload करें",
    type=["xlsx"]
)

# ================= PROCESS =================

if uploaded_file and sheet_name:
    try:
        # Read template with header at row 3 (index 2)
        df = pd.read_excel(
            uploaded_file,
            sheet_name=sheet_name,
            header=2
        )

        # Image columns (auto-detect)
        image_columns = [
            col for col in df.columns
            if str(col).lower().startswith("image")
        ]

        style_col = "Product ID / style ID"

        if style_col not in df.columns:
            st.error(f"❌ Column '{style_col}' नहीं मिला.")
            st.stop()

        if len(image_columns) < images_per_style:
            st.error("❌ Template में image columns style size से कम हैं.")
            st.stop()

        image_columns = image_columns[:images_per_style]

        # Data start row = Row 5 → index 4
        data_df = df.iloc[4:].copy()

        links = []
        for _, row in data_df.iterrows():
            for col in image_columns:
                if pd.notna(row[col]):
                    links.append(row[col])

        total_styles = len(links) // images_per_style

        if total_styles == 0:
            st.warning("❗ Image links पर्याप्त नहीं हैं.")
            st.stop()

        st.markdown("## ✏️ हर Style के लिए Product ID / Style ID लिखें")

        style_ids = []
        for i in range(total_styles):
            sid = st.text_input(
                f"Style {i+1} Product ID / Style ID",
                key=f"style_{i}"
            )
            style_ids.append(sid)

        if st.button("✅ Fill Template"):
            output_rows = []
            start_row_index = 4  # row 5 in Excel

            current_excel_row = start_row_index

            for i in range(total_styles):
                style_images = links[
                    i*images_per_style:(i+1)*images_per_style
                ]

                for _ in range(repeat_rows):
                    for j, col in enumerate(image_columns):
                        df.at[current_excel_row, col] = style_images[j]

                    df.at[current_excel_row, style_col] = style_ids[i]
                    current_excel_row += 1

            st.success("✅ Template Successfully Filled!")

            st.markdown("## 📋 Preview (Exact Template Format)")
            st.dataframe(df.iloc[:current_excel_row], use_container_width=True)

            # Download filled template
            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df.to_excel(
                    writer,
                    index=False,
                    sheet_name=sheet_name,
                    startrow=2   # header back to row 3
                )

            st.download_button(
                label="⬇️ Download Filled Meesho Template",
                data=output.getvalue(),
                file_name="meesho_filled_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"❌ Error: {e}")
