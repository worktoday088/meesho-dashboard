import streamlit as st
import pandas as pd
import io
from datetime import datetime
from fpdf import FPDF

# -----------------------------
# Helper functions & classes
# -----------------------------
class PDF(FPDF):
    def header(self):
        # ASCII-only header to avoid encoding issues
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Final Combined Report', 0, 1, 'C')

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def dataframe_to_pdf(self, df, total_difference=None, title="Table"):
        # add page and title
        self.add_page()
        self.set_font('Arial', 'B', 11)
        # Ensure title only contains ascii characters
        safe_title = title if all(ord(c) < 128 for c in title) else ''.join(c if ord(c) < 128 else '?' for c in title)
        self.cell(0, 8, safe_title, 0, 1, 'L')
        self.ln(1)

        self.set_font("Arial", size=8)
        col_widths = {
            'Sr. No.': 15, 'Sub Order No': 40, 'Old Status': 30, 'New Status': 30,
            'Old Price': 25, 'New Price': 25, 'Difference': 30, 'Remarks': 35
        }

        header = list(df.columns)
        # header row
        self.set_font('Arial', 'B', 8)
        for col_name in header:
            w = col_widths.get(col_name, 30)
            # make header ascii-safe
            htxt = col_name if all(ord(c) < 128 for c in str(col_name)) else ''.join(c if ord(c) < 128 else '?' for c in str(col_name))
            self.cell(w, 8, htxt, 1, 0, 'C')
        self.ln()

        # data rows
        self.set_font('Arial', '', 8)
        for _, row in df.iterrows():
            for col_name in header:
                raw_text = str(row[col_name]) if pd.notna(row[col_name]) else ""
                # keep width from mapping
                w = col_widths.get(col_name, 30)
                # shorten long text
                if len(raw_text) > 40:
                    raw_text = raw_text[:37] + "..."
                # make ascii-safe: replace non-ascii with '?'
                text = ''.join(ch if ord(ch) < 128 else '?' for ch in raw_text)
                self.cell(w, 7, text, 1)
            self.ln()

        # Add total difference summary under the table if provided
        if total_difference is not None:
            self.ln(3)
            self.set_font('Arial', 'B', 9)
            # Use ASCII "Rs." here to avoid encoding errors
            total_str = f"Total Difference: Rs.{total_difference:,.2f}"
            self.cell(0, 8, total_str, 0, 1, 'R')

def dataframe_to_pdf_bytes(df, total_difference=None, title="Table"):
    # Work on a safe copy: replace rupee sign if present and ensure strings
    df2 = df.fillna('').astype(str).applymap(lambda x: x.replace('₹', 'Rs.'))
    pdf = PDF()
    pdf.dataframe_to_pdf(df2, total_difference=total_difference, title=title)
    # fpdf returns a string; encode to latin-1 with replace to avoid exceptions on unicode
    pdf_str = pdf.output(dest='S')
    pdf_bytes = pdf_str.encode('latin-1', 'replace')
    return pdf_bytes

# find column names case-insensitively (best-effort)
def detect_column(df, candidates):
    cols = list(df.columns)
    low_cols = [str(c).lower().strip() for c in cols]
    for cand in candidates:
        cand_low = cand.lower().strip()
        for i, c in enumerate(low_cols):
            if cand_low in c:
                return cols[i]
    return None

def ensure_columns(df):
    mapping = {}
    mapping['sub'] = detect_column(df, ['sub order no', 'sub order id', 'suborder', 'sub order'])
    mapping['status'] = detect_column(df, ['live order status', 'order status', 'status'])
    mapping['price'] = detect_column(df, ['final settlement amount', 'final amount', 'settlement amount', 'amount', 'price', 'new price'])
    return mapping

def safe_float(x):
    try:
        if pd.isna(x):
            return 0.0
        s = str(x).strip().replace(',', '')
        if s.startswith('₹'):
            s = s[1:]
        if s.startswith('(') and s.endswith(')'):
            s = '-' + s[1:-1]
        if s == '':
            return 0.0
        return float(s)
    except (ValueError, TypeError):
        return 0.0

def normalize_df(df, mapping, prefix):
    df = df.copy()
    renames = {}
    if mapping['sub']:
        renames[mapping['sub']] = f'{prefix}_sub'
    if mapping['status']:
        renames[mapping['status']] = f'{prefix}_status'
    if mapping['price']:
        renames[mapping['price']] = f'{prefix}_price'
    df = df.rename(columns=renames)
    for k in ['sub', 'status', 'price']:
        col = f'{prefix}_{k}'
        if col not in df.columns:
            df[col] = None
    if f'{prefix}_sub' in df.columns:
        df[f'{prefix}_sub'] = df[f'{prefix}_sub'].astype(str).str.strip()
    return df

# -----------------------------
# Streamlit App
# -----------------------------
st.set_page_config(page_title="Order Comparator Dashboard", layout="wide")
st.title("Order Comparator Dashboard")

if 'data_processed' not in st.session_state:
    st.session_state.data_processed = False

# Upload section
with st.expander("Upload Excel Sheets (Old, New, Payout)", expanded=not st.session_state.data_processed):
    col1, col2, col3 = st.columns(3)
    with col1:
        old_file = st.file_uploader("Upload Old Sheet", type=['xlsx', 'xls', 'csv'], key="old_u")
    with col2:
        new_file = st.file_uploader("Upload New Sheet", type=['xlsx', 'xls', 'csv'], key="new_u")
    with col3:
        payout_file = st.file_uploader("Upload Payout Sheet", type=['xlsx', 'xls', 'csv'], key="payout_u")

def read_any(file):
    file.seek(0)
    try:
        return pd.read_excel(file, engine='openpyxl')
    except Exception:
        file.seek(0)
        try:
            return pd.read_csv(file)
        except Exception as e:
            st.error(f"Could not read file: {e}")
            return None

# Process button
if st.button("Run Comparison and Generate Dashboard"):
    if not all([old_file, new_file, payout_file]):
        st.error("Please upload all three files: Old, New, and Payout sheets.")
    else:
        with st.spinner("Processing files and building dashboard..."):
            original_old_df = read_any(old_file)
            original_new_df = read_any(new_file)
            original_payout_df = read_any(payout_file)

            if original_old_df is not None and original_new_df is not None and original_payout_df is not None:
                old_map = ensure_columns(original_old_df)
                new_map = ensure_columns(original_new_df)
                payout_map = ensure_columns(original_payout_df)

                old = normalize_df(original_old_df.copy(), old_map, 'old')
                new = normalize_df(original_new_df.copy(), new_map, 'new')
                payout = normalize_df(original_payout_df.copy(), payout_map, 'payout')

                # Match payout to old
                step1 = payout.merge(old, left_on='payout_sub', right_on='old_sub', how='left')
                payout_comparisons = []
                matched_old_subs = set()
                for _, row in step1.iterrows():
                    sub = str(row.get('payout_sub', '')).strip()
                    if pd.notna(row.get('old_sub')):
                        old_price_val = safe_float(row.get('old_price'))
                        payout_price_val = safe_float(row.get('payout_price'))
                        payout_comparisons.append({
                            'Sub Order No': sub,
                            'Old Status': row.get('old_status'),
                            'New Status': row.get('payout_status'),
                            'Old Price': old_price_val,
                            'New Price': payout_price_val,
                            'Difference': old_price_val - payout_price_val,
                            'Remarks': 'Payout Settlement Amount'
                        })
                        if sub:
                            matched_old_subs.add(sub)

                payout_comp_df = pd.DataFrame(payout_comparisons)

                old_after_payout = old[~old['old_sub'].isin(matched_old_subs)].copy()
                merged_old_new = old_after_payout.merge(new, left_on='old_sub', right_on='new_sub', how='outer', indicator=True)

                comparisons, new_orders_list = [], []
                for _, row in merged_old_new.iterrows():
                    if row['_merge'] == 'both':
                        old_price = safe_float(row.get('old_price'))
                        new_price = safe_float(row.get('new_price'))
                        remark = 'Status & Price Changed'
                        if str(row.get('old_status')).strip() == str(row.get('new_status')).strip():
                            remark = 'Price Difference' if abs(old_price - new_price) > 0.01 else 'No Change'
                        elif abs(old_price - new_price) < 0.01:
                            remark = 'Status Changed'
                        comparisons.append({
                            'Sub Order No': str(row.get('old_sub','')).strip(),
                            'Old Status': row.get('old_status'),
                            'New Status': row.get('new_status'),
                            'Old Price': old_price,
                            'New Price': new_price,
                            'Difference': old_price - new_price,
                            'Remarks': remark
                        })
                    elif row['_merge'] == 'left_only':
                        comparisons.append({
                            'Sub Order No': str(row.get('old_sub','')).strip(),
                            'Old Status': row.get('old_status'),
                            'New Status': None,
                            'Old Price': safe_float(row.get('old_price')),
                            'New Price': None,
                            'Difference': None,
                            'Remarks': 'Missing in New'
                        })
                    elif row['_merge'] == 'right_only':
                        new_orders_list.append({
                            'Sub Order No': str(row.get('new_sub', '')).strip(),
                            'New Status': row.get('new_status'),
                            'New Price': safe_float(row.get('new_price')),
                            'Remarks': 'New Order'
                        })

                old_new_comp_df = pd.DataFrame(comparisons)
                new_orders_df = pd.DataFrame(new_orders_list)
                final_combined_df = pd.concat([payout_comp_df, old_new_comp_df], ignore_index=True).fillna('')

                # Save to session
                st.session_state.data_processed = True
                st.session_state.original_old_df = original_old_df
                st.session_state.original_new_df = original_new_df
                st.session_state.original_payout_df = original_payout_df
                st.session_state.old_map = old_map
                st.session_state.payout_comp_df = payout_comp_df
                st.session_state.new_orders_df = new_orders_df
                st.session_state.final_combined_df = final_combined_df

                # Create Excel bytes
                to_write = io.BytesIO()
                with pd.ExcelWriter(to_write, engine='openpyxl') as writer:
                    original_old_df.to_excel(writer, sheet_name='Original_Old', index=False)
                    original_new_df.to_excel(writer, sheet_name='Original_New', index=False)
                    original_payout_df.to_excel(writer, sheet_name='Original_Payout', index=False)
                    final_combined_df.to_excel(writer, sheet_name='Final_Combined', index=False)
                    payout_comp_df.to_excel(writer, sheet_name='Payout_Comparison', index=False)
                    old_new_comp_df.to_excel(writer, sheet_name='OldNew_Comparison', index=False)
                    new_orders_df.to_excel(writer, sheet_name='New_Orders', index=False)
                st.session_state.excel_data = to_write.getvalue()

# Dashboard rendering
if st.session_state.data_processed:
    original_old_df = st.session_state.original_old_df
    original_new_df = st.session_state.original_new_df
    original_payout_df = st.session_state.original_payout_df
    old_map = st.session_state.old_map
    payout_comp_df = st.session_state.payout_comp_df
    new_orders_df = st.session_state.new_orders_df
    final_combined_df = st.session_state.final_combined_df

    old_orders_count = len(original_old_df)
    old_orders_sum = original_old_df[old_map['price']].apply(safe_float).sum() if old_map.get('price') else 0.0
    payout_orders_count = len(payout_comp_df)
    payout_orders_sum = payout_comp_df['New Price'].apply(safe_float).sum() if 'New Price' in payout_comp_df else 0.0
    pending_old_count = old_orders_count - payout_orders_count
    pending_old_sum = old_orders_sum - payout_orders_sum
    new_orders_count = len(new_orders_df)
    new_orders_sum = new_orders_df['New Price'].apply(safe_float).sum() if 'New Price' in new_orders_df else 0.0
    total_pending_count = pending_old_count + new_orders_count
    total_pending_sum = pending_old_sum + new_orders_sum
    other_adjustments_sum = final_combined_df['Difference'].replace('', 0).fillna(0).apply(safe_float).sum()
    final_net_due = total_pending_sum - other_adjustments_sum

    # cards CSS
    st.markdown("""
    <style>
    .card {
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        background: linear-gradient(180deg,#ffffff,#fbfbfb);
        margin-bottom: 12px;
    }
    .card h4 { margin:0; font-size:15px; color:#222; }
    .card .big { font-size:28px; font-weight:700; margin-top:6px; }
    .card .small { font-size:13px; color:#2d6a4f; margin-top:4px; }
    .cards-row { display:flex; gap:12px; flex-wrap:wrap; }
    </style>
    """, unsafe_allow_html=True)

    st.subheader("Old Accounts")
    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        st.markdown(f"""
            <div class="card">
                <h4>📂 Total Old Orders</h4>
                <div class="big">{old_orders_count} Orders</div>
                <div class="small">₹{old_orders_sum:,.2f}</div>
            </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
            <div class="card">
                <h4>💳 Paid Orders</h4>
                <div class="big">{payout_orders_count} Orders</div>
                <div class="small">₹{payout_orders_sum:,.2f}</div>
            </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
            <div class="card">
                <h4>🕒 Pending Old Orders</h4>
                <div class="big">{pending_old_count} Orders</div>
                <div class="small">₹{pending_old_sum:,.2f}</div>
            </div>
        """, unsafe_allow_html=True)

    st.subheader("New Accounts")
    st.markdown(f"""
        <div class="cards-row">
            <div class="card" style="flex:1;">
                <h4>🆕 Total New Orders</h4>
                <div class="big">{new_orders_count} Orders</div>
                <div class="small">₹{new_orders_sum:,.2f}</div>
            </div>
            <div class="card" style="flex:1;">
                <h4>📦 Total Pending</h4>
                <div class="big">{total_pending_count} Orders</div>
                <div class="small">₹{total_pending_sum:,.2f}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.subheader("Final Due Amount")
    st.markdown(f"""
        <div class="cards-row">
            <div class="card" style="flex:1;">
                <h4>⚖️ Other Adjustments</h4>
                <div class="big">{len(final_combined_df)} Entries</div>
                <div class="small">₹{other_adjustments_sum:,.2f}</div>
            </div>
            <div class="card" style="flex:1;">
                <h4>✅ Final Net Due</h4>
                <div class="big">₹{final_net_due:,.2f}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Final Combined Data Table
    st.subheader("Final Combined Data Table")
    if 'Remarks' not in final_combined_df.columns:
        final_combined_df['Remarks'] = ''

    # use ASCII-safe placeholder '-' for empty remarks
    remarks_options = list(final_combined_df['Remarks'].replace('', '-').unique())
    selected_remarks = st.multiselect('Filter by Remarks:', remarks_options, default=remarks_options)
    selected_real = [r if r != '-' else '' for r in selected_remarks]

    filtered_df = final_combined_df[final_combined_df['Remarks'].isin(selected_real)]
    filtered_df = filtered_df.reset_index(drop=True)
    filtered_df.index = filtered_df.index + 1
    filtered_df = filtered_df.rename_axis('Sr. No.').reset_index()

    st.dataframe(filtered_df.fillna(''), use_container_width=True)

    # total difference
    total_difference_filtered = 0.0
    if 'Difference' in filtered_df.columns:
        try:
            total_difference_filtered = pd.to_numeric(filtered_df['Difference'], errors='coerce').fillna(0).sum()
        except Exception:
            total_difference_filtered = filtered_df['Difference'].apply(safe_float).sum()

    st.markdown(f"<h3 style='text-align: right; color: blue;'>Total Difference: ₹{total_difference_filtered:,.2f}</h3>", unsafe_allow_html=True)
    st.markdown("---")

    # Download buttons
    col1, col2 = st.columns(2)
    with col1:
        if not filtered_df.empty:
            pdf_bytes = dataframe_to_pdf_bytes(filtered_df.fillna(''), total_difference_filtered, title="Final Combined Data")
            st.download_button(
                label="Download Table as PDF",
                data=pdf_bytes,
                file_name=f"Filtered_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                mime="application/pdf"
            )
        else:
            st.info("Filtered table is empty — PDF unavailable.")
    with col2:
        st.download_button(
            label="Download Full Report as Excel (includes original uploaded sheets)",
            data=st.session_state.excel_data,
            file_name=f"order_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    st.caption("Excel now includes Original_Old / Original_New / Original_Payout sheets exactly as uploaded.")

# End of script
