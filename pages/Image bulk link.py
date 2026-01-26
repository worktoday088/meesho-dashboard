import streamlit as st
import pandas as pd
from io import BytesIO
import string

st.set_page_config(
    page_title="Advanced Style Excel Tool",
    layout="wide"
)

st.title("🧠 Advanced Image Style Excel Tool (Streamlit)")

st.markdown("### ⚙️ Style Configuration")

# USER INPUTS
images_per_style = st.number_input(
    "एक Style में कितनी Images होंगी?",
    min_value=1,
    max_value=20,
    value=4
)

repeat_rows = st.number_input(
    "एक Style को कितनी Rows में Repeat करना है?",
    min_value=1,
    max_value=20,
    value=4
)

style_name = st.text_input(
    "Style Name / Style ID (optional)",
    value=""
)

uploaded_file = st.file_uploader(
    "📤 Excel Upload करें (Image links Column A में)",
    type=["xlsx"]
)

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file, usecols=[0], header=None)
        links = df[0].dropna().tolist()

        if len(links) < images_per_style:
            st.warning("❗ Images count style size से कम है.")
        else:
            final_rows = []

            for i in range(0, len(links), images_per_style):
                style_images = links[i:i + images_per_style]

                if len(style_images) == images_per_style:
                    for _ in range(repeat_rows):
                        row = []
                        if style_name.strip():
                            row.append(style_name)
                        row.extend(style_images)
                        final_rows.append(row)

            # Column names
            columns = []
            if style_name.strip():
                columns.append("Style_Name")

            for i in range(images_per_style):
                columns.append(f"Image_{i+1}")

            output_df = pd.DataFrame(final_rows, columns=columns)

            st.success("✅ Excel Successfully Processed!")

            st.subheader("📋 Full Preview (Copy–Paste Ready)")
            st.dataframe(output_df, use_container_width=True)

            # Download
            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                output_df.to_excel(
                    writer,
                    index=False,
                    sheet_name="Final_Output"
                )

            st.download_button(
                label="⬇️ Download Excel",
                data=output.getvalue(),
                file_name="style_ready_output.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"❌ Error: {e}")
