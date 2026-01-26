import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(
    page_title="Final Image Style Excel Tool",
    layout="wide"
)

st.title("🧵 Final Image Style Excel Tool (Streamlit)")
st.write("Excel Upload → Style-wise Images → Individual Style IDs → Repeat → Preview → Download")

# ================= USER SETTINGS =================

images_per_style = st.number_input(
    "एक Style में कितनी Images होंगी?",
    min_value=1,
    max_value=30,
    value=5
)

repeat_rows = st.number_input(
    "एक Style को कितनी Rows में Repeat करना है? (Ctrl + D जैसा)",
    min_value=1,
    max_value=30,
    value=4
)

uploaded_file = st.file_uploader(
    "📤 Excel Upload करें (Image links Column A में)",
    type=["xlsx"]
)

# ================= PROCESS =================

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file, usecols=[0], header=None)
        links = df[0].dropna().tolist()

        total_styles = len(links) // images_per_style

        if total_styles == 0:
            st.warning("❗ Images की संख्या style size से कम है.")
        else:
            st.markdown("## ✏️ हर Style के लिए Style ID लिखें")

            style_ids = []
            for i in range(total_styles):
                sid = st.text_input(
                    f"Style {i+1} ID (Images {i*images_per_style + 1} – {(i+1)*images_per_style})",
                    key=f"style_id_{i}"
                )
                style_ids.append(sid)

            if st.button("✅ Generate Final Excel"):
                final_rows = []

                for i in range(total_styles):
                    style_images = links[
                        i*images_per_style:(i+1)*images_per_style
                    ]

                    for _ in range(repeat_rows):
                        row = []
                        row.extend(style_images)
                        row.append(style_ids[i])
                        final_rows.append(row)

                # Column names
                columns = []
                for i in range(images_per_style):
                    columns.append(f"Image_{i+1}")
                columns.append("Style_ID")

                output_df = pd.DataFrame(final_rows, columns=columns)

                st.success("✅ Excel Successfully Generated!")

                st.markdown("## 📋 Full Preview (Copy–Paste Ready)")
                st.dataframe(output_df, use_container_width=True)

                # Download Excel
                output = BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                    output_df.to_excel(
                        writer,
                        index=False,
                        sheet_name="Final_Output"
                    )

                st.download_button(
                    label="⬇️ Download Final Excel",
                    data=output.getvalue(),
                    file_name="final_style_output.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    except Exception as e:
        st.error(f"❌ Error: {e}")
