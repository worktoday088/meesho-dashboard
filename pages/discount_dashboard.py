import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF

st.set_page_config(page_title="Supplier Discount Analysis", layout="wide")

st.title("Supplier Discount Analysis Dashboard")

st.markdown(
    """
    Yeh dashboard **Supplier Listed Price (Incl. GST + Commission)** 
    aur **Supplier Discounted Price (Incl GST and Commision)** ke beech ka 
    discount amount (₹) aur discount percentage (%) calculate karke dikhata hai.
    """
)

# Column names
COL_REASON = "Reason for Credit Entry"
COL_SUBORDER = "Sub Order No"
COL_ORDER_DATE = "Order Date"
COL_PRODUCT = "Product Name"
COL_SKU = "SKU"
COL_LIST_PRICE = "Supplier Listed Price (Incl. GST + Commission)"
COL_DISC_PRICE = "Supplier Discounted Price (Incl GST and Commision)"

required_cols = [
    COL_REASON,
    COL_SUBORDER,
    COL_ORDER_DATE,
    COL_PRODUCT,
    COL_SKU,
    COL_LIST_PRICE,
    COL_DISC_PRICE,
]

# 1) CSV Upload & Merge
with st.expander("📂 CSV Upload & Merge (Multiple Files)", expanded=True):
    uploaded_files = st.file_uploader(
        "Ek ya multiple Orders CSV files upload karein",
        type=["csv"],
        accept_multiple_files=True,
    )

    merged_df = None
    if uploaded_files:
        dfs = []
        base_cols = None

        for file in uploaded_files:
            try:
                temp_df = pd.read_csv(file)
            except pd.errors.EmptyDataError:
                st.warning(f"{file.name} khali hai (no data), isko skip kiya gaya.")
                continue
            except Exception as e:
                st.error(f"{file.name} read karne mein error: {e}")
                continue

            if temp_df.empty:
                st.warning(f"{file.name} me koi rows nahin mili, isko skip kiya gaya.")
                continue

            if base_cols is None:
                base_cols = temp_df.columns
                dfs.append(temp_df)
            else:
                common_cols = [c for c in base_cols if c in temp_df.columns]
                temp_df = temp_df[common_cols]
                temp_df = temp_df.reindex(columns=base_cols)
                dfs.append(temp_df)

        if dfs:
            merged_df = pd.concat(dfs, ignore_index=True)
            st.success(
                f"Total {len(uploaded_files)} file(s) merge ho gayi hain. "
                f"Total rows: {len(merged_df)}"
            )
        else:
            st.error("Koi valid CSV data merge nahin ho paya.")
    else:
        st.info("Yahan se apni CSV files select karke merge kar sakte hain.")

if merged_df is None:
    st.stop()

# 2) Cleaning + Discount
df = merged_df.copy()

missing = [c for c in required_cols if c not in df.columns]
if missing:
    st.error(f"In columns ki zarurat hai, lekin file(s) me nahin mile: {missing}")
    st.stop()

df[COL_ORDER_DATE] = pd.to_datetime(df[COL_ORDER_DATE], errors="coerce")
df[COL_LIST_PRICE] = pd.to_numeric(df[COL_LIST_PRICE], errors="coerce")
df[COL_DISC_PRICE] = pd.to_numeric(df[COL_DISC_PRICE], errors="coerce")

df["Discount Amount (₹)"] = df[COL_LIST_PRICE] - df[COL_DISC_PRICE]
df["Discount %"] = (df["Discount Amount (₹)"] / df[COL_LIST_PRICE].replace(0, pd.NA)) * 100

# 3) Global Filters
st.sidebar.header("Global Filters")

min_date = df[COL_ORDER_DATE].min()
max_date = df[COL_ORDER_DATE].max()

if pd.isna(min_date) or pd.isna(max_date):
    start_date = end_date = datetime.today().date()
else:
    start_date, end_date = st.sidebar.date_input(
        "Order Date Range (Global)",
        value=(min_date.date(), max_date.date()),
    )

if isinstance(start_date, datetime):
    start_date = start_date.date()
if isinstance(end_date, datetime):
    end_date = end_date.date()

all_skus = sorted(df[COL_SKU].dropna().unique().tolist())
selected_skus = st.sidebar.multiselect(
    "SKU filter (Global, optional)", options=all_skus, default=all_skus
)

mask_date_global = (df[COL_ORDER_DATE].dt.date >= start_date) & (
    df[COL_ORDER_DATE].dt.date <= end_date
)
mask_sku_global = df[COL_SKU].isin(selected_skus) if selected_skus else True

gdf = df[mask_date_global & mask_sku_global].copy()
gdf = gdf[gdf["Discount Amount (₹)"] > 0]

# 4) Detailed Filters (multi-select)
st.subheader("Detailed Discount Table Filters")

col_f1, col_f2 = st.columns(2)

with col_f1:
    reasons_list = sorted(gdf[COL_REASON].dropna().unique().tolist())
    selected_reasons = st.multiselect(
        "Reason for Credit Entry (multi-select)",
        options=["All"] + reasons_list,
        default=["All"],
    )

with col_f2:
    available_dates = sorted(gdf[COL_ORDER_DATE].dropna().dt.date.unique().tolist())
    date_labels = [d.strftime("%Y-%m-%d") for d in available_dates]
    selected_dates = st.multiselect(
        "Order Date (Specific, multi-select)",
        options=["All"] + date_labels,
        default=["All"],
    )

fdf = gdf.copy()

if "All" not in selected_reasons:
    fdf = fdf[fdf[COL_REASON].isin(selected_reasons)]

if "All" not in selected_dates:
    sel_dates_obj = [datetime.strptime(d, "%Y-%m-%d").date() for d in selected_dates]
    fdf = fdf[fdf[COL_ORDER_DATE].dt.date.isin(sel_dates_obj)]

# 5) Summary (bigger cards, based on fdf)
st.markdown("## Filtered Data Summary")

total_discount_amount = fdf["Discount Amount (₹)"].sum(skipna=True)
avg_discount_percent = fdf["Discount %"].mean(skipna=True)
total_rows_with_discount = len(fdf)
total_orders = len(fdf[COL_SUBORDER].dropna().unique())
total_revenue_after_discount = fdf[COL_DISC_PRICE].sum(skipna=True)

c1, c2, c3, c4, c5 = st.columns(5)

card_style = "background-color:{bg};padding:16px;border-radius:10px;text-align:center;"

with c1:
    st.markdown(
        f"""
        <div style="{card_style.format(bg='#e3f2fd')}">
        <div style="font-size:14px;color:#555;">Total Orders (Filtered)</div>
        <div style="font-size:26px;font-weight:bold;color:#0d47a1;">{total_orders}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c2:
    st.markdown(
        f"""
        <div style="{card_style.format(bg='#fce4ec')}">
        <div style="font-size:14px;color:#555;">Total Discount Amount</div>
        <div style="font-size:26px;font-weight:bold;color:#880e4f;">{total_discount_amount:,.2f}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c3:
    st.markdown(
        f"""
        <div style="{card_style.format(bg='#e8f5e9')}">
        <div style="font-size:14px;color:#555;">Average Discount (%)</div>
        <div style="font-size:26px;font-weight:bold;color:#1b5e20;">{avg_discount_percent:,.2f}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c4:
    st.markdown(
        f"""
        <div style="{card_style.format(bg='#fff3e0')}">
        <div style="font-size:14px;color:#555;">Rows With Discount</div>
        <div style="font-size:26px;font-weight:bold;color:#e65100;">{int(total_rows_with_discount)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c5:
    st.markdown(
        f"""
        <div style="{card_style.format(bg='#ede7f6')}">
        <div style="font-size:14px;color:#555;">Revenue After Discount</div>
        <div style="font-size:26px;font-weight:bold;color:#311b92;">{total_revenue_after_discount:,.2f}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("---")

# 6) Detailed Table (screen par full info, PDF ke liye alag selection)
st.subheader("Detailed Discount Table (Only Discount > 0)")

fdf["Discount Amount (₹)"] = fdf["Discount Amount (₹)"].round(2)
fdf["Discount %"] = fdf["Discount %"].round(2)

display_cols_full = [
    COL_REASON,
    COL_SUBORDER,
    COL_ORDER_DATE,
    COL_SKU,
    COL_PRODUCT,
    COL_LIST_PRICE,
    COL_DISC_PRICE,
    "Discount Amount (₹)",
    "Discount %",
]

st.dataframe(fdf[display_cols_full], use_container_width=True)

# 7) PDF – sirf Sub Order No, SKU, Discount %
st.markdown("---")
st.subheader("Download PDF (Sub Order No, SKU, Discount %)")

pdf_cols = [COL_SUBORDER, COL_SKU, "Discount %"]
pdf_df = fdf[pdf_cols].copy()

def df_to_pdf(dataframe: pd.DataFrame) -> bytes:
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=10)

    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 12, "Discount Report (Sub Order, SKU, Discount %)", ln=1, align="C")

    pdf.set_font("Arial", size=10)

    max_width = 280
    num_cols = len(dataframe.columns)
    col_width = max_width / num_cols

    # Header
    for col in dataframe.columns:
        header_txt = str(col).replace("₹", "INR")
        pdf.cell(col_width, 10, header_txt[:30], border=1, align="C")
    pdf.ln(10)

    # Rows
    for _, row in dataframe.iterrows():
        for col in dataframe.columns:
            txt = str(row[col]).replace("₹", "INR")
            if len(txt) > 30:
                txt = txt[:27] + "..."
            pdf.cell(col_width, 8, txt, border=1)
        pdf.ln(8)

    out = pdf.output(dest="S")
    if isinstance(out, str):
        return out.encode("latin-1", "ignore")
    return out

if not pdf_df.empty:
    pdf_bytes = df_to_pdf(pdf_df)
    st.download_button(
        label="Download PDF (Sub Order No, SKU, Discount %)",
        data=pdf_bytes,
        file_name=f"discount_table_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        mime="application/pdf",
    )
else:
    st.info("Current filters ke hisaab se koi discounted rows nahin mili.")
