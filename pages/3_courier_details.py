import streamlit as st
import pandas as pd
from io import BytesIO
from fpdf import FPDF

st.set_page_config(page_title="Courier Partner Delivery & Return Analysis", layout="wide")
st.title("📦 Courier Partner Delivery & Return Analysis")

# --- Grand Total util ---
def add_grand_totals(df):
    df["Grand Total"] = df.sum(axis=1, numeric_only=True)
    total_row = df.sum(axis=0, numeric_only=True)
    total_row.name = "Grand Total"
    df = pd.concat([df, pd.DataFrame([total_row])], axis=0)
    return df

# --- PDF wide printable utility ---
def pivot_to_pdf(pivot_df, title="Courier Partner Summary by Delivered Date"):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", style='B', size=16)
    pdf.cell(0, 12, title, ln=1, align='C')
    pdf.set_font("Arial", size=9)
    col_names = [str(x) for x in [""] + list(pivot_df.columns)]
    data = [col_names]
    for idx, row in pivot_df.iterrows():
        data.append([str(idx)] + [str(x) for x in row])
    max_cols = len(data[0])
    col_width = max(26, 210 // max_cols)
    for row in data:
        for value in row:
            pdf.cell(col_width, 8, str(value), border=1, align="C")
        pdf.ln()
    return pdf.output(dest="S").encode("latin-1")

# File Upload
st.sidebar.header("Upload multiple files")
uploaded_files = st.sidebar.file_uploader(
    "Select CSV/XLSX/XLS files", type=["csv", "xlsx", "xls"], accept_multiple_files=True
)
HEADER_ROW_INDEX = 7

if uploaded_files:
    dataframes = []
    for f in uploaded_files:
        df = pd.read_csv(f, skiprows=HEADER_ROW_INDEX) if f.name.endswith(".csv") else pd.read_excel(f, skiprows=HEADER_ROW_INDEX)
        dataframes.append(df)
    df_all = pd.concat(dataframes, ignore_index=True)

    # Clean up columns
    if 'Courier Partner' in df_all.columns:
        df_all['Courier Partner'] = df_all['Courier Partner'].replace({'PocketShip': 'Valmo', 'Valmo': 'Valmo'})
    if 'Delivered Date' in df_all.columns:
        df_all['Delivered Date'] = pd.to_datetime(df_all['Delivered Date'], errors='coerce').dt.date

    # FILTERS
    st.sidebar.header("Filters")
    # Delivered Date
    all_dates = sorted([str(x) for x in df_all['Delivered Date'].dropna().unique()])
    search_date = st.sidebar.text_input("Search Date (YYYY-MM-DD)", key="date_search")
    filtered_dates = [d for d in all_dates if search_date in d] if search_date else all_dates
    select_all_dates = st.sidebar.checkbox("Select all dates", value=True, key="selectalldates")
    sel_dates = filtered_dates if select_all_dates else st.sidebar.multiselect("Select Delivered Date(s)", filtered_dates, default=filtered_dates)
    # Courier Partner
    all_cour = sorted([str(x) for x in df_all['Courier Partner'].dropna().unique()])
    search_cour = st.sidebar.text_input("Search Courier", key="cour_search")
    filtered_cour = [c for c in all_cour if search_cour.lower() in c.lower()] if search_cour else all_cour
    select_all_cour = st.sidebar.checkbox("Select all couriers", value=True, key="selectallcour")
    sel_cour = filtered_cour if select_all_cour else st.sidebar.multiselect("Select Courier(s)", filtered_cour, default=filtered_cour)
    # SKU
    all_sku = [str(x) for x in df_all['SKU'].dropna().unique()] if 'SKU' in df_all.columns else []
    search_sku = st.sidebar.text_input("Search SKU", key="sku_search")
    filtered_sku = [x for x in all_sku if search_sku.lower() in x.lower()] if search_sku else all_sku
    select_all_sku = st.sidebar.checkbox("Select all SKUs", value=True, key="selectallsku")
    sel_sku = filtered_sku if select_all_sku else st.sidebar.multiselect("Select SKU(s)", filtered_sku, default=filtered_sku)

    # Apply filters
    df_filt = df_all.copy()
    if sel_dates:
        df_filt = df_filt[df_filt['Delivered Date'].astype(str).isin(sel_dates)]
    if sel_cour:
        df_filt = df_filt[df_filt['Courier Partner'].isin(sel_cour)]
    if sel_sku:
        df_filt = df_filt[df_filt['SKU'].isin(sel_sku)]

    # --- MAIN TABLE (Wide, large size) ---
    if {'Delivered Date', 'Courier Partner'}.issubset(df_filt.columns):
        sumdf = df_filt.groupby(['Delivered Date', 'Courier Partner']).size().reset_index(name="Total Packets")
        pivotdf = sumdf.pivot_table(index="Delivered Date", columns="Courier Partner", values="Total Packets", aggfunc="sum", fill_value=0)
        pivotdf = add_grand_totals(pivotdf)
        st.subheader("Courier Partner Summary by Delivered Date")
        # Wide responsive, large table exactly like your old script
        st.dataframe(pivotdf, use_container_width=True)
        # PDF Download
        pdf_bytes = pivot_to_pdf(pivotdf, title="Courier Partner Summary by Delivered Date")
        st.download_button("Download Courier Partner Table (PDF, Portrait)", pdf_bytes, file_name="courier_partner_summary.pdf", mime="application/pdf")

    # --- SKU-wise Reason Table (Wide, large size) ---
    if {'SKU', 'Detailed Return Reason'}.issubset(df_filt.columns):
        st.subheader("SKU-wise Return Reason Summary")
        reason_summary = df_filt.groupby(['SKU','Detailed Return Reason']).size().reset_index(name='Return Count')
        reason_pivot = reason_summary.pivot_table(index='SKU', columns='Detailed Return Reason', values='Return Count', fill_value=0)
        reason_pivot = add_grand_totals(reason_pivot)
        st.dataframe(reason_pivot, use_container_width=True)

    # --- Style Group Analysis Table (Wide, large size) ---
    st.subheader("Style Group Reason Summary (by keyword)")
    style_group_key = st.text_input("Enter Style Group keyword (e.g. 'POCKET TIE')")
    if style_group_key:
        df_filt['Style Group'] = df_filt['SKU'].apply(
            lambda x: style_group_key if style_group_key.lower() in str(x).lower() else None
        )
        group_df = df_filt[df_filt['Style Group'].notna()]
        if not group_df.empty:
            g_summary = group_df.groupby(['Style Group','Detailed Return Reason']).size().reset_index(name='Return Count')
            group_pivot = g_summary.pivot_table(index='Style Group', columns='Detailed Return Reason', values='Return Count', fill_value=0)
            group_pivot = add_grand_totals(group_pivot)
            st.dataframe(group_pivot, use_container_width=True)
        else:
            st.info("No SKUs found matching that style group.")

    # --- DOWNLOAD OPTIONS ---
    st.subheader("Download Options")
    csv_master = df_all.to_csv(index=False).encode("utf-8")
    st.download_button("Download All Data (CSV)", csv_master, "all_data.csv", "text/csv")
    csv_filtered = df_filt.to_csv(index=False).encode("utf-8")
    st.download_button("Download Filtered Data (CSV)", csv_filtered, "filtered_data.csv", "text/csv")
    excel_buf = BytesIO()
    with pd.ExcelWriter(excel_buf, engine='xlsxwriter') as writer:
        df_all.to_excel(writer, index=False, sheet_name="All Data")
        df_filt.to_excel(writer, index=False, sheet_name="Filtered Data")
        if 'pivotdf' in locals():
            pivotdf.to_excel(writer, sheet_name="Courier Summary")
        if 'reason_pivot' in locals():
            reason_pivot.to_excel(writer, sheet_name="Return Reason Summary")
        if 'group_pivot' in locals():
            group_pivot.to_excel(writer, sheet_name="Style Group Summary")
    st.download_button("Download Excel (All Summaries)", excel_buf.getvalue(), "courier_return_full.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
else:
    st.info("Please upload at least one CSV or Excel file.")
