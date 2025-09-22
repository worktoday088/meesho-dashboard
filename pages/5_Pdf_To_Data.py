import streamlit as st
import fitz  # PyMuPDF
import re
import pandas as pd
from datetime import datetime
from collections import defaultdict
import io
import zipfile

st.set_page_config(page_title="PDF → Data (Meesho) — Updated", layout="wide")

# -----------------------
# Patterns & Regex
# -----------------------
size_pattern = r"(XS|S|M|L|XL|XXL|XXXL|FREE SIZE|24|26|28|30|32|34|36|38|40|42|44|46|48|50|6-7 Years|7-8 Years|8-9 Years|9-10 Years|10-11 Years|11-12 Years|12-13 Years|13-14 Years|14-15 Years|15-16 Years|16-17 Years|17-18 Years)"

awb_patterns = [
    r"\bVL\d{10,14}\b",        # Valmo
    r"\bSF\d{10,14}[A-Z]{2,3}\b",  # Shadowfax
    r"\b\d{14,16}\b",         # Delhivery & XpressBees
    r"\b[A-Z0-9]{10,16}\b"    # generic fallback
]

courier_regex = re.compile(
    r"(Valmo|Xpress\s*Bees|Delhivery|Shadowfax|Ecom\s*Express|DTDC|BlueDart|Bluedart|WowExpress|Wow\s*Express|India\s*Post|Speed\s*Post|EKART|Ekart|Amazon\s*Shipping)",
    re.IGNORECASE
)

# -----------------------
# Helper Functions
# -----------------------
def sanitize_sheet_name(name: str) -> str:
    s = re.sub(r'[\\/*?:\[\]]', '_', (name or "UnknownSeller").strip().replace(" ", "_"))
    return s[:31] if s else "UnknownSeller"

def extract_from_page_text(text: str, entry_date: str):
    seller_block = re.search(r"If undelivered, return to:\s*\n([^\n]+)", text)
    seller = seller_block.group(1).strip() if seller_block else "UnknownSeller"
    seller_filename = sanitize_sheet_name(seller)

    courier_m = courier_regex.search(text)
    courier = courier_m.group(1).strip() if courier_m else "UnknownCourier"

    awb_number = "N/A"
    for patt in awb_patterns:
        m = re.search(patt, text)
        if m:
            awb_number = m.group(0)
            break

    order_date_match = re.search(r"Order Date\s+(\d{2}\.\d{2}\.\d{4})", text)
    invoice_date_match = re.search(r"Invoice Date\s+(\d{2}\.\d{2}\.\d{4})", text)
    order_date = order_date_match.group(1) if order_date_match else ""
    invoice_date = invoice_date_match.group(1) if invoice_date_match else ""

    product_pattern = re.compile(rf"(.+?)\s+{size_pattern}\s+(\d+)\s+(.+?)\s+(\d+_\d+)", re.MULTILINE)
    product_lines = product_pattern.findall(text)

    rows = []
    for item in product_lines:
        if len(item) == 5:
            sku, size, qty, color, order_id = item
        elif len(item) == 4:
            sku, size, qty, order_id = item
            color = ""
        else:
            continue

        gst_m = re.search(rf"{re.escape(order_id)}.*?Total\s+Rs\.\d+\.\d+\s+Rs\.(\d+\.\d+)", text, re.DOTALL)
        gst_price = gst_m.group(1) if gst_m else ""
        base_m = re.search(rf"{re.escape(order_id)}.*?Taxable Value.*?Rs\.(\d+\.\d+)", text, re.DOTALL)
        base_price = base_m.group(1) if base_m else ""

        row = {
            "Order ID": order_id,
            "SKU": sku.strip(),
            "Size": size.strip(),
            "Qty": qty.strip(),
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
        }
        rows.append(row)

    if not rows:
        po_m = re.search(r"Purchase Order No\.\s*(\d+)", text)
        purchase_no = po_m.group(1) if po_m else ""
        rows.append({
            "Order ID": purchase_no or "",
            "SKU": "",
            "Size": "",
            "Qty": "",
            "Color": "",
            "Courier": courier,
            "AWB Number": awb_number,
            "Price (Incl. GST)": "",
            "Price (Excl. GST)": "",
            "Order Date": order_date,
            "Invoice Date": invoice_date,
            "Entry Date": entry_date,
            "Source PDF": "",
            "Action": ""
        })

    return seller_filename, rows

def process_pdfs(uploaded_files, max_pages_per_pdf=0, strict_awb=False):
    entry_date = datetime.today().strftime("%d.%m.%Y")
    data = defaultdict(list)
    total_pages_read = 0

    for uploaded in uploaded_files:
        file_bytes = uploaded.read()
        try:
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                n_pages = len(doc)
                pages_to_read = n_pages if max_pages_per_pdf <= 0 else min(n_pages, max_pages_per_pdf)
                for i in range(pages_to_read):
                    text = doc.load_page(i).get_text()
                    seller_filename, rows = extract_from_page_text(text, entry_date)
                    if strict_awb:
                        rows = [r for r in rows if r.get("AWB Number", "N/A") != "N/A"]
                    for r in rows:
                        r["Source PDF"] = uploaded.name
                        data[seller_filename].append(r)
                total_pages_read += pages_to_read
        except Exception as e:
            st.error(f"Error reading {uploaded.name}: {e}")

    seller_dfs = {}
    duplicates_report = {}
    for seller, rows in data.items():
        df = pd.DataFrame(rows)
        key_cols = ["Order ID", "SKU", "Size", "Qty", "Color", "AWB Number"]
        before = len(df)
        df = df.drop_duplicates(subset=[c for c in key_cols if c in df.columns], keep="first")
        after = len(df)
        removed = before - after
        duplicates_report[seller] = removed

        # Blank out duplicate Courier/AWB rows (packet-level logic)
        df["Courier"] = df.groupby("AWB Number")["Courier"].transform(lambda x: [x.iat[0]] + ["" for _ in range(len(x)-1)])
        df["AWB Number"] = df.groupby("AWB Number")["AWB Number"].transform(lambda x: [x.iat[0]] + ["" for _ in range(len(x)-1)])

        df.insert(0, "S.No", range(1, len(df) + 1))
        seller_dfs[seller] = df

    return seller_dfs, total_pages_read, duplicates_report

def to_excel_bytes(seller_dfs: dict):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        for seller, df in seller_dfs.items():
            df.to_excel(writer, sheet_name=sanitize_sheet_name(seller), index=False)
    output.seek(0)
    return output.read()

def create_zip_of_excels(seller_dfs: dict):
    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for seller, df in seller_dfs.items():
            excel_bytes = io.BytesIO()
            with pd.ExcelWriter(excel_bytes, engine="xlsxwriter") as writer:
                df.to_excel(writer, sheet_name=sanitize_sheet_name(seller), index=False)
            excel_bytes.seek(0)
            zf.writestr(f"{seller}.xlsx", excel_bytes.read())
    mem_zip.seek(0)
    return mem_zip.read()

# -----------------------
# Streamlit UI
# -----------------------
st.title("PDF → Data (Meesho) — Updated")

with st.sidebar:
    st.header("Upload & Settings")
    uploaded_files = st.file_uploader("Select PDF files (multiple OK)", type=["pdf"], accept_multiple_files=True)
    max_pages = st.slider("Max pages per PDF (0 = all)", 0, 50, 0, 1)
    strict_awb = st.checkbox("Strict AWB (skip pages without AWB)", False)
    process_btn = st.button("Process Files")
    clear_btn = st.button("Clear stored data (reset)")

if "seller_dfs" not in st.session_state:
    st.session_state["seller_dfs"] = {}
    st.session_state["total_pages"] = 0
    st.session_state["duplicates_report"] = {}

if clear_btn:
    st.session_state["seller_dfs"] = {}
    st.session_state["total_pages"] = 0
    st.session_state["duplicates_report"] = {}
    st.success("Session data cleared. Upload & Process files again.")

if process_btn:
    if not uploaded_files:
        st.warning("पहले PDF फाइल(s) अपलोड करें।")
    else:
        with st.spinner("Processing PDFs..."):
            seller_dfs, total_pages, duplicates_report = process_pdfs(uploaded_files, max_pages_per_pdf=max_pages, strict_awb=strict_awb)
        st.session_state["seller_dfs"] = seller_dfs
        st.session_state["total_pages"] = total_pages
        st.session_state["duplicates_report"] = duplicates_report
        st.success(f"Processing done — pages read: {total_pages}, sellers found: {len(seller_dfs)}")

if st.session_state["seller_dfs"]:
    seller_dfs = st.session_state["seller_dfs"]

    # PIVOT / CHART SECTION (Moved to top)
    st.header("Pivot / Chart (per-seller)")
    seller_list = list(seller_dfs.keys())
    if seller_list:
        sel = st.selectbox("Choose seller", seller_list)
        df_sel = seller_dfs[sel].copy()
        col_options = list(df_sel.columns)
        default_x = "Courier" if "Courier" in col_options else col_options[0]
        default_y = "AWB Number" if "AWB Number" in col_options else (col_options[1] if len(col_options) > 1 else col_options[0])
        colA, colB = st.columns(2)
        with colA:
            x_col = st.selectbox("Group by (X)", col_options, index=col_options.index(default_x))
        with colB:
            y_col = st.selectbox("Count column (Y)", col_options, index=col_options.index(default_y))

        pivot = df_sel.groupby([x_col, y_col]).size().reset_index(name="Count")
        agg_by_x = pivot.groupby(x_col)["Count"].sum().reset_index().sort_values("Count", ascending=False)

        # Grand Total excluding blank values
        non_blank_total = agg_by_x.loc[agg_by_x[x_col] != "", "Count"].sum()
        grand_total = pd.DataFrame({x_col: ["Grand Total"], "Count": [non_blank_total]})
        agg_with_total = pd.concat([agg_by_x, grand_total], ignore_index=True)

        st.subheader(f"{sel} — {x_col} summary")
        st.table(agg_with_total.head(200))
        st.bar_chart(data=agg_by_x.set_index(x_col)["Count"])

        buf_pivot = io.BytesIO()
        with pd.ExcelWriter(buf_pivot, engine='xlsxwriter') as writer:
            agg_with_total.to_excel(writer, sheet_name="Pivot", index=False)
        buf_pivot.seek(0)

        col1, col2, col3 = st.columns(3)
        with col1:
            excel_bytes = to_excel_bytes(seller_dfs)
            st.download_button("Download Combined Excel", data=excel_bytes, file_name=f"Meesho_Extract_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with col2:
            zip_bytes = create_zip_of_excels(seller_dfs)
            st.download_button("Download All Sellers (ZIP)", data=zip_bytes, file_name=f"PerSeller_Excels_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip", mime="application/zip")
        with col3:
            st.download_button("Download Pivot (this seller)", data=buf_pivot.read(), file_name=f"{sel}_pivot.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # Summary Metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Sellers", len(seller_dfs))
    col2.metric("Total pages read", st.session_state.get("total_pages", 0))
    total_rows = sum(len(df) for df in seller_dfs.values())
    col3.metric("Total rows (after dedup)", total_rows)

    if st.session_state.get("duplicates_report"):
        st.markdown("**Duplicates removed per seller:**")
        dup_df = pd.DataFrame([{"Seller": k, "Duplicates Removed": v} for k, v in st.session_state["duplicates_report"].items()])
        st.table(dup_df)

    # Per-seller preview
    for seller, df in seller_dfs.items():
        with st.expander(f"{seller} — {len(df)} rows"):
            st.write("Source PDFs:", ", ".join(df["Source PDF"].unique()) if "Source PDF" in df.columns else "")
            st.dataframe(df.head(200))
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name=sanitize_sheet_name(seller), index=False)
            buf.seek(0)
            st.download_button(f"Download Excel — {seller}.xlsx", data=buf.read(), file_name=f"{seller}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.caption("Updated: Duplicate courier entries blanked, Pivot moved on top with Grand Total (excluding blanks), buttons aligned.")