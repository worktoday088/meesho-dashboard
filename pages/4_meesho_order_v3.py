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

# ================= PAGE CONFIG =================
st.set_page_config(page_title="📦 Meesho Orders & Ads Dashboard", layout="wide")

# ================= CSS =================
st.markdown("""
<style>
.title { font-size:28px; font-weight:700; color:#0b3d91; }
.subtitle { color:#445267; margin-top:-8px; margin-bottom:16px; }
.metric-row { display:flex; flex-wrap:wrap; gap:12px; }
.metric-box {
    padding:14px 18px;
    border-radius:10px;
    color:#fff;
    font-weight:700;
    text-align:center;
    min-width:210px;
}
.ADS { background:#f39c12; }
.ORD { background:#27ae60; }
.PER { background:#8e44ad; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="title">📊 Meesho Orders & Ads Dashboard</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Orders + Ads Analysis | PDF Export</div>', unsafe_allow_html=True)

# ================= HELPERS =================
def detect_and_load(file):
    if file.name.lower().endswith(".csv"):
        return pd.read_csv(file, low_memory=False)
    return pd.read_excel(file)

def merge_files(files):
    dfs = []
    for i, f in enumerate(files):
        df = detect_and_load(f)
        if i > 0:
            df = df.iloc[1:]  # duplicate header ignore
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)

def robust_parse_dates(series):
    s = pd.to_datetime(series, errors="coerce", infer_datetime_format=True)
    if s.notna().any():
        return s
    return pd.to_datetime(series, errors="coerce", dayfirst=True)

def to_excel_bytes(df):
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return buf.getvalue()

# ================= SIDEBAR UPLOAD =================
st.sidebar.markdown("### 📤 Upload Files")

uploaded_orders = st.sidebar.file_uploader(
    "Upload Orders Files",
    type=["csv","xls","xlsx"],
    accept_multiple_files=True
)

uploaded_ads = st.sidebar.file_uploader(
    "Upload Ads Cost Files",
    type=["csv","xls","xlsx"],
    accept_multiple_files=True
)

if not uploaded_orders:
    st.warning("⚠️ Please upload Orders files")
    st.stop()

# ================= LOAD ORDERS =================
df = merge_files(uploaded_orders)
cols = df.columns.tolist()

col_status = "Reason for Credit Entry"
col_date   = "Order Date"

df["_order_date"] = robust_parse_dates(df[col_date])

# ================= DATE FILTER =================
st.sidebar.markdown("### 📅 Date Filter")
start_date = st.sidebar.date_input("Start Date", df["_order_date"].min().date())
end_date   = st.sidebar.date_input("End Date", df["_order_date"].max().date())

start_dt = datetime.combine(start_date, datetime.min.time())
end_dt   = datetime.combine(end_date, datetime.max.time())

filtered = df[(df["_order_date"] >= start_dt) & (df["_order_date"] <= end_dt)]
total_orders = len(filtered)

# ================= ORDERS OVERVIEW =================
st.markdown("### 📦 Orders Overview")

status_counts = filtered[col_status].value_counts().to_dict()

status_df = (
    filtered.groupby(filtered["_order_date"].dt.date)
    .size().reset_index(name="Orders")
)

fig_orders = px.bar(
    status_df,
    x="_order_date",
    y="Orders",
    text="Orders",
    title="Orders by Date"
)
fig_orders.update_traces(textposition="outside")
st.plotly_chart(fig_orders, use_container_width=True)

# ================= ADS SECTION =================
combined = None

if uploaded_ads:
    ads_frames = []
    for f in uploaded_ads:
        raw = pd.read_excel(f, header=None)
        raw = raw.drop(index=[0,2], errors="ignore").reset_index(drop=True)
        raw.columns = raw.iloc[0]
        raw = raw.drop(index=0).reset_index(drop=True)
        ads_frames.append(raw)

    ads = pd.concat(ads_frames, ignore_index=True)
    ads["_date"] = pd.to_datetime(
        ads["Deduction Duration"], errors="coerce"
    ).dt.date
    ads["_amount"] = pd.to_numeric(
        ads["Total Ads Cost"], errors="coerce"
    )

    ads_by_date = ads.groupby("_date")["_amount"].sum().reset_index()
    ads_by_date.rename(columns={"_amount":"Ads Cost"}, inplace=True)

    total_ads = ads_by_date["Ads Cost"].sum()
    per_order_cost = total_ads / total_orders if total_orders else 0

    # ========== ADS OVERVIEW (3 BOXES) ==========
    st.markdown("### 📢 Ads Cost Overview")
    st.markdown(f"""
    <div class="metric-row">
        <div class="metric-box ADS">💰 Total Ads Cost<br>₹{total_ads:,.0f}</div>
        <div class="metric-box ORD">📦 Total Orders<br>{total_orders}</div>
        <div class="metric-box PER">📉 Ads Cost / Order<br>₹{per_order_cost:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)

    fig_ads = px.bar(
        ads_by_date,
        x="_date",
        y="Ads Cost",
        text="Ads Cost",
        title="Daily Ads Spend"
    )
    fig_ads.update_traces(textposition="outside")
    st.plotly_chart(fig_ads, use_container_width=True)

    # ========== COMBINED TABLE ==========
    combined = pd.merge(
        status_df,
        ads_by_date,
        left_on="_order_date",
        right_on="_date",
        how="outer"
    ).fillna(0)

    combined["Ads Cost / Order"] = combined.apply(
        lambda r: r["Ads Cost"] / r["Orders"] if r["Orders"] > 0 else 0,
        axis=1
    )

    st.markdown("### 📊 Orders vs Ads Cost (Daily Comparison)")
    st.dataframe(combined, use_container_width=True)

    fig_compare = px.bar(
        combined,
        x="_order_date",
        y=["Orders","Ads Cost"],
        barmode="group",
        title="Orders vs Ads Cost"
    )
    st.plotly_chart(fig_compare, use_container_width=True)

# ================= DOWNLOAD SECTION =================
st.markdown("### 📥 Download")

c1, c2, c3 = st.columns(3)

with c1:
    st.download_button(
        "Download CSV",
        filtered.to_csv(index=False),
        "orders_filtered.csv"
    )

with c2:
    st.download_button(
        "Download Excel",
        to_excel_bytes(filtered),
        "orders_filtered.xlsx"
    )

with c3:
    def create_pdf():
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        doc = SimpleDocTemplate(tmp.name, pagesize=landscape(A4))
        styles = getSampleStyleSheet()
        H = styles["Heading1"]

        elements = []
        elements.append(Paragraph("Orders & Ads Report", H))
        elements.append(Spacer(1, 12))

        if combined is not None:
            table_data = [["Date","Orders","Ads Cost","Ads Cost / Order"]]
            for _, r in combined.iterrows():
                table_data.append([
                    str(r["_order_date"]),
                    int(r["Orders"]),
                    f"₹{r['Ads Cost']:,.0f}",
                    f"₹{r['Ads Cost / Order']:,.2f}"
                ])

            t = Table(table_data)
            t.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#0b3d91")),
                ("TEXTCOLOR",(0,0),(-1,0),colors.white),
                ("GRID",(0,0),(-1,-1),0.6,colors.black),
            ]))
            elements.append(t)

        doc.build(elements)
        tmp.seek(0)
        return tmp.read()

    st.download_button(
        "Download PDF",
        create_pdf(),
        "orders_ads_report.pdf",
        "application/pdf"
    )
