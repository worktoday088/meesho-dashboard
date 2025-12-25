# ================= ORIGINAL IMPORTS =================
import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
from datetime import datetime
import tempfile
import re

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, Image, PageBreak
)
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

# ================= STREAMLIT PAGE =================
st.set_page_config(page_title="📦 Meesho Orders & Ads Dashboard", layout="wide")

# ================= THEME / CSS (UNCHANGED + ADDITIONS) =================
st.markdown("""
<style>
.title { font-size:28px; font-weight:700; color:#0b3d91; }
.subtitle { color:#445267; margin-top:-8px; margin-bottom:16px; }
.metric-box {
    display:inline-block; padding:14px 16px; margin:6px 8px;
    border-radius:10px; color:#fff;
    font-weight:700; text-align:center; min-width:150px;
}
.CANCELLED{background:#e74c3c;} .DELIVERED{background:#27ae60;}
.DOOR_STEP_EXCHANGED{background:#9b59b6;} .HOLD{background:#f39c12;}
.PENDING{background:#e67e22;} .READY_TO_SHIP{background:#2980b9;}
.RTO_COMPLETE{background:#1abc9c;} .RTO_INITIATED{background:#d35400;}
.RTO_LOCKED{background:#8e44ad;} .SHIPPED{background:#2c3e50;}
.GRAND_TOTAL{background:#0b3d91;}
.ADS{background:#f39c12;} .ORD{background:#27ae60;} .PER{background:#8e44ad;}
.metric-row { display:flex; flex-wrap:wrap; align-items:center }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="title">📊 Meesho Orders & Ads Dashboard</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Upload Orders + Ads → Insights → Export Reports</div>', unsafe_allow_html=True)

# ================= HELPERS =================
def detect_and_load(file):
    name = file.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(file, low_memory=False)
    elif name.endswith((".xls", ".xlsx")):
        return pd.read_excel(file)
    else:
        raise ValueError("Upload CSV or Excel only.")

def merge_multiple(files):
    dfs = []
    for i, f in enumerate(files):
        df = detect_and_load(f)
        if i > 0:
            df = df.iloc[1:]
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)

def to_excel_bytes(df):
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Filtered")
    return buf.getvalue()

def robust_parse_dates(series):
    s = pd.to_datetime(series, errors="coerce", infer_datetime_format=True)
    if s.notna().any():
        return s
    return pd.to_datetime(series, errors="coerce", dayfirst=True)

STATUS_LIST = [
    "CANCELLED","DELIVERED","DOOR_STEP_EXCHANGED","HOLD","PENDING",
    "READY_TO_SHIP","RTO_COMPLETE","RTO_INITIATED","RTO_LOCKED","SHIPPED"
]

COLOR_MAP = {
    "CANCELLED":"#e74c3c","DELIVERED":"#27ae60",
    "DOOR_STEP_EXCHANGED":"#9b59b6","HOLD":"#f39c12",
    "PENDING":"#e67e22","READY_TO_SHIP":"#2980b9",
    "RTO_COMPLETE":"#1abc9c","RTO_INITIATED":"#d35400",
    "RTO_LOCKED":"#8e44ad","SHIPPED":"#2c3e50",
    "GRAND_TOTAL":"#0b3d91"
}

GRAND_INCLUDE = [
    "DELIVERED","DOOR_STEP_EXCHANGED","HOLD","PENDING",
    "READY_TO_SHIP","RTO_COMPLETE","RTO_INITIATED","RTO_LOCKED","SHIPPED"
]

ORDERS_BY_DATE_COLOR = "#0b3d91"

# ================= UPLOAD (MULTIPLE FILES) =================
st.sidebar.markdown("### Upload Files")

uploaded_orders = st.sidebar.file_uploader(
    "Upload Orders Files",
    type=["csv","xls","xlsx"],
    accept_multiple_files=True,
    key="orders"
)

uploaded_ads = st.sidebar.file_uploader(
    "Upload Ads Cost Files",
    type=["csv","xls","xlsx"],
    accept_multiple_files=True,
    key="ads"
)

if not uploaded_orders:
    st.info("⚠️ Please upload Orders file to continue.")
    st.stop()

# ================= LOAD ORDERS =================
df = merge_multiple(uploaded_orders)
cols = list(df.columns)

supplier_id = "Unknown"
try:
    match = re.search(r"_(\d+)\.csv$", uploaded_orders[0].name)
    if match:
        supplier_id = match.group(1)
except:
    pass

col_status     = "Reason for Credit Entry"
col_order_date = "Order Date"
col_sku        = "SKU"
col_size       = "Size"
col_state      = "Customer State"

# ================= FILTERS =================
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
    return st.sidebar.multiselect(label, options, default_opts, key=f"{key}_multi")

status_sel = searchable_multiselect("Status", sorted(filtered[col_status].dropna().unique()), "status")
sku_sel    = searchable_multiselect("SKU", sorted(filtered[col_sku].dropna().unique()), "sku")
size_sel   = searchable_multiselect("Size", sorted(filtered[col_size].dropna().unique()), "size")
state_sel  = searchable_multiselect("Customer State", sorted(filtered[col_state].dropna().unique()), "state")

if status_sel: filtered = filtered[filtered[col_status].isin(status_sel)]
if sku_sel:    filtered = filtered[filtered[col_sku].isin(sku_sel)]
if size_sel:   filtered = filtered[filtered[col_size].isin(size_sel)]
if state_sel:  filtered = filtered[filtered[col_state].isin(state_sel)]

total_orders = len(filtered)

# ================= ORDERS OVERVIEW (UNCHANGED) =================
st.markdown("### 📦 Orders Overview")

status_counts = filtered[col_status].value_counts().to_dict()
boxes_html = '<div class="metric-row">'
for s in STATUS_LIST:
    boxes_html += f"<div class='metric-box {s}'>{s}<br>{status_counts.get(s,0)}</div>"
grand_total = sum(status_counts.get(s,0) for s in GRAND_INCLUDE)
boxes_html += f"<div class='metric-box GRAND_TOTAL'>GRAND TOTAL<br>{grand_total}</div></div>"
st.markdown(boxes_html, unsafe_allow_html=True)

# ================= STATUS BAR =================
status_bar_df = pd.DataFrame({
    "status": STATUS_LIST,
    "count": [status_counts.get(s,0) for s in STATUS_LIST]
})
fig_status = px.bar(status_bar_df, x="status", y="count", text="count")
fig_status.update_traces(marker_color=[COLOR_MAP[s] for s in STATUS_LIST], textposition="outside")
st.plotly_chart(fig_status, use_container_width=True)

# ================= ORDERS BY DATE =================
orders_by_date = (
    filtered.groupby(filtered["_order_date_parsed"].dt.date)
    .size().reset_index(name="Orders")
)

fig_time = px.bar(
    orders_by_date, x="_order_date_parsed", y="Orders",
    text="Orders", title="Orders by Date"
)
fig_time.update_traces(textposition="outside", marker_color=ORDERS_BY_DATE_COLOR)
st.plotly_chart(fig_time, use_container_width=True)

# ================= ADS DASHBOARD (ENHANCED) =================
if uploaded_ads:
    ads_frames = []
    for f in uploaded_ads:
        raw = pd.read_excel(f, header=None)
        raw = raw.drop(index=[0,2], errors="ignore").reset_index(drop=True)
        raw.columns = raw.iloc[0]
        raw = raw.drop(index=0).reset_index(drop=True)
        ads_frames.append(raw)

    ads = pd.concat(ads_frames, ignore_index=True)
    ads["_date"] = pd.to_datetime(ads["Deduction Duration"], errors="coerce").dt.date
    ads["_amount"] = pd.to_numeric(ads["Total Ads Cost"], errors="coerce")

    ads_by_date = ads.groupby("_date")["_amount"].sum().reset_index()
    ads_by_date.rename(columns={"_amount":"Ads Cost"}, inplace=True)

    total_ads = ads_by_date["Ads Cost"].sum()
    per_order_cost = total_ads / total_orders if total_orders else 0

    st.markdown("### 📢 Ads Cost Overview")
    st.markdown(f"""
    <div class="metric-row">
        <div class="metric-box ADS">Total Ads Cost<br>₹{total_ads:,.0f}</div>
        <div class="metric-box ORD">Total Orders<br>{total_orders}</div>
        <div class="metric-box PER">Ads Cost / Order<br>₹{per_order_cost:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)

    combined = pd.merge(
        orders_by_date, ads_by_date,
        left_on="_order_date_parsed", right_on="_date",
        how="outer"
    ).fillna(0)

    combined["Ads Cost / Order"] = combined.apply(
        lambda r: r["Ads Cost"]/r["Orders"] if r["Orders"] > 0 else 0,
        axis=1
    )

    st.markdown("### 📊 Orders vs Ads Cost (Daily Comparison)")
    st.dataframe(combined, use_container_width=True)

# ================= DOWNLOADS (UNCHANGED + TABLE IN PDF) =================
st.markdown("### Download filtered data")
file_prefix = f"Report_By_Razi_Supplier_{supplier_id}"

c1, c2, c3 = st.columns(3)
with c1:
    st.download_button("Download CSV", filtered.to_csv(index=False).encode(), f"{file_prefix}.csv")
with c2:
    st.download_button("Download Excel", to_excel_bytes(filtered), f"{file_prefix}.xlsx")

with c3:
    def create_pdf():
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        doc = SimpleDocTemplate(tmp.name, pagesize=landscape(A4))
        styles = getSampleStyleSheet()
        H = styles["Heading1"]

        elements = [Paragraph("Orders & Ads Report", H), Spacer(1,12)]

        if uploaded_ads:
            data = [["Date","Orders","Ads Cost","Ads Cost / Order"]]
            for _, r in combined.iterrows():
                data.append([
                    str(r["_order_date_parsed"]),
                    int(r["Orders"]),
                    f"₹{r['Ads Cost']:,.0f}",
                    f"₹{r['Ads Cost / Order']:,.2f}"
                ])
            t = Table(data)
            t.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#0b3d91")),
                ("TEXTCOLOR",(0,0),(-1,0),colors.white),
                ("GRID",(0,0),(-1,-1),0.6,colors.black),
            ]))
            elements.append(t)

        doc.build(elements)
        tmp.seek(0)
        return tmp.read()

    st.download_button("Download PDF", create_pdf(), f"{file_prefix}.pdf", "application/pdf")
