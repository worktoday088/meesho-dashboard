# ============================================================
# PDF → Data (Meesho) — SINGLE CLEAN FINAL SCRIPT (UPDATED)
# ============================================================

import streamlit as st
import fitz  # PyMuPDF
import re
import pandas as pd
from datetime import datetime
from collections import defaultdict
import io
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

# ------------------------------------------------------------
# PAGE CONFIG
# ------------------------------------------------------------
st.set_page_config(page_title="PDF → Data (Meesho)", layout="wide")
st.title("📦 PDF → Data (Meesho) — FINAL STABLE VERSION")

# ------------------------------------------------------------
# REGEX DEFINITIONS
# ------------------------------------------------------------
SIZE_PATTERN = r"(XS|S|M|L|XL|XXL|XXXL|FREE SIZE|24|26|28|30|32|34|36|38|40|42|44|46|48|50)"

AWB_PATTERNS = [
    r"\bVL\d{10,14}\b",
    r"\bSF\d{10,14}[A-Z]{2,3}\b",
    r"\b\d{14,16}\b",
]

COURIER_REGEX = re.compile(
    r"(Valmo|Xpress\s*Bees|Delhivery|Shadowfax|Ecom\s*Express|DTDC|BlueDart|Bluedart|WowExpress|India\s*Post|Speed\s*Post|EKART|Ekart)",
    re.IGNORECASE
)

# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------
def sanitize_sheet_name(name: str) -> str:
    return re.sub(r'[\\/*?:\[\]]', '_', name)[:31]

# ------------------------------------------------------------
# EXTRACTION LOGIC (UNCHANGED – BASE LOGIC)
# ------------------------------------------------------------
def extract_from_page_text(text: str, entry_date: str):
    seller_match = re.search(r"If undelivered, return to:\s*\n([^\n]+)", text)
    seller = seller_match.group(1).strip() if seller_match else "UnknownSeller"

    courier_match = COURIER_REGEX.search(text)
    courier = courier_match.group(1).title() if courier_match else "Unknown"

    awb = ""
    for p in AWB_PATTERNS:
        m = re.search(p, text)
        if m:
            awb = m.group(0)
            break

    order_date = ""
    invoice_date = ""
    m = re.search(r"Order Date\s+(\d{2}\.\d{2}\.\d{4})", text)
    if m:
        order_date = m.group(1)
    m = re.search(r"Invoice Date\s+(\d{2}\.\d{2}\.\d{4})", text)
    if m:
        invoice_date = m.group(1)

    product_lines = re.findall(
        rf"(.+?)\s+{SIZE_PATTERN}\s+(\d+)\s+(.+?)\s+((?:\d+_\d+\s*,?\s*)+)",
        text
    )

    rows = []

    for sku, size, qty, color, order_ids_raw in product_lines:
        qty = int(qty)
        order_ids = [o.strip() for o in order_ids_raw.split(",") if o.strip()]

        if qty == len(order_ids):
            for oid in order_ids:
                rows.append({
                    "Order ID": oid,
                    "SKU": sku.strip(),
                    "Size": size,
                    "Qty": 1,
                    "Color": color.strip(),
                    "Courier": courier,
                    "AWB Number": awb,
                    "Order Date": order_date,
                    "Invoice Date": invoice_date,
                    "Entry Date": entry_date,
                })
        elif qty > len(order_ids):
            for idx, oid in enumerate(order_ids):
                rows.append({
                    "Order ID": oid,
                    "SKU": sku.strip(),
                    "Size": size,
                    "Qty": qty if idx == 0 else "",
                    "Color": color.strip(),
                    "Courier": courier,
                    "AWB Number": awb,
                    "Order Date": order_date,
                    "Invoice Date": invoice_date,
                    "Entry Date": entry_date,
                })
        else:
            for oid in order_ids:
                rows.append({
                    "Order ID": oid,
                    "SKU": sku.strip(),
                    "Size": size,
                    "Qty": qty,
                    "Color": color.strip(),
                    "Courier": courier,
                    "AWB Number": awb,
                    "Order Date": order_date,
                    "Invoice Date": invoice_date,
                    "Entry Date": entry_date,
                })

    return seller, rows

# ------------------------------------------------------------
# PROCESS PDFs
# ------------------------------------------------------------
def process_pdfs(files):
    entry_date = datetime.today().strftime("%d.%m.%Y")
    data = defaultdict(list)

    for f in files:
        with fitz.open(stream=f.read(), filetype="pdf") as doc:
            for page in doc:
                seller, rows = extract_from_page_text(page.get_text(), entry_date)
                data[seller].extend(rows)

    seller_dfs = {}
    for seller, rows in data.items():
        df = pd.DataFrame(rows)
        if df.empty:
            continue

        df.drop_duplicates(
            subset=["Order ID", "SKU", "Size", "Color", "AWB Number"],
            inplace=True
        )
        df.insert(0, "S.No", range(1, len(df) + 1))
        seller_dfs[seller] = df

    return seller_dfs

# ------------------------------------------------------------
# COURIER SUMMARY
# ------------------------------------------------------------
def courier_summary(df: pd.DataFrame):
    if "AWB Number" not in df.columns or df.empty:
        return pd.DataFrame(columns=["Courier", "Packets"])

    s = (
        df[df["AWB Number"] != ""]
        .drop_duplicates(subset=["AWB Number"])
        .groupby("Courier")
        .size()
        .reset_index(name="Packets")
    )

    if not s.empty:
        s.loc[len(s)] = ["GRAND TOTAL", s["Packets"].sum()]

    return s

# ------------------------------------------------------------
# PDF REPORT
# ------------------------------------------------------------
def create_pdf(summary_df: pd.DataFrame):
    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        fig, ax = plt.subplots(figsize=(8.27, 11.69))
        ax.axis("off")
        ax.table(cellText=summary_df.values, colLabels=summary_df.columns, loc="center")
        pdf.savefig(fig)
        plt.close()
    buf.seek(0)
    return buf.read()

# ------------------------------------------------------------
# EXCEL REPORT (Seller-wise – unchanged)
# ------------------------------------------------------------
def create_excel(seller_dfs, selected_couriers, selected_sellers):
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        for seller, df in seller_dfs.items():

            if "ALL" not in selected_sellers and seller not in selected_sellers:
                continue

            temp = df.copy()
            if "ALL" not in selected_couriers:
                temp = temp[temp["Courier"].isin(selected_couriers)]

            if temp.empty:
                continue

            temp.to_excel(writer, sanitize_sheet_name(seller), index=False)
            courier_summary(temp).to_excel(
                writer,
                sanitize_sheet_name(seller + "_Summary"),
                index=False
            )
    out.seek(0)
    return out.read()

# ------------------------------------------------------------
# THIRD EXCEL (ALL SELLERS – SINGLE SHEET)
# ------------------------------------------------------------
def create_single_sheet_excel(seller_dfs, selected_couriers, selected_sellers):
    rows = []

    for seller, df in seller_dfs.items():
        if "ALL" not in selected_sellers and seller not in selected_sellers:
            continue

        temp = df.copy()
        if "ALL" not in selected_couriers:
            temp = temp[temp["Courier"].isin(selected_couriers)]

        if temp.empty:
            continue

        temp.insert(1, "Seller Name", seller)
        rows.append(temp)

    if not rows:
        return None

    final_df = pd.concat(rows, ignore_index=True)

    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        final_df.to_excel(writer, "ALL_SELLERS_DATA", index=False)

    out.seek(0)
    return out.read()

# ------------------------------------------------------------
# UI
# ------------------------------------------------------------
with st.expander("📤 Upload PDFs", expanded=True):
    files = st.file_uploader("Upload Meesho PDFs", type=["pdf"], accept_multiple_files=True)
    if st.button("🚀 Process PDFs") and files:
        with st.spinner("📄 PDFs पढ़े जा रहे हैं..."):
            st.session_state["seller_dfs"] = process_pdfs(files)
        st.success("✅ Processing Completed Successfully")

# ------------------------------------------------------------
# OUTPUT
# ------------------------------------------------------------
if "seller_dfs" in st.session_state:
    seller_dfs = st.session_state["seller_dfs"]
    all_df = pd.concat(seller_dfs.values(), ignore_index=True)

    # 🔎 FILTERS (SAME LINE)
    col1, col2 = st.columns(2)

    with col1:
        couriers = sorted(all_df["Courier"].dropna().unique())
        selected_couriers = st.multiselect(
            "🚚 Filter by Courier", ["ALL"] + couriers, default=["ALL"]
        )

    with col2:
        sellers = sorted(seller_dfs.keys())
        selected_sellers = st.multiselect(
            "🏪 Filter by Seller", ["ALL"] + sellers, default=["ALL"]
        )

    # APPLY FILTER TO COMBINED DF
    filtered_df = all_df.copy()
    if "ALL" not in selected_couriers:
        filtered_df = filtered_df[filtered_df["Courier"].isin(selected_couriers)]
    if "ALL" not in selected_sellers:
        filtered_df = filtered_df[filtered_df["Seller Name"].isin(selected_sellers)] if "Seller Name" in filtered_df else filtered_df

    st.subheader("📦 Combined Courier Summary")
    st.table(courier_summary(filtered_df))

    st.subheader("🏬 Seller-wise Data Preview")
    for seller, df in seller_dfs.items():
        if "ALL" not in selected_sellers and seller not in selected_sellers:
            continue

        view = df.copy()
        if "ALL" not in selected_couriers:
            view = view[view["Courier"].isin(selected_couriers)]

        if not view.empty:
            with st.expander(seller):
                st.dataframe(view, use_container_width=True)

    # DOWNLOADS
    st.download_button(
        "📊 Download Excel Report (Seller-wise)",
        create_excel(seller_dfs, selected_couriers, selected_sellers),
        file_name="Meesho_Report.xlsx"
    )

    single_excel = create_single_sheet_excel(
        seller_dfs, selected_couriers, selected_sellers
    )

    if single_excel:
        st.download_button(
            "📥 Download Excel (All Sellers – Single Sheet)",
            single_excel,
            file_name="Meesho_All_Sellers_Single_Sheet.xlsx"
        )

    st.download_button(
        "📄 Download PDF Report",
        create_pdf(courier_summary(filtered_df)),
        file_name="Courier_Summary.pdf",
        mime="application/pdf"
    )
