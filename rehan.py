# test_11.py
# 📦 Meesho Order Analysis Dashboard — Final (test_11)
# Merged from rehan_v11.py + SKU Groups, Chart toggles, Clear fixes, PDF & Excel improvements
# Date: 2025-09-16
# Version: test_11_final

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

# optional libs for PDF export
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

# ----------------- PASSWORD PROTECTION v3 (Safer) -----------------
def check_password():
    """Returns `True` if the user had a correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        # Check if the password key exists in session state
        if "password" in st.session_state and st.session_state["password"] == "888":
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

    # Initialize password_correct if it doesn't exist
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    # Show password input if not authenticated
    if not st.session_state["password_correct"]:
        st.text_input(
            "पासवर्ड दर्ज करें", type="password", on_change=password_entered, key="password"
        )
        if st.button("लॉगिन"):
            password_entered() # Re-run password check on button click
        
        # Display error message if there was a wrong attempt
        if "password" in st.session_state and not st.session_state["password_correct"]:
             st.error("😕 गलत पासवर्ड!")
        return False
    else:
        return True

if check_password():
    # --- बाकी का डैशबोर्ड कोड यहाँ से शुरू होगा ---
    __VERSION__ = "Power By Rehan"
    
    # ---------------- PAGE SETUP ----------------
    st.set_page_config(layout="wide", page_title=f"📦 Meesho Dashboard — {__VERSION__}")
    st.title(f"📦 Meesho Order Analysis Dashboard — {__VERSION__}")
    # ... (और बाकी की पूरी स्क्रिप्ट)
else:
    st.stop()
# --------------------------------------------------------------------

__VERSION__ = "Power By Rehan"


# ---------------- PAGE SETUP ----------------
st.set_page_config(layout="wide", page_title=f"📦 Meesho Dashboard — {__VERSION__}")
st.title(f"📦 Meesho Order Analysis Dashboard — {__VERSION__}")
st.caption(
    "Merged: original v11 features + SKU Groups, Chart toggles, Clear fixes, improved PDF/Excel"
)
if not _kaleido_ok:
    st.warning("Colorful chart PDF के लिए 'kaleido' आवश्यक है → pip install kaleido")
if not _pdf_merge_ok:
    st.info("Final PDF merge optional: pip install PyPDF2 to enable PDF merge feedback")

# ---------------- HELPERS ----------------
def safe_str(x):
    return "" if x is None else str(x)

def extract_supplier_id_from_filename(filename: str) -> str:
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
    # read excel/csv robustly
    name = file.name.lower()
    if name.endswith('.csv'):
        return pd.read_csv(file), None
    xls = pd.ExcelFile(file)
    sheet_map = {s.lower(): s for s in xls.sheet_names}
    # try common sheet names
    orders_sheet = sheet_map.get('order payments', xls.sheet_names[0])
    df_orders = pd.read_excel(xls, sheet_name=orders_sheet)
    df_ads = pd.read_excel(xls, sheet_name=sheet_map['ads cost']) if 'ads cost' in sheet_map else None
    return df_orders, df_ads

def _sum(series):
    if series is None:
        return 0.0
    return pd.to_numeric(series, errors='coerce').fillna(0).sum()

def _card_html(title, value, bg="#0d47a1", icon="₹", tooltip=None):
    tt = f" title='{html_escape(tooltip)}' " if tooltip else ""
    return f"""
    <div{tt} style='background:{bg}; padding:14px; border-radius:12px; color:white; text-align:center'>
        <div style="font-size:14px; opacity:.95; display:flex; gap:8px; align-items:center; justify-content:center">
            <span style="font-weight:700">{icon}</span>
            <span style="font-weight:700">{title}</span>
        </div>
        <div style="font-size:22px; font-weight:800; margin-top:6px">₹{value:,.2f}</div>
    </div>
    """

def html_escape(s):
    import html
    return html.escape(str(s)) if s is not None else ""

def _date(val):
    try:
        d = pd.to_datetime(val, errors='coerce')
        return "" if pd.isna(d) else str(d.date())
    except Exception:
        return str(val)

# ---------------- SIDEBAR ----------------
st.sidebar.header("⚙️ Controls & Filters")
st.sidebar.caption("Tip: use the SKU Grouping to create multi-keyword selections")

# ensure session_state keys exist
if 'filters' not in st.session_state:
    st.session_state['filters'] = {}
if 'sku_groups' not in st.session_state:
    # sku_groups: list of dicts {'name', 'pattern', 'skus'}
    st.session_state['sku_groups'] = []

# Supplier header
supplier_name_input = st.sidebar.text_input(
    "🔹 Supplier / Client Name (header)",
    value="",
    help="Type a label so screenshots & PDFs clearly show whose data this is."
)

# File uploader
up = st.sidebar.file_uploader("Upload Excel/CSV", type=["xlsx", "csv"])
if up is None:
    st.info("Please upload Excel/CSV (sheet 'Order Payments' expected).")
    st.stop()

# try to auto detect supplier id from filename
supplier_id_auto = extract_supplier_id_from_filename(up.name)

# Banner
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

# Clear All Filters — improved reset
if st.sidebar.button("🔄 Clear All Filters"):
    # remove known keys and preserve upload
    keys_to_remove = [k for k in list(st.session_state.keys()) if k not in ['_rerun_counter', 'uploaded_files', 'sidebar_collapsed']]
    # specifically clear known filter keys
    for k in ['status_multiselect', 'sku_search_q', 'selected_skus', 'selected_sizes', 'selected_states',
              'order_date_range', 'dispatch_date_range', 'ads_date_range', 'group_choice', 'dispatch_group_choice',
              'sku_group_multiselect', 'sku_new_group_name', 'sku_group_multiselect', 'show_filtered_table', 'show_full_table']:
        if k in st.session_state:
            del st.session_state[k]
    # clear sku groups but keep session key
    st.session_state['sku_groups'] = []
    st.rerun()

# ---------------- READ FILES ----------------
try:
    orders_df, ads_df = _read_uploaded(up)
except Exception as e:
    st.error(f"File read error: {e}")
    st.stop()

if orders_df is None or orders_df.empty:
    st.error("'Order Payments' data not found. Upload correct file.")
    st.stop()

# normalize column names
orders_df.columns = [str(c).strip() for c in orders_df.columns]
if ads_df is not None:
    ads_df.columns = [str(c).strip() for c in ads_df.columns]

# Detect columns (reuse original heuristics)
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

if not status_col:
    st.error("Status column not detected (e.g. 'Live Order Status').")
    st.stop()

# parse date columns
for c in [order_date_col, payment_date_col, dispatch_date_col]:
    if c and c in orders_df.columns:
        orders_df[c] = pd.to_datetime(orders_df[c], errors='coerce')

# ---------------- SIDEBAR FILTER CONTROLS ----------------
with st.sidebar.expander("🎛️ Basic Filters", expanded=True):
    status_options = ['All', 'Delivered', 'Return', 'RTO', 'Exchange', 'Cancelled', 'Shipped']
    selected_statuses = st.multiselect("Status", options=status_options, default=['All'], key='status_multiselect')

    # SKU grouping controls (improved)
    if sku_col and sku_col in orders_df.columns:
        st.markdown("**SKU Grouping** — type keyword and click ➕ Add Group")
        skus = sorted([str(x) for x in orders_df[sku_col].dropna().unique().tolist()])

        # text input for searching SKU tokens (supports repeated digits/characters like '99' or '021')
        sku_search_q = st.text_input("Search SKU keyword (type part of SKU)", value="", key='sku_search_q')
        # show matches (exact substring)
        if sku_search_q:
            matches = [s for s in skus if sku_search_q.lower() in s.lower()]
            st.caption(f"Matches: {len(matches)} — preview: {matches[:12]}")
        else:
            matches = []

        new_group_name = st.text_input("Group name (optional)", value=sku_search_q or "", key='sku_new_group_name')

        col_a, col_b, col_c = st.columns([2,1,1])
        with col_a:
            if st.button("➕ Add Group"):
                pattern = (sku_search_q or new_group_name or "").strip()
                if not pattern:
                    st.warning("Please provide a keyword to make a group (e.g., '99' or 'taz').")
                else:
                    matched_skus = [s for s in skus if pattern.lower() in s.lower()]
                    if not matched_skus:
                        st.warning(f"No SKUs matched for '{pattern}'")
                    else:
                        existing = [g['pattern'] for g in st.session_state['sku_groups']]
                        if pattern in existing:
                            # update existing
                            for g in st.session_state['sku_groups']:
                                if g['pattern'] == pattern:
                                    g['skus'] = matched_skus
                                    g['name'] = new_group_name or pattern
                            st.info(f"Group '{pattern}' updated ({len(matched_skus)} SKUs).")
                        else:
                            st.session_state['sku_groups'].append({'name': new_group_name or pattern, 'pattern': pattern, 'skus': matched_skus})
                            st.success(f"Group '{new_group_name or pattern}' added ({len(matched_skus)} SKUs).")
                        st.experimental_rerun()
        with col_b:
            if st.button("🧹 Clear SKU Groups"):
                st.session_state['sku_groups'] = []
                if 'selected_skus' in st.session_state:
                    del st.session_state['selected_skus']
                st.rerun()
        with col_c:
            st.write("")  # spacer

        # show existing groups and allow selection to apply
        if st.session_state.get('sku_groups'):
            st.markdown("**Existing SKU Groups**")
            grp_labels = [f"{i+1}. {g['name']} ({len(g['skus'])})" for i,g in enumerate(st.session_state['sku_groups'])]
            chosen = st.multiselect("Select Groups to apply (their SKUs will be merged)", options=grp_labels, key='sku_group_multiselect')
            # map chosen to skus
            selected_from_groups = []
            for label in chosen:
                idx = int(label.split('.',1)[0]) - 1
                if 0 <= idx < len(st.session_state['sku_groups']):
                    selected_from_groups.extend(st.session_state['sku_groups'][idx]['skus'])
            # manual include of live-search matches
            select_all_live = st.checkbox("Include ALL live-search matches (if any)", value=True)
            manual_selected = [s for s in skus if sku_search_q.lower() in s.lower()] if (sku_search_q and select_all_live) else []
            union_selected = sorted(list(set(selected_from_groups + manual_selected)))
            selected_skus = st.multiselect("Selected SKU(s) (groups + manual)", options=skus, default=union_selected, key='selected_skus')
        else:
            select_all_skus = st.checkbox("Select ALL matching SKUs", value=True)
            sku_opts = [s for s in skus if sku_search_q.lower() in s.lower()] if sku_search_q else skus
            default_skus = sku_opts if select_all_skus else []
            selected_skus = st.multiselect("Select SKU(s)", options=sku_opts, default=default_skus, key='selected_skus')
    else:
        selected_skus = None
        st.caption("SKU column not found — skipping SKU filter.")

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
        date_range = st.date_input("Order Date Range", value=[od_min.date() if pd.notna(od_min) else od_min, od_max.date() if pd.notna(od_max) else od_max], key='order_date_range') if pd.notna(od_min) and pd.notna(od_max) else None
        group_choice = st.selectbox("Group order by", ["Month", "Day"], index=0, key='group_choice')
    else:
        date_range = None
        group_choice = "Month"

    if dispatch_date_col:
        dmin = pd.to_datetime(orders_df[dispatch_date_col]).min()
        dmax = pd.to_datetime(orders_df[dispatch_date_col]).max()
        dispatch_range = st.date_input("Dispatch Date Range", value=[dmin.date() if pd.notna(dmin) else dmin, dmax.date() if pd.notna(dmax) else dmax], key='dispatch_date_range') if pd.notna(dmin) and pd.notna(dmax) else None
        dispatch_group_choice = st.selectbox("Group dispatch by", ["Month", "Day"], index=0, key='dispatch_group_choice')
    else:
        dispatch_range = None
        dispatch_group_choice = "Month"

# ---------------- APPLY FILTERS ----------------
work = orders_df.copy()
# date filters
if order_date_col and date_range and len(date_range) == 2:
    s, e = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
    work = work[(work[order_date_col] >= s) & (work[order_date_col] <= e)]
if dispatch_date_col and dispatch_range and len(dispatch_range) == 2:
    s, e = pd.to_datetime(dispatch_range[0]), pd.to_datetime(dispatch_range[1])
    work = work[(work[dispatch_date_col] >= s) & (work[dispatch_date_col] <= e)]
# sku filter
if sku_col and selected_skus:
    work = work[work[sku_col].astype(str).isin([str(x) for x in selected_skus])]
# size/state filters
if size_col and selected_sizes:
    work = work[work[size_col].astype(str).isin([str(x) for x in selected_sizes])]
if state_col and selected_states:
    work = work[work[state_col].astype(str).isin([str(x) for x in selected_states])]

# status filter
if 'All' in selected_statuses:
    df_f = work.copy()
    applied_status = 'All'
else:
    sel_up = [s.upper() for s in selected_statuses]
    df_f = work[work[status_col].astype(str).str.upper().isin(sel_up)].copy()
    applied_status = ", ".join(selected_statuses)

# Ensure RTO special columns if possible (reuse v11 logic)
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

# Caption summary
cap = (f"Applied: **Status = {applied_status}**")
if order_date_col and date_range:
    cap += f" | **OrderDate = {_date(date_range[0])} → {_date(date_range[1])}**"
if dispatch_date_col and dispatch_range:
    cap += f" | **DispatchDate = {_date(dispatch_range[0])} → {_date(dispatch_range[1])}**"
if sku_col and selected_skus is not None:
    cap += f" | **SKUs = {len(selected_skus)}**"
if size_col and selected_sizes is not None:
    cap += f" | **Sizes = {len(selected_sizes)}**"
if state_col and selected_states is not None:
    cap += f" | **States = {len(selected_states)}**"
cap += f" | **Rows = {len(df_f)}**"
if (supplier_name_input or supplier_id_auto):
    cap += f" | **Supplier = {(supplier_name_input or supplier_id_auto)}**"
st.caption(cap)

# ---------------- TOP STATUS CARDS (existing v11 style) ----------------
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
filtered_total = df_f.shape[0]

cols = st.columns(len(status_labels) + 1)
i = 0
for label in status_labels:
    display_label = status_labels[label]
    cols[i].markdown(
        f"""
        <div style='background-color:{status_colors[label]}; padding:10px; border-radius:8px; text-align:center; color:white'>
            <div style="font-size:14px; margin-bottom:6px">{display_label}</div>
            <div style="font-size:22px; font-weight:700">{counts[label]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    i += 1

cols[-1].markdown(
    f"""
    <div title="इन सभी Orders को टोटल करके बताया जा रहा है" style='background-color:#37474f; padding:10px; border-radius:8px; text-align:center; color:white'>
        <div style="font-size:14px; margin-bottom:6px">📦 Filtered Total</div>
        <div style="font-size:22px; font-weight:700">{filtered_total}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------- AMOUNT SUMMARY (Filtered) — keep original calculations ----------------
st.subheader("₹ Amount Summary (Filtered — Status-wise)")
if settle_amt_col and settle_amt_col in df_f.columns:
    df_f[settle_amt_col] = pd.to_numeric(df_f[settle_amt_col], errors='coerce').fillna(0)

def _sum_by_status(df, status_name, col):
    if not col or col not in df.columns:
        return 0.0
    mask = df[status_col].astype(str).str.upper().eq(status_name.upper())
    return pd.to_numeric(df.loc[mask, col], errors='coerce').fillna(0).sum()

u_del = _sum_by_status(df_f, 'Delivered', settle_amt_col)
u_exc = _sum_by_status(df_f, 'Exchange', settle_amt_col)
u_can = _sum_by_status(df_f, 'Cancelled', settle_amt_col)
u_ret = _sum_by_status(df_f, 'Return', settle_amt_col)

u_ship = _sum_by_status(df_f, 'Shipped', settle_amt_col)
if u_ship == 0:
    u_ship = _sum_by_status(df_f, 'Shipping', settle_amt_col)

u_rto = 0.0
if 'RTO Amount' in df_f.columns:
    u_rto = pd.to_numeric(
        df_f.loc[df_f[status_col].astype(str).str.upper().eq('RTO'), 'RTO Amount'], errors='coerce'
    ).fillna(0).sum()

u_total = (u_del + u_exc + u_can) - abs(u_ret)

shipped_with_total = (u_del + u_can + u_ship) - (abs(u_ret) + abs(u_exc))
shipped_with_tooltip = "Delivered + Cancelled + Shipped - (Return + Exchange)"

abox = [
    ("Delivered ₹", u_del, "#1b5e20", "✅"),
    ("Exchange ₹",  u_exc, "#e65100", "🔄"),
    ("Cancelled ₹", u_can, "#455a64", "❌"),
    ("Return ₹",    u_ret, "#b71c1c", "↩️"),
    ("RTO ₹",       u_rto, "#6a1b9a", "📪"),
    ("Shipped With Total ₹", shipped_with_total, "#0b3d91", "🚚",),
    ("Total Amount ₹", u_total, "#0d47a1", "🧾"),
]

cc = st.columns(len(abox))
for i, (label, val, color, icon) in enumerate(abox):
    tooltip = shipped_with_tooltip if "Shipped With Total" in label else None
    if tooltip:
        cc[i].markdown(_card_html(label, val, bg=color, icon=icon, tooltip=tooltip), unsafe_allow_html=True)
    else:
        cc[i].markdown(_card_html(label, val, bg=color, icon=icon), unsafe_allow_html=True)

# ---------------- DATA PREVIEW ----------------
st.markdown("---")
st.subheader("🔎 Filtered Data Preview")
show_table = st.checkbox("Show Filtered Table", value=False, key='show_filtered_table')
show_full_table = st.checkbox("Show Full Table (may be large)", value=False, key='show_full_table')
if show_table:
    prev = df_f.copy()
    for c in [order_date_col, payment_date_col, dispatch_date_col]:
        if c in prev.columns:
            try:
                prev[c] = pd.to_datetime(prev[c], errors='coerce').dt.date
            except Exception:
                pass
    if show_full_table:
        st.dataframe(prev, use_container_width=True, height=800)
    else:
        st.dataframe(prev.head(200), use_container_width=True, height=420)
else:
    st.info("Filtered table hidden — Tick 'Show Filtered Table' to view.")

# ---------------- CHARTS (with toggle) ----------------
_figs_for_pdf = []  # collect (title, figure)

st.markdown("---")

# 1) Live Order Status Count
st.subheader("1️⃣ Live Order Status Count (Filtered)")
chart_type_status = st.radio("Chart Type (Status)", ["Bar", "Line"], horizontal=True, key="chart_status_toggle")
status_df = df_f[status_col].value_counts().reset_index()
status_df.columns = ['Status', 'Count']
if status_df.empty:
    st.warning("Filtered data में कोई status record नहीं मिला।")
else:
    if chart_type_status == "Bar":
        f1 = px.bar(status_df, x='Status', y='Count', color='Status', text='Count')
        f1.update_traces(texttemplate='%{text}', textposition='outside')
    else:
        f1 = px.line(status_df, x='Status', y='Count', markers=True, title="Live Order Status Count")
    f1.update_layout(height=560)
    st.plotly_chart(f1, use_container_width=True)
    _figs_for_pdf.append(("Live Order Status Count", f1))

# 2) Orders by Order Date
st.markdown("---")
st.subheader("2️⃣ Orders by Date (Order Date, Filtered)")
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
else:
    st.info("'Order Date' जैसा कॉलम detect नहीं हुआ।")

# 3) Orders by Dispatch Date
if dispatch_date_col:
    st.subheader("2️⃣🅰️ Orders by Dispatch Date (Filtered)")
    df_f['__disp_dt'] = pd.to_datetime(df_f[dispatch_date_col], errors='coerce')
    if dispatch_group_choice == "Month":
        g2 = df_f.groupby(df_f['__disp_dt'].dt.to_period('M'))['__disp_dt'].count().reset_index(name='Total Dispatched')
        g2[dispatch_date_col] = g2['__disp_dt'].astype(str)
        xcol2 = dispatch_date_col
    else:
        g2 = df_f.groupby(df_f['__disp_dt'].dt.date)['__disp_dt'].count().reset_index(name='Total Dispatched')
        g2.rename(columns={'__disp_dt': dispatch_date_col}, inplace=True)
        xcol2 = dispatch_date_col

    chart_type_dispatch = st.radio("Chart Type (Dispatch)", ["Bar", "Line"], horizontal=True, key="chart_dispatch_toggle")
    if not g2.empty:
        if chart_type_dispatch == "Bar":
            f2a = px.bar(g2, x=xcol2, y='Total Dispatched', text='Total Dispatched', title="Orders by Dispatch Date")
            f2a.update_traces(textposition='outside', texttemplate='%{text}')
        else:
            f2a = px.line(g2, x=xcol2, y='Total Dispatched', markers=True, title="Orders by Dispatch Date")
        f2a.update_layout(height=520)
        st.plotly_chart(f2a, use_container_width=True)
        _figs_for_pdf.append(("Orders by Dispatch Date", f2a))

# 4) Payments Received by Date
st.markdown("---")
st.subheader("3️⃣ Payments Received by Date (Filtered)")
if payment_date_col and settle_amt_col and settle_amt_col in df_f.columns:
    df_f['__pay_dt'] = pd.to_datetime(df_f[payment_date_col], errors='coerce')
    df_f[settle_amt_col] = pd.to_numeric(df_f[settle_amt_col], errors='coerce').fillna(0)
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
            f3 = px.bar(g3, x=xcol3, y=settle_amt_col, title="Payments Received by Date", text=settle_amt_col)
            f3.update_traces(textposition='outside', texttemplate='%{text:.2f}')
        else:
            f3 = px.line(g3, x=xcol3, y=settle_amt_col, markers=True, title="Payments Received by Date")
        f3.update_layout(height=520)
        st.plotly_chart(f3, use_container_width=True)
        _figs_for_pdf.append(("Payments Received by Date", f3))
else:
    st.info("'Payment Date' या 'Final Settlement Amount' कॉलम detect नहीं हुआ।")

# 4) Return & Exchange % of Delivered — as CARDS + Pivot + Chart toggle
st.markdown("---")
st.subheader("4️⃣ Return & Exchange % of Delivered (Filtered)")
_deliv = int(status_df[status_df['Status'].str.upper()== 'DELIVERED']['Count'].sum()) if not status_df.empty else 0
_ret   = int(status_df[status_df['Status'].str.upper()== 'RETURN']['Count'].sum()) if not status_df.empty else 0
_exc   = int(status_df[status_df['Status'].str.upper()== 'EXCHANGE']['Count'].sum()) if not status_df.empty else 0

ret_pct = (_ret/_deliv*100) if _deliv else 0.0
exc_pct = (_exc/_deliv*100) if _deliv else 0.0

c1, c2, c3 = st.columns(3)
c1.markdown(f"""
<div style='background:#1565c0; padding:16px; border-radius:12px; color:white'>
  <div style='font-size:18px; font-weight:800'>📦 Delivered</div>
  <div style='font-size:28px; font-weight:900; margin-top:6px'>{_deliv}</div>
  <div style='opacity:.9'>100.00%</div>
</div>
""", unsafe_allow_html=True)

c2.markdown(f"""
<div style='background:#c62828; padding:16px; border-radius:12px; color:white'>
  <div style='font-size:18px; font-weight:800'>↩️ Return</div>
  <div style='font-size:28px; font-weight:900; margin-top:6px'>{_ret}</div>
  <div style='opacity:.9'>{ret_pct:.2f}%</div>
</div>
""", unsafe_allow_html=True)

c3.markdown(f"""
<div style='background:#ef6c00; padding:16px; border-radius:12px; color:white'>
  <div style='font-size:18px; font-weight:800'>🔄 Exchange</div>
  <div style='font-size:28px; font-weight:900; margin-top:6px'>{_exc}</div>
  <div style='opacity:.9'>{exc_pct:.2f}%</div>
</div>
""", unsafe_allow_html=True)

# pivot + chart toggle
pivot_df = pd.DataFrame({
    'Metric': ['Delivered', 'Return', 'Exchange', 'Return % of Delivered', 'Exchange % of Delivered'],
    'Value':  [_deliv, _ret, _exc, round(ret_pct, 2), round(exc_pct, 2)]
})

cpt1, cpt2 = st.columns([1,2])
with cpt1:
    st.dataframe(pivot_df, use_container_width=True, height=220)
with cpt2:
    chart_type_ret = st.radio("Chart Type (Return/Exchange)", ["Bar", "Line"], horizontal=True, key="chart_return_toggle")
    f4 = None
    if chart_type_ret == "Bar":
        f4 = px.bar(
            pd.DataFrame({'Type':['Return %','Exchange %'], 'Percent':[ret_pct, exc_pct]}),
            x='Type', y='Percent', text='Percent',
            title='Return/Exchange % of Delivered'
        )
        f4.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
    else:
        f4 = px.line(pd.DataFrame({'Type':['Return %','Exchange %'], 'Percent':[ret_pct, exc_pct]}), x='Type', y='Percent', markers=True, title='Return/Exchange % of Delivered')
    f4.update_layout(height=360)
    st.plotly_chart(f4, use_container_width=True)
    _figs_for_pdf.append(("Return/Exchange % of Delivered", f4))

# ---------------- PROFIT SECTION (from original v11) ----------------
st.markdown("---")
st.subheader("💹 Profit Calculation (Corrected)")
profit_sum = _sum(df_f[profit_amt_col]) if profit_amt_col and profit_amt_col in df_f.columns else 0.0
return_loss_sum = abs(u_ret)  # returns treated as loss (using amount earlier)
exchange_loss_sum = _sum(df_f[exchange_loss_col]) if exchange_loss_col and exchange_loss_col in df_f.columns else 0.0
net_profit = profit_sum - (return_loss_sum + abs(exchange_loss_sum))

pc1, pc2, pc3, pc4 = st.columns(4)
pc1.markdown(_card_html("Profit Amount (Σ)", profit_sum, bg="#1b5e20", icon="💹"), unsafe_allow_html=True)
pc2.markdown(_card_html("Return Loss (Σ)", return_loss_sum, bg="#b71c1c", icon="➖"), unsafe_allow_html=True)
pc3.markdown(_card_html("Exchange Loss (Σ)", exchange_loss_sum, bg="#f57c00", icon="🔄"), unsafe_allow_html=True)
pc4.markdown(_card_html("Net Profit", net_profit, bg="#0d47a1", icon="🧮"), unsafe_allow_html=True)

# ---------------- ADS COST ANALYSIS (existing logic retained + fixed) ----------------
st.markdown("---")
st.subheader("📢 Ads Cost Analysis (STRICT — Deduction Duration + Total Ads Cost)")
ads_table_for_export = None

with st.expander("Ads Cost Analysis", expanded=True):
    if ads_df is None or ads_df.empty:
        st.info("'Ads Cost' sheet नहीं मिली।")
    else:
        miss = []
        if 'Deduction Duration' not in ads_df.columns: 
            miss.append('Deduction Duration')
        if 'Total Ads Cost' not in ads_df.columns: 
            miss.append('Total Ads Cost')

        if miss:
            st.error("इन columns की आवश्यकता है: " + ", ".join(miss))
        else:
            # Date conversion
            ads_df['Deduction Duration'] = pd.to_datetime(
                ads_df['Deduction Duration'], errors='coerce'
            ).dt.date

            # Date range filter
            dmin, dmax = ads_df['Deduction Duration'].min(), ads_df['Deduction Duration'].max()
            rng = st.date_input(
                "Deduction Duration — Date Range", 
                value=[dmin, dmax], 
                key='ads_date_range'
            ) if pd.notna(dmin) and pd.notna(dmax) else None

            if rng and len(rng) == 2:
                d0, d1 = rng
                ads_view = ads_df[
                    (ads_df['Deduction Duration'] >= d0) & (ads_df['Deduction Duration'] <= d1)
                ].copy()
            else:
                ads_view = ads_df.copy()

            # Orders per date (if order date available)
            orders_dates = None
            if order_date_col and order_date_col in orders_df.columns:
                orders_dates = pd.to_datetime(
                    orders_df[order_date_col], errors='coerce'
                ).dt.date

            # Calculate per-order cost
            ads_view['Total Ads Cost'] = pd.to_numeric(
                ads_view['Total Ads Cost'], errors='coerce'
            ).fillna(0)

            def orders_count_for_date(dt):
                if orders_dates is None:
                    return 0
                return int((orders_dates == dt).sum())

            ads_view['Orders Count'] = ads_view['Deduction Duration'].apply(orders_count_for_date)
            ads_view['Per Order Cost'] = ads_view.apply(
                lambda r: (r['Total Ads Cost'] / r['Orders Count']) 
                          if r['Orders Count'] and r['Orders Count'] > 0 else 0.0,
                axis=1
            )

            # Total cost card
            ads_sum = ads_view['Total Ads Cost'].sum()
            st.markdown(
                _card_html("Total Ads Cost (Σ)", ads_sum, bg="#4a148c", icon="📣"), 
                unsafe_allow_html=True
            )

            # Chart
            if not ads_view.empty:
                gads = ads_view.groupby('Deduction Duration', as_index=False)['Total Ads Cost'].sum().sort_values('Deduction Duration')

                chart_type_ads = st.radio(
                    "Chart Type (Ads)", ["Bar", "Line"], horizontal=True, key="chart_ads_toggle"
                )

                if chart_type_ads == "Bar":
                    fads = px.bar(
                        gads, 
                        x='Deduction Duration', 
                        y='Total Ads Cost', 
                        text='Total Ads Cost', 
                        title="Ads Cost Over Time"
                    )
                    fads.update_traces(textposition="outside")
                else:
                    fads = px.line(
                        gads, 
                        x='Deduction Duration', 
                        y='Total Ads Cost', 
                        markers=True, 
                        title="Ads Cost Over Time"
                    )

                fads.update_layout(height=480)
                st.plotly_chart(fads, use_container_width=True)
                _figs_for_pdf.append(("Ads Cost Over Time", fads))

            # Table
            ads_show_cols = ['Deduction Duration', 'Total Ads Cost', 'Orders Count', 'Per Order Cost']
            ads_table_for_export = ads_view[ads_show_cols].sort_values('Deduction Duration', ascending=False)

            show_ads_table = st.checkbox("Show Ads Cost Table", value=True)
            if show_ads_table:
                st.dataframe(ads_table_for_export, use_container_width=True, height=350)


# ---------------- SAFE FILENAME HELPER ----------------
def _safe_filename(name: str, fallback: str) -> str:
    import os as _os
    name = (name or "").strip()
    if not name:
        return fallback
    safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in name)[:40]
    base, ext = _os.path.splitext(fallback)
    return f"{base}__{safe}{ext}"

# ---------------- EXCEL EXPORT ----------------
st.markdown("---")
st.subheader("📥 Download Excel Summary")
excel_buf = BytesIO()
with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
    orders_df.to_excel(writer, index=False, sheet_name="Raw Orders")
    df_f.to_excel(writer, index=False, sheet_name="Filtered Orders")
    status_df.to_excel(writer, index=False, sheet_name="Status Summary (Filtered)")
    pd.DataFrame({
        'Metric': ['Delivered','Return','Exchange','Return % of Delivered','Exchange % of Delivered'],
        'Value': [_deliv, _ret, _exc, f"{ret_pct:.2f}%", f"{exc_pct:.2f}%"]
    }).to_excel(writer, index=False, sheet_name="Return-Exchange Summary")
    pd.DataFrame({
        'Label': ['Delivered ₹','Exchange ₹','Cancelled ₹','Return ₹','RTO ₹','Shipped With Total ₹','Total Amount ₹'],
        'Value': [u_del, u_exc, u_can, u_ret, u_rto, shipped_with_total, u_total]
    }).to_excel(writer, index=False, sheet_name="Amount Summary (Filtered)")
    pd.DataFrame({
        'Metric': ['Profit Amount (Σ)', 'Return Loss (Σ)', 'Exchange Loss (Σ)', 'Net Profit'],
        'Value': [profit_sum, return_loss_sum, exchange_loss_sum, net_profit]
    }).to_excel(writer, index=False, sheet_name="Profit Summary (Corrected)")
    if ads_table_for_export is not None and not ads_table_for_export.empty:
        ads_table_for_export.to_excel(writer, index=False, sheet_name="Ads Cost Per Day")
    if ads_df is not None and not ads_df.empty:
        ads_df.to_excel(writer, index=False, sheet_name="Ads Cost Raw")
    # metadata sheet
    meta = pd.DataFrame([[supplier_name_input or "", supplier_id_auto or "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")]], columns=["Supplier Name","Supplier ID","Generated"])
    meta.to_excel(writer, index=False, sheet_name="Meta")

st.download_button(
    "⬇️ Download Excel File",
    data=excel_buf.getvalue(),
    file_name=_safe_filename(supplier_name_input or supplier_id_auto, "Meesho_Report_test_11.xlsx"),
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)

# ---------------- PDF EXPORT HELPERS ----------------
def _make_summary_table_figure(supplier_name: str = "", supplier_id: str = ""):
    rows = [
        ["Delivered (cnt)", counts.get('Delivered', 0)],
        ["Return (cnt)",    counts.get('Return', 0)],
        ["Exchange (cnt)",  counts.get('Exchange', 0)],
        ["Cancelled (cnt)", counts.get('Cancelled', 0)],
        ["Shipped (cnt)",   counts.get('Shipped', 0)],
        ["RTO (cnt)",       counts.get('RTO', 0)],
        ["Filtered Total",  filtered_total],
        ["—", "—"],
        ["Delivered ₹", u_del],
        ["Exchange ₹",  u_exc],
        ["Cancelled ₹", u_can],
        ["Return ₹",    u_ret],
        ["RTO ₹",       u_rto],
        ["Shipped With Total ₹", shipped_with_total],
        ["Total Amount ₹", u_total],
        ["—", "—"],
        ["Profit Amount (Σ)", profit_sum],
        ["Return Loss (Σ)", return_loss_sum],
        ["Exchange Loss (Σ)", exchange_loss_sum],
        ["Net Profit", net_profit],
    ]
    figx, ax = plt.subplots(figsize=(12, 8))
    ax.axis('off')
    table = ax.table(
        cellText=rows,
        colLabels=["Metric", "Value"],
        loc='center',
        cellLoc='center',
        colColours=["#e3f2fd", "#e3f2fd"],
    )
    n_rows = len(rows) + 1
    for r in range(1, n_rows):
        color = "#f9fbe7" if r % 2 == 1 else "#fffde7"
        try:
            table[(r, 0)].set_facecolor(color)
            table[(r, 1)].set_facecolor(color)
        except Exception:
            pass
    table.auto_set_font_size(False)
    table.set_fontsize(12)
    table.scale(1.45, 1.6)
    title = "📦 Orders & Profit Summary (Filtered)"
    if supplier_name.strip():
        title += f" — Supplier: {supplier_name}"
    elif supplier_id:
        title += f" — Supplier ID: {supplier_id}"
    ax.set_title(title, fontsize=18, fontweight='bold')
    return figx

def _export_pdf_detailed(figs_with_titles, file_name: str, supplier_name: str = "", supplier_id: str = "") -> bytes:
    if not _kaleido_ok:
        raise RuntimeError("kaleido missing (Plotly -> image export)")
    tmpdir = tempfile.mkdtemp(prefix="meesho_test11_det_")
    out_pdf_path = os.path.join(tmpdir, file_name)

    with PdfPages(out_pdf_path) as pdf:
        # summary
        fig_summary = _make_summary_table_figure(supplier_name, supplier_id)
        pdf.savefig(fig_summary, bbox_inches='tight')
        plt.close(fig_summary)

        # Ads table page (if exists)
        if ads_table_for_export is not None and not ads_table_for_export.empty:
            try:
                fig_ads, ax_ads = plt.subplots(figsize=(11.69, 8.27))
                ax_ads.axis('off')
                ads_tab = ads_table_for_export.head(31).copy()
                ads_tab_values = ads_tab.values.tolist()
                colLabels = list(ads_tab.columns)
                table = ax_ads.table(cellText=ads_tab_values, colLabels=colLabels, loc='center', cellLoc='center')
                table.auto_set_font_size(False)
                table.set_fontsize(9)
                table.scale(1, 1.2)
                ax_ads.set_title("Ads Cost — Deduction Duration (up to 31 days)", fontsize=14, fontweight='bold')
                pdf.savefig(fig_ads, bbox_inches='tight')
                plt.close(fig_ads)
            except Exception:
                pass

        # each plotly fig -> png -> page
        for (title, fig) in figs_with_titles:
            try:
                buf = BytesIO()
                fig.write_image(buf, format="png", engine="kaleido", width=2200, height=1400, scale=2)
                buf.seek(0)
                pil_img = Image.open(buf).convert("RGB")

                f, ax = plt.subplots(figsize=(12, 8))
                ax.imshow(pil_img)
                ax.axis('off')
                full_title = title
                if supplier_name.strip():
                    full_title += f" — {supplier_name}"
                elif supplier_id:
                    full_title += f" — {supplier_id}"
                ax.set_title(full_title, fontsize=14, fontweight='bold')
                pdf.savefig(f, bbox_inches='tight')
                plt.close(f)
            except Exception as e:
                f_err, ax_err = plt.subplots(figsize=(12, 7))
                ax_err.axis('off')
                ax_err.text(
                    0.5, 0.5,
                    "Could not render chart: " + str(title) + "\nError: " + str(e),
                    ha='center', va='center', fontsize=14
                )
                pdf.savefig(f_err, bbox_inches='tight')
                plt.close(f_err)

    with open(out_pdf_path, 'rb') as f:
        return f.read()

def _export_pdf_compact(figs_with_titles, file_name: str, supplier_name: str = "", supplier_id: str = "") -> bytes:
    if not _kaleido_ok:
        raise RuntimeError("kaleido missing (Plotly -> image export)")
    tmpdir = tempfile.mkdtemp(prefix="meesho_test11_cmp_")
    png_paths = []

    # summary table PNG
    fig_sum = _make_summary_table_figure(supplier_name, supplier_id)
    table_png = os.path.join(tmpdir, "summary_table.png")
    fig_sum.savefig(table_png, dpi=240, bbox_inches='tight')
    plt.close(fig_sum)
    png_paths.append(("Summary", table_png))

    # convert each plotly fig to png
    for (title, fig) in figs_with_titles:
        try:
            p = os.path.join(tmpdir, f"fig_{abs(hash(title))}.png")
            fig.update_layout(title=title)
            fig.write_image(p, format="png", engine="kaleido", width=2000, height=1200, scale=2)
            png_paths.append((title, p))
        except Exception as e:
            p = os.path.join(tmpdir, f"fig_err_{abs(hash(title))}.png")
            fig_err = plt.figure(figsize=(8, 5))
            ax = fig_err.add_subplot(111)
            ax.axis('off')
            ax.text(0.5, 0.5, "Error rendering: " + str(title) + "\nError: " + str(e), ha='center', va='center', fontsize=14)
            fig_err.savefig(p, dpi=200, bbox_inches='tight')
            plt.close(fig_err)
            png_paths.append((title + " (error)", p))

    out_pdf_path = os.path.join(tmpdir, file_name)
    pages = math.ceil(len(png_paths) / 4)

    with PdfPages(out_pdf_path) as pdf:
        for page in range(pages):
            start = page * 4
            chunk = png_paths[start:start + 4]
            fig, axes = plt.subplots(2, 2, figsize=(12, 8))
            if supplier_name_input.strip():
                fig.suptitle(f"Supplier: {supplier_name_input}", fontsize=14, fontweight='bold')
            elif supplier_id_auto:
                fig.suptitle(f"Supplier ID: {supplier_id_auto}", fontsize=14, fontweight='bold')
            axes = axes.flatten()
            for i in range(4):
                ax = axes[i]
                ax.axis('off')
                if i < len(chunk):
                    t, img_path = chunk[i]
                    try:
                        img = Image.open(img_path).convert('RGB')
                        ax.imshow(img)
                        ax.set_title(t, fontsize=12, fontweight='bold')
                    except Exception as e:
                        ax.text(0.5, 0.5, "Unable to show image: " + str(e), ha='center', va='center')
            fig.tight_layout()
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)

    with open(out_pdf_path, 'rb') as f:
        return f.read()

# ---------------- PDF BUTTONS ----------------
st.markdown("---")
st.subheader("📄 Download PDF Reports (Color)")

col_pdf1, col_pdf2 = st.columns(2)
with col_pdf1:
    if _kaleido_ok:
        try:
            pdf_bytes_det = _export_pdf_detailed(
                _figs_for_pdf,
                file_name=_safe_filename(supplier_name_input or supplier_id_auto, "Meesho_Report_Detailed_test11.pdf"),
                supplier_name=supplier_name_input,
                supplier_id=supplier_id_auto
            )
            st.download_button(
                label="⬇️ Download PDF (Detailed)",
                data=pdf_bytes_det,
                file_name=_safe_filename(supplier_name_input or supplier_id_auto, "Meesho_Report_Detailed_test11.pdf"),
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            st.error("Detailed PDF export में समस्या: " + str(e))
    else:
        st.info("Detailed PDF के लिए kaleido ज़रूरी है।")

with col_pdf2:
    if _kaleido_ok:
        try:
            pdf_bytes_cmp = _export_pdf_compact(
                _figs_for_pdf,
                file_name=_safe_filename(supplier_name_input or supplier_id_auto, "Meesho_Report_Compact_test11.pdf"),
                supplier_name=supplier_name_input,
                supplier_id=supplier_id_auto
            )
            st.download_button(
                label="⬇️ Download PDF (Compact Grid)",
                data=pdf_bytes_cmp,
                file_name=_safe_filename(supplier_name_input or supplier_id_auto, "Meesho_Report_Compact_test11.pdf"),
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            st.error("Compact PDF export में समस्या: " + str(e))
    else:
        st.info("Compact PDF के लिए kaleido ज़रूरी है।")

st.success("✅ test_11 ready — merged original features + SKU Groups + Chart toggles + PDF/Excel improvements")

