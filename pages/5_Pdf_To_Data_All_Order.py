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

st.set_page_config(page_title="PDF → Data (Meesho) — Final", layout="wide")

# -----------------------
# Regex Patterns
# -----------------------
size_pattern = r"(XS|S|M|L|XL|XXL|XXXL|FREE SIZE|24|26|28|30|32|34|36|38|40|42|44|46|48|50|6-7 Years|7-8 Years|8-9 Years|9-10 Years|10-11 Years|11-12 Years|12-13 Years|13-14 Years|14-15 Years|15-16 Years|16-17 Years|17-18 Years)"

awb_patterns = [
    r"\bVL\d{10,14}\b",
    r"\bSF\d{10,14}[A-Z]{2,3}\b",
    r"\b\d{14,16}\b",
    r"\b[A-Z0-9]{10,16}\b"
]

courier_regex = re.compile(
    r"(Valmo|Xpress\s*Bees|Delhivery|Shadowfax|Ecom\s*Express|DTDC|BlueDart|Bluedart|WowExpress|Wow\s*Express|India\s*Post|Speed\s*Post|EKART|Ekart|Amazon\s*Shipping)",
    re.IGNORECASE
)

# -----------------------
# Helpers
# -----------------------
def sanitize_sheet_name(name: str) -> str:
    s = re.sub(r'[\/*?:\[\]]', '_', (name or "UnknownSeller").strip().replace(" ", "_"))
    return s[:31] if s else "UnknownSeller"


# -----------------------
# Core Extraction Logic
# -----------------------
def extract_from_page_text(text: str, entry_date: str):
    seller_block = re.search(r"If undelivered, return to:\s*\n([^\n]+)", text)
    seller = seller_block.group(1).strip() if seller_block else "UnknownSeller"
    seller_filename = sanitize_sheet_name(seller)

    courier_m = courier_regex.search(text)
    courier = courier_m.group(1).strip() if courier_m else "UnknownCourier"

    awb_number = next(
        (m.group(0) for patt in awb_patterns if (m := re.search(patt, text))),
        "N/A"
    )

    order_date = (m.group(1) if (m := re.search(r"Order Date\s+(\d{2}\.\d{2}\.\d{4})", text)) else "")
    invoice_date = (m.group(1) if (m := re.search(r"Invoice Date\s+(\d{2}\.\d{2}\.\d{4})", text)) else "")

    product_lines = re.compile(
        rf"(.+?)\s+{size_pattern}\s+(\d+)\s+(.+?)\s+([0-9_,\s]+)",
        re.MULTILINE
    ).findall(text)

    rows = []

    for item in product_lines:
        if len(item) < 5:
            continue

        sku, size, qty, color, order_ids_raw = item
        qty = int(qty.strip())

        order_id_list = [oid.strip() for oid in order_ids_raw.split(",") if oid.strip()]

        # -------- CASE 1: Single Order ID (Qty may be >1)
        if len(order_id_list) == 1:
            oid = order_id_list[0]

            gst_price = ""
            base_price = ""

            gst_m = re.search(
                rf"{re.escape(oid)}.*?Total\s+Rs\.\d+\.\d+\s+Rs\.(\d+\.\d+)",
                text,
                re.DOTALL
            )
            if gst_m:
                gst_price = gst_m.group(1)

            base_m = re.search(
                rf"{re.escape(oid)}.*?Taxable Value.*?Rs\.(\d+\.\d+)",
                text,
                re.DOTALL
            )
            if base_m:
                base_price = base_m.group(1)

            rows.append({
                "Order ID": oid,
                "SKU": sku.strip(),
                "Size": size.strip(),
                "Qty": str(qty),
                "Color": color.strip(),
                "Courier": courier,
                "AWB Number": awb_number,
                "Price (Incl. GST)": gst_price,
                "Price (Excl. GST)": base_price,
                "Order Date": order_date,
                "Invoice Date": invoice_date,
                "Entry Date": entry_date,
                "Source PDF": "",
                "Action": ""
            })

        # -------- CASE 2 / 3: Multiple Order IDs
        else:
            for oid in order_id_list:
                gst_price = ""
                base_price = ""

                gst_m = re.search(
                    rf"{re.escape(oid)}.*?Total\s+Rs\.\d+\.\d+\s+Rs\.(\d+\.\d+)",
                    text,
                    re.DOTALL
                )
                if gst_m:
                    gst_price = gst_m.group(1)

                base_m = re.search(
                    rf"{re.escape(oid)}.*?Taxable Value.*?Rs\.(\d+\.\d+)",
                    text,
                    re.DOTALL
                )
                if base_m:
                    base_price = base_m.group(1)

                rows.append({
                    "Order ID": oid,
                    "SKU": sku.strip(),
                    "Size": size.strip(),
                    "Qty": "1",
                    "Color": color.strip(),
                    "Courier": courier,
                    "AWB Number": awb_number,
                    "Price (Incl. GST)": gst_price,
                    "Price (Excl. GST)": base_price,
                    "Order Date": order_date,
                    "Invoice Date": invoice_date,
                    "Entry Date": entry_date,
                    "Source PDF": "",
                    "Action": ""
                })

    return seller_filename, rows


# -----------------------
# PDF Processor
# -----------------------
def process_pdfs(uploaded_files):
    entry_date = datetime.today().strftime("%d.%m.%Y")
    data = defaultdict(list)

    for uploaded in uploaded_files:
        with fitz.open(stream=uploaded.read(), filetype="pdf") as doc:
            for i in range(len(doc)):
                seller, rows = extract_from_page_text(doc.load_page(i).get_text(), entry_date)
                for r in rows:
                    r["Source PDF"] = uploaded.name
                    data[seller].append(r)

    seller_dfs = {}
    for seller, rows in data.items():
        df = pd.DataFrame(rows)

        df.drop_duplicates(
            subset=["Order ID", "SKU", "Size", "Qty", "Color", "AWB Number"],
            keep="first",
            inplace=True
        )

        df.insert(0, "S.No", range(1, len(df) + 1))
        seller_dfs[seller] = df

    return seller_dfs


# -----------------------
# Streamlit UI
# -----------------------
st.title("📦 PDF → Data (Meesho) — FINAL VERSION")

uploaded_files = st.file_uploader(
    "Upload Meesho PDF files",
    type=["pdf"],
    accept_multiple_files=True
)

if st.button("Process PDFs"):
    if not uploaded_files:
        st.warning("कृपया PDF upload करें")
    else:
        with st.spinner("Processing PDFs..."):
            seller_dfs = process_pdfs(uploaded_files)
            st.session_state["seller_dfs"] = seller_dfs
            st.success("Processing completed successfully")

if "seller_dfs" in st.session_state:
    for seller, df in st.session_state["seller_dfs"].items():
        st.subheader(f"{seller} ({len(df)} rows)")
        st.dataframe(df)

        excel_buf = io.BytesIO()
        df.to_excel(excel_buf, index=False)
        excel_buf.seek(0)

        st.download_button(
            f"⬇️ Download Excel - {seller}",
            excel_buf,
            file_name=f"{seller}.xlsx"
        )
