import streamlit as st
import pandas as pd
from io import BytesIO
from fpdf import FPDF
import tempfile

# Streamlit Config
st.set_page_config(
    page_title="Courier Partner Delivery & Return Analysis",
    layout="wide"
)
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


def pivot_to_pdf(pivot_df: pd.DataFrame,
                 title: str = "Courier Partner Summary by Delivered Date") -> bytes:
    """Convert a pivot DataFrame to simple table PDF."""
    max_cols = len(pivot_df.columns) + 1  # +1 for index column

    # Decide orientation based on column count
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

    # Prepare data rows (index as first column)
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


# ----------------- Upload section (with triangle) -----------------
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

    # Normalise Courier Partner names
    if "Courier Partner" in df_all.columns:
        df_all["Courier Partner"] = df_all["Courier Partner"].apply(
            lambda x: "Valmo"
            if pd.notna(x) and ("PocketShip" in str(x) or "Valmo" in str(x))
            else x
        )

    # Date column को proper date में बदलें
    if "Return Created Date" in df_all.columns:
        df_all["Return Created Date"] = pd.to_datetime(
            df_all["Return Created Date"],
            errors="coerce"
        ).dt.date

    # ----------------- Sidebar Filters -----------------
    st.sidebar.header("Filters")

    # Date filter
    if "Return Created Date" in df_all.columns:
        all_dates = sorted(
            str(x) for x in df_all["Return Created Date"].dropna().unique()
        )
        selected_dates = st.sidebar.multiselect(
            "Select Return Created Dates",
            all_dates,
            default=all_dates
        )
    else:
        selected_dates = []

    # Courier Partner filter
    if "Courier Partner" in df_all.columns:
        all_couriers = sorted(
            str(x) for x in df_all["Courier Partner"].dropna().unique()
        )
        selected_couriers = st.sidebar.multiselect(
            "Select Courier Partners",
            all_couriers,
            default=all_couriers
        )
    else:
        selected_couriers = []

    # Type of Return filter
    if "Type of Return" in df_all.columns:
        all_types = sorted(
            str(x) for x in df_all["Type of Return"].dropna().unique()
        )
        selected_types = st.sidebar.multiselect(
            "Select Type of Returns",
            all_types,
            default=all_types
        )
    else:
        selected_types = []

    # ----------------- UPDATED SKU filter -----------------
    if "SKU" in df_all.columns:
        all_skus = sorted(
            str(x) for x in df_all["SKU"].dropna().unique()
        )

        st.sidebar.write("SKU Filters:")

        # Search box (substring, case-insensitive)
        sku_search = st.sidebar.text_input("Search SKU")

        if sku_search:
            filtered_skus = [s for s in all_skus if sku_search.lower() in s.lower()]
        else:
            filtered_skus = all_skus

        col_sku1, col_sku2 = st.sidebar.columns(2)
        if col_sku1.button("Select All SKUs"):
            st.session_state["selected_skus"] = filtered_skus
        if col_sku2.button("Clear All SKUs"):
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

    # ----------------- Apply Filters to df_all -----------------
    df_filtered = df_all.copy()

    if "Return Created Date" in df_filtered.columns and selected_dates:
        df_filtered = df_filtered[
            df_filtered["Return Created Date"].astype(str).isin(selected_dates)
        ]

    if "Courier Partner" in df_filtered.columns and selected_couriers:
        df_filtered = df_filtered[
            df_filtered["Courier Partner"].isin(selected_couriers)
        ]

    if "Type of Return" in df_filtered.columns and selected_types:
        df_filtered = df_filtered[
            df_filtered["Type of Return"].isin(selected_types)
        ]

    if "SKU" in df_filtered.columns and selected_skus:
        df_filtered = df_filtered[
            df_filtered["SKU"].isin(selected_skus)
        ]

    # ----------------- Top KPI Boxes (filtered data पर) -----------------
    courier_rto_count = 0
    customer_return_count = 0

    if "Type of Return" in df_filtered.columns:
        courier_rto_count = df_filtered[
            df_filtered["Type of Return"] == "Courier Return (RTO)"
        ].shape[0]
        customer_return_count = df_filtered[
            df_filtered["Type of Return"] == "Customer Return"
        ].shape[0]

    total_returns_count = courier_rto_count + customer_return_count

    col1, col2, col3 = st.columns(3)

    col1.markdown(
        f"""
        <div style="background-color:#d4edda; padding:10px; border-radius:5px; text-align:center;">
            <h3 style="color:#155724;">Courier Return (RTO)</h3>
            <h1>{courier_rto_count}</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col2.markdown(
        f"""
        <div style="background-color:#f8d7da; padding:10px; border-radius:5px; text-align:center;">
            <h3 style="color:#721c24;">Customer Return</h3>
            <h1>{customer_return_count}</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col3.markdown(
        f"""
        <div style="background-color:#cce5ff; padding:10px; border-radius:5px; text-align:center;">
            <h3 style="color:#004085;">Total Returns</h3>
            <h1>{total_returns_count}</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ----------------- Courier & Customer Summary Tables -----------------
    required_cols = {"Return Created Date", "Type of Return", "Courier Partner", "Qty"}
    if required_cols.issubset(df_filtered.columns):
        df_filtered["Qty"] = pd.to_numeric(
            df_filtered["Qty"],
            errors="coerce"
        ).fillna(0)

        cour_return = df_filtered[
            df_filtered["Type of Return"] == "Courier Return (RTO)"
        ]
        cust_return = df_filtered[
            df_filtered["Type of Return"] == "Customer Return"
        ]

        # Courier Return (RTO) Summary
        if not cour_return.empty:
            cour_pivot = cour_return.groupby(
                ["Return Created Date", "Courier Partner"]
            )["Qty"].sum().unstack(fill_value=0)

            cour_pivot = add_totals_column(cour_pivot)

            st.subheader("Courier Return (RTO) Summary")
            st.dataframe(cour_pivot, use_container_width=True)

            pdf_courier = pivot_to_pdf(
                cour_pivot,
                title="Courier Return (RTO) Summary"
            )
            st.download_button(
                "Download Courier Return Summary PDF",
                pdf_courier,
                "courier_return_summary.pdf",
                "application/pdf"
            )
        else:
            st.info("No Courier Return (RTO) data for selected filters.")

        # Customer Return Summary
        if not cust_return.empty:
            cust_pivot = cust_return.groupby(
                ["Return Created Date", "Courier Partner"]
            )["Qty"].sum().unstack(fill_value=0)

            cust_pivot = add_totals_column(cust_pivot)

            st.subheader("Customer Return Summary")
            st.dataframe(cust_pivot, use_container_width=True)

            pdf_customer = pivot_to_pdf(
                cust_pivot,
                title="Customer Return Summary"
            )
            st.download_button(
                "Download Customer Return Summary PDF",
                pdf_customer,
                "customer_return_summary.pdf",
                "application/pdf"
            )
        else:
            st.info("No Customer Return data for selected filters.")

        # -------- Combined Return Summary (Courier + Customer) --------
        combined_required_cols = {
            "Return Created Date", "Courier Partner", "Qty"
        }

        if combined_required_cols.issubset(df_filtered.columns):
            st.subheader("Combined Return Summary (All Returns)")

            combined_df = df_filtered.copy()
            combined_df["Qty"] = pd.to_numeric(
                combined_df["Qty"], errors="coerce"
            ).fillna(0)

            combined_pivot = (
                combined_df
                .groupby(["Return Created Date", "Courier Partner"])["Qty"]
                .sum()
                .unstack(fill_value=0)
            )

            combined_pivot = add_totals_column(combined_pivot)

            st.dataframe(combined_pivot, use_container_width=True)

            pdf_combined = pivot_to_pdf(
                combined_pivot,
                title="Combined Return Summary (All Returns)"
            )
            st.download_button(
                "Download Combined Return Summary PDF",
                pdf_combined,
                "combined_return_summary.pdf",
                "application/pdf"
            )

    # ----------------- SKU-wise Return Reason Summary -----------------
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

    # ----------------- Style Group Reason Summary by keyword (VERTICAL) -----------------
    st.subheader("Style Group Reason Summary by keyword")
    stylegroup_key = st.text_input(
        "Enter Style Group keyword (e.g. POCKET TIE)"
    )

    if stylegroup_key and "SKU" in df_filtered.columns:
        temp_df = df_filtered.copy()
        temp_df["Style Group"] = temp_df["SKU"].apply(
            lambda x: stylegroup_key
            if stylegroup_key.lower() in str(x).lower()
            else None
        )

        group_df = temp_df[temp_df["Style Group"].notna()]

        if not group_df.empty and {
            "Detailed Return Reason", "Qty"
        }.issubset(group_df.columns):

            group_df["Qty"] = pd.to_numeric(
                group_df["Qty"], errors="coerce"
            ).fillna(0)

            groupsummary = (
                group_df
                .groupby(["Style Group", "Detailed Return Reason"])["Qty"]
                .sum()
                .reset_index(name="Return Count")
            )

            total_count = groupsummary["Return Count"].sum()
            st.markdown(f"**Grand Total: {total_count}**")

            st.dataframe(
                groupsummary.sort_values(
                    by="Return Count", ascending=False
                ),
                use_container_width=True
            )
        else:
            st.info("No SKUs found matching this style keyword.")

    # ----------------- Download Options -----------------
    st.subheader("Download Options")

    # All data CSV
    csv_all = df_all.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download All Data CSV",
        csv_all,
        file_name="all_data.csv",
        mime="text/csv"
    )

    # Filtered data CSV
    csv_filtered = df_filtered.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download Filtered Data CSV",
        csv_filtered,
        file_name="filtered_data.csv",
        mime="text/csv"
    )

    # Excel with all summaries
    excel_buf = BytesIO()
    with pd.ExcelWriter(excel_buf, engine="xlsxwriter") as writer:
        df_all.to_excel(writer, index=False, sheet_name="All Data")
        df_filtered.to_excel(writer, index=False, sheet_name="Filtered Data")

        if "cour_pivot" in locals():
            cour_pivot.to_excel(writer, sheet_name="Courier Return Summary")

        if "cust_pivot" in locals():
            cust_pivot.to_excel(writer, sheet_name="Customer Return Summary")

        if "reason_pivot" in locals():
            reason_pivot.to_excel(writer, sheet_name="Return Reason Summary")

        # Style group vertical वाली summary अलग sheet पर:
        if "groupsummary" in locals():
            groupsummary.to_excel(writer, sheet_name="Style Group Summary", index=False)

        if "combined_pivot" in locals():
            combined_pivot.to_excel(writer, sheet_name="Combined Return Summary")

    st.download_button(
        "Download Excel (All Summaries)",
        excel_buf.getvalue(),
        file_name="courier_return_full.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("Please upload CSV or Excel files to begin analysis.")
