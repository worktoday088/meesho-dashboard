import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(
    page_title="Image Style Excel Tool",
    layout="wide"
)

st.title("📊 Image Style Excel Automation (Streamlit)")
st.write("Upload Excel → Get Style-wise Repeated Output")

GROUP_SIZE = 4      # 4 images = 1 style
REPEAT_ROWS = 4     # same style repeat 4 rows

uploaded_file = st.file_uploader(
    "📤 Upload Excel (Image links in Column A)",
    type=["xlsx"]
)

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file, usecols=[0], header=None)
        links = df[0].dropna().tolist()

        if len(links) < GROUP_SIZE:
            st.warning("❗ Minimum 4 image links required.")
        else:
            final_rows = []

            for i in range(0, len(links), GROUP_SIZE):
                style = links[i:i + GROUP_SIZE]

                if len(style) == GROUP_SIZE:
                    for _ in range(REPEAT_ROWS):
                        final_rows.append(style)

            output_df = pd.DataFrame(
                final_rows,
                columns=["Image 1", "Image 2", "Image 3", "Image 4"]
            )

            st.success("✅ File processed successfully!")

            # FULL PREVIEW (no limit)
            st.subheader("📋 Full Preview (Copy–Paste Ready)")
            st.dataframe(output_df, use_container_width=True)

            # Download Excel
            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                output_df.to_excel(
                    writer,
                    index=False,
                    sheet_name="Final_Data"
                )

            st.download_button(
                label="⬇️ Download Excel Output",
                data=output.getvalue(),
                file_name="final_style_repeated_output.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"❌ Error: {e}")
