import streamlit as st
import pandas as pd
from io import BytesIO
from fpdf import FPDF
import tempfile

# Streamlit Config
st.set_page_config(page_title="Courier Partner Delivery & Return Analysis", layout="wide")
st.title("📦 Courier Partner Delivery & Return Analysis")

def add_grand_totals(df: pd.DataFrame) -> pd.DataFrame:
    """Add 'Grand Total' column and row for generic pivot tables."""
    df["Grand Total"] = df.sum(axis=1, numeric_only=True)
    total_row = df.sum(axis=0, numeric_only=True)
    total_row.name = "Grand Total"
    df = pd.concat([df, pd.DataFrame([total_row])], axis=0)
    return df

def add_totals_column(df: pd.DataFrame) -> pd.DataFrame:
    """Add 'Total' column and a 'Grand Total' row for date x courier table."""
    df["Total"] = df.sum(axis=1, numeric_only=True)
    total_row = df.sum(axis=0, numeric_only=True)
    total_row.name = "Grand Total"
    return pd.concat([df, pd.DataFrame([total_row])], axis=0)

def pivot_to_pdf(pivot_df: pd.DataFrame, title: str = "Summary") -> bytes:
    """Generic summary tables के लिए simple PDF."""
    max_cols = len(pivot_df.columns) + 1
    orientation = "L" if max_cols > 7 else "P"
    pdf_width = 297 if orientation == "L" else 210

    pdf = FPDF(orientation=orientation, unit="mm", format="A4")
    pdf.add_page()

    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, title, ln=1, align="C")
    pdf.ln(3)

    pdf.set_font("Arial", "", 8)
    margin_lr = 10
    usable_width = pdf_width - 2 * margin_lr
    col_width = max(15, usable_width // max_cols)

    col_names = [""] + list(pivot_df.columns)
    data = [col_names]

    for idx, row in pivot_df.iterrows():
        data.append([str(idx)] + [str(x) for x in row])

    for row in data:
        for val in row:
            pdf.cell(col_width, 7, str(val)[:20], border=1, align="C")
        pdf.ln()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf.output(tmp.name)
        tmp.seek(0)
        pdf_bytes = tmp.read()
    return pdf_bytes

def pivot_to_pdf_stylegroup(pivot_df: pd.DataFrame, title: str = "Style Group Reason Summary", grand_total: int = 0) -> bytes:
    """Style Group reasons के लिए special PDF."""
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()

    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, title, ln=1, align="C")
    pdf.ln(3)

    pdf_width = 297
    margin = 8
    usable_width = pdf_width - 2 * margin

    reason_col_width = 120
    other_col_width = (usable_width - reason_col_width) / max(1, len(pivot_df.columns))

    # Header
    pdf.set_font("Arial", "B", 9)
    pdf.set_fill_color(220, 220, 220)

    pdf.cell(reason_col_width, 8, "Detailed Return Reason", border=1, align="C", fill=True)
    for col in pivot_df.columns:
        pdf.cell(other_col_width, 8, str(col)[:20], border=1, align="C", fill=True)
    pdf.ln()

    # Data rows
    pdf.set_font("Arial", "", 8)
    max_chars_per_line = 50
    line_height = 5

    for idx, row in pivot_df.iterrows():
        reason_text = str(idx)

        lines = []
        for i in range(0, len(reason_text), max_chars_per_line):
            lines.append(reason_text[i:i + max_chars_per_line])

        cell_height = line_height * max(1, len(lines))

        x_start = pdf.get_x()
        y_start = pdf.get_y()

        pdf.multi_cell(reason_col_width, line_height, "\n".join(lines), border=1, align="L")

        pdf.set_xy(x_start + reason_col_width, y_start)

        for val in row:
            if isinstance(val, (int, float)):
                txt = str(int(val))
            else:
                txt = str(val)
            pdf.cell(other_col_width, cell_height, txt, border=1, align="C")

        pdf.ln(cell_height)

    # TOTAL row
    if grand_total > 0:
        pdf.set_font("Arial", "B", 9)
        pdf.set_fill_color(200, 200, 200)

        pdf.cell(reason_col_width, 10, "TOTAL", border=1, align="C", fill=True)
        pdf.cell(other_col_width, 10, str(int(grand_total)), border=1, align="C", fill=True)
        pdf.ln()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf.output(tmp.name)
        tmp.seek(0)
        pdf_bytes = tmp.read()
    return pdf_bytes

# ----------------- Upload section -----------------
with st.expander("📁 Upload CSV/XLSX Files", expanded=True):
    uploaded_files = st.file_uploader(
        "Upload CSV/XLSX Files",
        accept_multiple_files=True,
        type=["csv", "xlsx", "xls"]
    )

HEADER_ROW_INDEX = 7

if uploaded_files:
    dfs = []
    for f in uploaded_files:
        if f.name.endswith(".csv"):
            df = pd.read_csv(f, skiprows=HEADER_ROW_INDEX)
        else:
            df = pd.read_excel(f, skiprows=HEADER_ROW_INDEX)
        dfs.append(df)

    df_all = pd.concat(dfs, ignore_index=True)

    # Normalise Courier Partner names
    if "Courier Partner" in df_all.columns:
        df_all["Courier Partner"] = df_all["Courier Partner"].apply(
            lambda x: "Valmo"
            if pd.notna(x) and ("PocketShip" in str(x) or "Valmo" in str(x))
            else x
        )

    # Date to proper date
    if "Delivered Date" in df_all.columns:
        df_all["Delivered Date"] = pd.to_datetime(
            df_all["Delivered Date"],
            errors="coerce"
        ).dt.date

    # ----------------- Sidebar Filters -----------------
    st.sidebar.header("🔍 Filters")

    # Date filter
    if "Delivered Date" in df_all.columns:
        all_dates = sorted(str(x) for x in df_all["Delivered Date"].dropna().unique())
        search_date = st.sidebar.text_input("Search Date (YYYY-MM-DD)")
        filtered_dates = [d for d in all_dates if search_date in d] if search_date else all_dates
        select_all_dates = st.sidebar.checkbox("Select all dates", True)
        selected_dates = filtered_dates if select_all_dates else st.sidebar.multiselect(
            "Select Delivered Date(s)", filtered_dates, default=filtered_dates
        )
    else:
        selected_dates = []

    # Courier Partner filter
    if "Courier Partner" in df_all.columns:
        all_couriers = sorted(str(x) for x in df_all["Courier Partner"].dropna().unique())
        search_cour = st.sidebar.text_input("Search Courier")
        filtered_couriers = [c for c in all_couriers if search_cour.lower() in c.lower()] if search_cour else all_couriers
        select_all_couriers = st.sidebar.checkbox("Select all couriers", True)
        selected_couriers = filtered_couriers if select_all_couriers else st.sidebar.multiselect(
            "Select Courier Partners", filtered_couriers, default=filtered_couriers
        )
    else:
        selected_couriers = []

    # SKU filter
    if "SKU" in df_all.columns:
        all_skus = sorted(str(x) for x in df_all["SKU"].dropna().unique())
        search_sku = st.sidebar.text_input("Search SKU")
        filtered_skus = [s for s in all_skus if search_sku.lower() in s.lower()] if search_sku else all_skus
        select_all_skus = st.sidebar.checkbox("Select all SKUs", True)
        selected_skus = filtered_skus if select_all_skus else st.sidebar.multiselect(
            "Select SKUs", filtered_skus, default=filtered_skus
        )
    else:
        selected_skus = []

    # ----------------- Apply Filters -----------------
    df_filtered = df_all.copy()

    if "Delivered Date" in df_filtered.columns and selected_dates:
        df_filtered = df_filtered[df_filtered["Delivered Date"].astype(str).isin(selected_dates)]

    if "Courier Partner" in df_filtered.columns and selected_couriers:
        df_filtered = df_filtered[df_filtered["Courier Partner"].isin(selected_couriers)]

    if "SKU" in df_filtered.columns and selected_skus:
        df_filtered = df_filtered[df_filtered["SKU"].isin(selected_skus)]

    # ----------------- Data Preview (Hide/Show) -----------------
    with st.expander("👁️ **Data Preview** (All Records - No Limit)", expanded=False):
        st.dataframe(df_all, use_container_width=True, height=400)
    
    with st.expander("👁️ **Filtered Data Preview** (All Records - No Limit)", expanded=False):
        st.dataframe(df_filtered, use_container_width=True, height=400)

    # ----------------- KPI Boxes (Same colors as provided script) -----------------
    courier_rto_count = 0
    customer_return_count = 0

    if "Detailed Return Reason" in df_filtered.columns:
        courier_rto_count = len(df_filtered[df_filtered["Detailed Return Reason"].str.contains("RTO|Courier", na=False)])
        customer_return_count = len(df_filtered[df_filtered["Detailed Return Reason"].str.contains("Customer", na=False)])

    total_returns_count = courier_rto_count + customer_return_count

    col1, col2, col3 = st.columns(3)

    col1.markdown(
        f"""
        <div style="background-color:#d4edda; padding:15px; border-radius:10px; text-align:center; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <h3 style="color:#155724; margin:0; font-size:16px;">Courier Return (RTO)</h3>
            <h1 style="color:#155724; margin:5px 0 0 0; font-size:32px; font-weight:bold;">{courier_rto_count}</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col2.markdown(
        f"""
        <div style="background-color:#f8d7da; padding:15px; border-radius:10px; text-align:center; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <h3 style="color:#721c24; margin:0; font-size:16px;">Customer Return</h3>
            <h1 style="color:#721c24; margin:5px 0 0 0; font-size:32px; font-weight:bold;">{customer_return_count}</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col3.markdown(
        f"""
        <div style="background-color:#cce5ff; padding:15px; border-radius:10px; text-align:center; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <h3 style="color:#004085; margin:0; font-size:16px;">Total Returns</h3>
            <h1 style="color:#004085; margin:5px 0 0 0; font-size:32px; font-weight:bold;">{total_returns_count}</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # ----------------- Courier Table (AWB Unique Count) -----------------
    if {'Delivered Date', 'Courier Partner', 'AWB Number'}.issubset(df_filtered.columns):
        # AWB Number से unique count (duplicate ignore)
        summary = df_filtered.groupby(['Delivered Date', 'Courier Partner'])['AWB Number'].nunique().reset_index(name='Total Packets')
        pivot_df = summary.pivot_table(index="Delivered Date", columns="Courier Partner", values="Total Packets", fill_value=0)
        pivot_df = add_grand_totals(pivot_df)

        st.subheader("📦 **Courier Partner Summary by Delivered Date**")
        st.dataframe(pivot_df, use_container_width=True)

        pdf_bytes = pivot_to_pdf(pivot_df, title="Courier Partner Summary by Delivered Date")
        st.download_button("📥 Download Courier Summary (PDF)", pdf_bytes, "courier_partner_summary.pdf", "application/pdf")

    # ----------------- SKU-wise Return Reason Summary -----------------
    if {"SKU", "Detailed Return Reason"}.issubset(df_filtered.columns):
        st.subheader("SKU-wise Return Reason Summary")
        reason_summary = df_filtered.groupby(["SKU", "Detailed Return Reason"]).size().reset_index(name="Return Count")
        reason_pivot = reason_summary.pivot_table(index="SKU", columns="Detailed Return Reason", values="Return Count", fill_value=0)
        reason_pivot = add_grand_totals(reason_pivot)
        st.dataframe(reason_pivot, use_container_width=True)

    # ----------------- Style Group Reason Summary (vertical) -----------------
    st.subheader("**Style Group Reason Summary by keyword**")
    stylegroup_key = st.text_input("Enter Style Group keyword (e.g. 'POCKET TIE')")

    groupsummary_with_total = None

    if stylegroup_key and "SKU" in df_filtered.columns:
        temp_df = df_filtered.copy()
        temp_df["Style Group"] = temp_df["SKU"].apply(
            lambda x: stylegroup_key
            if stylegroup_key.lower() in str(x).lower()
            else None
        )

        group_df = temp_df[temp_df["Style Group"].notna()]

        if not group_df.empty and {"Detailed Return Reason"}.issubset(group_df.columns):
            group_summary = group_df.groupby(["Style Group", "Detailed Return Reason"]).size().reset_index(name="Return Count")
            total_count = group_summary["Return Count"].sum()

            grand_total_row = pd.DataFrame({
                "Style Group": ["Grand Total"],
                "Detailed Return Reason": [""],
                "Return Count": [int(total_count)]
            })

            groupsummary_with_total = pd.concat([
                group_summary.sort_values(by="Return Count", ascending=False),
                grand_total_row
            ], ignore_index=True)

            # Vertical display (transpose)
            groupsummary_pivot = group_summary.pivot_table(
                index="Detailed Return Reason",
                columns="Style Group",
                values="Return Count",
                fill_value=0
            )

            st.dataframe(groupsummary_pivot.T, use_container_width=True)

            # PDF के लिए same stylegroup PDF function
            pdf_stylegroup = pivot_to_pdf_stylegroup(
                groupsummary_pivot,
                title=f"Style Group Reason Summary - {stylegroup_key}",
                grand_total=int(total_count)
            )

            st.download_button(
                "📥 Download Style Group Summary PDF",
                pdf_stylegroup,
                f"style_group_summary_{stylegroup_key}.pdf",
                "application/pdf"
            )
        else:
            st.info("No SKUs found matching this style keyword.")

    # ----------------- Download Options -----------------
    st.subheader("💾 **Download Options**")

    csv_all = df_all.to_csv(index=False).encode("utf-8")
    st.download_button("📄 Download All Data CSV", csv_all, file_name="all_data.csv", mime="text/csv")

    csv_filtered = df_filtered.to_csv(index=False).encode("utf-8")
    st.download_button("📄 Download Filtered Data CSV", csv_filtered, file_name="filtered_data.csv", mime="text/csv")

    excel_buf = BytesIO()
    with pd.ExcelWriter(excel_buf, engine="xlsxwriter") as writer:
        df_all.to_excel(writer, index=False, sheet_name="All Data")
        df_filtered.to_excel(writer, index=False, sheet_name="Filtered Data")
        
        if 'pivot_df' in locals():
            pivot_df.to_excel(writer, sheet_name="Courier Summary")
        if 'reason_pivot' in locals():
            reason_pivot.to_excel(writer, sheet_name="Return Reason Summary")
        if groupsummary_with_total is not None:
            groupsummary_with_total.to_excel(writer, sheet_name="Style Group Summary", index=False)

    st.download_button(
        "📊 Download Excel (All Summaries)",
        excel_buf.getvalue(),
        file_name="courier_return_full.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("👆 **Please upload CSV or Excel files using the expander above to begin analysis.**")
