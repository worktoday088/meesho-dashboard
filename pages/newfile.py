# 📦 Meesho Order Analysis Dashboard — COMPLETE MASTER VERSION (v11)
# Base: User's 'profit loss.py'
# Updates: 
# 1. Full Code Restoration (No summarizing)
# 2. Dynamic Catalog ID Filter added
# 3. Toolkit/Tooltips (?) added to Financial Cards
# 4. HTML Formatting fixed for Streamlit
# 5. Full PDF & Excel Export Logic preserved
# Date: 2026-01-29

import os
import re
import math
import tempfile
from io import BytesIO
from datetime import datetime, date

import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
from PIL import Image

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

# ---------------- OPTIONAL LIBRARIES ----------------
# Try importing optional libraries for PDF generation
try:
    from PyPDF2 import PdfMerger
    _pdf_merge_ok = True
except Exception:
    _pdf_merge_ok = False

try:
    import kaleido  # for plotly -> png conversion
    _kaleido_ok = True
except Exception:
    _kaleido_ok = False

__VERSION__ = "Power By Rehan — Master v11 (Full)"

# ---------------- PAGE SETUP ----------------
st.set_page_config(layout="wide", page_title=f"📦 Meesho Dashboard — {__VERSION__}")
st.title(f"📦 Meesho Order Analysis Dashboard — {__VERSION__}")
st.caption("Full Version: SKU Groups + Catalog ID Filter + Calculation Tooltips + Ads + Exports")

if not _kaleido_ok:
    st.warning("⚠️ Colorful chart PDF के लिए 'kaleido' आवश्यक है → pip install kaleido")
if not _pdf_merge_ok:
    st.info("ℹ️ Final PDF merge optional: pip install PyPDF2 to enable PDF merge feedback")

# ---------------- HELPER FUNCTIONS ----------------

def safe_str(x):
    """Safely convert value to string, handling None."""
    return "" if x is None else str(x)

def extract_supplier_id_from_filename(filename: str) -> str:
    """Extracts numeric supplier ID from the uploaded filename."""
    if not filename:
        return ""
    base = os.path.basename(filename)
    name, _ = os.path.splitext(base)
    if "_" in name:
        return name.split("_", 1)[0]
    m = re.match(r"^(\d+)", name)
    if m:
        return m.group(1)
    return name

def _detect_col(df: pd.DataFrame, *keyword_groups):
    """
    Scans column names to find one that matches the keyword groups.
    Useful for finding columns even if names change slightly (e.g. 'Order Date' vs 'Date of Order').
    """
    if df is None or df.empty:
        return None
    cols = list(df.columns)
    low = [str(c).lower() for c in cols]
    for i, c in enumerate(cols):
        lc = low[i]
        for grp in keyword_groups:
            if all(k in lc for k in grp):
                return c
    return None

@st.cache_data(show_spinner=False)
def _read_uploaded(file):
    """Reads Excel or CSV file and returns DataFrames for Orders and Ads."""
    name = file.name.lower()
    if name.endswith('.csv'):
        return pd.read_csv(file), None
    xls = pd.ExcelFile(file)
    sheet_map = {s.lower(): s for s in xls.sheet_names}
    
    # Try to find 'Order Payments' sheet
    orders_sheet = sheet_map.get('order payments', xls.sheet_names[0])
    df_orders = pd.read_excel(xls, sheet_name=orders_sheet)
    
    # Try to find 'Ads Cost' sheet
    df_ads = pd.read_excel(xls, sheet_name=sheet_map['ads cost']) if 'ads cost' in sheet_map else None
    return df_orders, df_ads

def _sum(series):
    """Sum a series safely converting to numeric."""
    if series is None:
        return 0.0
    return pd.to_numeric(series, errors='coerce').fillna(0).sum()

def html_escape(s):
    """Escapes HTML special characters."""
    import html
    return html.escape(str(s)) if s is not None else ""

def _format_display(v):
    """Formats numbers with commas or currency symbols."""
    try:
        if isinstance(v, (int, np.integer)):
            return f"{v:,}"
        if isinstance(v, (float, np.floating)):
            return f"₹{v:,.2f}"
        return str(v)
    except Exception:
        return str(v)

def _date(val):
    """Formats date to string YYYY-MM-DD."""
    try:
        d = pd.to_datetime(val, errors='coerce')
        return "" if pd.isna(d) else str(d.date())
    except Exception:
        return str(val)

# --- UPDATED CARD HTML WITH TOOLTIP SUPPORT ---
def _card_html(title, value, bg="#0d47a1", icon="₹", tooltip=None):
    """
    Generates HTML for a metric card. 
    If 'tooltip' is provided, adds a (?) icon with hover text.
    """
    # Tooltip logic: Single line string to avoid Streamlit rendering issues
    tt_html = ""
    if tooltip:
        tt_html = f'<span title="{html_escape(tooltip)}" style="cursor:help; margin-left:8px; border:1px solid rgba(255,255,255,0.7); border-radius:50%; width:18px; height:18px; display:inline-flex; align-items:center; justify-content:center; font-size:11px; font-weight:bold; background-color:rgba(0,0,0,0.2);">?</span>'
    
    return f"""
    <div style='background:{bg}; padding:14px; border-radius:12px; color:white; text-align:center'>
        <div style="font-size:14px; opacity:.95; display:flex; gap:6px; align-items:center; justify-content:center">
            <span style="font-weight:700">{icon}</span>
            <span style="font-weight:700">{title}</span>
            {tt_html}
        </div>
        <div style="font-size:22px; font-weight:800; margin-top:6px">{_format_display(value)}</div>
    </div>
    """

# ---------------- SIDEBAR SETUP ----------------
st.sidebar.header("⚙️ Controls & Filters")
st.sidebar.caption("Tip: use the SKU Grouping to create multi-keyword selections")

# Initialize Session State for SKU Groups
if 'sku_groups' not in st.session_state:
    st.session_state['sku_groups'] = []

supplier_name_input = st.sidebar.text_input(
    "🔹 Supplier / Client Name (header)",
    value="",
    help="Type a label so screenshots & PDFs clearly show whose data this is."
)

up = st.sidebar.file_uploader("Upload Excel/CSV", type=["xlsx", "csv"])
if up is None:
    st.info("Please upload Excel/CSV (sheet 'Order Payments' expected).")
    st.stop()

supplier_id_auto = extract_supplier_id_from_filename(up.name)

def _render_supplier_banner(name: str, supplier_id: str):
    import html as _html
    name = (name or "").strip()
    if name:
        label = f"{_html.escape(name)} ({_html.escape(supplier_id)})" if supplier_id else _html.escape(name)
    else:
        label = _html.escape(supplier_id) if supplier_id else "No Supplier Selected"
    st.markdown(
        f"""
        <div style="background-color:#FFEB3B; padding:12px; border-radius:12px; text-align:center;
                    font-size:20px; font-weight:800; color:#000; margin-top:6px; margin-bottom:8px;">
            📌 Analyzing Data for: {label}
        </div>
        """, unsafe_allow_html=True
    )

_render_supplier_banner(supplier_name_input, supplier_id_auto)

# Reset Filters Button
if st.sidebar.button("🔄 Clear All Filters"):
    keys_to_remove = [k for k in list(st.session_state.keys()) if k not in ['_rerun_counter', 'uploaded_files', 'sidebar_collapsed']]
    for k in ['status_multiselect', 'sku_search_q', 'selected_skus', 'selected_sizes', 'selected_states', 'selected_cat_ids',
              'order_date_range', 'dispatch_date_range', 'ads_date_range', 'group_choice', 'dispatch_group_choice',
              'sku_group_multiselect', 'sku_new_group_name', 'show_filtered_table', 'show_full_table']:
        if k in st.session_state:
            del st.session_state[k]
    st.session_state['sku_groups'] = []
    st.rerun()

# ---------------- READ & PROCESS FILES ----------------
try:
    orders_df, ads_df = _read_uploaded(up)
except Exception as e:
    st.error(f"File read error: {e}")
    st.stop()

if orders_df is None or orders_df.empty:
    st.error("'Order Payments' data not found. Upload correct file.")
    st.stop()

# Clean column names
orders_df.columns = [str(c).strip() for c in orders_df.columns]
if ads_df is not None:
    ads_df.columns = [str(c).strip() for c in ads_df.columns]

# Detect columns using keywords
status_col        = _detect_col(orders_df, ("live","order","status"), ("status",))
order_date_col    = _detect_col(orders_df, ("order","date"))
payment_date_col  = _detect_col(orders_df, ("payment","date"))
dispatch_date_col = _detect_col(orders_df, ("dispatch","date"))
sku_col           = 'Supplier SKU' if 'Supplier SKU' in orders_df.columns else _detect_col(orders_df, ("sku",))
size_col          = 'Size' if 'Size' in orders_df.columns else _detect_col(orders_df, ("size",))
state_col         = 'State' if 'State' in orders_df.columns else _detect_col(orders_df, ("state",))
settle_amt_col    = _detect_col(orders_df, ("final","settlement","amount"), ("settlement","amount"))
exchange_loss_col = _detect_col(orders_df, ("exchange","loss"))
profit_amt_col    = _detect_col(orders_df, ("profit","amount"), ("profit",))

# --- NEW: CATALOG ID DETECTION ---
catalog_id_col    = _detect_col(orders_df, ("catalog","id"), ("catalog_id",))

if not status_col:
    st.error("Status column not detected (e.g. 'Live Order Status').")
    st.stop()

# Parse date columns
for c in [order_date_col, payment_date_col, dispatch_date_col]:
    if c and c in orders_df.columns:
        orders_df[c] = pd.to_datetime(orders_df[c], errors='coerce')

# ---------------- SIDEBAR FILTERS ----------------
with st.sidebar.expander("🎛️ Basic Filters", expanded=True):
    # Status Filter
    status_options = ['All', 'Delivered', 'Return', 'RTO', 'Exchange', 'Cancelled', 'Shipped', ""]
    selected_statuses = st.multiselect("Status", options=status_options, default=['All'], key='status_multiselect')

    # SKU Grouping & Filter
    if sku_col and sku_col in orders_df.columns:
        st.markdown("**SKU Grouping**")
        skus = sorted([str(x) for x in orders_df[sku_col].dropna().unique().tolist()])

        sku_search_q = st.text_input("Search SKU keyword (type part of SKU)", value="", key='sku_search_q')
        
        # Logic to add/clear groups
        new_group_name = st.text_input("Group name (optional)", value=sku_search_q or "", key='sku_new_group_name')
        col_a, col_b = st.columns([1,1])
        with col_a:
            if st.button("➕ Add Group"):
                pattern = (sku_search_q or new_group_name or "").strip()
                if pattern:
                    matched_skus = [s for s in skus if pattern.lower() in s.lower()]
                    if matched_skus:
                        # Check if update or new
                        found = False
                        for g in st.session_state['sku_groups']:
                            if g['name'] == (new_group_name or pattern):
                                g['skus'] = matched_skus
                                found = True
                        if not found:
                            st.session_state['sku_groups'].append({'name': new_group_name or pattern, 'pattern': pattern, 'skus': matched_skus})
                        st.rerun()
        with col_b:
            if st.button("🧹 Clear Groups"):
                st.session_state['sku_groups'] = []
                if 'selected_skus' in st.session_state: del st.session_state['selected_skus']
                st.rerun()

        # Selection Logic (Groups + Manual)
        if st.session_state.get('sku_groups'):
            st.markdown("**Select Groups:**")
            grp_labels = [f"{g['name']} ({len(g['skus'])})" for g in st.session_state['sku_groups']]
            chosen_group_labels = st.multiselect("Active Groups", options=grp_labels, key='sku_group_multiselect')
            
            selected_from_groups = []
            for label in chosen_group_labels:
                # Find group by name matching
                g_name = label.rsplit(" (", 1)[0]
                for g in st.session_state['sku_groups']:
                    if g['name'] == g_name:
                        selected_from_groups.extend(g['skus'])
            
            manual_matches = [s for s in skus if sku_search_q.lower() in s.lower()] if sku_search_q else []
            union_skus = sorted(list(set(selected_from_groups + manual_matches)))
            selected_skus = st.multiselect("Selected SKU(s)", options=skus, default=union_skus, key='selected_skus')
        else:
            sku_opts = [s for s in skus if sku_search_q.lower() in s.lower()] if sku_search_q else skus
            selected_skus = st.multiselect("Select SKU(s)", options=sku_opts, key='selected_skus')
    else:
        selected_skus = None
        st.caption("SKU column not found.")

    # --- NEW: CATALOG ID FILTER ---
    if catalog_id_col and catalog_id_col in orders_df.columns:
        cat_ids = sorted([str(x) for x in orders_df[catalog_id_col].dropna().unique().tolist()])
        st.markdown("---")
        selected_cat_ids = st.multiselect("📂 Catalog ID Filter", options=cat_ids, key='selected_cat_ids', help="Filter by specific Catalog IDs")
    else:
        selected_cat_ids = None

    # Size & State Filters
    if size_col and size_col in orders_df.columns:
        size_opts = sorted([str(x) for x in orders_df[size_col].dropna().unique().tolist()])
        selected_sizes = st.multiselect("Size", options=size_opts, default=[], key='selected_sizes')
    else:
        selected_sizes = None

    if state_col and state_col in orders_df.columns:
        state_opts = sorted([str(x) for x in orders_df[state_col].dropna().unique().tolist()])
        selected_states = st.multiselect("State", options=state_opts, default=[], key='selected_states')
    else:
        selected_states = None

with st.sidebar.expander("📅 Date Filters", expanded=True):
    if order_date_col:
        od_min = pd.to_datetime(orders_df[order_date_col]).min()
        od_max = pd.to_datetime(orders_df[order_date_col]).max()
        # Default full range
        date_range = st.date_input("Order Date Range", value=[od_min.date(), od_max.date()], key='order_date_range') if pd.notna(od_min) else None
        group_choice = st.selectbox("Group order by", ["Month", "Day"], index=0, key='group_choice')
    else:
        date_range = None
        group_choice = "Month"

    if dispatch_date_col:
        dmin = pd.to_datetime(orders_df[dispatch_date_col]).min()
        dmax = pd.to_datetime(orders_df[dispatch_date_col]).max()
        dispatch_range = st.date_input("Dispatch Date Range", value=[dmin.date(), dmax.date()], key='dispatch_date_range') if pd.notna(dmin) else None
        dispatch_group_choice = st.selectbox("Group dispatch by", ["Month", "Day"], index=0, key='dispatch_group_choice')
    else:
        dispatch_range = None
        dispatch_group_choice = "Month"

# ---------------- FILTERING LOGIC ----------------
work = orders_df.copy()

# 1. Date
if order_date_col and date_range and len(date_range) == 2:
    s, e = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
    work = work[(work[order_date_col] >= s) & (work[order_date_col] <= e)]
if dispatch_date_col and dispatch_range and len(dispatch_range) == 2:
    s, e = pd.to_datetime(dispatch_range[0]), pd.to_datetime(dispatch_range[1])
    work = work[(work[dispatch_date_col] >= s) & (work[dispatch_date_col] <= e)]

# 2. SKU
if sku_col and selected_skus:
    work = work[work[sku_col].astype(str).isin(selected_skus)]

# 3. Catalog ID (New)
if catalog_id_col and selected_cat_ids:
    work = work[work[catalog_id_col].astype(str).isin(selected_cat_ids)]

# 4. Size/State
if size_col and selected_sizes:
    work = work[work[size_col].astype(str).isin([str(x) for x in selected_sizes])]
if state_col and selected_states:
    work = work[work[state_col].astype(str).isin([str(x) for x in selected_states])]

# 5. Status (Handle Blanks)
if 'All' in selected_statuses:
    df_f = work.copy()
    applied_status = 'All'
else:
    include_blank = "" in selected_statuses
    nonblank_selected = [s for s in selected_statuses if s != ""]
    sel_up = [s.upper() for s in nonblank_selected]
    
    # Logic: Selected OR (Blank if included)
    if sel_up and include_blank:
        mask_sel = work[status_col].astype(str).str.upper().isin(sel_up) | (work[status_col].isna() | (work[status_col].astype(str).str.strip() == ""))
    elif sel_up:
        mask_sel = work[status_col].astype(str).str.upper().isin(sel_up)
    else:
        mask_sel = (work[status_col].isna() | (work[status_col].astype(str).str.strip() == ""))
    
    df_f = work[mask_sel].copy()
    applied_status = ", ".join(selected_statuses)

# Ensure RTO Columns exist for calculation
def _ensure_rto_cols(df: pd.DataFrame, status_col: str) -> pd.DataFrame:
    out = df.copy()
    need = ['Listing Price (Incl. taxes)', 'Total Sale Amount (Incl. Shipping & GST)']
    if status_col and all(col in out.columns for col in need):
        mask = out[status_col].astype(str).str.upper() == 'RTO'
        if 'Shipping Charge' not in out.columns:
            out.loc[mask, 'Shipping Charge'] = (
                pd.to_numeric(out.loc[mask, 'Total Sale Amount (Incl. Shipping & GST)'], errors='coerce').fillna(0)
                - pd.to_numeric(out.loc[mask, 'Listing Price (Incl. taxes)'], errors='coerce').fillna(0)
            )
        if 'Shipping Charge Only GST' not in out.columns:
            out.loc[mask, 'Shipping Charge Only GST'] = pd.to_numeric(out.loc[mask, 'Shipping Charge'], errors='coerce').fillna(0) * 0.18
        if 'RTO Amount' not in out.columns:
            out.loc[mask, 'RTO Amount'] = (
                pd.to_numeric(out.loc[mask, 'Listing Price (Incl. taxes)'], errors='coerce').fillna(0)
                - pd.to_numeric(out.loc[mask, 'Shipping Charge Only GST'], errors='coerce').fillna(0)
            )
    return out

orders_df = _ensure_rto_cols(orders_df, status_col)
df_f = _ensure_rto_cols(df_f, status_col)

# Caption
cap = f"Applied: Status={applied_status} | Rows={len(df_f)}"
if (supplier_name_input or supplier_id_auto):
    cap += f" | Supplier={supplier_name_input or supplier_id_auto}"
st.caption(cap)

# ---------------- STATUS CARDS ----------------
status_labels = {
    'Delivered': '✅ Delivered',
    'Return': '↩️ Return',
    'Exchange': '🔄 Exchange',
    'Cancelled': '❌ Cancelled',
    'Shipped': '🚚 Shipped',
    'RTO': '📪 RTO'
}
status_colors = {
    'Delivered': '#2e7d32',
    'Return': '#c62828',
    'Exchange': '#f57c00',
    'Cancelled': '#616161',
    'Shipped': '#1565c0',
    'RTO': '#8e24aa'
}

counts = {s: int(df_f[status_col].astype(str).str.upper().eq(s.upper()).sum()) for s in status_labels}
blank_mask_full = (df_f[status_col].isna() | (df_f[status_col].astype(str).str.strip() == ""))
platform_recovery_count = int(blank_mask_full.sum())
grand_total_count = df_f.shape[0]

cols = st.columns(len(status_labels) + 2)
i = 0
for label in status_labels:
    display_label = status_labels[label]
    cols[i].markdown(f"""<div style='background-color:{status_colors[label]}; padding:10px; border-radius:8px; text-align:center; color:white'><div style="font-size:14px; margin-bottom:6px">{display_label}</div><div style="font-size:22px; font-weight:700">{counts[label]}</div></div>""", unsafe_allow_html=True)
    i += 1

cols[i].markdown(f"""<div title="Blank/empty status rows" style='background-color:#37474f; padding:10px; border-radius:8px; text-align:center; color:white'><div style="font-size:14px; margin-bottom:6px">📦 Recovery (Count)</div><div style="font-size:22px; font-weight:700">{platform_recovery_count}</div></div>""", unsafe_allow_html=True)
i+=1
cols[i].markdown(f"""<div style='background-color:#0d47a1; padding:10px; border-radius:8px; text-align:center; color:white'><div style="font-size:14px; margin-bottom:6px">📊 Grand Total</div><div style="font-size:22px; font-weight:700">{grand_total_count}</div></div>""", unsafe_allow_html=True)

# ---------------- FINANCIAL SUMMARY ----------------
st.subheader("₹ Amount Summary (Status-wise)")

if settle_amt_col and settle_amt_col in df_f.columns:
    df_f[settle_amt_col] = pd.to_numeric(df_f[settle_amt_col], errors='coerce').fillna(0)

def _sum_by_status(df, status_name, col):
    if not col or col not in df.columns: return 0.0
    mask = df[status_col].astype(str).str.upper().eq(status_name.upper())
    return pd.to_numeric(df.loc[mask, col], errors='coerce').fillna(0).sum()

u_del = _sum_by_status(df_f, 'Delivered', settle_amt_col)
u_exc = _sum_by_status(df_f, 'Exchange', settle_amt_col)
u_can = _sum_by_status(df_f, 'Cancelled', settle_amt_col)
u_ret = _sum_by_status(df_f, 'Return', settle_amt_col)
u_ship = _sum_by_status(df_f, 'Shipped', settle_amt_col)

u_rto = 0.0
if 'RTO Amount' in df_f.columns:
    u_rto = pd.to_numeric(df_f.loc[df_f[status_col].astype(str).str.upper().eq('RTO'), 'RTO Amount'], errors='coerce').fillna(0).sum()

blank_amt = pd.to_numeric(df_f.loc[blank_mask_full, settle_amt_col], errors='coerce').fillna(0).sum() if settle_amt_col in df_f.columns else 0.0

# --- CALCULATIONS ---
u_total = (u_del + u_exc + u_can) - abs(u_ret)
shipped_with_total = (u_del + u_can + u_ship) - (abs(u_ret) + abs(u_exc))

# --- TOOLTIPS TEXT ---
tt_shipped = "Calculation: (Delivered + Cancelled + Shipped) - (Return + Exchange)"
tt_total = "Calculation: (Delivered + Exchange + Cancelled) - Return Amount"

abox = [
    ("Delivered ₹", u_del, "#1b5e20", "✅", None),
    ("Exchange ₹",  u_exc, "#e65100", "🔄", None),
    ("Cancelled ₹", u_can, "#455a64", "❌", None),
    ("Return ₹",    u_ret, "#b71c1c", "↩️", None),
    ("RTO ₹",       u_rto, "#6a1b9a", "📪", None),
    ("Shipping (₹)",   u_ship, "#0b3d91", "🚚", None),
    ("Platform Recovery ₹", blank_amt, "#546e7a", "🔍", None),
    ("Shipped With Total ₹", shipped_with_total, "#0b3d91", "🚚", tt_shipped),
    ("Total Amount ₹", u_total, "#0d47a1", "🧾", tt_total),
]

first_row = abox[:5]
second_row = abox[5:]

cc = st.columns(len(first_row))
for i, (label, val, color, icon, tt) in enumerate(first_row):
    cc[i].markdown(_card_html(label, val, bg=color, icon=icon, tooltip=tt), unsafe_allow_html=True)

cc2 = st.columns(len(second_row))
for i, (label, val, color, icon, tt) in enumerate(second_row):
    cc2[i].markdown(_card_html(label, val, bg=color, icon=icon, tooltip=tt), unsafe_allow_html=True)

# ---------------- CHARTS & ANALYTICS ----------------
st.markdown("---")
_figs_for_pdf = []

# 1. Live Order Status Count
st.subheader("1️⃣ Live Order Status Count")
chart_type_status = st.radio("Chart Type (Status)", ["Bar", "Line"], horizontal=True, key="chart_status_toggle")
status_df = df_f[status_col].fillna("BLANK").value_counts().reset_index()
status_df.columns = ['Status', 'Count']
if status_df.empty:
    st.warning("No data found.")
else:
    if chart_type_status == "Bar":
        f1 = px.bar(status_df, x='Status', y='Count', color='Status', text='Count')
        f1.update_traces(texttemplate='%{text}', textposition='outside')
    else:
        f1 = px.line(status_df, x='Status', y='Count', markers=True, title="Live Order Status Count")
    f1.update_layout(height=560)
    st.plotly_chart(f1, use_container_width=True)
    _figs_for_pdf.append(("Live Order Status Count", f1))

# 2. Orders by Date
st.markdown("---")
st.subheader("2️⃣ Orders by Date")
if order_date_col:
    df_f['__order_dt'] = pd.to_datetime(df_f[order_date_col], errors='coerce')
    if group_choice == "Month":
        g = df_f.groupby(df_f['__order_dt'].dt.to_period('M'))['__order_dt'].count().reset_index(name='Total Orders')
        g[order_date_col] = g['__order_dt'].astype(str)
        xcol = order_date_col
    else:
        g = df_f.groupby(df_f['__order_dt'].dt.date)['__order_dt'].count().reset_index(name='Total Orders')
        g.rename(columns={'__order_dt': order_date_col}, inplace=True)
        xcol = order_date_col

    chart_type_orders = st.radio("Chart Type (Orders)", ["Bar", "Line"], horizontal=True, key="chart_orders_toggle")
    if not g.empty:
        if chart_type_orders == "Bar":
            f2 = px.bar(g, x=xcol, y='Total Orders', text='Total Orders', title="Orders by Order Date")
            f2.update_traces(textposition='outside', texttemplate='%{text}')
        else:
            f2 = px.line(g, x=xcol, y='Total Orders', markers=True, title="Orders by Order Date")
        f2.update_layout(height=520)
        st.plotly_chart(f2, use_container_width=True)
        _figs_for_pdf.append(("Orders by Order Date", f2))

# 3. Payments Received
st.markdown("---")
st.subheader("3️⃣ Payments Received")
if payment_date_col and settle_amt_col:
    df_f['__pay_dt'] = pd.to_datetime(df_f[payment_date_col], errors='coerce')
    if group_choice == "Month":
        g3 = df_f.groupby(df_f['__pay_dt'].dt.to_period('M'))[settle_amt_col].sum().reset_index()
        g3[payment_date_col] = g3['__pay_dt'].astype(str)
        xcol3 = payment_date_col
    else:
        g3 = df_f.groupby(df_f['__pay_dt'].dt.date)[settle_amt_col].sum().reset_index()
        g3.rename(columns={'__pay_dt': payment_date_col}, inplace=True)
        xcol3 = payment_date_col

    chart_type_payments = st.radio("Chart Type (Payments)", ["Bar", "Line"], horizontal=True, key="chart_payments_toggle")
    if not g3.empty:
        if chart_type_payments == "Bar":
            f3 = px.bar(g3, x=xcol3, y=settle_amt_col, title="Payments Received", text=settle_amt_col)
            f3.update_traces(textposition='outside', texttemplate='%{text:.2f}')
        else:
            f3 = px.line(g3, x=xcol3, y=settle_amt_col, markers=True, title="Payments Received")
        f3.update_layout(height=520)
        st.plotly_chart(f3, use_container_width=True)
        _figs_for_pdf.append(("Payments Received", f3))

# 4. Return & Exchange %
st.markdown("---")
st.subheader("4️⃣ Return & Exchange % of Delivered")
# Recalculate based on current filter
_deliv = int(status_df[status_df['Status'].str.upper()== 'DELIVERED']['Count'].sum()) if not status_df.empty else 0
_ret   = int(status_df[status_df['Status'].str.upper()== 'RETURN']['Count'].sum()) if not status_df.empty else 0
_exc   = int(status_df[status_df['Status'].str.upper()== 'EXCHANGE']['Count'].sum()) if not status_df.empty else 0

ret_pct = (_ret/_deliv*100) if _deliv else 0.0
exc_pct = (_exc/_deliv*100) if _deliv else 0.0

c1, c2, c3 = st.columns(3)
c1.markdown(f"<div style='background:#1565c0; padding:16px; border-radius:12px; color:white'><div style='font-size:18px'>Delivered</div><div style='font-size:28px'>{_deliv}</div><div>100%</div></div>", unsafe_allow_html=True)
c2.markdown(f"<div style='background:#c62828; padding:16px; border-radius:12px; color:white'><div style='font-size:18px'>Return</div><div style='font-size:28px'>{_ret}</div><div>{ret_pct:.2f}%</div></div>", unsafe_allow_html=True)
c3.markdown(f"<div style='background:#ef6c00; padding:16px; border-radius:12px; color:white'><div style='font-size:18px'>Exchange</div><div style='font-size:28px'>{_exc}</div><div>{exc_pct:.2f}%</div></div>", unsafe_allow_html=True)

# 5. Profit Section
st.markdown("---")
st.subheader("💹 Profit Calculation")
profit_sum = _sum(df_f[profit_amt_col]) if profit_amt_col else 0.0
return_loss_sum = abs(u_ret)
exchange_loss_sum = _sum(df_f[exchange_loss_col]) if exchange_loss_col else 0.0
net_profit = profit_sum - (return_loss_sum + abs(exchange_loss_sum))

pc1, pc2, pc3, pc4 = st.columns(4)
pc1.markdown(_card_html("Profit Amount", profit_sum, "#1b5e20", "💹"), unsafe_allow_html=True)
pc2.markdown(_card_html("Return Loss", return_loss_sum, "#b71c1c", "➖"), unsafe_allow_html=True)
pc3.markdown(_card_html("Exchange Loss", exchange_loss_sum, "#f57c00", "🔄"), unsafe_allow_html=True)
pc4.markdown(_card_html("Net Profit", net_profit, "#0d47a1", "🧮"), unsafe_allow_html=True)

# 6. Ads Cost Analysis
st.markdown("---")
st.subheader("📢 Ads Cost Analysis")
ads_table_for_export = None
with st.expander("Ads Cost Analysis", expanded=True):
    if ads_df is None or ads_df.empty:
        st.info("Ads Cost sheet not found.")
    else:
        if 'Deduction Duration' in ads_df.columns and 'Total Ads Cost' in ads_df.columns:
            ads_df['Deduction Duration'] = pd.to_datetime(ads_df['Deduction Duration'], errors='coerce').dt.date
            dmin, dmax = ads_df['Deduction Duration'].min(), ads_df['Deduction Duration'].max()
            rng = st.date_input("Ads Date Range", value=[dmin, dmax], key='ads_date_range')
            
            if rng and len(rng)==2:
                ads_view = ads_df[(ads_df['Deduction Duration'] >= rng[0]) & (ads_df['Deduction Duration'] <= rng[1])].copy()
            else:
                ads_view = ads_df.copy()

            ads_view['Total Ads Cost'] = pd.to_numeric(ads_view['Total Ads Cost'], errors='coerce').fillna(0)
            ads_sum = ads_view['Total Ads Cost'].sum()
            
            st.markdown(_card_html("Total Ads Cost", ads_sum, "#4a148c", "📣"), unsafe_allow_html=True)

            gads = ads_view.groupby('Deduction Duration', as_index=False)['Total Ads Cost'].sum()
            fads = px.bar(gads, x='Deduction Duration', y='Total Ads Cost', text='Total Ads Cost', title="Ads Cost Over Time")
            st.plotly_chart(fads, use_container_width=True)
            _figs_for_pdf.append(("Ads Cost Over Time", fads))
            
            ads_table_for_export = ads_view
            if st.checkbox("Show Ads Table"):
                st.dataframe(ads_view, use_container_width=True)

# ---------------- EXPORTS ----------------
st.markdown("---")
st.subheader("📥 Download Summary")

# 1. EXCEL
excel_buf = BytesIO()
with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
    orders_df.to_excel(writer, index=False, sheet_name="Raw Orders")
    df_f.to_excel(writer, index=False, sheet_name="Filtered Orders")
    pd.DataFrame({'Metric':['Net Profit','Total Amount'], 'Value':[net_profit, u_total]}).to_excel(writer, sheet_name="Summary")
    if ads_table_for_export is not None:
        ads_table_for_export.to_excel(writer, index=False, sheet_name="Ads Data")

st.download_button("⬇️ Download Excel", data=excel_buf.getvalue(), file_name="Meesho_Report_v11.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# 2. PDF GENERATION
def _make_summary_table_figure(supplier_name="", supplier_id=""):
    rows = [
        ["Delivered", counts.get('Delivered', 0)],
        ["Return", counts.get('Return', 0)],
        ["Net Profit", f"{net_profit:.2f}"],
        ["Total Amount", f"{u_total:.2f}"],
    ]
    figx, ax = plt.subplots(figsize=(10, 6))
    ax.axis('off')
    ax.table(cellText=rows, colLabels=["Metric", "Value"], loc='center')
    ax.set_title(f"Report: {supplier_name} ({supplier_id})", fontsize=16)
    return figx

def _export_pdf(figs):
    if not _kaleido_ok: return None
    buf = BytesIO()
    with PdfPages(buf) as pdf:
        # Summary
        fig_sum = _make_summary_table_figure(supplier_name_input, supplier_id_auto)
        pdf.savefig(fig_sum, bbox_inches='tight')
        plt.close(fig_sum)
        # Charts
        for title, fig in figs:
            try:
                img_buf = BytesIO()
                fig.write_image(img_buf, format="png", width=1200, height=800, scale=2)
                img = Image.open(img_buf)
                f, ax = plt.subplots(figsize=(10,6))
                ax.imshow(img)
                ax.axis('off')
                ax.set_title(title)
                pdf.savefig(f, bbox_inches='tight')
                plt.close(f)
            except: pass
    buf.seek(0)
    return buf.read()

if _kaleido_ok:
    pdf_data = _export_pdf(_figs_for_pdf)
    if pdf_data:
        st.download_button("⬇️ Download PDF (Charts)", data=pdf_data, file_name="Report_v11.pdf", mime="application/pdf")
else:
    st.info("Install 'kaleido' library to enable PDF exports.")

st.success("✅ Dashboard Fully Loaded (v11)")
