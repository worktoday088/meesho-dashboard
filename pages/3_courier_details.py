import streamlit as st
import pandas as pd
from io import BytesIO
from fpdf import FPDF
import tempfile

# Streamlit Page Config
st.set_page_config(page_title="Courier Partner Delivery & Return Analysis", layout="wide")
st.title("📦 Courier Partner Delivery & Return Analysis")

# Add Grand Totals helper
def add_grand_totals(df):
    df["Grand Total"] = df.sum(axis=1, numeric_only=True)
    total_row = df.sum(axis=0, numeric_only=True)
    total_row.name = "Grand Total"
    df = pd.concat([df, pd.DataFrame([total_row])], axis=0)
    return df

# PDF Generator with auto orientation and dynamic widths
def pivot_to_pdf(pivot_df, title="Courier Partner Summary by Delivered Date"):
    max_cols = len(pivot_df.columns) + 1  # plus index column
    if max_cols > 7:
        orientation = 'L'  # Landscape
        pdf_width = 297
    else:
        orientation = 'P'  # Portrait
        pdf_width = 210

    pdf = FPDF(orientation=orientation, unit='mm', format='A4')
    pdf.add_page()

    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 12, title, 0, 1, 'C')

    pdf.set_font("Arial", '', 9)
    col_names = [""] + list(pivot_df.columns)

    data = [col_names]
    for idx, row in pivot_df.iterrows():
        data.append([str(idx)] + [str(x) for x in row])

    col_width = max(20, pdf_width // max_cols)

    for row in data:
        for value in row:
            pdf.cell(col_width, 8, str(value), border=1, align='C')
        pdf.ln()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf.output(tmp.name)
        tmp.seek(0)
        pdf_bytes = tmp.read()

    return pdf_bytes

# File upload
st.sidebar.header("Upload CSV/XLSX/XLS files")
uploaded_files = st.sidebar.file_uploader(
    "Select files", type=["csv", "xlsx", "xls"], accept_multiple_files=True)

HEADER_ROW_INDEX = 7

if uploaded_files:
    dfs = []
    for file in uploaded_files:
        if file.name.endswith('.csv'):
            dfs.append(pd.read_csv(file, skiprows=HEADER_ROW_INDEX))
        else:
            dfs.append(pd.read_excel(file, skiprows=HEADER_ROW_INDEX))
    df_all = pd.concat(dfs, ignore_index=True)

    if 'Courier Partner' in df_all.columns:
        df_all['Courier Partner'] = df_all['Courier Partner'].replace({'PocketShip': 'Valmo', 'Valmo': 'Valmo'})

    if 'Delivered Date' in df_all.columns:
        df_all['Delivered Date'] = pd.to_datetime(df_all['Delivered Date'], errors='coerce').dt.date

    # Filters
    st.sidebar.header("Filters")
    all_dates = sorted([str(d) for d in df_all['Delivered Date'].dropna()])
    search_date = st.sidebar.text_input("Search Date (YYYY-MM-DD)")
    filtered_dates = [d for d in all_dates if search_date in d] if search_date else all_dates
    select_all_dates = st.sidebar.checkbox("Select all dates", True)
    sel_dates = filtered_dates if select_all_dates else st.sidebar.multiselect("Select Dates", filtered_dates, default=filtered_dates)

    all_couriers = sorted([str(c) for c in df_all['Courier Partner'].dropna()])
    search_courier = st.sidebar.text_input("Search Courier")
    filtered_couriers = [c for c in all_couriers if search_courier.lower() in c.lower()] if search_courier else all_couriers
    select_all_couriers = st.sidebar.checkbox("Select all couriers", True)
    sel_couriers = filtered_couriers if select_all_couriers else st.sidebar.multiselect("Select Couriers", filtered_couriers, default=filtered_couriers)

    all_skus = list(df_all['SKU'].dropna().unique()) if 'SKU' in df_all.columns else []
    search_sku = st.sidebar.text_input("Search SKU")
    filtered_skus = [sku for sku in all_skus if search_sku.lower() in sku.lower()] if search_sku else all_skus
    select_all_skus = st.sidebar.checkbox("Select all SKUs", True)
    sel_skus = filtered_skus if select_all_skus else st.sidebar.multiselect("Select SKUs", filtered_skus, default=filtered_skus)

    # Apply filters
    df_filtered = df_all.copy()
    if sel_dates:
        df_filtered = df_filtered[df_filtered['Delivered Date'].astype(str).isin(sel_dates)]
    if sel_couriers:
        df_filtered = df_filtered[df_filtered['Courier Partner'].isin(sel_couriers)]
    if sel_skus:
        df_filtered = df_filtered[df_filtered['SKU'].isin(sel_skus)]

    # Pivot summarization
    if {'Delivered Date', 'Courier Partner'}.issubset(df_filtered.columns):
        summary = df_filtered.groupby(['Delivered Date', 'Courier Partner']).size().reset_index(name='Total Packets')
        pivot_df = summary.pivot_table(index='Delivered Date', columns='Courier Partner', values='Total Packets', fill_value=0)
        pivot_df = add_grand_totals(pivot_df)

        st.subheader("Courier Partner Summary by Delivered Date")
        st.dataframe(pivot_df, use_container_width=True)

        pdf_bytes = pivot_to_pdf(pivot_df)
        st.download_button("Download Courier Partner Summary (PDF)", pdf_bytes, file_name="courier_partner_summary.pdf", mime="application/pdf")

    # SKU Wise Return Reason Table
    if {'SKU','Detailed Return Reason'}.issubset(df_filtered.columns):
        st.subheader("SKU-wise Return Reason Summary")
        reason_summary = df_filtered.groupby(['SKU','Detailed Return Reason']).size().reset_index(name='Return Count')
        reason_pivot = reason_summary.pivot_table(index='SKU', columns='Detailed Return Reason', values='Return Count', fill_value=0)
        reason_pivot = add_grand_totals(reason_pivot)
        st.dataframe(reason_pivot, use_container_width=True)

    # Style Group Reason Table
    st.subheader("Style Group Reason Summary (by keyword)")
    style_group_key = st.text_input("Enter Style Group keyword (e.g. 'POCKET TIE')")
    if style_group_key:
        df_filtered['Style Group'] = df_filtered['SKU'].apply(lambda x: style_group_key if style_group_key.lower() in str(x).lower() else None)
        style_group_df = df_filtered[df_filtered['Style Group'].notna()]
        if not style_group_df.empty:
            group_summary = style_group_df.groupby(['Style Group', 'Detailed Return Reason']).size().reset_index(name='Return Count')
            group_pivot = group_summary.pivot_table(index='Style Group', columns='Detailed Return Reason', values='Return Count', fill_value=0)
            group_pivot = add_grand_totals(group_pivot)
            st.dataframe(group_pivot, use_container_width=True)
        else:
            st.info("No matching SKUs found for the style group.")

    # Download full data buttons
    st.subheader("Download Options")
    csv_all = df_all.to_csv(index=False).encode('utf-8')
    st.download_button("Download All Data (CSV)", csv_all, file_name="all_data.csv", mime="text/csv")

    csv_filtered = df_filtered.to_csv(index=False).encode('utf-8')
    st.download_button("Download Filtered Data (CSV)", csv_filtered, file_name="filtered_data.csv", mime="text/csv")

    excel_buf = BytesIO()
    with pd.ExcelWriter(excel_buf, engine='xlsxwriter') as writer:
        df_all.to_excel(writer, index=False, sheet_name="All Data")
        df_filtered.to_excel(writer, index=False, sheet_name="Filtered Data")
        if 'pivot_df' in locals():
            pivot_df.to_excel(writer, sheet_name="Courier Summary")
        if 'reason_pivot' in locals():
            reason_pivot.to_excel(writer, sheet_name="Return Reason Summary")
        if 'group_pivot' in locals():
            group_pivot.to_excel(writer, sheet_name="Style Group Summary")
    st.download_button("Download Excel (All Summaries)", excel_buf.getvalue(),
                       file_name="courier_return_full.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

else:
    st.info("Please upload CSV or Excel files to begin analysis.")
