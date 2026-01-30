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
st.title("📦 Courier Partner Delivery & Return Analysis (Smart Grouping)")


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
                 title: str = "Summary") -> bytes:
    """Generic summary tables ke liye simple PDF."""
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


def pivot_to_pdf_stylegroup(pivot_df: pd.DataFrame,
                            title: str = "Style Group Reason Summary",
                            grand_total: int = 0) -> bytes:
    """
    Style Group reasons ke liye special PDF.
    """
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

        pdf.multi_cell(
            reason_col_width, line_height, "\n".join(lines),
            border=1, align="L"
        )

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

    # Date to proper date
    if "Return Created Date" in df_all.columns:
        df_all["Return Created Date"] = pd.to_datetime(
            df_all["Return Created Date"],
            errors="coerce"
        ).dt.date

    # ----------------- Sidebar Filters -----------------
    st.sidebar.header("Filters")

    # 1. Date filter
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

    # 2. Courier Partner filter
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

    # 3. Type of Return filter
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

    # 4. SKU Grouping & Filter (SMART LOGIC)
    final_sku_list = [] 
    
    if "SKU" in df_all.columns:
        df_all["SKU"] = df_all["SKU"].astype(str)
        all_skus = sorted(df_all["SKU"].dropna().unique())

        st.sidebar.markdown("---")
        st.sidebar.markdown("### 📦 SKU Grouping & Selection")

        # --- Session State Init ---
        if 'sku_groups' not in st.session_state:
            st.session_state['sku_groups'] = []
        
        # --- CALLBACK: Add Group ---
        def add_group_callback():
            name = st.session_state.new_group_name
            search = st.session_state.new_group_search
            
            if name and search:
                matches = [s for s in all_skus if search.lower() in s.lower()]
                if matches:
                    found = False
                    for g in st.session_state["sku_groups"]:
                        if g["name"] == name:
                            g["skus"] = matches
                            found = True
                            break
                    if not found:
                        st.session_state["sku_groups"].append({"name": name, "skus": matches})
                    st.toast(f"✅ Group '{name}' Saved!")
                else:
                    st.toast("⚠️ No SKUs matched.")
            else:
                st.toast("⚠️ Name & Keyword required.")

        def clear_groups_callback():
            st.session_state["sku_groups"] = []

        # --- Group Creation UI ---
        with st.sidebar.expander("➕ Create New Group", expanded=False):
            with st.form("group_creator_form", clear_on_submit=True):
                st.text_input("1. Search SKU keyword", key='new_group_search')
                st.text_input("2. Group Name", key='new_group_name')
                c1, c2 = st.columns(2)
                submitted = c1.form_submit_button("Save Group", on_click=add_group_callback)
                cleared = c2.form_submit_button("Clear All", on_click=clear_groups_callback)

        # -------------------------------------------------------------
        # STEP 1: Select Group (This creates the BASE selection)
        # -------------------------------------------------------------
        group_options = [f"{g['name']} ({len(g['skus'])})" for g in st.session_state['sku_groups']]
        selected_group_names = st.sidebar.multiselect("1. Select Saved Groups", group_options)
        
        skus_from_groups = []
        for label in selected_group_names:
            actual_name = label.rsplit(" (", 1)[0]
            for g in st.session_state['sku_groups']:
                if g['name'] == actual_name:
                    skus_from_groups.extend(g['skus'])
                    break
        
        # Remove duplicates from group selection
        skus_from_groups = list(set(skus_from_groups))

        # Show visual confirmation
        if skus_from_groups:
            st.sidebar.success(f"✅ {len(skus_from_groups)} SKUs included from Groups.")

        # -------------------------------------------------------------
        # STEP 2: Add Extra SKUs (Options EXCLUDE group SKUs)
        # -------------------------------------------------------------
        # Filter options: Only show SKUs that are NOT already in the selected groups
        # This solves your problem: Group wale SKUs yahan list mein nahi dikhenge!
        
        available_extra_options = sorted(list(set(all_skus) - set(skus_from_groups)))
        
        manual_skus = st.sidebar.multiselect(
            "2. Add Extra SKUs (Optional)", 
            options=available_extra_options,
            help="SKUs in Groups are hidden here to avoid duplicates."
        )
        
        # -------------------------------------------------------------
        # STEP 3: Final Union
        # -------------------------------------------------------------
        final_sku_list = list(set(skus_from_groups) | set(manual_skus))
        
        if final_sku_list:
            st.sidebar.info(f"✨ Total Filtering SKUs: {len(final_sku_list)}")
        else:
            st.sidebar.text("No SKUs selected (Showing All)")

    # ----------------- Apply Filters -----------------
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

    # FORCE FILTER using the calculated list
    if "SKU" in df_filtered.columns and final_sku_list:
        df_filtered = df_filtered[
            df_filtered["SKU"].astype(str).isin(final_sku_list)
        ]

    # ----------------- KPI Boxes -----------------
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

    # ----------------- Courier & Customer Summary -----------------
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

        # Combined Return Summary (RTO + Customer)
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

        st.subheader("Combined Return Summary (All Returns)")
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

    # ----------------- Style Group Reason Summary (vertical) -----------------
    st.subheader("Style Group Reason Summary by keyword")
    stylegroup_key = st.text_input(
        "Enter Style Group keyword (e.g. POCKET TIE)"
    )

    groupsummary_with_total = None

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

            grand_total_row = pd.DataFrame({
                "Style Group": ["Grand Total"],
                "Detailed Return Reason": [""],
                "Return Count": [int(total_count)]
            })

            groupsummary_with_total = pd.concat(
                [
                    groupsummary.sort_values(by="Return Count", ascending=False),
                    grand_total_row
                ],
                ignore_index=True
            )

            st.dataframe(
                groupsummary_with_total,
                use_container_width=True
            )

            # PDF ke liye pivot (index = Detailed Return Reason)
            groupsummary_pivot = groupsummary.pivot_table(
                index="Detailed Return Reason",
                columns="Style Group",
                values="Return Count",
                fill_value=0
            )

            pdf_stylegroup = pivot_to_pdf_stylegroup(
                groupsummary_pivot,
                title=f"Style Group Reason Summary - {stylegroup_key}",
                grand_total=int(total_count)
            )

            st.download_button(
                "Download Style Group Summary PDF",
                pdf_stylegroup,
                f"style_group_summary_{stylegroup_key}.pdf",
                "application/pdf"
            )
        else:
            st.info("No SKUs found matching this style keyword.")

    # ----------------- Download Options -----------------
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

        if "combined_pivot" in locals():
            combined_pivot.to_excel(writer, sheet_name="Combined Return Summary")

        if groupsummary_with_total is not None:
            groupsummary_with_total.to_excel(
                writer, sheet_name="Style Group Summary", index=False
            )

    st.download_button(
        "Download Excel (All Summaries)",
        excel_buf.getvalue(),
        file_name="courier_return_full.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("Please upload CSV or Excel files to begin analysis.")
