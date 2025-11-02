import streamlit as st
import pandas as pd
from io import BytesIO
from fpdf import FPDF
import tempfile

st.set_page_config(page_title="Courier Partner Delivery & Return Analysis", layout="wide")
st.title("📦 Courier Partner Delivery & Return Analysis")

def add_grand_totals(df):
    df["Grand Total"] = df.sum(axis=1, numeric_only=True)
    total_row = df.sum(axis=0, numeric_only=True)
    total_row.name = "Grand Total"
    df = pd.concat([df, pd.DataFrame([total_row])], axis=0)
    return df

def pivot_to_pdf(pivot_df, title="Report"):
    max_cols = len(pivot_df.columns) + 1
    orientation = 'L' if max_cols > 7 else 'P'
    pdf_width = 297 if orientation == 'L' else 210
    pdf = FPDF(orientation=orientation, unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, title, ln=1, align='C')
    pdf.set_font("Arial", '', 8)

    margin_lr = 10
    usable_width = pdf_width - 2 * margin_lr
    col_width = max(15, usable_width // max_cols)

    col_names = [""] + list(pivot_df.columns)
    data = [col_names]
    for idx, row in pivot_df.iterrows():
        data.append([str(idx)] + [str(x) for x in row])

    for row in data:
        for val in row:
            pdf.cell(col_width, 7, str(val)[:20], border=1, align='C')
        pdf.ln()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf.output(tmp.name)
        tmp.seek(0)
        pdf_bytes = tmp.read()
    return pdf_bytes

def add_totals_column(df):
    df['Total'] = df.sum(axis=1)
    total_row = df.sum(axis=0)
    total_row.name = 'Grand Total'
    return pd.concat([df, pd.DataFrame([total_row])])

# Collapsible file uploader section
with st.expander("Upload CSV/XLSX Files", expanded=True):
    uploaded_files = st.file_uploader("Select CSV/XLSX Files", accept_multiple_files=True)

if uploaded_files:
    dfs = []
    for f in uploaded_files:
        if f.name.endswith('.csv'):
            df = pd.read_csv(f, skiprows=7)
        else:
            df = pd.read_excel(f, skiprows=7)
        dfs.append(df)
    df_all = pd.concat(dfs, ignore_index=True)

    if 'Courier Partner' in df_all.columns:
        df_all['Courier Partner'] = df_all['Courier Partner'].apply(
            lambda x: 'Valmo' if pd.notna(x) and ('PocketShip' in str(x) or 'Valmo' in str(x)) else x
        )

    df_all['Return Created Date'] = pd.to_datetime(df_all['Return Created Date'], errors='coerce').dt.date

    # Filters
    st.sidebar.header("Filters")
    all_dates = sorted([str(x) for x in df_all['Return Created Date'].dropna().unique()])
    selected_dates = st.sidebar.multiselect("Select Return Created Date(s)", all_dates, default=all_dates)

    all_couriers = sorted([str(x) for x in df_all['Courier Partner'].dropna().unique()])
    selected_couriers = st.sidebar.multiselect("Select Courier Partner(s)", all_couriers, default=all_couriers)

    all_types = sorted([str(x) for x in df_all['Type of Return'].dropna().unique()])
    selected_types = st.sidebar.multiselect("Select Type of Return(s)", all_types, default=all_types)

    all_skus = sorted([str(x) for x in df_all['SKU'].dropna().unique()]) if 'SKU' in df_all.columns else []
    selected_skus = st.sidebar.multiselect("Select SKU(s)", all_skus, default=all_skus)

    df_filtered = df_all[
        (df_all['Return Created Date'].astype(str).isin(selected_dates)) &
        (df_all['Courier Partner'].isin(selected_couriers)) &
        (df_all['Type of Return'].isin(selected_types)) &
        (df_all['SKU'].isin(selected_skus))
    ]

    # Separate tables for Courier Return (RTO) and Customer Return
    if {'Return Created Date', 'Type of Return', 'Courier Partner', 'Qty'}.issubset(df_filtered.columns):
        df_filtered['Qty'] = pd.to_numeric(df_filtered['Qty'], errors='coerce').fillna(0)

        cour_return = df_filtered[df_filtered['Type of Return'] == 'Courier Return (RTO)']
        cust_return = df_filtered[df_filtered['Type of Return'] == 'Customer Return']

        cour_pivot = cour_return.groupby(['Return Created Date', 'Courier Partner']).agg({'Qty': 'sum'}).unstack(fill_value=0)
        cour_pivot.columns = cour_pivot.columns.droplevel()
        cour_pivot = add_totals_column(cour_pivot)

        cust_pivot = cust_return.groupby(['Return Created Date', 'Courier Partner']).agg({'Qty': 'sum'}).unstack(fill_value=0)
        cust_pivot.columns = cust_pivot.columns.droplevel()
        cust_pivot = add_totals_column(cust_pivot)

        st.subheader("Courier Return (RTO) Summary")
        st.dataframe(cour_pivot, use_container_width=True)
        pdf_courier = pivot_to_pdf(cour_pivot, "Courier Return (RTO) Summary")
        st.download_button("Download Courier Return Summary PDF", pdf_courier, "courier_return_summary.pdf", "application/pdf")

        st.subheader("Customer Return Summary")
        st.dataframe(cust_pivot, use_container_width=True)
        pdf_customer = pivot_to_pdf(cust_pivot, "Customer Return Summary")
        st.download_button("Download Customer Return Summary PDF", pdf_customer, "customer_return_summary.pdf", "application/pdf")

    # SKU-wise Return Reason Summary
    if {'SKU', 'Detailed Return Reason'}.issubset(df_filtered.columns):
        st.subheader("SKU-wise Return Reason Summary")
        reason_summary = df_filtered.groupby(['SKU', 'Detailed Return Reason']).size().reset_index(name='Return Count')
        reason_pivot = reason_summary.pivot_table(index='SKU', columns='Detailed Return Reason', values='Return Count', fill_value=0)
        reason_pivot = add_grand_totals(reason_pivot)
        st.dataframe(reason_pivot, use_container_width=True)

    # Style Group Reason Summary with keyword search
    st.subheader("Style Group Reason Summary (by keyword)")
    style_group_key = st.text_input("Enter Style Group keyword (e.g. 'POCKET TIE')")
    if style_group_key:
        df_filtered['Style Group'] = df_filtered['SKU'].apply(lambda x: style_group_key if style_group_key.lower() in str(x).lower() else None)
        group_df = df_filtered[df_filtered['Style Group'].notna()]
        if not group_df.empty:
            group_summary = group_df.groupby(['Style Group', 'Detailed Return Reason']).size().reset_index(name='Return Count')
            group_pivot = group_summary.pivot_table(index='Style Group', columns='Detailed Return Reason', values='Return Count', fill_value=0)
            group_pivot = add_grand_totals(group_pivot)
            st.dataframe(group_pivot, use_container_width=True)
        else:
            st.info("No SKUs found matching this style keyword.")

    # Download Options
    st.subheader("Download Options")
    csv_all = df_all.to_csv(index=False).encode('utf-8')
    st.download_button("Download All Data (CSV)", csv_all, file_name="all_data.csv", mime="text/csv")

    csv_filtered = df_filtered.to_csv(index=False).encode('utf-8')
    st.download_button("Download Filtered Data (CSV)", csv_filtered, file_name="filtered_data.csv", mime="text/csv")

    excel_buf = BytesIO()
    with pd.ExcelWriter(excel_buf, engine='xlsxwriter') as writer:
        df_all.to_excel(writer, index=False, sheet_name="All Data")
        df_filtered.to_excel(writer, index=False, sheet_name="Filtered Data")
        if 'cour_pivot' in locals():
            cour_pivot.to_excel(writer, sheet_name="Courier Return Summary")
        if 'cust_pivot' in locals():
            cust_pivot.to_excel(writer, sheet_name="Customer Return Summary")
        if 'reason_pivot' in locals():
            reason_pivot.to_excel(writer, sheet_name="Return Reason Summary")
        if 'group_pivot' in locals():
            group_pivot.to_excel(writer, sheet_name="Style Group Summary")
    st.download_button("Download Excel (All Summaries)", excel_buf.getvalue(), file_name="courier_return_full.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

else:
    st.info("Please upload CSV or Excel files to begin analysis.")
