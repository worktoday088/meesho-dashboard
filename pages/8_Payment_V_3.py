import streamlit as st
import pandas as pd
import io
from datetime import datetime
from fpdf import FPDF

# Helper function to convert dataframe to PDF
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Final Combined Report', 0, 1, 'C')

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def dataframe_to_pdf(self, df):
        self.add_page()
        self.set_font("Arial", size=8)
        
        # Column Headers
        self.set_font('Arial', 'B', 8)
        col_widths = {'Sr. No.': 15, 'Sub Order No': 40, 'Old Status': 25, 'New Status': 25, 'Old Price': 20, 'New Price': 20, 'Difference': 20, 'Remarks': 25}
        
        header = list(df.columns)
        for col_name in header:
            self.cell(col_widths.get(col_name, 25), 10, col_name, 1, 0, 'C')
        self.ln()
        
        # Data
        self.set_font('Arial', '', 8)
        for index, row in df.iterrows():
            for col_name in header:
                cell_text = str(row[col_name])
                self.cell(col_widths.get(col_name, 25), 10, cell_text, 1)
            self.ln()

def dataframe_to_pdf_bytes(df):
    pdf = PDF()
    pdf.dataframe_to_pdf(df)
    return pdf.output(dest='S').encode('latin-1')

# Function to find column names case-insensitively
def detect_column(df, candidates):
    cols = list(df.columns)
    low_cols = [c.lower().strip() for c in cols]
    for cand in candidates:
        cand_low = cand.lower().strip()
        for i, c in enumerate(low_cols):
            if cand_low in c:
                return cols[i]
    return None

def ensure_columns(df):
    mapping = {}
    mapping['sub'] = detect_column(df, ['sub order no', 'sub order id', 'suborder'])
    mapping['status'] = detect_column(df, ['live order status', 'order status', 'status'])
    mapping['price'] = detect_column(df, ['final settlement amount', 'final amount', 'settlement amount', 'amount', 'price', 'new price'])
    return mapping

# Safely convert to float
def safe_float(x):
    try:
        if pd.isna(x): return 0.0
        s = str(x).strip().replace(',', '')
        if s.startswith('₹'): s = s[1:]
        if s.startswith('-') and '₹' in s: s = '-' + s.replace('₹','').replace('-','')
        return float(s)
    except (ValueError, TypeError):
        return 0.0

# Normalize dataframe columns
def normalize_df(df, mapping, prefix):
    df = df.copy()
    renames = {}
    if mapping['sub']: renames[mapping['sub']] = f'{prefix}_sub'
    if mapping['status']: renames[mapping['status']] = f'{prefix}_status'
    if mapping['price']: renames[mapping['price']] = f'{prefix}_price'
    df = df.rename(columns=renames)
    for k in ['sub', 'status', 'price']:
        col = f'{prefix}_{k}'
        if col not in df.columns:
            df[col] = None
    if f'{prefix}_sub' in df.columns:
        df[f'{prefix}_sub'] = df[f'{prefix}_sub'].astype(str).str.strip()
    return df

st.set_page_config(page_title="Order Comparator Dashboard", layout="wide")
st.title("Order Comparator Dashboard")

# Initialize session_state
if 'data_processed' not in st.session_state:
    st.session_state.data_processed = False

# --- UI for File Upload ---
with st.expander("Upload Excel Sheets (Old, New, Payout)", expanded=not st.session_state.data_processed):
    col1, col2, col3 = st.columns(3)
    with col1:
        old_file = st.file_uploader("Upload Old Sheet", type=['xlsx', 'xls', 'csv'], key="old")
    with col2:
        new_file = st.file_uploader("Upload New Sheet", type=['xlsx', 'xls', 'csv'], key="new")
    with col3:
        payout_file = st.file_uploader("Upload Payout Sheet", type=['xlsx', 'xls', 'csv'], key="payout")

# Process button
if st.button("Run Comparison and Generate Dashboard"):
    if not all([old_file, new_file, payout_file]):
        st.error("Please upload all three files: Old, New, and Payout sheets.")
    else:
        with st.spinner("Processing files and building dashboard..."):
            def read_any(file):
                file.seek(0)
                try: return pd.read_excel(file, engine='openpyxl')
                except Exception:
                    file.seek(0)
                    try: return pd.read_csv(file)
                    except Exception as e:
                        st.error(f"Could not read file: {e}")
                        return None

            original_old_df = read_any(old_file)
            new_df = read_any(new_file)
            payout_df = read_any(payout_file)

            if original_old_df is not None and new_df is not None and payout_df is not None:
                old_map = ensure_columns(original_old_df)
                new_map = ensure_columns(new_df)
                payout_map = ensure_columns(payout_df)
                
                old = normalize_df(original_old_df.copy(), old_map, 'old')
                new = normalize_df(new_df, new_map, 'new')
                payout = normalize_df(payout_df, payout_map, 'payout')

                step1 = payout.merge(old, left_on='payout_sub', right_on='old_sub', how='left')
                payout_comparisons = []
                matched_old_subs = set()

                for _, row in step1.iterrows():
                    sub = str(row.get('payout_sub', '')).strip()
                    if pd.notna(row.get('old_sub')):
                        payout_comparisons.append({
                            'Sub Order No': sub, 'Old Status': row.get('old_status'), 'New Status': row.get('payout_status'),
                            'Old Price': safe_float(row.get('old_price')), 'New Price': safe_float(row.get('payout_price')), 
                            'Difference': safe_float(row.get('old_price')) - safe_float(row.get('payout_price')),
                            'Remarks': 'Payout Settlement Amount'
                        })
                        if sub: matched_old_subs.add(sub)
                
                payout_comp_df = pd.DataFrame(payout_comparisons)
                old_after_payout = old[~old['old_sub'].isin(matched_old_subs)].copy()
                merged_old_new = old_after_payout.merge(new, left_on='old_sub', right_on='new_sub', how='outer', indicator=True)
                
                comparisons, new_orders_list = [], []
                for _, row in merged_old_new.iterrows():
                    if row['_merge'] == 'both':
                        old_price, new_price = safe_float(row.get('old_price')), safe_float(row.get('new_price'))
                        remark = 'Status & Price Changed'
                        if str(row.get('old_status')).strip() == str(row.get('new_status')).strip():
                           remark = 'Price Difference' if abs(old_price - new_price) > 0.01 else 'No Change'
                        elif abs(old_price - new_price) < 0.01:
                            remark = 'Status Changed'
                        comparisons.append({
                            'Sub Order No': str(row.get('old_sub','')).strip(), 'Old Status': row.get('old_status'), 'New Status': row.get('new_status'),
                            'Old Price': old_price, 'New Price': new_price, 'Difference': old_price - new_price, 'Remarks': remark
                        })
                    elif row['_merge'] == 'left_only':
                        comparisons.append({
                            'Sub Order No': str(row.get('old_sub','')).strip(), 'Old Status': row.get('old_status'), 'New Status': None,
                            'Old Price': safe_float(row.get('old_price')), 'New Price': None, 'Difference': None, 'Remarks': 'Missing in New'
                        })
                    elif row['_merge'] == 'right_only':
                        new_orders_list.append({
                            'Sub Order No': str(row.get('new_sub', '')).strip(), 'New Status': row.get('new_status'),
                            'New Price': safe_float(row.get('new_price')), 'Remarks': 'New Order'
                        })

                old_new_comp_df = pd.DataFrame(comparisons)
                new_orders_df = pd.DataFrame(new_orders_list)
                final_combined_df = pd.concat([payout_comp_df, old_new_comp_df], ignore_index=True)
                
                # Store everything in session state
                st.session_state.data_processed = True
                st.session_state.original_old_df = original_old_df
                st.session_state.old_map = old_map
                st.session_state.payout_comp_df = payout_comp_df
                st.session_state.new_orders_df = new_orders_df
                st.session_state.final_combined_df = final_combined_df
                
                # Excel data for download
                to_write = io.BytesIO()
                with pd.ExcelWriter(to_write, engine='openpyxl') as writer:
                    final_combined_df.to_excel(writer, sheet_name='Final_Combined', index=False)
                    payout_comp_df.to_excel(writer, sheet_name='Payout_Comparison', index=False)
                    old_new_comp_df.to_excel(writer, sheet_name='OldNew_Comparison', index=False)
                    new_orders_df.to_excel(writer, sheet_name='New_Orders', index=False)
                st.session_state.excel_data = to_write.getvalue()

# --- Display Dashboard if data is processed ---
if st.session_state.data_processed:
    original_old_df = st.session_state.original_old_df
    old_map = st.session_state.old_map
    payout_comp_df = st.session_state.payout_comp_df
    new_orders_df = st.session_state.new_orders_df
    final_combined_df = st.session_state.final_combined_df

    # --- Calculations ---
    old_orders_count = len(original_old_df)
    old_orders_sum = original_old_df[old_map['price']].apply(safe_float).sum()
    payout_orders_count = len(payout_comp_df)
    payout_orders_sum = payout_comp_df['New Price'].sum()
    pending_old_count = old_orders_count - payout_orders_count
    pending_old_sum = old_orders_sum - payout_orders_sum
    new_orders_count = len(new_orders_df)
    new_orders_sum = new_orders_df['New Price'].sum() if 'New Price' in new_orders_df else 0
    total_pending_count = pending_old_count + new_orders_count
    total_pending_sum = pending_old_sum + new_orders_sum
    other_adjustments_sum = final_combined_df['Difference'].sum()
    final_net_due = total_pending_sum - other_adjustments_sum
    
    # --- Display Metrics ---
    st.subheader("पुराना हिसाब (Old Accounts)")
    c1, c2, c3 = st.columns(3)
    c1.metric("कुल पुराने ऑर्डर", f"{old_orders_count} ऑर्डर्स", f"₹{old_orders_sum:,.2f}")
    c2.metric("भुगतान हुए ऑर्डर", f"{payout_orders_count} ऑर्डर्स", f"₹{payout_orders_sum:,.2f}")
    c3.metric("बकाया पुराने ऑर्डर", f"{pending_old_count} ऑर्डर्स", f"₹{pending_old_sum:,.2f}")
    
    st.subheader("नया हिसाब (New Accounts)")
    st.metric("कुल नए ऑर्डर", f"{new_orders_count} ऑर्डर्स", f"₹{new_orders_sum:,.2f}")

    st.subheader("कुल बकाया (Total Outstanding)")
    st.metric("कुल बकाया ऑर्डर", f"{total_pending_count} ऑर्डर्स", f"₹{total_pending_sum:,.2f}")

    st.subheader("अंतिम देय राशि (Final Due Amount)")
    c1, c2 = st.columns(2)
    c1.metric("अन्य समायोजन", f"{len(final_combined_df)} एंट्री", f"₹{other_adjustments_sum:,.2f}")
    c2.metric("अंतिम शुद्ध देय राशि", f"₹{final_net_due:,.2f}")
    st.markdown("---")

    # --- Interactive Table ---
    st.subheader("Final Combined Data Table")
    
    remarks_options = list(final_combined_df['Remarks'].dropna().unique())
    selected_remarks = st.multiselect('Filter by Remarks:', remarks_options, default=remarks_options)

    filtered_df = final_combined_df[final_combined_df['Remarks'].isin(selected_remarks)]
    
    filtered_df = filtered_df.reset_index(drop=True)
    filtered_df.index = filtered_df.index + 1
    filtered_df = filtered_df.rename_axis('Sr. No.').reset_index()

    st.dataframe(filtered_df.fillna(''), use_container_width=True)

    # --- TOTAL OF FILTERED DIFFERENCE ---
    total_difference_filtered = filtered_df['Difference'].sum()
    st.markdown(f"<h3 style='text-align: right; color: blue;'>कुल अंतर: ₹{total_difference_filtered:,.2f}</h3>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # --- Download Buttons ---
    col1, col2 = st.columns(2)
    with col1:
        if not filtered_df.empty:
            st.download_button(
                label="Download Table as PDF",
                data=dataframe_to_pdf_bytes(filtered_df),
                file_name=f"Filtered_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                mime="application/pdf"
            )
    with col2:
        st.download_button(
            label="Download Full Report as Excel",
            data=st.session_state.excel_data,
            file_name=f"order_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
