# 📦 Meesho Order Analysis Dashboard — Final v15
# Updates:
# 1. Recovery Logic: Uses 'Recovery' column (summing absolute values).
# 2. Claims Logic: Added 'Claims' column, filter, and display cards.
# 3. Ads Logic: Added Total Orders & Per Order Cost.
# 4. RTO Logic: Restored 3-column calculation (Shipping Charge, GST, RTO Amount).
# 5. Order Source: Added Filter next to Date Range.
# 6. PDF Removed: Only Excel export remains.
# Date: 2026-01-29

import os
import re
import math
from io import BytesIO
from datetime import datetime, date

import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
from PIL import Image

__VERSION__ = "Power By Rehan — v15 (Recovery/Claims/RTO Fix)"

# ---------------- PAGE SETUP ----------------
st.set_page_config(layout="wide", page_title=f"📦 Meesho Dashboard — {__VERSION__}")
st.title(f"📦 Meesho Order Analysis Dashboard — {__VERSION__}")
st.caption("New Logic: Recovery (Abs) | Claims | Order Source | RTO (3-Col) | Ads Per Order")

# ---------------- HELPERS ----------------
def extract_supplier_id_from_filename(filename: str) -> str:
    if not filename: return ""
    base = os.path.basename(filename)
    name, _ = os.path.splitext(base)
    if "_" in name: return name.split("_", 1)[0]
    m = re.match(r"^(\d+)", name)
    return m.group(1) if m else name

def _detect_col(df: pd.DataFrame, *keyword_groups):
    if df is None or df.empty: return None
    cols = list(df.columns)
    low = [str(c).lower() for c in cols]
    for i, c in enumerate(cols):
        lc = low[i]
        for grp in keyword_groups:
            if all(k in lc for k in grp): return c
    return None

@st.cache_data(show_spinner=False)
def _read_uploaded(file):
    name = file.name.lower()
    if name.endswith('.csv'): return pd.read_csv(file), None
    xls = pd.ExcelFile(file)
    sheet_map = {s.lower(): s for s in xls.sheet_names}
    orders_sheet = sheet_map.get('order payments', xls.sheet_names[0])
    df_orders = pd.read_excel(xls, sheet_name=orders_sheet)
    df_ads = pd.read_excel(xls, sheet_name=sheet_map['ads cost']) if 'ads cost' in sheet_map else None
    return df_orders, df_ads

def _format_display(v):
    try:
        if isinstance(v, (int, np.integer)): return f"{v:,}"
        if isinstance(v, (float, np.floating)): return f"₹{v:,.2f}"
        return str(v)
    except: return str(v)

def html_escape(s):
    import html
    return html.escape(str(s)) if s is not None else ""

# --- CARD HTML ---
def _card_html(title, value, bg="#0d47a1", icon="₹", tooltip=None):
    tt_attr = f'title="{html_escape(tooltip)}"' if tooltip else ""
    tt_icon = '<span style="margin-left:5px;cursor:help;font-size:11px;border:1px solid rgba(255,255,255,0.5);border-radius:50%;width:16px;height:16px;display:inline-flex;align-items:center;justify-content:center;">?</span>' if tooltip else ""
    return f"<div {tt_attr} style='background:{bg};padding:14px;border-radius:12px;color:white;text-align:center'><div style='font-size:14px;opacity:0.95;display:flex;gap:6px;align-items:center;justify-content:center'><span style='font-weight:700'>{icon}</span><span style='font-weight:700'>{title}</span>{tt_icon}</div><div style='font-size:22px;font-weight:800;margin-top:6px'>{_format_display(value)}</div></div>"

# ---------------- SIDEBAR ----------------
st.sidebar.header("⚙️ Controls")

if 'sku_groups' not in st.session_state: st.session_state['sku_groups'] = []

supplier_name_input = st.sidebar.text_input("🔹 Supplier Name", value="")
up = st.sidebar.file_uploader("Upload Excel/CSV", type=["xlsx", "csv"])

if up is None:
    st.info("Please upload your Meesho Excel File.")
    st.stop()

supplier_id_auto = extract_supplier_id_from_filename(up.name)
_supplier_label = f"{supplier_name_input} ({supplier_id_auto})" if supplier_id_auto else supplier_name_input
st.markdown(f"<div style='background-color:#FFEB3B;padding:10px;border-radius:10px;text-align:center;color:black;font-weight:bold;margin-bottom:10px'>📌 Analyzing: {_supplier_label}</div>", unsafe_allow_html=True)

if st.sidebar.button("🔄 Reset Filters"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state['sku_groups'] = []
    st.rerun()

# ---------------- DATA LOAD ----------------
try:
    orders_df, ads_df = _read_uploaded(up)
except Exception as e:
    st.error(f"Error reading file: {e}")
    st.stop()

orders_df.columns = [str(c).strip() for c in orders_df.columns]
if ads_df is not None: ads_df.columns = [str(c).strip() for c in ads_df.columns]

# Detect Columns
status_col = _detect_col(orders_df, ("live","status"), ("status",))
order_date_col = _detect_col(orders_df, ("order","date"))
dispatch_date_col = _detect_col(orders_df, ("dispatch","date"))
sku_col = _detect_col(orders_df, ("supplier","sku"), ("sku",))
settle_amt_col = _detect_col(orders_df, ("final","settlement"), ("settlement","amount"))
exchange_loss_col = _detect_col(orders_df, ("exchange","loss"))
profit_amt_col = _detect_col(orders_df, ("profit",))
catalog_id_col = _detect_col(orders_df, ("catalog","id"), ("catalog_id",))

# NEW COLUMNS
recovery_col = _detect_col(orders_df, ("recovery",))
claims_col = _detect_col(orders_df, ("claims",))
order_source_col = _detect_col(orders_df, ("order","source"))

# RTO Logic Cols
listing_price_col = _detect_col(orders_df, ("listing","price"))
total_sale_col = _detect_col(orders_df, ("total","sale","amount"))

if not status_col:
    st.error("Status column not found!")
    st.stop()

# Date Parsing
for c in [order_date_col, dispatch_date_col]:
    if c and c in orders_df.columns:
        orders_df[c] = pd.to_datetime(orders_df[c], errors='coerce')

# ---------------- FILTERS ----------------
with st.sidebar.expander("🎛️ Advanced Filters", expanded=True):
    # 1. Status
    status_opts = ['All', 'Delivered', 'Return', 'RTO', 'Exchange', 'Cancelled', 'Shipped', ""]
    sel_statuses = st.multiselect("Status", status_opts, default=['All'])
    
    # 2. SKU Grouping
    if sku_col:
        skus = sorted([str(x) for x in orders_df[sku_col].dropna().unique().tolist()])
        sku_search_q = st.text_input("Search SKU keyword", key='sku_search_q')
        new_group_name = st.text_input("Group name (Optional)", key='sku_new_group_name')

        c_grp1, c_grp2 = st.columns(2)
        with c_grp1:
            if st.button("➕ Add Group"):
                pattern = (sku_search_q or new_group_name).strip()
                if pattern:
                    matched = [s for s in skus if pattern.lower() in s.lower()]
                    if matched:
                        st.session_state['sku_groups'].append({'name': new_group_name or pattern, 'skus': matched})
                        st.rerun()
        with c_grp2:
            if st.button("🧹 Clear All"):
                st.session_state['sku_groups'] = []
                st.rerun()
        
        # Group Selection
        active_skus = []
        if st.session_state['sku_groups']:
            grp_labels = [f"{g['name']} ({len(g['skus'])})" for g in st.session_state['sku_groups']]
            sel_grps = st.multiselect("Select Groups", grp_labels)
            for label in sel_grps:
                g_name = label.rsplit(" (", 1)[0]
                for g in st.session_state['sku_groups']:
                    if g['name'] == g_name:
                        active_skus.extend(g['skus'])
        
        manual_matches = [s for s in skus if sku_search_q.lower() in s.lower()] if sku_search_q else []
        final_pool = sorted(list(set(active_skus + manual_matches)))
        sel_skus = st.multiselect("Selected SKUs", skus, default=final_pool)
    else:
        sel_skus = None
    
    # 3. Claims & Recovery Filters (Requested)
    if claims_col:
        claims_opts = sorted([str(x) for x in orders_df[claims_col].dropna().unique().tolist()])
        st.markdown("---")
        sel_claims = st.multiselect("📂 Filter Claims", claims_opts)
    else:
        sel_claims = None

    if recovery_col:
        rec_opts = sorted([str(x) for x in orders_df[recovery_col].dropna().unique().tolist()])
        sel_recovery = st.multiselect("📂 Filter Recovery", rec_opts)
    else:
        sel_recovery = None

    # 4. Catalog ID
    if catalog_id_col:
        st.markdown("---")
        cats = sorted([str(x) for x in orders_df[catalog_id_col].dropna().unique().tolist()])
        sel_cats = st.multiselect("📂 Catalog ID", cats)
    else:
        sel_cats = None

with st.sidebar.expander("📅 Date & Source Filters", expanded=True):
    # Order Date
    date_range = None
    if order_date_col:
        dmin, dmax = orders_df[order_date_col].min(), orders_df[order_date_col].max()
        if pd.notna(dmin):
            date_range = st.date_input("Order Date Range", [dmin, dmax])
    
    # NEW: Order Source Filter (Next to Date)
    sel_source = None
    if order_source_col:
        sources = sorted([str(x) for x in orders_df[order_source_col].dropna().unique().tolist()])
        sel_source = st.multiselect("Order Source", sources, default=None, help="Leave empty for All")

    # Dispatch Date
    dispatch_range = None
    if dispatch_date_col:
        ddmin, ddmax = orders_df[dispatch_date_col].min(), orders_df[dispatch_date_col].max()
        if pd.notna(ddmin):
            dispatch_range = st.date_input("Dispatch Date Range", [ddmin, ddmax])

# ---------------- APPLY FILTERS ----------------
df_f = orders_df.copy()

if order_date_col and date_range and len(date_range)==2:
    df_f = df_f[(df_f[order_date_col] >= pd.Timestamp(date_range[0])) & (df_f[order_date_col] <= pd.Timestamp(date_range[1]))]

if dispatch_date_col and dispatch_range and len(dispatch_range)==2:
    df_f = df_f[(df_f[dispatch_date_col] >= pd.Timestamp(dispatch_range[0])) & (df_f[dispatch_date_col] <= pd.Timestamp(dispatch_range[1]))]

if order_source_col and sel_source:
    df_f = df_f[df_f[order_source_col].astype(str).isin(sel_source)]

if sku_col and sel_skus:
    df_f = df_f[df_f[sku_col].astype(str).isin(sel_skus)]

if catalog_id_col and sel_cats:
    df_f = df_f[df_f[catalog_id_col].astype(str).isin(sel_cats)]

if claims_col and sel_claims:
    df_f = df_f[df_f[claims_col].astype(str).isin(sel_claims)]

if recovery_col and sel_recovery:
    df_f = df_f[df_f[recovery_col].astype(str).isin(sel_recovery)]

if 'All' not in sel_statuses:
    clean_stats = [s.upper() for s in sel_statuses if s]
    include_blank = "" in sel_statuses
    if clean_stats and include_blank:
        mask = df_f[status_col].astype(str).str.upper().isin(clean_stats) | df_f[status_col].isna()
    elif clean_stats:
        mask = df_f[status_col].astype(str).str.upper().isin(clean_stats)
    else:
        mask = df_f[status_col].isna()
    df_f = df_f[mask]

# ---------------- RTO LOGIC (3-COLUMNS RESTORED) ----------------
def _ensure_rto(df):
    if listing_price_col and total_sale_col:
        mask = df[status_col].astype(str).str.upper() == 'RTO'
        
        # Col 1: Shipping Charge (Total Sale - Listing)
        df.loc[mask, 'Shipping Charge'] = pd.to_numeric(df.loc[mask, total_sale_col], errors='coerce').fillna(0) - pd.to_numeric(df.loc[mask, listing_price_col], errors='coerce').fillna(0)
        
        # Col 2: Shipping GST (approx 18%)
        df.loc[mask, 'Shipping GST'] = df.loc[mask, 'Shipping Charge'] * 0.18
        
        # Col 3: RTO Amount (Listing - GST)
        df.loc[mask, 'RTO Amount'] = pd.to_numeric(df.loc[mask, listing_price_col], errors='coerce').fillna(0) - df.loc[mask, 'Shipping GST']
        
    return df

df_f = _ensure_rto(df_f)

# Counts
counts = df_f[status_col].astype(str).str.upper().value_counts()
c_del = counts.get('DELIVERED', 0)
c_ret = counts.get('RETURN', 0)
c_exc = counts.get('EXCHANGE', 0)
c_can = counts.get('CANCELLED', 0)
c_shp = counts.get('SHIPPED', 0)
c_rto = counts.get('RTO', 0)

# Claims Count
c_claim = df_f[claims_col].count() if claims_col else 0
# Recovery Count
c_rec = df_f[recovery_col].count() if recovery_col else 0

total_rows = len(df_f)

# Card Row 1
status_labels = [('✅ Delivered', c_del, '#2e7d32'), ('↩️ Return', c_ret, '#c62828'), 
                 ('🔄 Exchange', c_exc, '#f57c00'), ('❌ Cancelled', c_can, '#616161'),
                 ('🚚 Shipped', c_shp, '#1565c0'), ('📪 RTO', c_rto, '#8e24aa'),
                 ('🤕 Claims', c_claim, '#F9A825'), ('📊 Total', total_rows, '#0d47a1')]

cols = st.columns(8)
for i, (l, v, c) in enumerate(status_labels):
    cols[i].markdown(f"<div style='background:{c};padding:8px;border-radius:8px;text-align:center;color:white;font-size:12px;'><b>{l}</b><br><span style='font-size:18px'>{v}</span></div>", unsafe_allow_html=True)

# ---------------- FINANCIALS ----------------
st.subheader("₹ Financial Summary")
if settle_amt_col:
    df_f[settle_amt_col] = pd.to_numeric(df_f[settle_amt_col], errors='coerce').fillna(0)
    
    def get_sum(s): return df_f[df_f[status_col].astype(str).str.upper() == s][settle_amt_col].sum()
    
    a_del = get_sum('DELIVERED')
    a_exc = get_sum('EXCHANGE')
    a_can = get_sum('CANCELLED')
    a_ret = get_sum('RETURN')
    a_shp = get_sum('SHIPPED')
    
    # RTO Amount from 3-column logic
    a_rto = df_f[df_f[status_col].astype(str).str.upper() == 'RTO']['RTO Amount'].sum() if 'RTO Amount' in df_f.columns else 0

    # NEW: Claims Amount (Sum of Claims column)
    a_claims = pd.to_numeric(df_f[claims_col], errors='coerce').fillna(0).sum() if claims_col else 0
    
    # NEW: Recovery Amount (Sum of Recovery column - ABSOLUTE VALUE)
    raw_rec = pd.to_numeric(df_f[recovery_col], errors='coerce').fillna(0).sum() if recovery_col else 0
    a_rec = abs(raw_rec) # As requested: -100 becomes 100

    shipped_with_total = (a_del + a_can + a_shp) - (abs(a_ret) + abs(a_exc))
    u_total = (a_del + a_exc + a_can) - abs(a_ret)

    tt_ship = "Delivered + Cancelled + Shipped - (Return + Exchange)"
    tt_tot = "Delivered + Exchange + Cancelled - Return"

    r1 = st.columns(5)
    r1[0].markdown(_card_html("Delivered ₹", a_del, "#1b5e20"), unsafe_allow_html=True)
    r1[1].markdown(_card_html("Exchange ₹", a_exc, "#e65100"), unsafe_allow_html=True)
    r1[2].markdown(_card_html("Cancelled ₹", a_can, "#455a64"), unsafe_allow_html=True)
    r1[3].markdown(_card_html("Return ₹", a_ret, "#b71c1c"), unsafe_allow_html=True)
    r1[4].markdown(_card_html("RTO ₹", a_rto, "#6a1b9a"), unsafe_allow_html=True)

    r2 = st.columns(5)
    r2[0].markdown(_card_html("Shipping ₹", a_shp, "#0b3d91"), unsafe_allow_html=True)
    r2[1].markdown(_card_html("Recovery ₹", a_rec, "#546e7a"), unsafe_allow_html=True)
    r2[2].markdown(_card_html("Claims ₹", a_claims, "#F9A825"), unsafe_allow_html=True)
    r2[3].markdown(_card_html("Shipped Total", shipped_with_total, "#0b3d91", "🚚", tt_ship), unsafe_allow_html=True)
    r2[4].markdown(_card_html("Total Amount", u_total, "#0d47a1", "🧾", tt_tot), unsafe_allow_html=True)

    with st.expander("ℹ️ Click here to see Calculation Formulas (Mobile Friendly)"):
        st.markdown(f"""
        **Shipped With Total:** `(Delivered + Cancelled + Shipped) - (Return + Exchange)`
        **Total Amount:** `(Delivered + Exchange + Cancelled) - Return Amount`
        **Recovery:** Sum of 'Recovery' column (converted to Positive).
        **Claims:** Sum of 'Claims' column.
        """)

# ---------------- PROFIT ----------------
st.markdown("---")
st.subheader("💹 Profit Analysis")
profit_val = pd.to_numeric(df_f[profit_amt_col], errors='coerce').sum() if profit_amt_col in df_f.columns else 0.0
exc_loss_val = pd.to_numeric(df_f[exchange_loss_col], errors='coerce').sum() if exchange_loss_col in df_f.columns else 0.0
net_profit = profit_val - (abs(a_ret) + abs(exc_loss_val))

p1, p2, p3, p4 = st.columns(4)
p1.markdown(_card_html("Profit Sum", profit_val, "#1b5e20", "💹"), unsafe_allow_html=True)
p2.markdown(_card_html("Return Loss", abs(a_ret), "#b71c1c", "➖"), unsafe_allow_html=True)
p3.markdown(_card_html("Exchange Loss", exc_loss_val, "#f57c00", "🔄"), unsafe_allow_html=True)
p4.markdown(_card_html("Net Profit", net_profit, "#0d47a1", "🧮"), unsafe_allow_html=True)

# ---------------- RETURN % ----------------
st.markdown("---")
st.subheader("📊 Return & Exchange Percentage")

if c_del > 0:
    ret_pct = (c_ret / c_del) * 100
    exc_pct = (c_exc / c_del) * 100
else:
    ret_pct = 0
    exc_pct = 0

rp1, rp2, rp3 = st.columns(3)
rp1.markdown(f"<div style='background:#1565c0;padding:16px;border-radius:12px;color:white'><div style='font-size:18px'>Delivered</div><div style='font-size:28px'>{c_del}</div><div>100%</div></div>", unsafe_allow_html=True)
rp2.markdown(f"<div style='background:#c62828;padding:16px;border-radius:12px;color:white'><div style='font-size:18px'>Return</div><div style='font-size:28px'>{c_ret}</div><div>{ret_pct:.2f}%</div></div>", unsafe_allow_html=True)
rp3.markdown(f"<div style='background:#ef6c00;padding:16px;border-radius:12px;color:white'><div style='font-size:18px'>Exchange</div><div style='font-size:28px'>{c_exc}</div><div>{exc_pct:.2f}%</div></div>", unsafe_allow_html=True)

# ---------------- ADS ANALYSIS (UPDATED) ----------------
st.markdown("---")
st.subheader("📢 Ads Cost Analysis")
ads_table = None

if ads_df is not None and not ads_df.empty:
    if 'Deduction Duration' in ads_df.columns and 'Total Ads Cost' in ads_df.columns:
        ads_df['Total Ads Cost'] = pd.to_numeric(ads_df['Total Ads Cost'], errors='coerce').fillna(0)
        ads_df['Deduction Duration'] = pd.to_datetime(ads_df['Deduction Duration'], errors='coerce').dt.date
        
        # Ads Date Filter
        min_a, max_a = ads_df['Deduction Duration'].min(), ads_df['Deduction Duration'].max()
        ads_rng = st.date_input("Ads Date Range", [min_a, max_a])
        
        if len(ads_rng) == 2:
            ads_f = ads_df[(ads_df['Deduction Duration'] >= ads_rng[0]) & (ads_df['Deduction Duration'] <= ads_rng[1])].copy()
            
            # --- ADS METRICS ---
            ads_total = ads_f['Total Ads Cost'].sum()
            
            # 1. Calculate Total Orders for this period (using main filtered df or based on date match)
            # Strategy: Sum orders from df_f (since it's already date filtered if user selected same dates)
            # OR better: Count orders occurring on the dates present in ads_f to be precise
            
            # Aggregate orders by date from main dataframe
            daily_orders = df_f.groupby(df_f[order_date_col].dt.date).size().reset_index(name='Daily Orders')
            daily_orders.columns = ['Deduction Duration', 'Daily Orders']
            
            # Merge to calculate per day
            merged_ads = pd.merge(ads_f, daily_orders, on='Deduction Duration', how='left').fillna(0)
            
            total_orders_in_period = merged_ads['Daily Orders'].sum()
            per_order_cost = ads_total / total_orders_in_period if total_orders_in_period > 0 else 0
            
            # Display 3 Boxes
            ac1, ac2, ac3 = st.columns(3)
            ac1.markdown(_card_html("Total Ads Spend", ads_total, "#4a148c", "📣"), unsafe_allow_html=True)
            ac2.markdown(_card_html("Total Orders", total_orders_in_period, "#6A1B9A", "📦"), unsafe_allow_html=True)
            ac3.markdown(_card_html("Per Order Cost", per_order_cost, "#8E24AA", "🏷️"), unsafe_allow_html=True)

            fig_ads = px.bar(merged_ads, x='Deduction Duration', y='Total Ads Cost', title="Daily Ads Spend")
            st.plotly_chart(fig_ads, use_container_width=True)
            
            st.dataframe(merged_ads, use_container_width=True)
            ads_table = merged_ads
    else:
        st.warning("Ads sheet missing required columns.")
else:
    st.info("No Ads Data found in file.")

# ---------------- FULL DATA PREVIEW ----------------
st.markdown("---")
st.subheader("🔎 Full Data Preview")
if st.checkbox("Show All Filtered Data", value=True):
    st.dataframe(df_f, use_container_width=True)

# ---------------- CHARTS ----------------
st.markdown("---")
c1, c2 = st.columns(2)
with c1:
    status_counts_df = df_f[status_col].fillna("BLANK").value_counts().reset_index()
    status_counts_df.columns = ['Status', 'Count']
    fig1 = px.bar(status_counts_df, x='Status', y='Count', text='Count', title="Live Order Status")
    st.plotly_chart(fig1, use_container_width=True)

with c2:
    if order_date_col:
        date_counts = df_f.groupby(df_f[order_date_col].dt.date).size().reset_index(name='Orders')
        fig2 = px.bar(date_counts, x=order_date_col, y='Orders', text='Orders', title="Orders Timeline")
        st.plotly_chart(fig2, use_container_width=True)

# ---------------- EXPORTS ----------------
st.markdown("---")
st.subheader("📥 Downloads")

buffer = BytesIO()
with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
    df_f.to_excel(writer, sheet_name='Filtered Data', index=False)
    pd.DataFrame({'Metric':['Net Amount', 'Shipped Total', 'Net Profit', 'Claims', 'Recovery'], 'Value':[u_total, shipped_with_total, net_profit, a_claims, a_rec]}).to_excel(writer, sheet_name='Summary')
    if ads_table is not None: ads_table.to_excel(writer, sheet_name='Ads Analysis', index=False)

st.download_button("⬇️ Download Excel Report", data=buffer.getvalue(), file_name="Meesho_Report_v15.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.success("✅ Dashboard Ready (v15): Recovery (Abs), Claims, Order Source, RTO 3-Col, Ads Per Order Cost.")
