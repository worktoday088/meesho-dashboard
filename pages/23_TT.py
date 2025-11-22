import streamlit as st
import pandas as pd
from io import BytesIO
from fpdf import FPDF
import tempfile

st.set_page_config(page_title="Courier Partner Delivery & Return Analysis", layout="wide")
st.title("📦 Courier Partner Delivery & Return Analysis")

def add_grand_totals(df: pd.DataFrame) -> pd.DataFrame:
    df["Grand Total"] = df.sum(axis=1, numeric_only=True)
    total_row = df.sum(axis=0, numeric_only=True)
    total_row.name = "Grand Total"
    df = pd.concat([df, pd.DataFrame([total_row])], axis=0)
    return df

def add_totals_column(df: pd.DataFrame) -> pd.DataFrame:
    df["Total"] = df.sum(axis=1, numeric_only=True)
    total_row = df.sum(axis=0, numeric_only=True)
    total_row.name = "Grand Total"
    return pd.concat([df, pd.DataFrame([total_row])], axis=0)

def pivot_to_pdf(pivot_df: pd.DataFrame, title: str = "Courier Partner Summary by Delivered Date") -> bytes:
    max_cols = len(pivot_df.columns) + 1
    orientation = "L" if max_cols > 7 else "P"
    pdf_width = 297 if orientation == "L" else 210
    pdf = FPDF(orientation=orientation, unit="mm", format="A4")
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, title, ln=1, align="C")
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

with st.expander("Upload CSV/XLSX Files", expanded=True):
    uploaded_files = st.file_uploader(
        "Upload CSV/XLSX Files",
        accept_multiple_files=True
    )

if uploaded_files:
    dfs = []
    for f in uploaded_files:
        if f.name.endswith(".csv"):
            df = pd.read_csv(f, skiprows=7)
        else:
            df = pd.read_excel(f, skiprows=7)
        dfs.append(df)
    df_all = pd.concat(dfs, ignore_index=True)

    if "Courier Partner" in df_all.columns:
        df_all["Courier Partner"] = df_all["Courier Partner"].apply(
            lambda x: "Valmo"
            if pd.notna(x) and ("PocketShip" in str(x) or "Valmo" in str(x))
            else x
        )
    if "Return Created Date" in df_all.columns:
        df_all["Return Created Date"] = pd.to_datetime(
            df_all["Return Created Date"], errors="coerce"
        ).dt.date

    st.sidebar.header("Filters")
    # Date filter
    if "Return Created Date" in df_all.columns:
        all_dates = sorted(str(x) for x in df_all["Return Created Date"].dropna().unique())
        selected_dates = st.sidebar.multiselect(
            "Select Return Created Dates",
            all_dates,
            default=all_dates
        )
    else:
        selected_dates = []

    # Courier Partner filter
    if "Courier Partner" in df_all.columns:
        all_couriers = sorted(str(x) for x in df_all["Courier Partner"].dropna().unique())
        selected_couriers = st.sidebar.multiselect(
            "Select Courier Partners",
            all_couriers,
            default=all_couriers
        )
    else:
        selected_couriers = []

    # Type of Return filter
    if "Type of Return" in df_all.columns:
        all_types = sorted(str(x) for x in df_all["Type of Return"].dropna().unique())
        selected_types = st.sidebar.multiselect(
            "Select Type of Returns",
            all_types,
            default=all_types
        )
    else:
        selected_types = []

    # ---- ADVANCED SKU FILTER SYSTEM ----
    if "SKU" in df_all.columns:
        all_skus = sorted(str(x) for x in df_all["SKU"].dropna().unique())
        st.sidebar.write("SKU Filters:")
        sku_search = st.sidebar.text_input("Search SKU keyword", "")
        filtered_skus = [s for s in all_skus if sku_search.lower() in s.lower()] if sku_search else all_skus
        sku_col1, sku_col2 = st.sidebar.columns(2)
        if sku_col1.button("Select All SKUs"):
            st.session_state["selected_skus"] = filtered_skus
        if sku_col2.button("Clear All SKUs"):
            st.session_state["selected_skus"] = []
        if "selected_skus" not in st.session_state:
            st.session_state["selected_skus"] = filtered_skus
        selected_skus = st.sidebar.multiselect(
            "Select SKUs",
            filtered_skus,
            default=st.session_state["selected_skus"],
            key="selected_skus"
        )
        sku_keyword = st.sidebar.text_input("SKU keyword (auto-select, e.g. FRUIT)", key="sku_keyword")
        if st.sidebar.button("Auto-select SKUs by keyword"):
            if sku_keyword:
                auto_skus = [s for s in filtered_skus if sku_keyword.lower() in str(s).lower()]
                if auto_skus:
                    st.session_state["selected_skus"] = auto_skus
                else:
                    st.warning("No SKUs found for this keyword.")
    else:
        selected_skus = []

    df_filtered = df_all.copy()
    if "Return Created Date" in df_filtered.columns and selected_dates:
        df_filtered = df_filtered[df_filtered["Return Created Date"].astype(str).isin(selected_dates)]
    if "Courier Partner" in df_filtered.columns and selected_couriers:
        df_filtered = df_filtered[df_filtered["Courier Partner"].isin(selected_couriers)]
    if "Type of Return" in df_filtered.columns and selected_types:
        df_filtered = df_filtered[df_filtered["Type of Return"].isin(selected_types)]
    if "SKU" in df_filtered.columns and selected_skus:
        df_filtered = df_filtered[df_filtered["SKU"].isin(selected_skus)]

    courier_rto_count = 0
    customer_return_count = 0
    if "Type of Return" in df_filtered.columns:
        courier_rto_count = df_filtered[df_filtered["Type of Return"] == "Courier Return (RTO)"].shape[0]
        customer_return_count = df_filtered[df_filtered["Type of Return"] == "Customer Return"].shape[0]
    total_returns_count = courier_rto_count + customer_return_count

    col1, col2, col3 = st.columns(3)
    col1.metric("Courier Return (RTO)", courier_rto_count)
    col2.metric("Customer Return", customer_return_count)
    col3.metric("Total Returns", total_returns_count)

    # Courier & Customer Summary
    req_cols = {"Return Created Date", "Type of Return", "Courier Partner", "Qty"}
    if req_cols.issubset(df_filtered.columns):
        df_filtered["Qty"] = pd.to_numeric(df_filtered["Qty"], errors="coerce").fillna(0)
        cour_return = df_filtered[df_filtered["Type of Return"] == "Courier Return (RTO)"]
        cust_return = df_filtered[df_filtered["Type of Return"] == "Customer Return"]

        if not cour_return.empty:
            cour_pivot = cour_return.groupby(["Return Created Date", "Courier Partner"])["Qty"].sum().unstack(fill_value=0)
            cour_pivot = add_totals_column(cour_pivot)
            st.subheader("Courier Return (RTO) Summary")
            st.dataframe(cour_pivot, use_container_width=True)
        else:
            st.info("No Courier Return (RTO) data for selected filters.")

        if not cust_return.empty:
            cust_pivot = cust_return.groupby(["Return Created Date", "Courier Partner"])["Qty"].sum().unstack(fill_value=0)
            cust_pivot = add_totals_column(cust_pivot)
            st.subheader("Customer Return Summary")
            st.dataframe(cust_pivot, use_container_width=True)
        else:
            st.info("No Customer Return data for selected filters.")

    # SKU-wise Return Reason Summary
    if {"SKU", "Detailed Return Reason"}.issubset(df_filtered.columns):
        st.subheader("SKU-wise Return Reason Summary")
        reason_summary = (
            df_filtered
            .groupby(["SKU", "Detailed Return Reason"])
            .size()
            .reset_index(name="Return Count")
        )
        reason_pivot = reason_summary.pivot_table(
            index="SKU", columns="Detailed Return Reason",
            values="Return Count", fill_value=0
        )
        reason_pivot = add_grand_totals(reason_pivot)
        st.dataframe(reason_pivot, use_container_width=True)

    # Download Filtered Data
    st.subheader("Download Options")
    csv_filtered = df_filtered.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download Filtered Data CSV", csv_filtered,
        file_name="filtered_data.csv", mime="text/csv"
    )

else:
    st.info("Please upload CSV or Excel files to begin analysis.")
