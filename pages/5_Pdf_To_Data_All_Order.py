# ============================================================
# PDF → Data (Meesho) — FULL UPDATED FINAL SCRIPT
# Features:
# 1. Combined Courier Summary (All Sellers, Unique AWB)
# 2. Seller-wise Courier Summary (Expandable)
# 3. Duplicate AWB Ignored (Packet = Unique AWB)
# 4. Hide / Unhide Upload Section
# 5. Hide / Unhide Data Preview (Accordion)
# 6. Excel + PDF Reports with Totals
# ============================================================

import streamlit as st
import fitz  # PyMuPDF
import re
import pandas as pd
from datetime import datetime
from collections import defaultdict
import io
import zipfile
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

# ------------------------------------------------------------
# PAGE CONFIG
# ------------------------------------------------------------
st.set_page_config(
    page_title="PDF → Data (Meesho) — Final",
    layout="wide"
)

st.title("📦 PDF → Data (Meesho) — FINAL FULL VERSION")
st.caption("Combined + Seller-wise Courier Summary | Unique AWB Packet Logic")

# ------------------------------------------------------------
# REGEX DEFINITIONS
# ------------------------------------------------------------
size_pattern = r"(XS|S|M|L|XL|XXL|XXXL|FREE SIZE|24|26|28|30|32|34|36|38|40|42|44|46|48|50|6-7 Years|7-8 Years|8-9 Years|9-10 Years|10-11 Years|11-12 Years|12-13 Years|13-14 Years|14-15 Years|15-16 Years|16-17 Years|17-18 Years)"

awb_patterns = [
    r"\bVL\d{10,14}\b",
    r"\bSF\d{10,14}[A-Z]{2,3}\b",
    r"\b\d{14,16}\b",
]

courier_regex = re.compile(
    r"(Valmo|Xpress\s*Bees|Delhivery|Shadowfax|Ecom\s*Express|DTDC|BlueDart|Bluedart|WowExpress|Wow\s*Express|India\s*Post|Speed\s*Post|EKART|Ekart|Amazon\s*Shipping)",
    re.IGNORECASE
)

# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------

def sanitize_sheet_name(name: str, suffix: str = "") -> str:
    base = re.sub(r'[\\/*?:\[\]]', '_', name.replace(" ", "_"))
    max_len = 31 - len(suffix)
    return base[:max_len] + suffix


# ------------------------------------------------------------
# EXTRACTION LOGIC
# ------------------------------------------------------------

def extract_from_page_text(text: str, entry_date: str):
    seller_m = re.search(r"If undelivered, return to:\s*\n([^\n]+)", text)
    seller = seller_m.group(1).strip() if seller_m else "UnknownSeller"

    courier_m = courier_regex.search(text)
    courier = courier_m.group(1).title() if courier_m else "Unknown"

    awb = next((m.group(0) for p in awb_patterns if (m := re.search(p, text))), "")

    order_date = (m.group(1) if (m := re.search(r"Order Date\s+(\d{2}\.\d{2}\.\d{4})", text)) else "")
    invoice_date = (m.group(1) if (m := re.search(r"Invoice Date\s+(\d{2}\.\d{2}\.\d{4})", text)) else "")

    product_lines = re.findall(
        rf"(.+?)\s+{size_pattern}\s+(\d+)\s+(.+?)\s+([0-9_,\s]+)",
        text
    )

    rows = []
    for sku, size, qty, color, order_ids_raw in product_lines:
        order_ids = [o.strip() for o in order_ids_raw.split(",") if o.strip()]
        for oid in order_ids:
            rows.append({
                "Order ID": oid,
                "SKU": sku.strip(),
                "Size": size.strip(),
                "Qty": "1",
                "Color": color.strip(),
                "Courier": courier,
                "AWB Number": awb,
                "Order Date": order_date,
                "Invoice Date": invoice_date,
                "Entry Date": entry_date,
                "Source PDF": "",
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
            for i in range(len(doc)):
                seller, rows = extract_from_page_text(doc[i].get_text(), entry_date)
                for r in rows:
                    r["Source PDF"] = f.name
                    data[seller].append(r)

    seller_dfs = {}
    for seller, rows in data.items():
        df = pd.DataFrame(rows)

        # DUPLICATE IGNORE LOGIC
        df.drop_duplicates(
            subset=["Order ID", "SKU", "Size", "Color", "AWB Number"],
            inplace=True
        )

        df.insert(0, "S.No", range(1, len(df) + 1))
        seller_dfs[seller] = df

    return seller_dfs


# ------------------------------------------------------------
# COURIER SUMMARY (UNIQUE AWB = PACKET)
# ------------------------------------------------------------

def courier_summary(df: pd.DataFrame):
    summary = (
        df[df["AWB Number"] != ""]
        .drop_duplicates(subset=["AWB Number"])
        .groupby("Courier")
        .size()
        .reset_index(name="Packets")
    )

    total = summary["Packets"].sum()
    summary.loc[len(summary)] = ["GRAND TOTAL", total]
    return summary


# ------------------------------------------------------------
# COMBINED SUMMARY (ALL SELLERS)
# ------------------------------------------------------------

def combined_summary(seller_dfs: dict):
    combined = pd.concat(seller_dfs.values(), ignore_index=True)
    return courier_summary(combined)


# ------------------------------------------------------------
# PDF REPORT
# ------------------------------------------------------------

def create_pdf(summary_tables: dict):
    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        for title, df in summary_tables.items():
            fig, ax = plt.subplots(figsize=(8.27, 11.69))  # A4
            ax.axis("off")
            ax.table(cellText=df.values, colLabels=df.columns, loc="center")
            plt.title(title)
            pdf.savefig(fig)
            plt.close()
    buf.seek(0)
    return buf.read()


# ------------------------------------------------------------
# EXCEL REPORT
# ------------------------------------------------------------

def create_excel(seller_dfs: dict):
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:

        # Combined Summary Sheet
        combined_summary(seller_dfs).to_excel(
            writer,
            sheet_name="ALL_SELLERS_SUMMARY",
            index=False
        )

        # Seller-wise sheets
        for seller, df in seller_dfs.items():
            df.to_excel(
                writer,
                sheet_name=sanitize_sheet_name(seller),
                index=False
            )

            courier_summary(df).to_excel(
                writer,
                sheet_name=sanitize_sheet_name(seller, "_Summary"),
                index=False
            )

    out.seek(0)
    return out.read()


# ------------------------------------------------------------
# UI — UPLOAD (HIDE / UNHIDE)
# ------------------------------------------------------------

with st.expander("📤 Upload & Settings", expanded=True):
    uploaded_files = st.file_uploader(
        "Upload Meesho PDFs",
        type=["pdf"],
        accept_multiple_files=True
    )

    if st.button("🚀 Process PDFs"):
        if uploaded_files:
            st.session_state["seller_dfs"] = process_pdfs(uploaded_files)
            st.success("Processing Completed Successfully")


# ------------------------------------------------------------
# DASHBOARD OUTPUT
# ------------------------------------------------------------

if "seller_dfs" in st.session_state:

    seller_dfs = st.session_state["seller_dfs"]

    st.markdown("---")
    st.subheader("📦 ALL SELLERS — COMBINED COURIER SUMMARY")

    combined_df = combined_summary(seller_dfs)
    st.table(combined_df)

    st.markdown("---")
    st.subheader("🏬 Seller-wise Courier Details")

    for seller, df in seller_dfs.items():
        with st.expander(f"{seller} — Courier Summary"):
            st.table(courier_summary(df))

    st.markdown("---")
    st.subheader("📑 Data Preview (Hide / Unhide)")

    for seller, df in seller_dfs.items():
        with st.expander(f"{seller} — Data Preview"):
            st.dataframe(df, use_container_width=True)

    st.markdown("---")

    # DOWNLOADS
    st.download_button(
        "📊 Download Excel Report",
        create_excel(seller_dfs),
        file_name="Meesho_Report.xlsx"
    )

    st.download_button(
        "📄 Download PDF Report",
        create_pdf({"ALL SELLERS SUMMARY": combined_df}),
        file_name="Courier_Summary.pdf",
        mime="application/pdf"
    )

# ===================== END OF SCRIPT =====================
