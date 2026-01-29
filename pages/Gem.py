# 📦 Meesho Order Analysis Dashboard — Final Fixed v12
# Fixes: HTML appearing as text bug (Solved by single-line HTML strings)
# Changes: Removed Line Charts (Only Bar Charts kept), Added Catalog ID, Added Tooltips.
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

__VERSION__ = "Power By Rehan — Final v12"

# ---------------- PAGE SETUP ----------------
st.set_page_config(layout="wide", page_title=f"📦 Meesho Dashboard — {__VERSION__}")
st.title(f"📦 Meesho Order Analysis Dashboard — {__VERSION__}")
st.caption("Fixed Layout: Catalog ID + Tooltips + Bar Charts Only")

if not _kaleido_ok:
    st.warning("⚠️ For PDF Charts: Please install kaleido -> `pip install kaleido`")

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

# --- FIXED CARD HTML (SINGLE LINE TO PREVENT BUGS) ---
def _card_html(title, value, bg="#0d47a1", icon="₹", tooltip=None):
    tt_html = ""
    if tooltip:
        # Tooltip icon logic - Single line strict
        tt_html = f'<span title="{html_escape(tooltip)}" style="cursor:help;margin-left:8px;border:1px solid rgba(255,255,255,0.8);border-radius:50%;width:18px;height:18px;display:inline-flex;align-items:center;justify-content:center;font-size:11px;font-weight:bold;background-color:rgba(0,0,0,0.1);">?</span>'
    
    # STRICT SINGLE LINE HTML STRING
    return f"<div style='background:{bg};padding:14px;border-radius:12px;color:white;text-align:center'><div style='font-size:14px;opacity:0.95;display:flex;gap:6px;align-items:center;justify-content:center'><span style='font-weight:700'>{icon}</span><span style='font-weight:700'>{title}</span>{tt_html}</div><div style='font-size:22px;font-weight:800;margin-top:6px'>{_format_display(value)}</div></div>"

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
payment_date_col = _detect_col(orders_df, ("payment","date"))
dispatch_date_col = _detect_col(orders_df, ("dispatch","date"))
sku_col = _detect_col(orders_df, ("supplier","sku"), ("sku",))
settle_amt_col = _detect_col(orders_df, ("final","settlement"), ("settlement","amount"))
# NEW: Catalog ID
catalog_id_col = _detect_col(orders_df, ("catalog","id"), ("catalog_id",))

if not status_col:
    st.error("Status column not found!")
    st.stop()

# Date Parsing
for c in [order_date_col, payment_date_col, dispatch_date_col]:
    if c and c in orders_df.columns:
        orders_df[c] = pd.to_datetime(orders_df[c], errors='coerce')

# ---------------- FILTERS ----------------
with st.sidebar.expander("🎛️ Filters", expanded=True):
    # Status
    status_opts = ['All', 'Delivered', 'Return', 'RTO', 'Exchange', 'Cancelled', 'Shipped', ""]
    sel_statuses = st.multiselect("Status", status_opts, default=['All'])
    
    # SKU
    if sku_col:
        skus = sorted([str(x) for x in orders_df[sku_col].dropna().unique().tolist()])
        sel_skus = st.multiselect("Select SKUs", skus)
    else:
        sel_skus = None
    
    # Catalog ID
    if catalog_id_col:
        cats = sorted([str(x) for x in orders_df[catalog_id_col].dropna().unique().tolist()])
        st.markdown("---")
        sel_cats = st.multiselect("📂 Catalog ID", cats)
    else:
        sel_cats = None

# ---------------- APPLY FILTERS ----------------
df_f = orders_df.copy()

if order_date_col:
    # Basic date filter logic if needed, currently implied full range
    pass

if sku_col and sel_skus:
    df_f = df_f[df_f[sku_col].astype(str).isin(sel_skus)]

if catalog_id_col and sel_cats:
    df_f = df_f[df_f[catalog_id_col].astype(str).isin(sel_cats)]

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

# ---------------- CALCULATIONS ----------------
# RTO Fix
def _ensure_rto(df):
    if 'RTO Amount' not in df.columns and 'Listing Price (Incl. taxes)' in df.columns:
        mask = df[status_col].astype(str).str.upper() == 'RTO'
        df.loc[mask, 'RTO Amount'] = pd.to_numeric(df.loc[mask, 'Listing Price (Incl. taxes)'], errors='coerce').fillna(0) * 0.8
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
c_blank = df_f[status_col].isna().sum()
total_rows = len(df_f)

# Card Row 1 (Counts) - Single Line HTML
status_labels = [('✅ Delivered', c_del, '#2e7d32'), ('↩️ Return', c_ret, '#c62828'), 
                 ('🔄 Exchange', c_exc, '#f57c00'), ('❌ Cancelled', c_can, '#616161'),
                 ('🚚 Shipped', c_shp, '#1565c0'), ('📪 RTO', c_rto, '#8e24aa'),
                 ('📦 Recovery', c_blank, '#37474f'), ('📊 Total', total_rows, '#0d47a1')]

cols = st.columns(8)
for i, (l, v, c) in enumerate(status_labels):
    # Flattened HTML string
    cols[i].markdown(f"<div style='background:{c};padding:8px;border-radius:8px;text-align:center;color:white;font-size:12px;'><b>{l}</b><br><span style='font-size:18px'>{v}</span></div>", unsafe_allow_html=True)

# Amounts
st.subheader("₹ Financial Summary")
if settle_amt_col:
    df_f[settle_amt_col] = pd.to_numeric(df_f[settle_amt_col], errors='coerce').fillna(0)
    
    def get_sum(s): return df_f[df_f[status_col].astype(str).str.upper() == s][settle_amt_col].sum()
    
    a_del = get_sum('DELIVERED')
    a_exc = get_sum('EXCHANGE')
    a_can = get_sum('CANCELLED')
    a_ret = get_sum('RETURN')
    a_shp = get_sum('SHIPPED')
    a_rec = df_f[df_f[status_col].isna()][settle_amt_col].sum()
    
    # RTO Amount
    a_rto = df_f[df_f[status_col].astype(str).str.upper() == 'RTO']['RTO Amount'].sum() if 'RTO Amount' in df_f.columns else 0

    # Formulas
    shipped_with_total = (a_del + a_can + a_shp) - (abs(a_ret) + abs(a_exc))
    u_total = (a_del + a_exc + a_can) - abs(a_ret)

    # Tooltip Strings
    tt_ship = "Formula: (Delivered + Cancelled + Shipped) - (Return + Exchange)"
    tt_tot = "Formula: (Delivered + Exchange + Cancelled) - Return"

    # Display
    r1 = st.columns(5)
    r1[0].markdown(_card_html("Delivered ₹", a_del, "#1b5e20"), unsafe_allow_html=True)
    r1[1].markdown(_card_html("Exchange ₹", a_exc, "#e65100"), unsafe_allow_html=True)
    r1[2].markdown(_card_html("Cancelled ₹", a_can, "#455a64"), unsafe_allow_html=True)
    r1[3].markdown(_card_html("Return ₹", a_ret, "#b71c1c"), unsafe_allow_html=True)
    r1[4].markdown(_card_html("RTO ₹", a_rto, "#6a1b9a"), unsafe_allow_html=True)

    r2 = st.columns(4)
    r2[0].markdown(_card_html("Shipping ₹", a_shp, "#0b3d91"), unsafe_allow_html=True)
    r2[1].markdown(_card_html("Recovery ₹", a_rec, "#546e7a"), unsafe_allow_html=True)
    r2[2].markdown(_card_html("Shipped Total", shipped_with_total, "#0b3d91", "🚚", tt_ship), unsafe_allow_html=True)
    r2[3].markdown(_card_html("Total Amount", u_total, "#0d47a1", "🧾", tt_tot), unsafe_allow_html=True)

# ---------------- CHARTS (ONLY BAR CHARTS) ----------------
st.markdown("---")
st.subheader("📊 Charts")
_figs_for_pdf = []

c1, c2 = st.columns(2)

with c1:
    st.caption("Live Order Status Count")
    # Only Bar Chart for Status
    status_counts_df = df_f[status_col].fillna("BLANK").value_counts().reset_index()
    status_counts_df.columns = ['Status', 'Count']
    if not status_counts_df.empty:
        fig1 = px.bar(status_counts_df, x='Status', y='Count', color='Status', text='Count')
        fig1.update_traces(textposition='outside')
        st.plotly_chart(fig1, use_container_width=True)
        _figs_for_pdf.append(("Status Count", fig1))

with c2:
    st.caption("Orders by Date")
    # Only Bar Chart for Date
    if order_date_col:
        date_counts = df_f.groupby(df_f[order_date_col].dt.date).size().reset_index(name='Orders')
        # Using Bar instead of Line as requested to simplify
        fig2 = px.bar(date_counts, x=order_date_col, y='Orders', text='Orders')
        st.plotly_chart(fig2, use_container_width=True)
        _figs_for_pdf.append(("Orders by Date", fig2))

# ---------------- EXPORTS ----------------
st.markdown("---")
st.subheader("📥 Downloads")

# Excel
buffer = BytesIO()
with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
    df_f.to_excel(writer, sheet_name='Filtered Data', index=False)
    pd.DataFrame({'Metric':['Net Amount', 'Shipped Total'], 'Value':[u_total, shipped_with_total]}).to_excel(writer, sheet_name='Summary')

st.download_button("⬇️ Download Excel Report", data=buffer.getvalue(), file_name="Meesho_Report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# PDF (Simplified Logic)
if _kaleido_ok:
    def _create_pdf():
        import tempfile
        t = tempfile.mkdtemp()
        fname = os.path.join(t, "report.pdf")
        with PdfPages(fname) as pdf:
            # Page 1: Summary
            fig = plt.figure(figsize=(10,6))
            plt.axis('off')
            plt.text(0.5, 0.9, f"Report: {_supplier_label}", ha='center', fontsize=16)
            plt.text(0.5, 0.7, f"Total Amount: {u_total}", ha='center', fontsize=14)
            plt.text(0.5, 0.6, f"Shipped Total: {shipped_with_total}", ha='center', fontsize=14)
            pdf.savefig(fig)
            plt.close()
            
            # Page 2+: Charts
            for title, f in _figs_for_pdf:
                try:
                    img_bytes = f.to_image(format="png", width=1200, height=800, scale=2)
                    img = Image.open(BytesIO(img_bytes))
                    fig2 = plt.figure(figsize=(10,6))
                    plt.axis('off')
                    plt.imshow(img)
                    plt.title(title)
                    pdf.savefig(fig2)
                    plt.close()
                except: pass
        with open(fname, "rb") as f:
            return f.read()

    st.download_button("⬇️ Download PDF (Charts)", data=_create_pdf(), file_name="Report_v12.pdf", mime="application/pdf")
else:
    st.info("Install 'kaleido' for PDF exports.")

st.success("✅ Dashboard Ready: HTML Bug Fixed, Line Charts Removed, All Features Active.")
