# Meesho_Dashboard_Final_v6.py
# Final merged — Old look + Full features + SKU Groups fixed + Shipping strict sum + Grand Total + Memory safe
# Date: 2025-11-01
# Version: Final v6 (merged)

import os
import re
import math
import tempfile
import gc
from io import BytesIO
from datetime import datetime

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
    import kaleido
    _kaleido_ok = True
except Exception:
    _kaleido_ok = False

# ---------------- Page setup & constants ----------------
__VERSION__ = "Meesho Dashboard — Final v6"
st.set_page_config(layout="wide", page_title=__VERSION__, initial_sidebar_state="expanded")
st.title(f"📦 {__VERSION__}")
st.caption("Merged: Old UI & full features + SKU Groups & Shipping fixes")

# ---------------- Helpers ----------------
def _detect_col(df, *keyword_groups):
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

def _sum(series):
    if series is None:
        return 0.0
    return pd.to_numeric(series, errors='coerce').fillna(0).sum()

def extract_supplier_id(filename: str):
    if not filename:
        return ""
    n = os.path.basename(filename)
    name, _ = os.path.splitext(n)
    if "_" in name:
        return name.split("_",1)[0]
    m = re.match(r"^(\d+)", name)
    return m.group(1) if m else name

def _card_html(title, value, bg="#0d47a1", icon="", extra_small=None):
    # nice card html similar to old look
    val = _format(value)
    tt = f"<div style='font-size:12px; opacity:.9'>{extra_small}</div>" if extra_small else ""
    return f"""
    <div style="background:{bg}; padding:12px; border-radius:10px; color:white; text-align:center; min-height:80px;">
      <div style="font-weight:700; font-size:14px">{icon} {title}</div>
      <div style="font-size:20px; font-weight:800; margin-top:8px">{val}</div>
      {tt}
    </div>
    """

def _format(v):
    try:
        if isinstance(v, (int, np.integer)):
            return f"{v:,}"
        if isinstance(v, (float, np.floating)):
            return f"₹{v:,.2f}"
        return str(v)
    except Exception:
        return str(v)

def _make_table_figure(rows, col_labels, title, striped=True):
    # returns matplotlib figure with table (for PDF)
    fig, ax = plt.subplots(figsize=(11.0, max(2, len(rows)/3)))
    ax.axis('off')
    table = ax.table(cellText=rows, colLabels=col_labels, loc='center', cellLoc='center')
    if striped:
        n_rows = len(rows)
        for r in range(1, n_rows+1):
            color = "#f9fbe7" if r % 2 == 1 else "#fffde7"
            try:
                table[(r,0)].set_facecolor(color)
                table[(r,1)].set_facecolor(color)
            except Exception:
                pass
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.2)
    ax.set_title(title, fontsize=14, fontweight='bold')
    return fig

# ---------------- Sidebar: Upload & controls ----------------
st.sidebar.header("Upload & Controls")
supplier_name = st.sidebar.text_input("Supplier / Client Name", value="")
up = st.sidebar.file_uploader("Upload Excel/CSV (Order Payments sheet expected)", type=["xlsx","csv"])

# session state keys
if 'sku_groups' not in st.session_state:
    st.session_state['sku_groups'] = []  # list of dicts {name, pattern, skus}
if '__last_sku_group_selection' not in st.session_state:
    st.session_state['__last_sku_group_selection'] = None

# if no file, stop
if up is None:
    st.info("Please upload an Excel or CSV file (sheet with Order Payments).")
    st.stop()

supplier_id_auto = extract_supplier_id(up.name)

# memory-safe: deny extremely large file (avoid browser OOM)
try:
    up_size = up.size
except Exception:
    up_size = None

if up_size and up_size > 120_000_000:  # 120MB
    st.error("File too large (>120MB). Please upload a smaller file or split it.")
    st.stop()

# ---------------- Read file (cached) ----------------
@st.cache_data(show_spinner=False)
def _read_file(file):
    name = file.name.lower()
    if name.endswith('.csv'):
        df = pd.read_csv(file)
        return df, None
    xls = pd.ExcelFile(file)
    # try to find sheet names heuristically
    sheet_map = {s.lower(): s for s in xls.sheet_names}
    orders_sheet = sheet_map.get('order payments', xls.sheet_names[0])
    orders = pd.read_excel(xls, sheet_name=orders_sheet)
    ads = None
    if 'ads cost' in sheet_map:
        try:
            ads = pd.read_excel(xls, sheet_name=sheet_map['ads cost'])
        except Exception:
            ads = None
    return orders, ads

try:
    orders_df, ads_df = _read_file(up)
except Exception as e:
    st.error(f"Failed to read file: {e}")
    st.stop()

if orders_df is None or orders_df.empty:
    st.error("Orders data not found in the uploaded file.")
    st.stop()

orders_df.columns = [str(c).strip() for c in orders_df.columns]
if ads_df is not None:
    ads_df.columns = [str(c).strip() for c in ads_df.columns]

# ---------------- Detect important columns ----------------
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
    st.error("Status column could not be detected. Please ensure the uploaded sheet contains status column (e.g., Live Order Status).")
    st.stop()

# parse date columns where present
for c in [order_date_col, payment_date_col, dispatch_date_col]:
    if c and c in orders_df.columns:
        orders_df[c] = pd.to_datetime(orders_df[c], errors='coerce')

# ---------------- Sidebar Filters (SKU groups UI + others) ----------------
st.sidebar.markdown("### Filters")
with st.sidebar.expander("SKU Grouping (create & apply)", expanded=True):
    if sku_col and sku_col in orders_df.columns:
        st.markdown("Type a keyword & click ➕ Add Group. Then select group(s) to apply.")
        skus_all = sorted([str(x) for x in orders_df[sku_col].dropna().unique().tolist()])

        sku_search_q = st.text_input("Search SKU keyword (part of SKU)", value="", key='sku_search_q')
        if sku_search_q:
            matches = [s for s in skus_all if sku_search_q.lower() in s.lower()]
            st.caption(f"Matches: {len(matches)} — preview: {matches[:12]}")
        else:
            matches = []

        new_group_name = st.text_input("Group name (optional)", value=sku_search_q or "", key='sku_new_group_name')

        ca, cb, cc = st.columns([2,1,1])
        with ca:
            if st.button("➕ Add Group"):
                pattern = (sku_search_q or new_group_name or "").strip()
                if not pattern:
                    st.warning("Please provide a keyword or name for the group.")
                else:
                    matched = [s for s in skus_all if pattern.lower() in s.lower()]
                    if not matched:
                        st.warning("No SKUs matched the pattern.")
                    else:
                        existing = [g['pattern'] for g in st.session_state['sku_groups']]
                        if pattern in existing:
                            # update
                            for g in st.session_state['sku_groups']:
                                if g['pattern'] == pattern:
                                    g['skus'] = matched
                                    g['name'] = new_group_name or pattern
                            st.success(f"Group '{pattern}' updated ({len(matched)} SKUs).")
                        else:
                            st.session_state['sku_groups'].append({'name': new_group_name or pattern, 'pattern': pattern, 'skus': matched})
                            st.success(f"Group '{new_group_name or pattern}' added ({len(matched)} SKUs).")
                        # force rerun so selection widgets update
                        st.experimental_rerun()
        with cb:
            if st.button("🧹 Clear Groups"):
                st.session_state['sku_groups'] = []
                if 'sku_group_multiselect' in st.session_state: del st.session_state['sku_group_multiselect']
                if 'selected_skus' in st.session_state: del st.session_state['selected_skus']
                st.experimental_rerun()
        with cc:
            st.write("")

        if st.session_state.get('sku_groups'):
            st.markdown("**Existing SKU Groups**")
            grp_labels = [f"{i+1}. {g['name']} ({len(g['skus'])})" for i,g in enumerate(st.session_state['sku_groups'])]
            chosen_groups = st.multiselect("Select Groups to apply (their SKUs will be merged)", options=grp_labels, key='sku_group_multiselect')
            include_live = st.checkbox("Include live-search matches (if any)", value=True)
            manual_matches = [s for s in skus_all if sku_search_q.lower() in s.lower()] if (sku_search_q and include_live) else []
            # union for default selection in selected_skus
            union_sel = []
            for label in chosen_groups:
                try:
                    idx = int(label.split('.',1)[0]) - 1
                    if 0 <= idx < len(st.session_state['sku_groups']):
                        union_sel.extend(st.session_state['sku_groups'][idx]['skus'])
                except Exception:
                    continue
            union_selected = sorted(list(set(union_sel + manual_matches)))
            selected_skus = st.multiselect("Selected SKU(s) (groups + manual)", options=skus_all, default=union_selected, key='selected_skus')
        else:
            select_all = st.checkbox("Select all SKUs by default", value=True)
            sku_opts = [s for s in skus_all if sku_search_q.lower() in s.lower()] if sku_search_q else skus_all
            default_sel = sku_opts if select_all else []
            selected_skus = st.multiselect("Select SKU(s)", options=sku_opts, default=default_sel, key='selected_skus')
    else:
        st.caption("SKU column not found — cannot create groups here.")
    st.markdown("---")
    # sizes & states
    if size_col and size_col in orders_df.columns:
        size_opts = sorted([str(x) for x in orders_df[size_col].dropna().unique().tolist()])
        selected_sizes = st.multiselect("Size", options=size_opts, default=[], key='selected_sizes')
    else:
        selected_sizes = []
    if state_col and state_col in orders_df.columns:
        state_opts = sorted([str(x) for x in orders_df[state_col].dropna().unique().tolist()])
        selected_states = st.multiselect("State", options=state_opts, default=[], key='selected_states')
    else:
        selected_states = []

with st.sidebar.expander("Status & Date Filters", expanded=False):
    status_options = ['All','Delivered','Return','RTO','Exchange','Cancelled','Shipped', ""]
    selected_statuses = st.multiselect("Status", options=status_options, default=['All'], key='status_multiselect')
    if order_date_col:
        odmin = pd.to_datetime(orders_df[order_date_col]).min()
        odmax = pd.to_datetime(orders_df[order_date_col]).max()
        order_date_range = st.date_input("Order Date Range", value=[odmin.date() if pd.notna(odmin) else odmin, odmax.date() if pd.notna(odmax) else odmax], key='order_date_range')
        group_choice = st.selectbox("Group by (Orders)", ["Month","Day"], index=0, key='group_choice')
    else:
        order_date_range = None
        group_choice = "Month"
    if dispatch_date_col:
        dmin = pd.to_datetime(orders_df[dispatch_date_col]).min()
        dmax = pd.to_datetime(orders_df[dispatch_date_col]).max()
        dispatch_date_range = st.date_input("Dispatch Date Range", value=[dmin.date() if pd.notna(dmin) else dmin, dmax.date() if pd.notna(dmax) else dmax], key='dispatch_date_range')
        dispatch_group_choice = st.selectbox("Group by (Dispatch)", ["Month","Day"], index=0, key='dispatch_group_choice')
    else:
        dispatch_date_range = None
        dispatch_group_choice = "Month"

if st.sidebar.button("🔄 Clear All Filters"):
    keys = ['status_multiselect','sku_search_q','selected_skus','selected_sizes','selected_states',
            'order_date_range','dispatch_date_range','group_choice','dispatch_group_choice',
            'sku_group_multiselect','sku_new_group_name','show_filtered_table','show_full_table']
    for k in keys:
        if k in st.session_state:
            del st.session_state[k]
    st.session_state['sku_groups'] = []
    st.experimental_rerun()

# ---------------- APPLY FILTERS (careful ordering) ----------------
work = orders_df.copy()

# date filters early
if order_date_col and order_date_range and len(order_date_range) == 2:
    s, e = pd.to_datetime(order_date_range[0]), pd.to_datetime(order_date_range[1])
    work = work[(work[order_date_col] >= s) & (work[order_date_col] <= e)]
if dispatch_date_col and 'dispatch_date_range' in locals() and dispatch_date_range and len(dispatch_date_range) == 2:
    s, e = pd.to_datetime(dispatch_date_range[0]), pd.to_datetime(dispatch_date_range[1])
    work = work[(work[dispatch_date_col] >= s) & (work[dispatch_date_col] <= e)]

# --- SKU GROUP APPLICATION (stable) ---
chosen_group_labels = st.session_state.get('sku_group_multiselect', []) if 'sku_group_multiselect' in st.session_state else []
# rerun-on-change trick to ensure widget state fully propagates (prevents inconsistent selection)
if st.session_state.get('__last_sku_group_selection') != chosen_group_labels:
    st.session_state['__last_sku_group_selection'] = list(chosen_group_labels)
    # preserve explicit selected_skus across rerun
    st.experimental_rerun()

# compute SKUs from chosen groups
selected_group_skus = []
for label in chosen_group_labels:
    try:
        idx = int(label.split('.',1)[0]) - 1
        if 0 <= idx < len(st.session_state['sku_groups']):
            selected_group_skus.extend(st.session_state['sku_groups'][idx]['skus'])
    except Exception:
        continue

explicit_selected_skus = st.session_state.get('selected_skus', []) if 'selected_skus' in st.session_state else []
# union & dedupe
final_selected_skus = sorted(list(dict.fromkeys([str(x) for x in (selected_group_skus + explicit_selected_skus) if x is not None and str(x).strip() != ""])))

if final_selected_skus and sku_col and sku_col in work.columns:
    work = work[work[sku_col].astype(str).isin(final_selected_skus)]
    st.markdown(f"**Active SKU filter:** {len(final_selected_skus)} SKUs applied")
else:
    st.markdown("**Active SKU filter:** None (all SKUs)")

# apply size/state filters
if size_col and selected_sizes:
    work = work[work[size_col].astype(str).isin([str(x) for x in selected_sizes])]
if state_col and selected_states:
    work = work[work[state_col].astype(str).isin([str(x) for x in selected_states])]

# status filter (allow blank)
if 'All' in selected_statuses:
    df_f = work.copy()
    applied_status = 'All'
else:
    include_blank = "" in selected_statuses
    nonblank_selected = [s for s in selected_statuses if s != ""]
    sel_up = [s.upper() for s in nonblank_selected]
    if sel_up and include_blank:
        mask_sel = work[status_col].astype(str).str.upper().isin(sel_up) | (work[status_col].isna() | (work[status_col].astype(str).str.strip() == ""))
    elif sel_up:
        mask_sel = work[status_col].astype(str).str.upper().isin(sel_up)
    else:
        mask_sel = (work[status_col].isna() | (work[status_col].astype(str).str.strip() == ""))
    df_f = work[mask_sel].copy()
    applied_status = ", ".join(selected_statuses)

# ensure RTO columns computation if needed
def _ensure_rto_cols(df, status_col):
    out = df.copy()
    need = ['Listing Price (Incl. taxes)', 'Total Sale Amount (Incl. Shipping & GST)']
    if status_col and all(c in out.columns for c in need):
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

# caption summary on top (old look)
cap = f"Status: {applied_status}"
if order_date_col and order_date_range:
    cap += f" | OrderDate: {order_date_range[0]} → {order_date_range[1]}"
if final_selected_skus:
    cap += f" | SKUs: {len(final_selected_skus)}"
cap += f" | Rows: {len(df_f)}"
if supplier_name or supplier_id_auto:
    cap += f" | Supplier: {supplier_name or supplier_id_auto}"
st.caption(cap)

# ---------------- TOP STATUS CARDS (old look) + Platform Recovery + Grand Total ----------------
status_labels = ['Delivered','Return','Exchange','Cancelled','Shipped','RTO']
status_display = {'Delivered':'✅ Delivered','Return':'↩️ Return','Exchange':'🔄 Exchange','Cancelled':'❌ Cancelled','Shipped':'🚚 Shipped','RTO':'📪 RTO'}
status_color = {'Delivered':'#2e7d32','Return':'#c62828','Exchange':'#f57c00','Cancelled':'#616161','Shipped':'#1565c0','RTO':'#8e24aa'}

counts = {}
for s in status_labels:
    counts[s] = int(df_f[status_col].astype(str).str.upper().eq(s.upper()).sum())

blank_mask = (df_f[status_col].isna() | (df_f[status_col].astype(str).str.strip() == ""))
platform_recovery_count = int(blank_mask.sum())
filtered_total = df_f.shape[0]
grand_total_count = filtered_total

cols = st.columns(len(status_labels) + 2)
for i, s in enumerate(status_labels):
    cols[i].markdown(
        f"""<div style='background:{status_color[s]}; padding:10px; border-radius:8px; text-align:center; color:white'>
             <div style='font-size:14px'>{status_display[s]}</div>
             <div style='font-size:20px; font-weight:800'>{counts[s]}</div>
           </div>""",
        unsafe_allow_html=True
    )

# Platform Recovery
cols[len(status_labels)].markdown(
    f"""<div style='background:#37474f; padding:10px; border-radius:8px; text-align:center; color:white'>
         <div style='font-size:14px'>📦 Platform Recovery (Blank Status)</div>
         <div style='font-size:20px; font-weight:800'>{platform_recovery_count}</div>
       </div>""", unsafe_allow_html=True)

# Grand total
cols[len(status_labels)+1].markdown(
    f"""<div style='background:#0d47a1; padding:10px; border-radius:8px; text-align:center; color:white'>
         <div style='font-size:14px'>📊 Grand Total (Count)</div>
         <div style='font-size:20px; font-weight:800'>{grand_total_count}</div>
       </div>""", unsafe_allow_html=True)

# ---------------- AMOUNT SUMMARY (old style visuals) ----------------
st.markdown("---")
st.subheader("₹ Amount Summary (Filtered — Status-wise)")

if settle_amt_col and settle_amt_col in df_f.columns:
    df_f[settle_amt_col] = pd.to_numeric(df_f[settle_amt_col], errors='coerce').fillna(0)

def _sum_by_status(df, status_name):
    if not settle_amt_col or settle_amt_col not in df.columns:
        return 0.0
    return pd.to_numeric(df.loc[df[status_col].astype(str).str.upper() == status_name.upper(), settle_amt_col], errors='coerce').fillna(0).sum()

u_del = _sum_by_status(df_f, 'Delivered')
u_ret = _sum_by_status(df_f, 'Return')
u_exc = _sum_by_status(df_f, 'Exchange')
u_can = _sum_by_status(df_f, 'Cancelled')
# SHIPPING strict: only status == 'Shipped'
u_ship = _sum_by_status(df_f, 'Shipped')

u_rto = 0.0
if 'RTO Amount' in df_f.columns:
    u_rto = pd.to_numeric(df_f.loc[df_f[status_col].astype(str).str.upper()=='RTO','RTO Amount'], errors='coerce').fillna(0).sum()

platform_recovery_amt = pd.to_numeric(df_f.loc[blank_mask, settle_amt_col], errors='coerce').fillna(0).sum() if settle_amt_col in df_f.columns else 0.0

# Derived totals (same formula as you accepted)
u_total = (u_del + u_exc + u_can) - abs(u_ret)
shipped_with_total = (u_del + u_can + u_ship) - (abs(u_ret) + abs(u_exc))
shipped_with_tooltip = "Delivered + Cancelled + Shipping - (Return + Exchange)"

# layout cards similar to old theme
row1 = [
    ("Delivered ₹", u_del, "#1b5e20", "✅"),
    ("Exchange ₹", u_exc, "#e65100", "🔄"),
    ("Cancelled ₹", u_can, "#455a64", "❌"),
    ("Return ₹", u_ret, "#b71c1c", "↩️"),
    ("RTO ₹", u_rto, "#6a1b9a", "📪")
]
row2 = [
    ("Shipping (₹)", u_ship, "#0b3d91", "🚚"),
    ("Platform Recovery ₹", platform_recovery_amt, "#546e7a", "🔍"),
    ("Shipped With Total ₹", shipped_with_total, "#0b3d91", "📦"),
    ("Total Amount ₹", u_total, "#0d47a1", "🧾")
]

c1 = st.columns(len(row1))
for i, (lab, val, color, ic) in enumerate(row1):
    c1[i].markdown(_card_html(lab, val, bg=color, icon=ic), unsafe_allow_html=True)

c2 = st.columns(len(row2))
for i, (lab, val, color, ic) in enumerate(row2):
    tooltip = shipped_with_tooltip if "Shipped With Total" in lab else None
    c2[i].markdown(_card_html(lab, val, bg=color, icon=ic, extra_small=tooltip), unsafe_allow_html=True)

# ---------------- Data preview (old look tables with options) ----------------
st.markdown("---")
st.subheader("🔎 Filtered Data Preview (sample)")
show_table = st.checkbox("Show Filtered Table", value=False)
show_full_table = st.checkbox("Show Full Table (may be large)", value=False)
if show_table:
    prev = df_f.copy()
    for c in [order_date_col, payment_date_col, dispatch_date_col]:
        if c in prev.columns:
            try:
                prev[c] = pd.to_datetime(prev[c], errors='coerce').dt.date
            except Exception:
                pass
    if show_full_table:
        st.dataframe(prev, use_container_width=True, height=700)
    else:
        st.dataframe(prev.head(250), use_container_width=True, height=420)
else:
    st.info("Filtered table hidden — tick 'Show Filtered Table' to view rows.")

# ---------------- Charts & Pivot (preserved old look) ----------------
_figs_for_pdf = []

st.markdown("---")
st.subheader("1️⃣ Live Order Status Count (Filtered)")
status_df = df_f[status_col].fillna("BLANK").value_counts().reset_index()
status_df.columns = ['Status','Count']
if status_df.empty:
    st.warning("No status records in filtered data.")
else:
    f_status = px.bar(status_df, x='Status', y='Count', color='Status', text='Count', title="Live Order Status Count")
    f_status.update_traces(texttemplate='%{text}', textposition='outside')
    f_status.update_layout(height=520)
    st.plotly_chart(f_status, use_container_width=True)
    _figs_for_pdf.append(("Live Order Status Count", f_status))

st.markdown("---")
st.subheader("2️⃣ Orders by Date (Filtered)")
if order_date_col:
    df_f['__odt'] = pd.to_datetime(df_f[order_date_col], errors='coerce')
    if group_choice == "Month":
        g = df_f.groupby(df_f['__odt'].dt.to_period('M'))['__odt'].count().reset_index(name='Total Orders')
        g[order_date_col] = g['__odt'].astype(str)
        xcol = order_date_col
    else:
        g = df_f.groupby(df_f['__odt'].dt.date)['__odt'].count().reset_index(name='Total Orders')
        g.rename(columns={'__odt': order_date_col}, inplace=True)
        xcol = order_date_col
    if not g.empty:
        f2 = px.bar(g, x=xcol, y='Total Orders', text='Total Orders', title="Orders by Order Date")
        f2.update_traces(textposition='outside', texttemplate='%{text}')
        f2.update_layout(height=480)
        st.plotly_chart(f2, use_container_width=True)
        _figs_for_pdf.append(("Orders by Order Date", f2))
else:
    st.info("Order Date column not detected.")

# Payments by Date
st.markdown("---")
st.subheader("3️⃣ Payments Received by Date (Filtered)")
if payment_date_col and settle_amt_col and settle_amt_col in df_f.columns:
    df_f['__pdt'] = pd.to_datetime(df_f[payment_date_col], errors='coerce')
    if group_choice == "Month":
        g3 = df_f.groupby(df_f['__pdt'].dt.to_period('M'))[settle_amt_col].sum().reset_index()
        g3[payment_date_col] = g3['__pdt'].astype(str)
        xcol3 = payment_date_col
    else:
        g3 = df_f.groupby(df_f['__pdt'].dt.date)[settle_amt_col].sum().reset_index()
        g3.rename(columns={'__pdt': payment_date_col}, inplace=True)
        xcol3 = payment_date_col
    if not g3.empty:
        f3 = px.bar(g3, x=xcol3, y=settle_amt_col, title="Payments Received by Date", text=settle_amt_col)
        f3.update_traces(textposition='outside', texttemplate='%{text:.2f}')
        f3.update_layout(height=480)
        st.plotly_chart(f3, use_container_width=True)
        _figs_for_pdf.append(("Payments Received by Date", f3))
else:
    st.info("Payment Date or Settlement Amount column missing for payments chart.")

# Return & Exchange % of Delivered (pivot + chart)
st.markdown("---")
st.subheader("4️⃣ Return & Exchange % of Delivered (Filtered)")
_deliv = int(status_df[status_df['Status'].str.upper()=='DELIVERED']['Count'].sum()) if not status_df.empty else 0
_ret   = int(status_df[status_df['Status'].str.upper()=='RETURN']['Count'].sum()) if not status_df.empty else 0
_exc   = int(status_df[status_df['Status'].str.upper()=='EXCHANGE']['Count'].sum()) if not status_df.empty else 0
ret_pct = (_ret/_deliv*100) if _deliv else 0.0
exc_pct = (_exc/_deliv*100) if _deliv else 0.0

c1,c2,c3 = st.columns(3)
c1.markdown(_card_html("📦 Delivered", _deliv, bg="#1565c0", icon=""), unsafe_allow_html=True)
c2.markdown(_card_html("↩️ Return", _ret, bg="#c62828", icon=""), unsafe_allow_html=True)
c3.markdown(_card_html("🔄 Exchange", _exc, bg="#ef6c00", icon=""), unsafe_allow_html=True)

pivot_df = pd.DataFrame({
    'Metric': ['Delivered', 'Return', 'Exchange', 'Return % of Delivered', 'Exchange % of Delivered'],
    'Value':  [_deliv, _ret, _exc, round(ret_pct,2), round(exc_pct,2)]
})
st.dataframe(pivot_df, use_container_width=True, height=220)

ret_chart = px.bar(pd.DataFrame({'Type':['Return %','Exchange %'],'Percent':[ret_pct, exc_pct]}), x='Type', y='Percent', text='Percent', title="Return/Exchange % of Delivered")
ret_chart.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
ret_chart.update_layout(height=360)
st.plotly_chart(ret_chart, use_container_width=True)
_figs_for_pdf.append(("Return/Exchange % of Delivered", ret_chart))

# Profit section preserved
st.markdown("---")
st.subheader("💹 Profit Calculation (Filtered)")
profit_sum = _sum(df_f[profit_amt_col]) if profit_amt_col and profit_amt_col in df_f.columns else 0.0
return_loss_sum = abs(u_ret)
exchange_loss_sum = _sum(df_f[exchange_loss_col]) if exchange_loss_col and exchange_loss_col in df_f.columns else 0.0
net_profit = profit_sum - (return_loss_sum + abs(exchange_loss_sum))

pcols = st.columns(4)
pcols[0].markdown(_card_html("Profit Amount (Σ)", profit_sum, bg="#1b5e20"), unsafe_allow_html=True)
pcols[1].markdown(_card_html("Return Loss (Σ)", return_loss_sum, bg="#b71c1c"), unsafe_allow_html=True)
pcols[2].markdown(_card_html("Exchange Loss (Σ)", exchange_loss_sum, bg="#f57c00"), unsafe_allow_html=True)
pcols[3].markdown(_card_html("Net Profit", net_profit, bg="#0d47a1"), unsafe_allow_html=True)

# Ads block (compact)
st.markdown("---")
st.subheader("📢 Ads Cost (if provided)")
if ads_df is None or ads_df.empty:
    st.info("Ads sheet not present.")
else:
    try:
        ads_df['Deduction Duration'] = pd.to_datetime(ads_df['Deduction Duration'], errors='coerce').dt.date
        ads_df['Total Ads Cost'] = pd.to_numeric(ads_df['Total Ads Cost'], errors='coerce').fillna(0)
        total_ads = ads_df['Total Ads Cost'].sum()
        st.markdown(_card_html("Total Ads Cost (Σ)", total_ads, bg="#4a148c"), unsafe_allow_html=True)
    except Exception:
        st.info("Ads sheet columns vary — skipping detailed ads analysis.")

# ---------------- Exports (Excel & PDF) with old look formatting ----------------
st.markdown("---")
st.subheader("📥 Download Reports (Excel / PDF)")

def _safe_filename(name, fallback):
    if not name:
        return fallback
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in name)[:40]
    base, ext = os.path.splitext(fallback)
    return f"{base}__{safe}{ext}"

# Excel generation
excel_buf = BytesIO()
with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
    try:
        orders_df.to_excel(writer, index=False, sheet_name="Raw Orders")
    except Exception:
        pass
    try:
        df_f.to_excel(writer, index=False, sheet_name="Filtered Orders")
    except Exception:
        pass
    try:
        if not status_df.empty:
            status_df.to_excel(writer, index=False, sheet_name="Status Summary")
    except Exception:
        pass
    try:
        pd.DataFrame({
            'Label': ['Delivered','Exchange','Cancelled','Return','RTO','Shipping','Platform Recovery','Shipped With Total','Total Amount'],
            'Value': [u_del, u_exc, u_can, u_ret, u_rto, u_ship, platform_recovery_amt, shipped_with_total, u_total]
        }).to_excel(writer, index=False, sheet_name="Amount Summary")
    except Exception:
        pass
    try:
        meta = pd.DataFrame([[supplier_name or "", supplier_id_auto or "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")]], columns=["Supplier","SupplierID","Generated"])
        meta.to_excel(writer, index=False, sheet_name="Meta")
    except Exception:
        pass
excel_data = excel_buf.getvalue()

st.download_button("⬇️ Download Excel", data=excel_data, file_name=_safe_filename(supplier_name or supplier_id_auto, "Meesho_Report_Final_v6.xlsx"), mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

# PDF export (detailed)
def _make_summary_rows_for_pdf():
    rows = [
        ["Delivered (cnt)", counts.get('Delivered',0)],
        ["Return (cnt)", counts.get('Return',0)],
        ["Exchange (cnt)", counts.get('Exchange',0)],
        ["Cancelled (cnt)", counts.get('Cancelled',0)],
        ["Shipped (cnt)", counts.get('Shipped',0)],
        ["RTO (cnt)", counts.get('RTO',0)],
        ["Platform Recovery (cnt)", platform_recovery_count],
        ["Filtered Total", filtered_total],
        ["—","—"],
        ["Delivered ₹", u_del],
        ["Exchange ₹", u_exc],
        ["Cancelled ₹", u_can],
        ["Return ₹", u_ret],
        ["RTO ₹", u_rto],
        ["Shipping ₹", u_ship],
        ["Platform Recovery ₹", platform_recovery_amt],
        ["Shipped With Total ₹", shipped_with_total],
        ["Total Amount ₹", u_total],
        ["—","—"],
        ["Profit Amount (Σ)", profit_sum],
        ["Return Loss (Σ)", return_loss_sum],
        ["Exchange Loss (Σ)", exchange_loss_sum],
        ["Net Profit", net_profit],
    ]
    return rows

def _export_pdf(figs_with_titles, file_name="Meesho_Report_Final_v6.pdf"):
    if not _kaleido_ok:
        raise RuntimeError("kaleido required for chart -> image rendering in PDF export. Install 'kaleido'.")
    tmpdir = tempfile.mkdtemp(prefix="meesho_final_v6_")
    out_pdf = os.path.join(tmpdir, file_name)
    with PdfPages(out_pdf) as pdf:
        # summary table first (styled)
        rows = _make_summary_rows_for_pdf()
        fig_sum = _make_table_figure(rows, ["Metric","Value"], "📦 Orders & Profit Summary (Filtered)", striped=True)
        pdf.savefig(fig_sum, bbox_inches='tight')
        plt.close(fig_sum)
        # export each plotly fig
        for (title, fig) in figs_with_titles:
            try:
                buf = BytesIO()
                fig.write_image(buf, format='png', engine='kaleido', width=2000, height=1200, scale=2)
                buf.seek(0)
                img = Image.open(buf).convert("RGB")
                f, ax = plt.subplots(figsize=(11,8))
                ax.imshow(img); ax.axis('off')
                ax.set_title(title, fontsize=14, fontweight='bold')
                pdf.savefig(f, bbox_inches='tight'); plt.close(f)
            except Exception as e:
                # fallback: write a text page with error
                f_err, ax_err = plt.subplots(figsize=(11,8))
                ax_err.axis('off')
                ax_err.text(0.5, 0.5, f"Could not render chart: {title}\n{e}", ha='center', va='center')
                pdf.savefig(f_err, bbox_inches='tight')
                plt.close(f_err)
    with open(out_pdf, 'rb') as f:
        data = f.read()
    return data

if _kaleido_ok:
    try:
        pdf_bytes = _export_pdf(_figs_for_pdf, file_name=_safe_filename(supplier_name or supplier_id_auto, "Meesho_Report_Final_v6.pdf"))
        st.download_button("⬇️ Download PDF (Detailed)", data=pdf_bytes, file_name=_safe_filename(supplier_name or supplier_id_auto, "Meesho_Report_Final_v6.pdf"), mime="application/pdf", use_container_width=True)
    except Exception as e:
        st.error(f"PDF export failed: {e}. You can still download Excel.")
else:
    st.info("Install 'kaleido' to enable PDF export with charts (pip install kaleido).")

# ---------------- Final housekeeping: memory & message ----------------
# collect garbage to avoid browser OOM on multiple reruns
gc.collect()

st.success("✅ Meesho Dashboard Final v6 loaded — old UI + new SKU-groups, Shipping fix, Grand Total implemented.")
st.info("Test: 1) Create SKU group(s) in Sidebar → Add Group 2) Select groups from 'Existing SKU Groups' multi-select 3) Observe dashboard update (counts, amounts & charts) — should reflect only selected SKUs.")
