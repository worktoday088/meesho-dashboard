import streamlit as st
import pandas as pd
from io import BytesIO
from fpdf import FPDF
import tempfile

# Streamlit Config
st.set_page_config(page_title="Courier Partner Delivery & Return Analysis", layout="wide")
st.title("📦 Courier Partner Delivery & Return Analysis")

# ---------- Helper Functions ----------

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
    col_width = max(15, usable_width // (len(pivot_df.columns) + 1))

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

# ---------- Upload Section ----------

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

    # Normalisation जैसा आपके original में है
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

    # ---------- Sidebar Filters (same as nm.py, SKU updated) ----------

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

    # ---------- UPDATED SKU FILTER (pattern from 3_courier_details-2.py) ----------

    if "SKU" in df_all.columns:
        all_skus = sorted(str(x) for x in df_all["SKU"].dropna().unique())
        st.sidebar.write("SKU Filters:")

        # Search box like reference script
        sku_search = st.sidebar.text_input("Search SKU", "")

        if sku_search:
            filtered_skus = [s for s in all_skus if sku_search.lower() in s.lower()]
        else:
            filtered_skus = all_skus

        col_a, col_b = st.sidebar.columns(2)
        if col_a.button("Select All SKUs"):
            st.session_state["selected_skus"] = filtered_skus
        if col_b.button("Clear All SKUs"):
            st.session_state["selected_skus"] = []

        if "selected_skus" not in st.session_state:
            st.session_state["selected_skus"] = filtered_skus

        selected_skus = st.sidebar.multiselect(
            "Select SKUs",
            filtered_skus,
            default=st.session_state["selected_skus"],
            key="selected_skus"
        )
    else:
        selected_skus = []

    # ---------- Apply Filters to Data (same logic, सिर्फ selected_skus use) ----------

    df_filtered = df_all.copy()

    if "Return Created Date" in df_filtered.columns and selected_dates:
        df_filtered = df_filtered[df_filtered["Return Created Date"].astype(str).isin(selected_dates)]

    if "Courier Partner" in df_filtered.columns and selected_couriers:
        df_filtered = df_filtered[df_filtered["Courier Partner"].isin(selected_couriers)]

    if "Type of Return" in df_filtered.columns and selected_types:
        df_filtered = df_filtered[df_filtered["Type of Return"].isin(selected_types)]

    if "SKU" in df_filtered.columns and selected_skus:
        df_filtered = df_filtered[df_filtered["SKU"].isin(selected_skus)]

    # ---------- यहां से नीचे आपका nm.py जैसा ही analysis / reports ----------

    # Top KPI boxes (nm.py के pattern पर)
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

    # Courier & Customer summary tables (same columns/logic जैसा original nm.py में)
    required_cols = {"Return Created Date", "Type of Return", "Courier Partner", "Qty"}
    if required_cols.issubset(df_filtered.columns):
        df_filtered["Qty"] = pd.to_numeric(df_filtered["Qty"], errors="coerce").fillna(0)

        cour_return = df_filtered[df_filtered["Type of Return"] == "Courier Return (RTO)"]
        cust_return = df_filtered[df_filtered["Type of Return"] == "Customer Return"]

        if not cour_return.empty:
            cour_pivot = cour_return.groupby(
                ["Return Created Date", "Courier Partner"]
            )["Qty"].sum().unstack(fill_value=0)
            cour_pivot = add_totals_column(cour_pivot)
            st.subheader("Courier Return (RTO) Summary")
            st.dataframe(cour_pivot, use_container_width=True)

            pdf_courier = pivot_to_pdf(cour_pivot, title="Courier Return (RTO) Summary")
            st.download_button(
                "Download Courier Return Summary PDF",
                pdf_courier,
                "courier_return_summary.pdf",
                "application/pdf"
            )
        else:
            st.info("No Courier Return (RTO) data for selected filters.")

        if not cust_return.empty:
            cust_pivot = cust_return.groupby(
                ["Return Created Date", "Courier Partner"]
            )["Qty"].sum().unstack(fill_value=0)
            cust_pivot = add_totals_column(cust_pivot)
            st.subheader("Customer Return Summary")
            st.dataframe(cust_pivot, use_container_width=True)

            pdf_customer = pivot_to_pdf(cust_pivot, title="Customer Return Summary")
            st.download_button(
                "Download Customer Return Summary PDF",
                pdf_customer,
                "customer_return_summary.pdf",
                "application/pdf"
            )
        else:
            st.info("No Customer Return data for selected filters.")

    # SKU-wise Return Reason Summary (same as nm.py)
    if {"SKU", "Detailed Return Reason"}.issubset(df_filtered.columns):
        st.subheader("SKU-wise Return Reason Summary")
        reason_summary = (
            df_filtered
            .groupby(["SKU", "Detailed Return Reason"])
            .size()
            .reset_index(name="Return Count")
        )
        reason_pivot = reason_summary.pivot_table(
            index="SKU",
            columns="Detailed Return Reason",
            values="Return Count",
            fill_value=0
        )
        reason_pivot = add_grand_totals(reason_pivot)
        st.dataframe(reason_pivot, use_container_width=True)

    # (nm.py में जितनी और extra summaries / style group वगैरह हैं, उन्हें भी यही नीचे रखें;
    # उन हिस्सों का logic नहीं बदला गया, सिर्फ ऊपर SKU filter बदला है।)

    # Download options (same as nm.py)
    st.subheader("Download Options")
    csv_all = df_all.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download All Data CSV",
        csv_all,
        file_name="all_data.csv",
        mime="text/csv"
    )
    csv_filtered = df_filtered.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download Filtered Data CSV",
        csv_filtered,
        file_name="filtered_data.csv",
        mime="text/csv"
    )

else:
    st.info("Please upload CSV or Excel files to begin analysis.")
