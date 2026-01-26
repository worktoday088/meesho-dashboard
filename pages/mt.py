import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(
    page_title="Meesho Auto Detect Image Tool",
    layout="wide"
)

st.title("🧵 Meesho Auto-Detect Image & Style ID Tool (Streamlit)")
st.write("Original Meesho Template Upload करें → Auto Fill → Direct Upload")

# ================= USER INPUTS =================

uploaded_file = st.file_uploader(
    "📤 Original Meesho Excel Template Upload करें",
    type=["xlsx"]
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

# ================= PROCESS =================

if uploaded_file:
    try:
        # Load Excel
        xls = pd.ExcelFile(uploaded_file)
        sheet_name = st.selectbox(
            "📄 Image वाली Sheet select करें",
            xls.sheet_names
        )

        # Read sheet with header at row 3
        df = pd.read_excel(
            uploaded_file,
            sheet_name=sheet_name,
            header=2
        )

        # ---------- AUTO DETECT IMAGE COLUMNS ----------
        image_columns = []
        for col in df.columns:
            col_text = str(col).lower()
            if "image" in col_text:
                image_columns.append(col)

        if not image_columns:
            st.error("❌ Image columns auto-detect नहीं हो पाए.")
            st.stop()

        # Limit image columns to selected style size
        image_columns = image_columns[:images_per_style]

        # ---------- AUTO DETECT STYLE ID COLUMN ----------
        style_col = None
        for col in df.columns:
            col_text = str(col).lower()
            if "product" in col_text and "style" in col_text:
                style_col = col
                break

        if style_col is None:
            st.error("❌ Product ID / Style ID column auto-detect नहीं हुआ.")
            st.stop()

        # ---------- READ IMAGE LINKS (Row 5 onward) ----------
        data_df = df.iloc[4:].copy()

        links = []
        for _, row in data_df.iterrows():
            for col in image_columns:
                if pd.notna(row[col]):
                    links.append(row[col])

        total_styles = len(links) // images_per_style

        if total_styles == 0:
            st.warning("❗ पर्याप्त image links नहीं मिले.")
            st.stop()

        st.markdown("## ✏️ हर Style के लिए Product ID / Style ID लिखें")

        style_ids = []
        for i in range(total_styles):
            sid = st.text_input(
                f"Style {i+1} – Product ID / Style ID",
                key=f"sid_{i}"
            )
            style_ids.append(sid)

        # ---------- FILL TEMPLATE ----------
        if st.button("✅ Auto Fill Meesho Template"):
            start_excel_row = 4  # Row 5
            current_row = start_excel_row

            for i in range(total_styles):
                style_images = links[
                    i*images_per_style:(i+1)*images_per_style
                ]

                for _ in range(repeat_rows):
                    for j, col in enumerate(image_columns):
                        df.at[current_row, col] = style_images[j]

                    df.at[current_row, style_col] = style_ids[i]
                    current_row += 1

            st.success("✅ Meesho Template Successfully Filled!")

            st.markdown("## 📋 Preview (Exact Meesho Format)")
            st.dataframe(df.iloc[:current_row], use_container_width=True)

            # ---------- DOWNLOAD ----------
            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df.to_excel(
                    writer,
                    index=False,
                    sheet_name=sheet_name,
                    startrow=2  # Header back to row 3
                )

            st.download_button(
                label="⬇️ Download Filled Meesho Excel",
                data=output.getvalue(),
                file_name="meesho_auto_filled.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"❌ Error: {e}")
