import streamlit as st
import pandas as pd
from io import BytesIO
from fpdf import FPDF
import tempfile

# ================== Streamlit Config ==================
st.set_page_config(page_title="Courier Partner Delivery & Return Analysis", layout="wide")
st.title("📦 Courier Partner Delivery & Return Analysis — Final Merged (Global SKU Filter)")

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
    """
    Render the provided pivot_df (expected to ALREADY include 'Total' column and 'TOTAL' row if desired)
    to a landscape A4 PDF.
    """
    if exclude_cols is None:
        exclude_cols = []
    df = pivot_df.copy()

    # Convert numeric columns to int where possible for clean display
    for c in df.columns:
        try:
            df[c] = pd.to_numeric(df[c], errors='ignore')
            if pd.api.types.is_numeric_dtype(df[c]):
                df[c] = df[c].fillna(0).astype(int)
        except Exception:
            pass

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, title, ln=1, align="C")
    pdf.ln(3)

    pdf_width = 297
    margin = 8
    usable_width = pdf_width - 2 * margin

    reason_col_width = 110
    cols = list(df.columns)
    col_count = max(1, len(cols))
    other_col_width = int((usable_width - reason_col_width) / col_count) if col_count > 0 else 50

    # Header
    pdf.set_font("Arial", "B", 9)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(reason_col_width, 8, "Detailed Return Reason", border=1, align="C", fill=True)
    for col in cols:
        pdf.cell(other_col_width, 8, str(col)[:15], border=1, align="C", fill=True)
    pdf.ln()

    # Body: render rows exactly as in df
    pdf.set_font("Arial", "", 8)
    max_chars_per_line = 60
    line_height = 5

    for idx, row in df.iterrows():
        reason_text = str(idx)
        lines = [reason_text[i:i + max_chars_per_line] for i in range(0, len(reason_text), max_chars_per_line)]
        cell_height = line_height * max(1, len(lines))

        x_start = pdf.get_x()
        y_start = pdf.get_y()

        pdf.multi_cell(reason_col_width, line_height, "\n".join(lines), border=1, align="L")
        pdf.set_xy(x_start + reason_col_width, y_start)

        is_total_row = str(idx).strip().upper() == "TOTAL"

        if is_total_row:
            pdf.set_fill_color(200, 200, 200)
            fill_flag = True
            pdf.set_font("Arial", "B", 9)
        else:
            fill_flag = False
            pdf.set_font("Arial", "", 8)

        for col in cols:
            val = row[col]
            if pd.isna(val):
                text = ""
            else:
                # format numeric values as ints when possible
                if isinstance(val, (int, float)) or pd.api.types.is_numeric_dtype(type(val)):
                    try:
                        text = str(int(val))
                    except Exception:
                        text = str(val)
                else:
                    text = str(val)
            pdf.cell(other_col_width, cell_height, text[:15], border=1, align="C", fill=fill_flag)
        pdf.ln(cell_height)

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

    # ================= SKU Grouping System (Added Feature) =================
    final_sku_list = []
    
    if "SKU" in df_all.columns:
        df_all["SKU"] = df_all["SKU"].astype(str)
        all_skus = sorted(df_all["SKU"].dropna().unique())

        st.sidebar.markdown("---")
        st.sidebar.markdown("### 📦 SKU Group Manager")

        # --- Session State Init ---
        if 'sku_groups' not in st.session_state:
            st.session_state['sku_groups'] = []
        
        # --- Group Creator Interface (Search -> Select All -> Save) ---
        with st.sidebar.expander("➕ Create New Group", expanded=False):
            st.caption("Step 1: Search Keyword")
            search_keyword = st.text_input("Enter Keyword (e.g. Ramesh)", key="grp_search_box")
            
            # Find Matches
            found_matches = []
            if search_keyword:
                found_matches = [s for s in all_skus if search_keyword.lower() in s.lower()]
            
            st.caption(f"Step 2: Review Selection ({len(found_matches)} found)")
            
            # --- SELECT ALL BUTTONS LOGIC ---
            col_sel1, col_sel2 = st.columns(2)
            
            def select_all_matches():
                st.session_state.preview_multiselect = found_matches
            
            def deselect_all_matches():
                st.session_state.preview_multiselect = []
            
            if "preview_multiselect" not in st.session_state:
                st.session_state.preview_multiselect = []

            with col_sel1:
                st.button("✅ Select All", on_click=select_all_matches, use_container_width=True)
            with col_sel2:
                st.button("❌ Deselect All", on_click=deselect_all_matches, use_container_width=True)

            selected_for_group = st.multiselect(
                "Verify SKUs to add:",
                options=found_matches,
                key="preview_multiselect"
            )
            
            st.caption("Step 3: Name & Save")
            group_name_input = st.text_input("Group Name", key="grp_name_box")
            
            def save_filtered_group():
                if group_name_input and selected_for_group:
                    found = False
                    for g in st.session_state["sku_groups"]:
                        if g["name"] == group_name_input:
                            g["skus"] = selected_for_group
                            found = True
                            break
                    if not found:
                        st.session_state["sku_groups"].append({"name": group_name_input, "skus": selected_for_group})
                    st.toast(f"✅ Group '{group_name_input}' Saved with {len(selected_for_group)} SKUs!")
                else:
                    st.toast("⚠️ Name and valid selection required.")
            
            st.button("💾 Save Verified Group", on_click=save_filtered_group)
            
            st.markdown("---")
            if st.button("🧹 Clear All Groups"):
                st.session_state["sku_groups"] = []
                st.rerun()

        # --- Group Selection Logic ---
        st.sidebar.markdown("#### Select & View Groups")
        
        group_options = [f"{g['name']} ({len(g['skus'])})" for g in st.session_state['sku_groups']]
        selected_group_labels = st.sidebar.multiselect("1. Select Saved Groups", group_options)
        
        skus_from_groups = []
        for label in selected_group_labels:
            actual_name = label.rsplit(" (", 1)[0]
            for g in st.session_state['sku_groups']:
                if g['name'] == actual_name:
                    skus_from_groups.extend(g['skus'])
                    break
        skus_from_groups = list(set(skus_from_groups))

        # View Group Contents
        if skus_from_groups:
            with st.sidebar.expander(f"👁️ View SKUs in Selection ({len(skus_from_groups)})"):
                st.dataframe(pd.DataFrame(skus_from_groups, columns=["Included SKUs"]), hide_index=True)

        # --- Manual Extras ---
        available_extra_options = sorted(list(set(all_skus) - set(skus_from_groups)))
        manual_skus = st.sidebar.multiselect(
            "2. Add Extra SKUs (Unique only)", 
            options=available_extra_options,
            help="Allows adding single SKUs that are not in the selected groups."
        )
        
        # Final Combine
        final_sku_list = list(set(skus_from_groups) | set(manual_skus))
        
        if final_sku_list:
            st.sidebar.success(f"✨ Filtering by {len(final_sku_list)} SKUs")
        else:
            st.sidebar.text("Showing All Data")

    # ----------------- GLOBAL DATAFRAME FILTERING (FIXED) -----------------
    
    # 1. Start with full data
    df_filtered_global = df_all.copy()

    # 2. Apply Date Filter
    if "Delivered Date" in df_filtered_global.columns and selected_dates:
        df_filtered_global = df_filtered_global[df_filtered_global["Delivered Date"].astype(str).isin(selected_dates)]

    # 3. Apply Courier Filter
    if "Courier Partner" in df_filtered_global.columns and selected_couriers:
        df_filtered_global = df_filtered_global[df_filtered_global["Courier Partner"].isin(selected_couriers)]

    # 4. Apply SKU Filter (THIS IS THE CRITICAL FIX)
    # If any SKUs are selected (via Group or Manual), apply them to the GLOBAL data.
    if "SKU" in df_filtered_global.columns and final_sku_list:
        df_filtered_global = df_filtered_global[df_filtered_global["SKU"].astype(str).isin(final_sku_list)]
    
    # ----------------- ASSIGNMENT -----------------
    # Now all downstream usage (KPIs, Tables, Style) uses this filtered dataframe
    df_base = df_filtered_global.copy()
    df_table = df_filtered_global.copy()
    df_style = df_filtered_global.copy()

    # ----------------- Data Preview -----------------
    with st.expander("👁️ Data Preview — Raw (first 200 rows)", expanded=False):
        st.dataframe(df_all.head(200), use_container_width=True)

    with st.expander("👁️ Preview — Table DF (after All Filters)", expanded=False):
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
    st.subheader("Style Group Reason Summary by keyword (24_TT1 logic) — Customer Returns Only")
    stylegroup_key = st.text_input("Enter Style Group keyword (e.g. POCKET TIE)")

    groupsummary_with_total = None
    if stylegroup_key and "SKU" in df_style.columns:
        temp_df = df_style.copy()
        
        # 1. Filter by Keyword
        temp_df["Style Group"] = temp_df["SKU"].apply(
            lambda x: stylegroup_key if stylegroup_key.lower() in str(x).lower() else None
        )
        group_df = temp_df[temp_df["Style Group"].notna()]

        # -------------------------------------------------------------
        # FILTER: KEEP ONLY CUSTOMER RETURNS (EXCLUDE RTO)
        # -------------------------------------------------------------
        if return_col and not group_df.empty:
             # Logic: Exclude rows where Return Type contains "Courier" or "RTO"
             is_rto = group_df[return_col].astype(str).str.contains("RTO|Courier|Return to Origin", case=False, na=False)
             group_df = group_df[~is_rto]

        var_col = "Variation"  # user confirmed

        # Check required cols
        if not group_df.empty and {"Detailed Return Reason", "Qty"}.issubset(group_df.columns):
            # Ensure Variation exists; if not, fill with Unknown
            if var_col not in group_df.columns:
                group_df[var_col] = "Unknown"

            group_df["Qty"] = pd.to_numeric(group_df["Qty"], errors="coerce").fillna(0)

            # Build groupsummary aggregated by Style Group, Variation, Detailed Return Reason
            groupsummary = (
                group_df.groupby(["Style Group", var_col, "Detailed Return Reason"])["Qty"]
                .sum()
                .reset_index(name="Return Count")
            )

            # Pivot to get Variation columns (unique values will form columns)
            if not groupsummary.empty:
                try:
                    pivot_pdf_df = groupsummary.pivot_table(index="Detailed Return Reason", columns=var_col, values="Return Count", fill_value=0)
                except Exception:
                    # fallback: simple aggregation per reason
                    pivot_pdf_df = groupsummary.groupby("Detailed Return Reason")["Return Count"].sum().to_frame()

                # Add Total column (row sums) and TOTAL row (column sums)
                try:
                    # only sum numeric columns
                    numeric_cols = pivot_pdf_df.select_dtypes(include=['number']).columns.tolist()
                    if numeric_cols:
                        pivot_pdf_df["Total"] = pivot_pdf_df[numeric_cols].sum(axis=1).astype(int)
                        # add TOTAL row (column-wise sums)
                        total_row = pivot_pdf_df.sum(axis=0)
                        try:
                            total_row = total_row.astype(int)
                        except Exception:
                            pass
                        pivot_pdf_df.loc["TOTAL"] = total_row
                except Exception:
                    pass

                # For display on web: show pivot with totals (convert ints where possible)
                display_df = pivot_pdf_df.copy()
                try:
                    display_df = display_df.fillna(0)
                    for c in display_df.columns:
                        if pd.api.types.is_numeric_dtype(display_df[c]):
                            display_df[c] = display_df[c].astype(int)
                except Exception:
                    pass

                # Prepare a neat display with Reason as first column
                display_df_reset = display_df.reset_index().rename(columns={"index": "Detailed Return Reason"})
                st.dataframe(display_df_reset, use_container_width=True)

                # Create downloadable PDF using pivot_to_pdf_stylegroup
                try:
                    # compute total_count (grand total) from groupsummary
                    total_count = int(groupsummary["Return Count"].sum()) if not groupsummary.empty else 0
                    pdf_bytes = pivot_to_pdf_stylegroup(pivot_pdf_df, title=f"Style Group (Cust. Return) - {stylegroup_key}", grand_total=total_count)
                    st.download_button("📥 Download Style Group PDF", pdf_bytes, file_name=f"style_group_cust_ret_{stylegroup_key}.pdf", mime="application/pdf")
                except Exception as e:
                    st.warning(f"Unable to prepare Style Group PDF: {e}")

                # Save for Excel export
                groupsummary_with_total = display_df_reset.copy()
            else:
                st.warning("No Customer Return data found for this keyword (RTOs excluded).")

        else:
            if group_df.empty:
                st.info("No data found for this keyword (after excluding RTOs).")
            else:
                st.info("Required columns (Detailed Return Reason, Qty) missing in data.")
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
                    # groupsummary_with_total already had columns with Detailed Return Reason and totals
                    groupsummary_with_total.to_excel(writer, sheet_name="Style Group Summary", index=False)
                except Exception:
                    pass
            writer.save()
        st.download_button("📊 Download Excel (All Summaries)", excel_buf.getvalue(), file_name="courier_return_full.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:
        st.warning(f"Unable to prepare Excel file: {e}")

else:
    st.info("👆 कृपया ऊपर दिए गए expander से CSV/XLSX फाइलें upload कीजिए।")
