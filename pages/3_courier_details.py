import streamlit as st
import pandas as pd
from io import BytesIO

# Wide layout for bigger screen view
st.set_page_config(page_title="Courier Partner Delivery Analysis", layout="wide")

st.title("📦 Courier Partner Delivery Analysis")

# File uploader (CSV, XLSX, XLS) - in sidebar
st.sidebar.header("📂 Upload File")
uploaded_file = st.sidebar.file_uploader("Choose a file", type=["csv", "xlsx", "xls"])

if uploaded_file:
    # Auto detect file type
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file, skiprows=7)  # headers start from row 8
    else:
        df = pd.read_excel(uploaded_file, skiprows=7)

    # Merge PocketShip + Valmo → Valmo
    df['Courier Partner'] = df['Courier Partner'].replace({
        'PocketShip': 'Valmo',
        'Valmo': 'Valmo'
    })

    # Ensure Delivered Date is in date format
    df['Delivered Date'] = pd.to_datetime(df['Delivered Date'], errors='coerce').dt.date

    # Group by Delivered Date & Courier
    summary = df.groupby(['Delivered Date', 'Courier Partner']).size().reset_index(name="Total Packets")

    # Pivot table with Grand Total
    pivot_df = summary.pivot_table(
        index="Delivered Date",
        columns="Courier Partner",
        values="Total Packets",
        aggfunc="sum",
        fill_value=0
    )

    # Add Grand Total column
    pivot_df["Grand Total"] = pivot_df.sum(axis=1)

    # Sidebar Filters
    st.sidebar.header("🔍 Filters")

    # Default state → all selected
    all_dates = pivot_df.index.unique().tolist()
    all_couriers = [c for c in pivot_df.columns if c != "Grand Total"]

    # Reset button
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

    # Show Data Preview (expand/collapse)
    with st.expander("📋 Show Raw Data Preview"):
        st.dataframe(df, use_container_width=True)

    # Final Summary Table
    st.subheader("📊 Delivered Date-wise Courier Summary")
    st.dataframe(filtered_df, use_container_width=True)

    # ---- File Export ----
    # CSV Export
    csv_data = filtered_df.to_csv().encode("utf-8")

    # Excel Export (BytesIO fix)
    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
        filtered_df.to_excel(writer, index=True, sheet_name="Summary")
    excel_data = excel_buffer.getvalue()

    # Download Buttons
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
