# 📦 Meesho Order Analysis Dashboard — Final v21
# Updates:
# 1. Title Shortened to "📦 Meesho Order Analysis Dashboard".
# 2. Added Contact Section at the bottom:
#    - Direct WhatsApp Link.
#    - Direct Email Form (Sends mail without opening Gmail app).
# 3. All previous fixes (Grouping, Claims, Recovery, Ads) retained.
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

__VERSION__ = "v21"

# ---------------- PAGE SETUP ----------------
st.set_page_config(layout="wide", page_title="📦 Meesho Dashboard") # Title Shortened
st.title("📦 Meesho Order Analysis Dashboard") # Title Shortened
st.caption("Advanced Analytics: SKU Grouping | True Profit | Claims & Recovery | Ads Analysis")

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
if 'selected_skus' not in st.session_state: st.session_state['selected_skus'] = []

supplier_name_input = st.sidebar.text_input("🔹 Supplier Name", value="")
up = st.sidebar.file_uploader("Upload Excel/CSV", type=["xlsx", "csv"])

if up is None:
    st.info("Please upload your Meesho Excel File.")
    st.stop()

supplier_id_auto = extract_supplier_id_from_filename(up.name)
_supplier_label = f"{supplier_name_input} ({supplier_id_auto})" if supplier_id_auto else supplier_name_input
st.markdown(f"<div style='background-color:#FFEB3B;padding:10px;border-radius:10px;text-align:center;color:black;font-weight:bold;margin-bottom:10px'>📌 Analyzing: {_supplier_label}</div>", unsafe_allow_html=True)

# Product Cost
st.sidebar.markdown("---")
st.sidebar.subheader("💰 Profit Settings")
user_product_cost = st.sidebar.number_input("Enter Product Cost (Per Unit) ₹", min_value=0.0, value=0.0, step=10.0)

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
recovery_col = _detect_col(orders_df, ("recovery",))
claims_col = _detect_col(orders_df, ("claims",))
order_source_col = _detect_col(orders_df, ("order","source"))
listing_price_col = _detect_col(orders_df, ("listing","price"))
total_sale_col = _detect_col(orders_df, ("total","sale","amount"))

if not status_col:
    st.error("Status column not found!")
    st.stop()

# Date Parsing
for c in [order_date_col, dispatch_date_col]:
    if c and c in orders_df.columns:
        orders_df[c] = pd.to_datetime(orders_df[c], errors='coerce')

# Clean Numerics
if claims_col: orders_df[claims_col] = pd.to_numeric(orders_df[claims_col], errors='coerce').fillna(0)
if recovery_col: orders_df[recovery_col] = pd.to_numeric(orders_df[recovery_col], errors='coerce').fillna(0)

# ---------------- FILTERS ----------------
with st.sidebar.expander("🎛️ Advanced Filters", expanded=True):
    status_opts = ['All', 'Delivered', 'Return', 'RTO', 'Exchange', 'Cancelled', 'Shipped', ""]
    sel_statuses = st.multiselect("Status", status_opts, default=['All'])
    
    # SKU Grouping (Cloud Fixed)
    if sku_col:
        orders_df[sku_col] = orders_df[sku_col].astype(str)
        all_skus = sorted(orders_df[sku_col].dropna().unique())

        st.markdown("**SKU Grouping & Search**")
        search_kw = st.text_input("Search SKU keyword")
        matches = [s for s in all_skus if search_kw.lower() in s.lower()] if search_kw else []

        group_name = st.text_input("Group Name", value=search_kw)

        c1, c2 = st.columns(2)
        with c1:
            if st.button("➕ Add / Update"):
                if group_name and matches:
                    found = False
                    for g in st.session_state["sku_groups"]:
                        if g["name"] == group_name:
                            g["skus"] = matches
                            found = True
                    if not found:
                        st.session_state["sku_groups"].append({"name": group_name, "skus": matches})
                    st.rerun()
        with c2:
            if st.button("🧹 Clear All"):
                st.session_state["sku_groups"] = []
                st.session_state['selected_skus'] = []
                st.rerun()

        def update_sku_selection():
            chosen_labels = st.session_state.get('group_selector', [])
            include_live = st.session_state.get('live_match_checkbox', True)
            group_skus_list = []
            for label in chosen_labels:
                try:
                    idx = int(label.split('.')[0]) - 1
                    group_skus_list.extend(st.session_state['sku_groups'][idx]['skus'])
                except: pass
            current_search = st.session_state.get('search_kw_internal', '')
            manual = [s for s in all_skus if current_search.lower() in s.lower()] if (current_search and include_live) else []
            final_set = sorted(list(set(group_skus_list + manual)))
            st.session_state['selected_skus'] = final_set

        if st.session_state["sku_groups"]:
            labels = [f"{i+1}. {g['name']} ({len(g['skus'])})" for i, g in enumerate(st.session_state["sku_groups"])]
            st.multiselect("Select Groups", options=labels, key='group_selector', on_change=update_sku_selection)
            st.checkbox("Include live keyword matches", value=True, key='live_match_checkbox', on_change=update_sku_selection)
            st.text_input("Hidden Search Helper", value=search_kw, key='search_kw_internal', label_visibility="collapsed", on_change=update_sku_selection)

        selected_skus = st.multiselect("Selected SKU(s)", options=all_skus, key="selected_skus")
    else:
        selected_skus = None
    
    if claims_col:
        claims_vals = sorted(orders_df[orders_df[claims_col] != 0][claims_col].unique().tolist())
        st.markdown("---")
        sel_claims = st.multiselect("📂 Filter Claims (Values)", claims_vals, help="Leave empty for All")
    else:
        sel_claims = None

    if recovery_col:
        rec_vals = sorted(orders_df[orders_df[recovery_col] != 0][recovery_col].unique().tolist())
        sel_recovery = st.multiselect("📂 Filter Recovery (Values)", rec_vals, help="Leave empty for All")
    else:
        sel_recovery = None

    if catalog_id_col:
        st.markdown("---")
        cats = sorted([str(x) for x in orders_df[catalog_id_col].dropna().unique().tolist()])
        sel_cats = st.multiselect("📂 Catalog ID", cats)
    else:
        sel_cats = None

with st.sidebar.expander("📅 Date & Source Filters", expanded=True):
    date_range = None
    if order_date_col:
        dmin, dmax = orders_df[order_date_col].min(), orders_df[order_date_col].max()
        if pd.notna(dmin):
            date_range = st.date_input("Order Date Range", [dmin, dmax])
    
    sel_source = None
    if order_source_col:
        sources = sorted([str(x) for x in orders_df[order_source_col].dropna().unique().tolist()])
        sel_source = st.multiselect("Order Source", sources, default=None, help="Leave empty for All")

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

if sku_col and selected_skus:
    df_f = df_f[df_f[sku_col].astype(str).isin(selected_skus)]

if catalog_id_col and sel_cats:
    df_f = df_f[df_f[catalog_id_col].astype(str).isin(sel_cats)]

if claims_col and sel_claims:
    df_f = df_f[df_f[claims_col].isin(sel_claims)]

if recovery_col and sel_recovery:
    df_f = df_f[df_f[recovery_col].isin(sel_recovery)]

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

# ---------------- RTO LOGIC ----------------
def _ensure_rto(df):
    if listing_price_col and total_sale_col:
        mask = df[status_col].astype(str).str.upper() == 'RTO'
        df.loc[mask, 'Shipping Charge'] = pd.to_numeric(df.loc[mask, total_sale_col], errors='coerce').fillna(0) - pd.to_numeric(df.loc[mask, listing_price_col], errors='coerce').fillna(0)
        df.loc[mask, 'Shipping GST'] = df.loc[mask, 'Shipping Charge'] * 0.18
        df.loc[mask, 'RTO Amount'] = pd.to_numeric(df.loc[mask, listing_price_col], errors='coerce').fillna(0) - df.loc[mask, 'Shipping GST']
    return df

df_f = _ensure_rto(df_f)

# ---------------- COUNTS & METRICS ----------------
counts = df_f[status_col].astype(str).str.upper().value_counts()
c_del = counts.get('DELIVERED', 0)
c_ret = counts.get('RETURN', 0)
c_exc = counts.get('EXCHANGE', 0)
c_can = counts.get('CANCELLED', 0)
c_shp = counts.get('SHIPPED', 0)
c_rto = counts.get('RTO', 0)

c_claim = df_f[df_f[claims_col] != 0].shape[0] if claims_col else 0
c_rec = df_f[df_f[recovery_col] != 0].shape[0] if recovery_col else 0
grand_total_count = len(df_f)

# ---------------- VISUALS ----------------
status_labels = [('✅ Delivered', c_del, '#2e7d32'), ('↩️ Return', c_ret, '#c62828'), 
                 ('🔄 Exchange', c_exc, '#f57c00'), ('❌ Cancelled', c_can, '#616161'),
                 ('🚚 Shipped', c_shp, '#1565c0'), ('📪 RTO', c_rto, '#8e24aa'),
                 ('🤕 Claims', c_claim, '#F9A825'), ('🔁 Recovery', c_rec, '#546E7A')]

cols = st.columns(8)
for i, (l, v, c) in enumerate(status_labels):
    cols[i].markdown(f"<div style='background:{c};padding:8px;border-radius:8px;text-align:center;color:white;font-size:12px;'><b>{l}</b><br><span style='font-size:18px'>{v}</span></div>", unsafe_allow_html=True)

st.markdown(f"""<div style='background-color:#0d47a1;padding:10px;border-radius:8px;text-align:center;color:white;margin-bottom:15px;margin-top:5px'><div style="font-size:16px;font-weight:bold">📊 Grand Total Orders: {grand_total_count}</div></div>""", unsafe_allow_html=True)

# ---------------- FINANCIAL SUMMARY ----------------
st.subheader("₹ Financial Summary")
if settle_amt_col:
    df_f[settle_amt_col] = pd.to_numeric(df_f[settle_amt_col], errors='coerce').fillna(0)
    
    def get_sum(s): return df_f[df_f[status_col].astype(str).str.upper() == s][settle_amt_col].sum()
    
    a_del = get_sum('DELIVERED')
    a_exc = get_sum('EXCHANGE')
    a_can = get_sum('CANCELLED')
    a_ret = get_sum('RETURN')
    a_shp = get_sum('SHIPPED')
    a_rto = df_f[df_f[status_col].astype(str).str.upper() == 'RTO']['RTO Amount'].sum() if 'RTO Amount' in df_f.columns else 0

    a_claims = df_f[claims_col].sum() if claims_col else 0
    a_rec = abs(df_f[recovery_col].sum()) if recovery_col else 0

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
        st.markdown(f"**Shipped With Total:** `(Delivered + Cancelled + Shipped) - (Return + Exchange)`")
        st.markdown(f"**Total Amount:** `(Delivered + Exchange + Cancelled) - Return Amount`")

# ---------------- PROFIT & OTHER ----------------
st.markdown("---")
st.subheader("💹 True Profit Analysis")

total_ret_loss_abs = abs(a_ret)
avg_ret_cost = total_ret_loss_abs / c_ret if c_ret > 0 else 0.0
est_exchange_loss = c_exc * avg_ret_cost
total_cogs = c_del * user_product_cost
final_net_profit = a_del - (total_ret_loss_abs + est_exchange_loss + total_cogs)

profit_data = {
    "Metric": ["Delivered Revenue (+)", "Return Loss (-)", "Est. Exchange Charge (-)", "Product Cost (COGS) (-)", "FINAL NET PROFIT (=)"],
    "Amount (₹)": [a_del, -total_ret_loss_abs, -est_exchange_loss, -total_cogs, final_net_profit],
}
st.table(pd.DataFrame(profit_data))

kp1, kp2, kp3 = st.columns(3)
kp1.markdown(_card_html("Delivered Amount", a_del, "#1b5e20", "✅"), unsafe_allow_html=True)
kp2.markdown(_card_html("Total Deductions", (total_ret_loss_abs + est_exchange_loss + total_cogs), "#b71c1c", "Expenses"), unsafe_allow_html=True)
kp3.markdown(_card_html("FINAL TRUE PROFIT", final_net_profit, "#0d47a1", "💰"), unsafe_allow_html=True)

# Return %
st.markdown("---")
st.subheader("📊 Return & Exchange Percentage")
ret_pct = (c_ret / c_del) * 100 if c_del > 0 else 0
exc_pct = (c_exc / c_del) * 100 if c_del > 0 else 0
rp1, rp2, rp3 = st.columns(3)
rp1.markdown(f"<div style='background:#1565c0;padding:16px;border-radius:12px;color:white;text-align:center'><div style='font-size:18px'>Delivered</div><div style='font-size:28px'>{c_del}</div><div>100%</div></div>", unsafe_allow_html=True)
rp2.markdown(f"<div style='background:#c62828;padding:16px;border-radius:12px;color:white;text-align:center'><div style='font-size:18px'>Return</div><div style='font-size:28px'>{c_ret}</div><div>{ret_pct:.2f}%</div></div>", unsafe_allow_html=True)
rp3.markdown(f"<div style='background:#ef6c00;padding:16px;border-radius:12px;color:white;text-align:center'><div style='font-size:18px'>Exchange</div><div style='font-size:28px'>{c_exc}</div><div>{exc_pct:.2f}%</div></div>", unsafe_allow_html=True)

# Ads Analysis
st.markdown("---")
st.subheader("📢 Ads Cost Analysis")
ads_table = None
if ads_df is not None and not ads_df.empty:
    if 'Deduction Duration' in ads_df.columns and 'Total Ads Cost' in ads_df.columns:
        ads_df['Total Ads Cost'] = pd.to_numeric(ads_df['Total Ads Cost'], errors='coerce').fillna(0)
        ads_df['Deduction Duration'] = pd.to_datetime(ads_df['Deduction Duration'], errors='coerce').dt.date
        min_a, max_a = ads_df['Deduction Duration'].min(), ads_df['Deduction Duration'].max()
        ads_rng = st.date_input("Ads Date Range", [min_a, max_a])
        
        if len(ads_rng) == 2:
            ads_f = ads_df[(ads_df['Deduction Duration'] >= ads_rng[0]) & (ads_df['Deduction Duration'] <= ads_rng[1])].copy()
            if order_date_col:
                daily_orders = df_f.groupby(df_f[order_date_col].dt.date).size().reset_index(name='Daily Orders')
                daily_orders.columns = ['Deduction Duration', 'Daily Orders']
                ads_f = pd.merge(ads_f, daily_orders, on='Deduction Duration', how='left').fillna(0)
                ads_f['Per Order Cost'] = ads_f.apply(lambda row: row['Total Ads Cost'] / row['Daily Orders'] if row['Daily Orders'] > 0 else 0, axis=1)

            ads_total = ads_f['Total Ads Cost'].sum()
            total_orders_period = ads_f['Daily Orders'].sum() if 'Daily Orders' in ads_f.columns else 0
            avg_per_order = ads_total / total_orders_period if total_orders_period > 0 else 0

            ac1, ac2, ac3 = st.columns(3)
            ac1.markdown(_card_html("Total Ads Spend", ads_total, "#4a148c", "📣"), unsafe_allow_html=True)
            ac2.markdown(_card_html("Total Orders", total_orders_period, "#6A1B9A", "📦"), unsafe_allow_html=True)
            ac3.markdown(_card_html("Avg Cost / Order", avg_per_order, "#8E24AA", "🏷️"), unsafe_allow_html=True)
            fig_ads = px.bar(ads_f, x='Deduction Duration', y='Total Ads Cost', title="Daily Ads Spend")
            st.plotly_chart(fig_ads, use_container_width=True)
            ads_table = ads_f
else:
    st.info("No Ads Data found.")

# Charts
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

# ---------------- DOWNLOADS ----------------
st.markdown("---")
st.subheader("📥 Downloads")
buffer = BytesIO()
with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
    df_f.to_excel(writer, sheet_name='Filtered Data', index=False)
    pd.DataFrame(profit_data).to_excel(writer, sheet_name='Profit Logic', index=False)
    if ads_table is not None: ads_table.to_excel(writer, sheet_name='Ads Analysis', index=False)

st.download_button("⬇️ Download Excel Report", data=buffer.getvalue(), file_name="Meesho_Report_v21.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ---------------- CONTACT & SUPPORT SECTION ----------------
st.markdown("---")
st.header("📞 Contact & Support")

# Columns for Contact layout
col_contact1, col_contact2 = st.columns(2)

with col_contact1:
    st.subheader("💬 Chat on WhatsApp")
    st.write("Need quick help? Chat with Admin directly.")
    # REPLACE 918010952817 with your actual 10-digit number
    whatsapp_number = "918010952817" 
    whatsapp_url = f"https://wa.me/{whatsapp_number}"
    st.markdown(f'''
        <a href="{whatsapp_url}" target="_blank">
            <button style="background-color:#25D366;color:white;border:none;padding:10px 20px;border-radius:5px;font-size:16px;font-weight:bold;cursor:pointer;">
                🟢 Chat on WhatsApp
            </button>
        </a>
    ''', unsafe_allow_html=True)

with col_contact2:
    st.subheader("📧 Send Direct Email")
    st.write("Send a message directly to Admin (No Gmail app needed).")
    
    # FormSubmit.co Form - Sends directly to your email
    # Replace 'commercecatalyst088@gmail.com' with your actual email if different
    contact_form = """
    <form action="https://formsubmit.co/commercecatalyst088@gmail.com" method="POST">
        <input type="hidden" name="_captcha" value="false">
        <input type="text" name="name" placeholder="Your Name" required style="width:100%;padding:8px;margin-bottom:10px;border:1px solid #ccc;border-radius:4px;">
        <input type="email" name="email" placeholder="Your Email" required style="width:100%;padding:8px;margin-bottom:10px;border:1px solid #ccc;border-radius:4px;">
        <textarea name="message" placeholder="Your Message / Suggestion" required style="width:100%;padding:8px;margin-bottom:10px;border:1px solid #ccc;border-radius:4px;min-height:100px;"></textarea>
        <button type="submit" style="background-color:#0d47a1;color:white;border:none;padding:10px 20px;border-radius:5px;font-size:16px;cursor:pointer;">📩 Send Message</button>
    </form>
    """
    st.markdown(contact_form, unsafe_allow_html=True)

st.success("✅ Dashboard v21: Contact Form & WhatsApp Added!")
