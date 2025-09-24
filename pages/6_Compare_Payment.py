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

st.set_page_config(page_title="PDF → Data (Meesho) — Merged", layout="wide")

# -----------------------
# Patterns & Regex
# -----------------------
size_pattern = r"(XS|S|M|L|XL|XXL|XXXL|FREE SIZE|24|26|28|30|32|34|36|38|40|42|44|46|48|50|6-7 Years|7-8 Years|8-9 Years|9-10 Years|10-11 Years|11-12 Years|12-13 Years|13-14 Years|14-15 Years|15-16 Years|16-17 Years|17-18 Years)"
awb_patterns = [
    r"\bVL\d{10,14}\b", r"\bSF\d{10,14}[A-Z]{2,3}\b", r"\b\d{14,16}\b", r"\b[A-Z0-9]{10,16}\b"
]
courier_regex = re.compile(
    r"(Valmo|Xpress\s*Bees|Delhivery|Shadowfax|Ecom\s*Express|DTDC|BlueDart|Bluedart|WowExpress|Wow\s*Express|India\s*Post|Speed\s*Post|EKART|Ekart|Amazon\s*Shipping)",
    re.IGNORECASE
)

# -----------------------
# Helper Functions
# -----------------------
def sanitize_sheet_name(name: str) -> str:
    s = re.sub(r'[\/*?:\[\]]', '_', (name or "UnknownSeller").strip().replace(" ", "_"))
    return s[:31] if s else "UnknownSeller"

def extract_from_page_text(text: str, entry_date: str):
    seller_block = re.search(r"If undelivered, return to:\s*\n([^\n]+)", text)
    seller = seller_block.group(1).strip() if seller_block else "UnknownSeller"
    seller_filename = sanitize_sheet_name(seller)
    courier_m = courier_regex.search(text)
    courier = courier_m.group(1).strip() if courier_m else "UnknownCourier"
    awb_number = next((m.group(0) for patt in awb_patterns if (m := re.search(patt, text))), "N/A")
    order_date = (m.group(1) if (m := re.search(r"Order Date\s+(\d{2}\.\d{2}\.\d{4})", text)) else "")
    invoice_date = (m.group(1) if (m := re.search(r"Invoice Date\s+(\d{2}\.\d{2}\.\d{4})", text)) else "")
    product_lines = re.compile(rf"(.+?)\s+{size_pattern}\s+(\d+)\s+(.+?)\s+(\d+_\d+)", re.MULTILINE).findall(text)
    
    rows = []
    for item in product_lines:
        sku, size, qty, color, order_id = (*item, "") if len(item) == 4 else item
        if len(item) not in [4, 5]: continue
        gst_price = (m.group(1) if (m := re.search(rf"{re.escape(order_id)}.*?Total\s+Rs\.\d+\.\d+\s+Rs\.(\d+\.\d+)", text, re.DOTALL)) else "")
        base_price = (m.group(1) if (m := re.search(rf"{re.escape(order_id)}.*?Taxable Value.*?Rs\.(\d+\.\d+)", text, re.DOTALL)) else "")
        rows.append({
            "Order ID": order_id, "SKU": sku.strip(), "Size": size.strip(), "Qty": qty.strip(),
            "Color": color.strip(), "Courier": courier, "AWB Number": awb_number,
            "Price (Incl. GST)": gst_price, "Price (Excl. GST)": base_price, "Order Date": order_date,
            "Invoice Date": invoice_date, "Entry Date": entry_date, "Source PDF": "", "Action": ""
        })
    if not rows and (po_m := re.search(r"Purchase Order No\.\s*(\d+)", text)):
        rows.append({
            "Order ID": po_m.group(1), "SKU": "", "Size": "", "Qty": "", "Color": "", "Courier": courier, 
            "AWB Number": awb_number, "Price (Incl. GST)": "", "Price (Excl. GST)": "",
            "Order Date": order_date, "Invoice Date": invoice_date, "Entry Date": entry_date, 
            "Source PDF": "", "Action": ""
        })
    return seller_filename, rows

def process_pdfs(uploaded_files, max_pages_per_pdf=0, strict_awb=False):
    entry_date = datetime.today().strftime("%d.%m.%Y")
    data = defaultdict(list)
    total_pages_read = 0
    for uploaded in uploaded_files:
        try:
            with fitz.open(stream=uploaded.read(), filetype="pdf") as doc:
                pages_to_read = len(doc) if max_pages_per_pdf <= 0 else min(len(doc), max_pages_per_pdf)
                for i in range(pages_to_read):
                    seller_filename, rows = extract_from_page_text(doc.load_page(i).get_text(), entry_date)
                    rows = [r for r in rows if not strict_awb or r.get("AWB Number", "N/A") != "N/A"]
                    for r in rows:
                        r["Source PDF"] = uploaded.name
                        data[seller_filename].append(r)
                total_pages_read += pages_to_read
        except Exception as e: st.error(f"Error reading {uploaded.name}: {e}")
    
    seller_dfs, duplicates_report = {}, {}
    for seller, rows in data.items():
        df = pd.DataFrame(rows)
        duplicates_report[seller] = len(df)
        df.drop_duplicates(subset=["Order ID", "SKU", "Size", "Qty", "Color", "AWB Number"], keep="first", inplace=True)
        duplicates_report[seller] -= len(df)
        
        # --- FIX for TypeError: unhashable type: 'Series' ---
        df['AWB_ffill'] = df['AWB Number'].replace('', pd.NA).ffill()
        is_first = ~df.duplicated(subset=['AWB_ffill'], keep='first')
        df.drop(columns=['AWB_ffill'], inplace=True)
        
        df['Courier'] = df['Courier'].where(is_first, '')
        df['AWB Number'] = df['AWB Number'].where(is_first, '')
        
        df.insert(0, "S.No", range(1, len(df) + 1))
        seller_dfs[seller] = df
    return seller_dfs, total_pages_read, duplicates_report

def create_courier_summary(df: pd.DataFrame) -> pd.DataFrame:
    df_copy = df.copy()
    df_copy["Courier"].fillna("Unknown", inplace=True)
    summary = df_copy[df_copy['AWB Number'].notna() & (df_copy['AWB Number'] != '')].groupby("Courier").size().reset_index(name="Count")
    summary = summary[summary["Courier"] != ""].sort_values("Count", ascending=False)
    total = pd.DataFrame({"Courier": ["Grand Total"], "Count": [summary["Count"].sum()]})
    return pd.concat([summary, total], ignore_index=True)

def create_report_pdf_bytes(summary_dfs: dict) -> bytes:
    pdf_buffer = io.BytesIO()
    with PdfPages(pdf_buffer) as pdf:
        for title, df in summary_dfs.items():
            fig, ax = plt.subplots(figsize=(8.27, 11.69))
            ax.axis('tight'); ax.axis('off')
            table = ax.table(cellText=df.values, colLabels=df.columns, loc='center', cellLoc='center')
            table.auto_set_font_size(False); table.set_fontsize(10); table.scale(1.2, 1.2)
            plt.title(title, fontsize=16, pad=20)
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
    pdf_buffer.seek(0)
    return pdf_buffer.read()

def create_zip_of_excels(seller_dfs: dict):
    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for seller, df in seller_dfs.items():
            excel_bytes = io.BytesIO()
            with pd.ExcelWriter(excel_bytes, engine="xlsxwriter") as writer:
                df.to_excel(writer, sheet_name=sanitize_sheet_name(seller), index=False)
            zf.writestr(f"{seller}.xlsx", excel_bytes.getvalue())
    mem_zip.seek(0)
    return mem_zip.read()

def create_excel_report_bytes(seller_dfs: dict, selected_sellers: list):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        if len(selected_sellers) > 1:
            merged_df = pd.concat([seller_dfs[s] for s in selected_sellers], ignore_index=True)
            create_courier_summary(merged_df).to_excel(writer, sheet_name="Merged_Summary", index=False)
        for seller in selected_sellers:
            seller_df = seller_dfs[seller]
            create_courier_summary(seller_df).to_excel(writer, sheet_name=f"{sanitize_sheet_name(seller)}_Summary", index=False)
            seller_df.to_excel(writer, sheet_name=sanitize_sheet_name(seller), index=False)
    output.seek(0)
    return output.read()

# -----------------------
# Streamlit UI
# -----------------------
st.title("PDF → Data (Meesho) — Merged Reports")

with st.sidebar:
    st.header("Upload & Settings")
    uploaded_files = st.file_uploader("Select PDF files", type=["pdf"], accept_multiple_files=True)
    max_pages = st.slider("Max pages per PDF (0 = all)", 0, 50, 0, 1)
    strict_awb = st.checkbox("Strict AWB (skip pages without AWB)", False)
    
    if st.button("Process Files"):
        if uploaded_files:
            with st.spinner("Processing PDFs..."):
                s_dfs, total, dups = process_pdfs(uploaded_files, max_pages, strict_awb)
                st.session_state.update({"seller_dfs": s_dfs, "total_pages": total, "duplicates_report": dups})
                st.success(f"Processing done — pages read: {total}, sellers found: {len(s_dfs)}")
        else:
            st.warning("पहले PDF फाइल(s) अपलोड करें।")
            
    # --- FIX for Clear Button ---
    if st.button("Clear stored data (reset)"):
        st.session_state.clear()
        st.rerun()

if "seller_dfs" in st.session_state and st.session_state["seller_dfs"]:
    seller_dfs = st.session_state["seller_dfs"]
    st.header("Courier Summary & Reports")
    selected_sellers = st.multiselect("Choose sellers to view/merge", list(seller_dfs.keys()), default=list(seller_dfs.keys()) if len(seller_dfs) == 1 else [])

    if selected_sellers:
        summary_tables_for_pdf = {}
        if len(selected_sellers) > 1:
            st.subheader("Merged Courier Summary")
            merged_df = pd.concat([seller_dfs[s] for s in selected_sellers], ignore_index=True)
            merged_summary = create_courier_summary(merged_df)
            summary_tables_for_pdf["Merged Courier Summary"] = merged_summary
            st.table(merged_summary)
            
        for seller in selected_sellers:
            st.subheader(f"Courier Summary for: {seller}")
            seller_summary = create_courier_summary(seller_dfs[seller])
            summary_tables_for_pdf[f"Summary for {seller}"] = seller_summary
            st.table(seller_summary)
            
        st.header("Download Reports")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.download_button("📄 Download PDF Report", create_report_pdf_bytes(summary_tables_for_pdf), f"Courier_Report_{datetime.now().strftime('%Y%m%d')}.pdf", "application/pdf")
        with col2:
            st.download_button("📊 Download Excel Report", create_excel_report_bytes(seller_dfs, selected_sellers), f"Excel_Report_{datetime.now().strftime('%Y%m%d')}.xlsx")
        with col3:
            st.download_button("🗂️ Download All Sellers (ZIP)", create_zip_of_excels(seller_dfs), f"All_Sellers_{datetime.now().strftime('%Y%m%d')}.zip", "application/zip")
        
        st.header("Data Previews (for selected sellers)")
        for seller in selected_sellers:
            with st.expander(f"{seller} — {len(seller_dfs[seller])} rows"):
                st.dataframe(seller_dfs[seller])
    else:
        st.info("Select one or more sellers from the dropdown above to see their data.")
