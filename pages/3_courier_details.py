import streamlit as st
import pandas as pd
from io import BytesIO
from fpdf import FPDF
import tempfile

# Streamlit Config
st.set_page_config(page_title="Courier Partner Delivery & Return Analysis", layout="wide")
st.title("📦 Courier Partner Delivery & Return Analysis")

# Add Grand Totals helper
def add_grand_totals(df):
    df["Grand Total"] = df.sum(axis=1, numeric_only=True)
    total_row = df.sum(axis=0, numeric_only=True)
    total_row.name = "Grand Total"
    df = pd.concat([df, pd.DataFrame([total_row])], axis=0)
    return df

# PDF Creator (fixed width and smaller text)
def pivot_to_pdf(pivot_df, title="Courier Partner Summary by Delivered Date"):
    max_cols = len(pivot_df.columns) + 1  # one for index col
    if max_cols > 7:
        orientation = 'L'
        pdf_width = 297
    else:
        orientation = 'P'
        pdf_width = 210

    pdf = FPDF(orientation=orientation, unit='mm', format='A4')
    pdf.add_page()

    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, title, ln=1, align='C')

    pdf.set_font("Arial", '', 8)  # Smaller font for better fitting
    margin_lr = 10
    usable_width = pdf_width - (2 * margin_lr)
    col_width = max(15, usable_width // max_cols)  # Smaller width to fit all cols

    # Prepare table data
    col_names = [""] + list(pivot_df.columns)
    data = [col_names]
    for idx, row in pivot_df.iterrows():
        data.append([str(idx)] + [str(x) for x in row])

    # Draw table
    for row in data:
        for value in row:
            text = str(value)[:20]
            pdf.cell(col_width, 7, text, border=1, align='C')
        pdf.ln()

    # Write to temp PDF file for Streamlit compatibility
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf.output(tmp.name)
        tmp.seek(0)
        pdf_bytes = tmp.read()

    return pdf_bytes

st.sidebar.header("Upload multiple files")
uploaded_files = st.sidebar.file_uploader(
    "Select CSV/XLSX/XLS files", type=["csv", "xlsx", "xls"], accept_multiple_files=True
)

HEADER_ROW_INDEX = 7

if uploaded_files:
    dfs = []
    for f in uploaded_files:
        df = pd.read_csv(f, skiprows=HEADER_ROW_INDEX) if f.name.endswith(".csv") else pd.read_excel(f, skiprows=HEADER_ROW_INDEX)
        dfs.append(df)
    df_all = pd.concat(dfs, ignore_index=True)

    if 'Courier Partner' in df_all.columns:
        df_all['Courier Partner'] = df_all['Courier Partner'].replace({'PocketShip': 'Valmo', 'Valmo': 'Valmo'})
    if 'Delivered Date' in df_all.columns:
        df_all['Delivered Date'] = pd.to_datetime(df_all['Delivered Date'], errors='coerce').dt.date

    # --- FILTER PANEL ---
    st.sidebar.header("Filters")

    # Delivered Date
    all_dates = sorted([str(x) for x in df_all['Delivered Date'].dropna().unique()])
    search_date = st.sidebar.text_input("Search Date (YYYY-MM-DD)", key="date_search")
    filtered_dates = [d for d in all_dates if search_date in d] if search_date else all_dates
    select_all_dates = st.sidebar.checkbox("Select all dates", True, key="selectalldates")
    sel_dates = filtered_dates if select_all_dates else st.sidebar.multiselect("Select Delivered Date(s)", filtered_dates, default=filtered_dates)

    # Courier Partner
    all_cour = sorted([str(x) for x in df_all['Courier Partner'].dropna().unique()])
    search_cour = st.sidebar.text_input("Search Courier", key="cour_search")
    filtered_cour = [c for c in all_cour if search_cour.lower() in c.lower()] if search_cour else all_cour
    select_all_cour = st.sidebar.checkbox("Select all couriers", True, key="selectallcour")
    sel_cour = filtered_cour if select_all_cour else st.sidebar.multiselect("Select Courier(s)", filtered_cour, default=filtered_cour)

    # SKU
    all_sku = sorted([str(x) for x in df_all['SKU'].dropna().unique()]) if 'SKU' in df_all.columns else []
    search_sku = st.sidebar.text_input("Search SKU", key="sku_search")
    filtered_sku = [s for s in all_sku if search_sku.lower() in s.lower()] if search_sku else all_sku
    select_all_sku = st.sidebar.checkbox("Select all SKUs", True, key="selectallsku")
    sel_sku = filtered_sku if select_all_sku else st.sidebar.multiselect("Select SKU(s)", filtered_sku, default=filtered_sku)

    # Apply filters
    df_filtered = df_all.copy()
    if sel_dates:
        df_filtered = df_filtered[df_filtered['Delivered Date'].astype(str).isin(sel_dates)]
    if sel_cour:
        df_filtered = df_filtered[df_filtered['Courier Partner'].isin(sel_cour)]
    if sel_sku:
        df_filtered = df_filtered[df_filtered['SKU'].isin(sel_sku)]

    # --- COURIER TABLE ---
    if {'Delivered Date', 'Courier Partner'}.issubset(df_filtered.columns):
        summary = df_filtered.groupby(['Delivered Date', 'Courier Partner']).size().reset_index(name='Total Packets')
        pivot_df = summary.pivot_table(index="Delivered Date", columns="Courier Partner", values="Total Packets", fill_value=0)
        pivot_df = add_grand_totals(pivot_df)

        st.subheader("Courier Partner Summary by Delivered Date")
        st.dataframe(pivot_df, use_container_width=True)

        pdf_bytes = pivot_to_pdf(pivot_df)
        st.download_button("Download Courier Partner Summary (PDF)", pdf_bytes, file_name="courier_partner_summary.pdf", mime="application/pdf")

    # --- SKU-wise Table ---
    if {'SKU','Detailed Return Reason'}.issubset(df_filtered.columns):
        st.subheader("SKU-wise Return Reason Summary")
        reason_summary = df_filtered.groupby(['SKU','Detailed Return Reason']).size().reset_index(name='Return Count')
        reason_pivot = reason_summary.pivot_table(index='SKU', columns='Detailed Return Reason', values='Return Count', fill_value=0)
        reason_pivot = add_grand_totals(reason_pivot)
        st.dataframe(reason_pivot, use_container_width=True)

    # --- STYLE GROUP Table ---
    st.subheader("Style Group Reason Summary (by keyword)")
    style_group_key = st.text_input("Enter Style Group keyword (e.g. 'POCKET TIE')")
    if style_group_key:
        df_filtered['Style Group'] = df_filtered['SKU'].apply(lambda x: style_group_key if style_group_key.lower() in str(x).lower() else None)
        group_df = df_filtered[df_filtered['Style Group'].notna()]
        if not group_df.empty:
            group_summary = group_df.groupby(['Style Group','Detailed Return Reason']).size().reset_index(name='Return Count')
            group_pivot = group_summary.pivot_table(index='Style Group', columns='Detailed Return Reason', values='Return Count', fill_value=0)
            group_pivot = add_grand_totals(group_pivot)
            st.dataframe(group_pivot, use_container_width=True)
        else:
            st.info("No SKUs found matching this style keyword.")

    # --- DOWNLOAD EXCEL & CSV ---
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
    st.download_button("Download Excel (All Summaries)", excel_buf.getvalue(), file_name="courier_return_full.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

else:
    st.info("Please upload CSV or Excel files to begin analysis.")
