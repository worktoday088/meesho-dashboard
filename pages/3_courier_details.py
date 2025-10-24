import streamlit as st
import pandas as pd
from io import BytesIO

# -------------------------------
# Page Configuration
# -------------------------------
st.set_page_config(page_title="Courier Partner Delivery Analysis", layout="wide")
st.title("📦 Courier Partner Delivery Analysis")

# -------------------------------
# File Upload Section
# -------------------------------
st.sidebar.header("📂 Upload Files")

uploaded_files = st.sidebar.file_uploader(
    "Choose one or more files (CSV / Excel)",
    type=["csv", "xlsx", "xls"],
    accept_multiple_files=True
)

# Number of header rows to skip (headers start from row 8)
HEADER_ROW_INDEX = 7

# -------------------------------
# Process Uploaded Files
# -------------------------------
if uploaded_files:
    all_dataframes = []

    for i, uploaded_file in enumerate(uploaded_files):
        # Auto-detect file type
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file, skiprows=HEADER_ROW_INDEX)
        else:
            df = pd.read_excel(uploaded_file, skiprows=HEADER_ROW_INDEX)

        # Only for first file → Keep header
        if i == 0:
            master_df = df.copy()
        else:
            # For subsequent files → only add data (ignore headers)
            all_dataframes.append(df)

    # Combine all data together
    if all_dataframes:
        combined_df = pd.concat([master_df] + all_dataframes, ignore_index=True)
    else:
        combined_df = master_df.copy()

    # -------------------------------
    # Data Cleaning
    # -------------------------------
    # Replace PocketShip and Valmo → Valmo unified
    if 'Courier Partner' in combined_df.columns:
        combined_df['Courier Partner'] = combined_df['Courier Partner'].replace({
            'PocketShip': 'Valmo',
            'Valmo': 'Valmo'
        })

    # Ensure Delivered Date is in date format
    if 'Delivered Date' in combined_df.columns:
        combined_df['Delivered Date'] = pd.to_datetime(
            combined_df['Delivered Date'], errors='coerce'
        ).dt.date

    # -------------------------------
    # Group & Pivot for Summary
    # -------------------------------
    summary = combined_df.groupby(['Delivered Date', 'Courier Partner']).size().reset_index(name="Total Packets")

    pivot_df = summary.pivot_table(
        index="Delivered Date",
        columns="Courier Partner",
        values="Total Packets",
        aggfunc="sum",
        fill_value=0
    )

    # Add Grand Total column
    pivot_df["Grand Total"] = pivot_df.sum(axis=1)

    # -------------------------------
    # Sidebar Filters
    # -------------------------------
    st.sidebar.header("🔍 Filters")

    all_dates = pivot_df.index.unique().tolist()
    all_couriers = [c for c in pivot_df.columns if c != "Grand Total"]

    if st.sidebar.button("🗑 Clear All Filters"):
        selected_dates = []
        selected_couriers = []
    else:
        selected_dates = st.sidebar.multiselect("Select Delivered Date(s)", all_dates, default=all_dates)
        selected_couriers = st.sidebar.multiselect("Select Courier(s)", all_couriers, default=all_couriers)

    # Apply filters
    if selected_dates and selected_couriers:
        filtered_df = pivot_df.loc[selected_dates, selected_couriers + ["Grand Total"]]
    elif selected_dates:
        filtered_df = pivot_df.loc[selected_dates]
    elif selected_couriers:
        filtered_df = pivot_df[selected_couriers + ["Grand Total"]]
    else:
        filtered_df = pivot_df

    # -------------------------------
    # Data Preview & Display
    # -------------------------------
    with st.expander("📋 Show Combined Data Preview"):
        st.dataframe(combined_df, use_container_width=True)

    st.subheader("📊 Delivered Date-wise Courier Summary")
    st.dataframe(filtered_df, use_container_width=True)

    # -------------------------------
    # File Export Section
    # -------------------------------
    csv_data = filtered_df.to_csv().encode("utf-8")

    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
        filtered_df.to_excel(writer, index=True, sheet_name="Summary")
    excel_data = excel_buffer.getvalue()

    st.download_button(
        label="⬇ Download as CSV",
        data=csv_data,
        file_name="courier_summary.csv",
        mime="text/csv"
    )

    st.download_button(
        label="⬇ Download as Excel (XLSX)",
        data=excel_data,
        file_name="courier_summary.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("Please upload one or more CSV or Excel files to begin analysis.")
