import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(
    page_title="Sarita Lite – Image Style Grouper",
    layout="centered"
)

st.title("🧵 Sarita Lite Image Style Grouper")
st.write("Upload Excel → Get Style-wise Output (4 Images = 1 Style)")

GROUP_SIZE = 4

uploaded_file = st.file_uploader(
    "📤 Upload Excel File (Links in Column A)",
    type=["xlsx"]
)

if uploaded_file:
    try:
        # Read Excel
        df = pd.read_excel(uploaded_file, usecols=[0], header=None)
        links = df[0].dropna().tolist()

        if len(links) < GROUP_SIZE:
            st.warning("❗ Minimum 4 image links required.")
        else:
            # Group links (4 = 1 style)
            grouped = [
                links[i:i + GROUP_SIZE]
                for i in range(0, len(links), GROUP_SIZE)
            ]

            output_df = pd.DataFrame(grouped)

            st.success("✅ File processed successfully!")

            st.subheader("📊 Preview (Top 5 Styles)")
            st.dataframe(output_df.head())

            # Convert to Excel for download
            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                output_df.to_excel(
                    writer,
                    index=False,
                    header=False
                )

            st.download_button(
                label="⬇️ Download Output Excel",
                data=output.getvalue(),
                file_name="style_grouped_output.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"❌ Error: {e}")
