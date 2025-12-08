
# retrun_full.py
import streamlit as st
import pandas as pd
from io import BytesIO
from fpdf import FPDF
import tempfile

# ================== Streamlit Config ==================
st.set_page_config(page_title="Courier Partner Delivery & Return Analysis", layout="wide")
st.title("📦 Courier Partner Delivery & Return Analysis — Final Merged")

# ---------------- Helper functions ----------------

def df_make_integers(df: pd.DataFrame, exclude_cols=None) -> pd.DataFrame:
    """Convert numeric-like columns to ints where reasonable (except excluded cols)."""
    if exclude_cols is None:
        exclude_cols = []
    df2 = df.copy()
    for col in df2.columns:
        if col in exclude_cols:
            continue
        try:
            if pd.api.types.is_numeric_dtype(df2[col]):
                df2[col] = df2[col].fillna(0).astype(int)
            else:
                # try to coerce safely for mostly-numeric columns
                coerced = pd.to_numeric(df2[col], errors='coerce')
                if coerced.notna().sum() > len(df2) * 0.6:
                    df2[col] = coerced.fillna(0).astype(int)
        except Exception:
            pass
    return df2

def add_grand_totals(df: pd.DataFrame, exclude_cols=None) -> pd.DataFrame:
    """Add 'Grand Total' column and append a 'Grand Total' row for pivot-style tables."""
    if exclude_cols is None:
        exclude_cols = []
    df = df.copy()
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    if numeric_cols:
        df['Grand Total'] = df[numeric_cols].sum(axis=1).astype(int)
    else:
        df['Grand Total'] = ""
    total_row = {}
    for col in df.columns:
        if col in numeric_cols or col == 'Grand Total':
            try:
                total_row[col] = int(df[col].sum())
            except Exception:
                total_row[col] = 0
        else:
            total_row[col] = ""
    total_index = "Grand Total"
    try:
        total_df = pd.DataFrame([total_row], columns=df.columns, index=[total_index])
        df_out = pd.concat([df, total_df])
    except Exception:
        df_out = df
    return df_make_integers(df_out, exclude_cols=exclude_cols)

def add_totals_column(df: pd.DataFrame, exclude_cols=None) -> pd.DataFrame:
    """Add 'Total' column and 'Grand Total' row."""
    if exclude_cols is None:
        exclude_cols = []
    df = df.copy()
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    if numeric_cols:
        df['Total'] = df[numeric_cols].sum(axis=1).astype(int)
    else:
        df['Total'] = ""
    total_row = {}
    for col in df.columns:
        if col in numeric_cols or col == 'Total':
            try:
                total_row[col] = int(df[col].sum())
            except Exception:
                total_row[col] = 0
        else:
            total_row[col] = ""
    try:
        total_df = pd.DataFrame([total_row], columns=df.columns, index=["Grand Total"])
        df_out = pd.concat([df, total_df])
    except Exception:
        df_out = df
    return df_make_integers(df_out, exclude_cols=exclude_cols)

def pivot_to_pdf(pivot_df: pd.DataFrame, title: str = "Summary", exclude_cols=None) -> bytes:
    """Render a generic pivot/table to a simple PDF (A4)."""
    if exclude_cols is None:
        exclude_cols = []
    pivot_df = pivot_df.copy()
    pivot_df = df_make_integers(pivot_df, exclude_cols=exclude_cols)

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
    col_width = max(18, int(usable_width // max_cols))

    col_names = [str(pivot_df.index.name) if pivot_df.index.name else ""] + [str(c) for c in pivot_df.columns]
    data = [col_names]
    for idx, row in pivot_df.iterrows():
        row_vals = [str(idx)]
        for val in row:
            if isinstance(val, (int, float)):
                row_vals.append(str(int(val)))
            else:
                row_vals.append(str(val))
        data.append(row_vals)

    for r in data:
        for val in r:
            pdf.cell(col_width, 7, str(val)[:25], border=1, align="C")
        pdf.ln()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf.output(tmp.name)
        tmp.seek(0)
        pdf_bytes = tmp.read()
    return pdf_bytes

def pivot_to_pdf_stylegroup(pivot_df: pd.DataFrame, title: str = "Style Group Reason Summary", grand_total: int = 0, exclude_cols=None) -> bytes:
    """Render style-group reason table in a special wide-first-column PDF with total."""
    if exclude_cols is None:
        exclude_cols = []
    pivot_df = pivot_df.copy()
    pivot_df = df_make_integers(pivot_df, exclude_cols=exclude_cols)

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, title, ln=1, align="C")
    pdf.ln(3)

    pdf_width = 297
    margin = 8
    usable_width = pdf_width - 2 * margin

    reason_col_width = 120
    other_cols = max(1, len(pivot_df.columns))
    other_col_width = int((usable_width - reason_col_width) / other_cols) if other_cols > 0 else 50

    pdf.set_font("Arial", "B", 9)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(reason_col_width, 8, "Detailed Return Reason", border=1, align="C", fill=True)
    for col in pivot_df.columns:
        pdf.cell(other_col_width, 8, str(col)[:20], border=1, align="C", fill=True)
    pdf.ln()

    pdf.set_font("Arial", "", 8)
    max_chars_per_line = 60
    line_height = 5

    for idx, row in pivot_df.iterrows():
        reason_text = str(idx)
        lines = [reason_text[i:i + max_chars_per_line] for i in range(0, len(reason_text), max_chars_per_line)]
        cell_height = line_height * max(1, len(lines))

        x_start = pdf.get_x()
        y_start = pdf.get_y()

        pdf.multi_cell(reason_col_width, line_height, "\n".join(lines), border=1, align="L")
        pdf.set_xy(x_start + reason_col_width, y_start)
        for val in row:
            txt = str(int(val)) if isinstance(val, (int, float)) else str(val)
            pdf.cell(other_col_width, cell_height, txt[:20], border=1, align="C")
        pdf.ln(cell_height)

    if grand_total:
        pdf.set_font("Arial", "B", 9)
        pdf.set_fill_color(200, 200, 200)
        pdf.cell(reason_col_width, 10, "TOTAL", border=1, align="C", fill=True)
        if pivot_df.shape[1] >= 1:
            pdf.cell(other_col_width, 10, str(int(grand_total)), border=1, align="C", fill=True)
            for _ in range(pivot_df.shape[1] - 1):
                pdf.cell(other_col_width, 10, "", border=1, align="C", fill=True)
        else:
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
        try:
            if f.name.lower().endswith(".csv"):
                df = pd.read_csv(f, skiprows=HEADER_ROW_INDEX, dtype=str, encoding="utf-8")
            else:
                df = pd.read_excel(f, skiprows=HEADER_ROW_INDEX, dtype=str)
        except Exception:
            try:
                if f.name.lower().endswith(".csv"):
                    df = pd.read_csv(f, dtype=str, encoding="utf-8")
                else:
                    df = pd.read_excel(f, dtype=str)
            except Exception as e:
                st.error(f"Failed to read {f.name}: {e}")
                continue
        dfs.append(df)

    if not dfs:
        st.error("No readable files uploaded.")
        st.stop()

    df_all = pd.concat(dfs, ignore_index=True).reset_index(drop=True)
    df_all.columns = [str(c).strip() for c in df_all.columns]

    # Ensure AWB Number preserved as string
    if "AWB Number" in df_all.columns:
        df_all["AWB Number"] = df_all["AWB Number"].astype(str).fillna("").apply(lambda x: x.strip())

    # Normalize Courier Partner names (Valmo / PocketShip)
    if "Courier Partner" in df_all.columns:
        df_all["Courier Partner"] = df_all["Courier Partner"].apply(
            lambda x: "Valmo" if pd.notna(x) and ("PocketShip" in str(x) or "Valmo" in str(x)) else x
        )

    # Normalize Delivered Date (if exists)
    if "Delivered Date" in df_all.columns:
        df_all["Delivered Date"] = pd.to_datetime(df_all["Delivered Date"], errors="coerce").dt.date

    # Detect return column
    possible_return_cols = ["Type of Return", "Detailed Return Reason", "Type of Return / Reason", "Type of Return Reason"]
    return_col = None
    for c in possible_return_cols:
        if c in df_all.columns:
            return_col = c
            break
    if return_col is None:
        for c in df_all.columns:
            if "return" in c.lower():
                return_col = c
                break

    if return_col is None:
        st.info("⚠️ Could not auto-detect return/reason column. If present, rename it to 'Type of Return' or 'Detailed Return Reason' for best results.")
    else:
        st.success(f"Detected return column: `{return_col}`")

    # ----------------- Sidebar Filters -----------------
    st.sidebar.header("🔍 Filters")

    # Date filter (Delivered Date)
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
        select_all_couriers = st.sidebar.checkbox("Select all couriers", True, key="cour_sel_all")
        selected_couriers = filtered_couriers if select_all_couriers else st.sidebar.multiselect(
            "Select Courier Partners", filtered_couriers, default=filtered_couriers
        )
    else:
        selected_couriers = []

    # SKU filter (for tables only)
    if "SKU" in df_all.columns:
        all_skus = sorted(str(x) for x in df_all["SKU"].dropna().unique())
        search_sku = st.sidebar.text_input("Search SKU")
        filtered_skus = [s for s in all_skus if search_sku.lower() in s.lower()] if search_sku else all_skus
        select_all_skus = st.sidebar.checkbox("Select all SKUs", True, key="sku_sel_all")
        selected_skus = filtered_skus if select_all_skus else st.sidebar.multiselect(
            "Select SKUs", filtered_skus, default=filtered_skus
        )
    else:
        selected_skus = []

    # ----------------- Independent DataFrames (24_TT1 Logic) -----------------

    # Base DF → used for KPI boxes (NO SKU filter)
    df_base = df_all.copy()

    if "Delivered Date" in df_base.columns and selected_dates:
        df_base = df_base[df_base["Delivered Date"].astype(str).isin(selected_dates)]

    if "Courier Partner" in df_base.columns and selected_couriers:
        df_base = df_base[df_base["Courier Partner"].isin(selected_couriers)]

    # Table DF → used for main summary tables (SKU filter applied here)
    df_table = df_base.copy()
    if "SKU" in df_table.columns and selected_skus:
        df_table = df_table[df_table["SKU"].isin(selected_skus)]

    # Style DF → independent copy of base for style-group logic (never apply SKU here)
    df_style = df_base.copy()

    # ----------------- Data Preview -----------------
    with st.expander("👁️ Data Preview — Raw (first 200 rows)", expanded=False):
        st.dataframe(df_all.head(200), use_container_width=True)

    with st.expander("👁️ Preview — Table DF (after Date/Courier + SKU if applied)", expanded=False):
        st.dataframe(df_table.head(200), use_container_width=True)

    # ----------------- KPI Boxes (Counts as integers) -----------------
    if "AWB Number" in df_base.columns:
        df_base["AWB Number"] = df_base["AWB Number"].astype(str).fillna("").apply(lambda x: x.strip())

    courier_rto_count = 0
    customer_return_count = 0

    if return_col and return_col in df_base.columns:
        # ensure string
        df_base[return_col] = df_base[return_col].astype(str)

        courier_rto_mask = df_base[return_col].str.contains("RTO|Courier|Return to Origin|Courier Return", case=False, na=False)
        customer_return_mask = df_base[return_col].str.contains("Customer|Customer Return|Customer Return Request", case=False, na=False)

        if "AWB Number" in df_base.columns:
            try:
                courier_rto_count = int(df_base.loc[courier_rto_mask, "AWB Number"].nunique())
            except Exception:
                courier_rto_count = int(df_base.loc[courier_rto_mask].shape[0])
            try:
                customer_return_count = int(df_base.loc[customer_return_mask, "AWB Number"].nunique())
            except Exception:
                customer_return_count = int(df_base.loc[customer_return_mask].shape[0])
        else:
            courier_rto_count = int(courier_rto_mask.sum())
            customer_return_count = int(customer_return_mask.sum())

    total_returns_count = int(courier_rto_count + customer_return_count)

    col1, col2, col3 = st.columns(3)
    col1.markdown(
        f"""
        <div style="background-color:#d4edda; padding:12px; border-radius:10px; text-align:center;">
            <h4 style="color:#155724; margin:0;">Courier Return (RTO)</h4>
            <h1 style="color:#155724; margin:0;">{int(courier_rto_count)}</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col2.markdown(
        f"""
        <div style="background-color:#f8d7da; padding:12px; border-radius:10px; text-align:center;">
            <h4 style="color:#721c24; margin:0;">Customer Return</h4>
            <h1 style="color:#721c24; margin:0;">{int(customer_return_count)}</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col3.markdown(
        f"""
        <div style="background-color:#cce5ff; padding:12px; border-radius:10px; text-align:center;">
            <h4 style="color:#004085; margin:0;">Total Returns</h4>
            <h1 style="color:#004085; margin:0;">{int(total_returns_count)}</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # ----------------- Courier Partner Summary by Delivered Date (TABLE DF) -----------------
    if {'Delivered Date', 'Courier Partner', 'AWB Number'}.issubset(df_table.columns):
        summary = df_table.groupby(['Delivered Date', 'Courier Partner'])['AWB Number'].nunique().reset_index(name='Total Packets')
        pivot_df = summary.pivot_table(index="Delivered Date", columns="Courier Partner", values="Total Packets", fill_value=0)
        pivot_df_with_totals = add_grand_totals(pivot_df, exclude_cols=["AWB Number"] if "AWB Number" in df_table.columns else None)

        st.subheader("📦 Courier Partner Summary by Delivered Date")
        st.dataframe(pivot_df_with_totals, use_container_width=True)

        pdf_bytes = pivot_to_pdf(pivot_df_with_totals, title="Courier Partner Summary by Delivered Date", exclude_cols=["AWB Number"] if "AWB Number" in df_table.columns else None)
        st.download_button("📥 Download Courier Summary (PDF)", pdf_bytes, "courier_partner_summary.pdf", "application/pdf")
    else:
        st.info("Courier summary requires columns: 'Delivered Date', 'Courier Partner', 'AWB Number' (in uploaded files).")

    # ----------------- SKU-wise Return Reason Summary (TABLE DF) -----------------
    reason_pivot = None
    if {"SKU", return_col} <= set(df_table.columns):
        st.subheader("SKU-wise Return Reason Summary")
        reason_summary = df_table.groupby(["SKU", return_col]).size().reset_index(name="Return Count")
        reason_pivot = reason_summary.pivot_table(index="SKU", columns=return_col, values="Return Count", fill_value=0)
        reason_pivot = add_grand_totals(reason_pivot, exclude_cols=["AWB Number"] if "AWB Number" in df_table.columns else None)
        st.dataframe(reason_pivot, use_container_width=True)
    else:
        st.info("SKU-wise summary requires 'SKU' and a return/reason column in the uploaded data.")

    # ----------------- Style Group Reason Summary (24_TT1 logic) using df_style -----------------
    st.subheader("Style Group Reason Summary by keyword (24_TT1 logic)")
    stylegroup_key = st.text_input("Enter Style Group keyword (e.g. POCKET TIE)")

    groupsummary_with_total = None
    if stylegroup_key and "SKU" in df_style.columns:
        temp_df = df_style.copy()
        temp_df["Style Group"] = temp_df["SKU"].apply(
            lambda x: stylegroup_key if stylegroup_key.lower() in str(x).lower() else None
        )
        group_df = temp_df[temp_df["Style Group"].notna()]

        if not group_df.empty and {"Detailed Return Reason", "Qty"}.issubset(group_df.columns):
            group_df["Qty"] = pd.to_numeric(group_df["Qty"], errors="coerce").fillna(0)
            groupsummary = group_df.groupby(["Style Group", "Detailed Return Reason"])["Qty"].sum().reset_index(name="Return Count")
            total_count = groupsummary["Return Count"].sum()
            grand_total_row = pd.DataFrame({
                "Style Group": ["Grand Total"],
                "Detailed Return Reason": [""],
                "Return Count": [int(total_count)]
            })
            groupsummary_with_total = pd.concat([groupsummary.sort_values(by="Return Count", ascending=False), grand_total_row], ignore_index=True)
            st.dataframe(groupsummary_with_total, use_container_width=True)

            # prepare pivot for pdf (index = Detailed Return Reason)
            groupsummary_pivot = groupsummary.pivot_table(index="Detailed Return Reason", columns="Style Group", values="Return Count", fill_value=0)
            pdf_stylegroup = pivot_to_pdf_stylegroup(groupsummary_pivot, title=f"Style Group Reason Summary - {stylegroup_key}", grand_total=int(total_count))
            st.download_button("Download Style Group Summary PDF", pdf_stylegroup, f"style_group_summary_{stylegroup_key}.pdf", "application/pdf")
        else:
            st.info("No SKUs matching that keyword or required columns (Detailed Return Reason, Qty) missing in data.")
    else:
        if stylegroup_key:
            st.info("Style Group requires 'SKU' and presence of 'Detailed Return Reason' and 'Qty' columns.")

    # ----------------- Download Options -----------------
    st.subheader("💾 Download Options")

    try:
        csv_all = df_all.to_csv(index=False).encode("utf-8")
        st.download_button("📄 Download All Data CSV", csv_all, file_name="all_data.csv", mime="text/csv")
    except Exception:
        st.warning("Unable to prepare All Data CSV for download.")

    try:
        csv_filtered = df_table.to_csv(index=False).encode("utf-8")
        st.download_button("📄 Download Filtered Data CSV (Table DF)", csv_filtered, file_name="filtered_table_data.csv", mime="text/csv")
    except Exception:
        st.warning("Unable to prepare Filtered Data CSV for download.")

    # Excel with multiple sheets
    try:
        excel_buf = BytesIO()
        with pd.ExcelWriter(excel_buf, engine="xlsxwriter") as writer:
            df_all.to_excel(writer, index=False, sheet_name="All Data")
            df_base.to_excel(writer, index=False, sheet_name="Base Data")
            df_table.to_excel(writer, index=False, sheet_name="Table Data")
            df_style.to_excel(writer, index=False, sheet_name="Style Data")

            if 'pivot_df_with_totals' in locals():
                try:
                    pivot_df_with_totals.to_excel(writer, sheet_name="Courier Summary")
                except Exception:
                    pass
            if reason_pivot is not None:
                try:
                    reason_pivot.to_excel(writer, sheet_name="Return Reason Summary")
                except Exception:
                    pass
            if groupsummary_with_total is not None:
                try:
                    groupsummary_with_total.to_excel(writer, sheet_name="Style Group Summary", index=False)
                except Exception:
                    pass
            writer.save()
        st.download_button("📊 Download Excel (All Summaries)", excel_buf.getvalue(), file_name="courier_return_full.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:
        st.warning(f"Unable to prepare Excel file: {e}")

else:
    st.info("👆 कृपया ऊपर दिए गए expander से CSV/XLSX फाइलें upload कीजिए।")
