# meesho_order_v3.py

import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
from datetime import datetime
import tempfile
import re

from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, Image, PageBreak)
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

# -------------------- Streamlit Page --------------------
st.set_page_config(page_title="📦 Meesho Orders & Ads Dashboard", layout="wide")

# -------------------- THEME / CSS --------------------
st.markdown(
    """
    <style>
    .title { font-size:28px; font-weight:700; color:#0b3d91; }
    .subtitle { color:#445267; margin-top:-8px; margin-bottom:16px; }
    .metric-box { display:inline-block; padding:14px 16px; margin:6px 8px; border-radius:10px; color:#fff;
                  font-weight:700; text-align:center; min-width:150px; }
    .CANCELLED{background:#e74c3c;} .DELIVERED{background:#27ae60;}
    .DOOR_STEP_EXCHANGED{background:#9b59b6;} .HOLD{background:#f39c12;}
    .PENDING{background:#e67e22;} .READY_TO_SHIP{background:#2980b9;}
    .RTO_COMPLETE{background:#1abc9c;} .RTO_INITIATED{background:#d35400;}
    .RTO_LOCKED{background:#8e44ad;} .SHIPPED{background:#2c3e50;}
    .GRAND_TOTAL{background:#0b3d91;}
    .metric-row { display:flex; flex-wrap:wrap; align-items:center }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="title">📊 Meesho Orders & Ads Dashboard</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Upload Orders + Ads → Insights → Export Reports</div>', unsafe_allow_html=True)

# -------------------- Helpers --------------------
def detect_and_load(file):
    name = file.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(file, low_memory=False)
    elif name.endswith((".xls", ".xlsx")):
        return pd.read_excel(file)
    else:
        raise ValueError("Upload CSV or Excel only.")

def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Filtered")
    return buf.getvalue()

def robust_parse_dates(series: pd.Series) -> pd.Series:
    s = pd.to_datetime(series, errors="coerce", infer_datetime_format=True)
    if s.notna().any():
        return s
    s = pd.to_datetime(series, errors="coerce", dayfirst=True, infer_datetime_format=True)
    return s

STATUS_LIST = [
    "CANCELLED","DELIVERED","DOOR_STEP_EXCHANGED","HOLD","PENDING",
    "READY_TO_SHIP","RTO_COMPLETE","RTO_INITIATED","RTO_LOCKED","SHIPPED"
]

COLOR_MAP = {
    "CANCELLED":"#e74c3c","DELIVERED":"#27ae60","DOOR_STEP_EXCHANGED":"#9b59b6",
    "HOLD":"#f39c12","PENDING":"#e67e22","READY_TO_SHIP":"#2980b9",
    "RTO_COMPLETE":"#1abc9c","RTO_INITIATED":"#d35400","RTO_LOCKED":"#8e44ad","SHIPPED":"#2c3e50",
    "GRAND_TOTAL":"#0b3d91"
}

GRAND_INCLUDE = [
    "DELIVERED","DOOR_STEP_EXCHANGED","HOLD","PENDING",
    "READY_TO_SHIP","RTO_COMPLETE","RTO_INITIATED","RTO_LOCKED","SHIPPED"
]

ORDERS_BY_DATE_COLOR = "#0b3d91"

# -------------------- Upload --------------------
st.sidebar.markdown("### Upload Files")
uploaded_orders = st.sidebar.file_uploader("Upload Orders File", type=["csv","xls","xlsx"], key="orders")
uploaded_ads    = st.sidebar.file_uploader("Upload Ads Cost File", type=["csv","xls","xlsx"], key="ads")

if not uploaded_orders:
    st.info("⚠️ Please upload Orders file to continue.")
    st.stop()

# Load Orders
df = detect_and_load(uploaded_orders)
cols = list(df.columns)

# Supplier ID from filename
supplier_id = "Unknown"
try:
    match = re.search(r"_(\d+)\.csv$", uploaded_orders.name)
    if match:
        supplier_id = match.group(1)
except Exception:
    pass

# Column mapping (Orders)
col_status     = "Reason for Credit Entry" if "Reason for Credit Entry" in cols else None
col_order_date = "Order Date" if "Order Date" in cols else None
col_sku        = "SKU" if "SKU" in cols else None
col_size       = "Size" if "Size" in cols else None
col_state      = "Customer State" if "Customer State" in cols else None

# -------------------- Filter Orders --------------------
st.sidebar.markdown("### Filters (Orders)")
df["_order_date_parsed"] = robust_parse_dates(df[col_order_date])
date_min, date_max = df["_order_date_parsed"].min(), df["_order_date_parsed"].max()
start_date = st.sidebar.date_input("Start date", value=date_min.date())
end_date   = st.sidebar.date_input("End date", value=date_max.date())

start_dt = datetime.combine(start_date, datetime.min.time())
end_dt   = datetime.combine(end_date, datetime.max.time())

filtered = df[(df["_order_date_parsed"] >= start_dt) & (df["_order_date_parsed"] <= end_dt)]

def searchable_multiselect(label, data_list, key):
    search = st.sidebar.text_input(f"{label} search", key=f"{key}_search")
    options = [x for x in data_list if search.lower() in str(x).lower()] if search else data_list
    select_all = st.sidebar.checkbox(f"Select All {label}", key=f"{key}_all")
    default_opts = options if select_all else []
    return st.sidebar.multiselect(label, options=options, default=default_opts, key=f"{key}_multi")

status_sel = searchable_multiselect("Status", sorted(filtered[col_status].dropna().unique()), "status") if col_status else []
sku_sel    = searchable_multiselect("SKU", sorted(filtered[col_sku].dropna().unique()), "sku") if col_sku else []
size_sel   = searchable_multiselect("Size", sorted(filtered[col_size].dropna().unique()), "size") if col_size else []
state_sel  = searchable_multiselect("Customer State", sorted(filtered[col_state].dropna().unique()), "state") if col_state else []

if status_sel: filtered = filtered[filtered[col_status].isin(status_sel)]
if sku_sel:    filtered = filtered[filtered[col_sku].isin(sku_sel)]
if size_sel:   filtered = filtered[filtered[col_size].isin(size_sel)]
if state_sel:  filtered = filtered[filtered[col_state].isin(state_sel)]

total_orders = len(filtered)

# -------------------- Orders Dashboard --------------------
st.markdown("### 📦 Orders Overview")
status_counts = filtered[col_status].value_counts().to_dict() if col_status else {}
boxes_html = '<div class="metric-row">'
for s in STATUS_LIST:
    boxes_html += f"<div class='metric-box {s}'>{s}<br>{status_counts.get(s,0)}</div>"
grand_total = sum([status_counts.get(s,0) for s in GRAND_INCLUDE])
boxes_html += f"<div class='metric-box GRAND_TOTAL'>GRAND TOTAL<br>{grand_total}</div></div>"
st.markdown(boxes_html, unsafe_allow_html=True)

st.markdown("### Status Count (Bar)")
status_bar_df = pd.DataFrame({"status": STATUS_LIST,"count": [status_counts.get(s,0) for s in STATUS_LIST]})
fig_status = px.bar(status_bar_df, x="status", y="count", text="count")
fig_status.update_traces(marker_color=[COLOR_MAP[s] for s in STATUS_LIST], textposition="outside")
fig_status.update_layout(
    height=560, margin=dict(l=30, r=30, t=40, b=80),
    xaxis_title=None, yaxis_title="Count",
    xaxis=dict(categoryorder="array", categoryarray=STATUS_LIST, tickangle=-30),
    title=f"Status Count (Supplier: {supplier_id} | Total Orders: {total_orders})"
)
st.plotly_chart(fig_status, use_container_width=True)

st.markdown("### Orders by Date")
orders_by_date = (
    filtered.groupby(filtered["_order_date_parsed"].dt.date).size()
    .reset_index(name="Orders").sort_values("_order_date_parsed")
)
title_time = ", ".join(status_sel) if status_sel else "All Statuses"
fig_time = px.bar(
    orders_by_date, x="_order_date_parsed", y="Orders", text="Orders",
    title=f"Orders by Date ({title_time}) | Supplier: {supplier_id} | Total Orders: {total_orders}"
)
fig_time.update_traces(textposition="outside", marker_color=ORDERS_BY_DATE_COLOR)
fig_time.update_layout(height=560, margin=dict(l=30, r=30, t=60, b=80),
                       xaxis_title=None, yaxis_title="Orders")
st.plotly_chart(fig_time, use_container_width=True)

# -------------------- Ads Dashboard --------------------
if uploaded_ads:
    st.markdown("### 📢 Ads Cost Overview")

    # Read raw, remove A1 and A3 rows
    df_ads_raw = pd.read_excel(uploaded_ads, header=None)
    df_ads_raw = df_ads_raw.drop(index=[0,2], errors="ignore").reset_index(drop=True)

    # First row as header
    df_ads_raw.columns = df_ads_raw.iloc[0]
    df_ads_raw = df_ads_raw.drop(index=0).reset_index(drop=True)

    # Multiply all data by 1 to ensure numeric
    df_ads_raw = df_ads_raw.apply(pd.to_numeric, errors="ignore") * 1

    # Keep required columns
    df_ads = df_ads_raw[["Deduction Duration", "Total Ads Cost"]].copy()
    df_ads["_date"] = pd.to_datetime(df_ads["Deduction Duration"], errors="coerce").dt.date
    df_ads["_amount"] = pd.to_numeric(df_ads["Total Ads Cost"], errors="coerce")

    # Date filter
    date_min_ads, date_max_ads = df_ads["_date"].min(), df_ads["_date"].max()
    start_date_ads = st.sidebar.date_input("Ads Start Date", value=date_min_ads, key="ads_start")
    end_date_ads   = st.sidebar.date_input("Ads End Date", value=date_max_ads, key="ads_end")
    ads_filtered = df_ads[(df_ads["_date"] >= start_date_ads) & (df_ads["_date"] <= end_date_ads)]

    ads_by_date = ads_filtered.groupby("_date")["_amount"].sum().reset_index().rename(columns={"_amount":"Ads Cost"})
    total_ads = ads_by_date["Ads Cost"].sum()

    st.metric("Total Ads Cost", f"₹{total_ads:,.0f}")
    fig_ads = px.bar(
        ads_by_date, x="_date", y="Ads Cost", text="Ads Cost",
        title=f"Daily Ads Spend (Supplier: {supplier_id} | Total Ads: ₹{total_ads:,.0f})"
    )
    fig_ads.update_traces(textposition="outside", marker_color="#f39c12")
    st.plotly_chart(fig_ads, use_container_width=True)

    # -------------------- Combined Orders + Ads --------------------
    st.markdown("### 📊 Orders vs Ads Cost (Daily Comparison)")
    combined = pd.merge(orders_by_date, ads_by_date, left_on="_order_date_parsed", right_on="_date", how="outer")
    combined = combined.rename(columns={"_order_date_parsed":"Date"})[["Date","Orders","Ads Cost"]].fillna(0)

    # Show Table
    st.dataframe(combined, use_container_width=True)

    # Show Grouped Bar Chart
    fig_compare = px.bar(
        combined, x="Date", y=["Orders","Ads Cost"], barmode="group",
        title=f"Orders vs Ads Cost (Supplier: {supplier_id})"
    )
    st.plotly_chart(fig_compare, use_container_width=True)

# -------------------- Downloads --------------------
st.markdown("### Download filtered data")
file_prefix = f"Report_By_Razi_Supplier_{supplier_id}"
c1, c2, c3 = st.columns(3)

with c1:
    st.download_button("Download CSV", filtered.to_csv(index=False).encode("utf-8"), f"{file_prefix}.csv")
with c2:
    st.download_button("Download Excel", to_excel_bytes(filtered), f"{file_prefix}.xlsx")
with c3:
    def create_pdf():
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        doc = SimpleDocTemplate(tmp.name, pagesize=landscape(A4),
                                leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24)
        styles = getSampleStyleSheet()
        H1 = styles["Heading1"]; H1.fontSize = 18; H1.spaceAfter = 12
        P  = styles["BodyText"]

        elements = []
        # Cover Page (NO blank page)
        elements.append(Paragraph(f"Orders Report — Supplier {supplier_id}", H1))
        summary_txt = f"Date Range: {start_dt.date()} to {end_dt.date()} | Supplier ID: {supplier_id} | Total Orders: {total_orders}"
        elements.append(Paragraph(summary_txt, P))
        elements.append(Spacer(1, 12))

        # Status Table
        elements.append(Paragraph("Status Summary", H1))
        data = [["Status", "Count"]] + [[s, status_counts.get(s,0)] for s in STATUS_LIST] + [["GRAND TOTAL", grand_total]]
        t = Table(data, colWidths=[360, 200])
        t.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#0b3d91")),
            ("TEXTCOLOR",(0,0),(-1,0),colors.whitesmoke),
            ("ALIGN",(0,0),(-1,-1),"CENTER"),
            ("GRID",(0,0),(-1,-1),0.8,colors.black),
            ("BACKGROUND",(0,1),(-1,-1),colors.HexColor("#f2f6fc")),
            ("FONTSIZE",(0,0),(-1,0),14),
            ("FONTSIZE",(0,1),(-1,-1),12),
            ("ROWSPACING",(0,0),(-1,-1),6),
        ]))
        elements.append(t)
        elements.append(PageBreak())

        def add_chart_page(fig, title):
            elements.append(Paragraph(title, H1))
            try:
                img_bytes = fig.to_image(format="png", scale=3)
                img_path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
                with open(img_path, "wb") as f:
                    f.write(img_bytes)
            except Exception:
                img_path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
                fig.write_image(img_path, scale=3)
            elements.append(Image(img_path, width=794, height=480))
            elements.append(PageBreak())

        add_chart_page(fig_status, "Status Count (Bar)")
        add_chart_page(fig_time,   "Orders by Date")
        if uploaded_ads:
            add_chart_page(fig_ads, "Daily Ads Spend")
            add_chart_page(fig_compare, "Orders vs Ads Cost")

        doc.build(elements)
        tmp.seek(0)
        return tmp.read()

    st.download_button("Download PDF", create_pdf(), f"{file_prefix}.pdf", "application/pdf")
