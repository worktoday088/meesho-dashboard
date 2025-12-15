import streamlit as st
import pandas as pd
import io
from datetime import datetime

st.set_page_config(page_title="Discount Analysis Dashboard", layout="wide")

st.title("Supplier Discount Analysis Dashboard")

st.markdown(
    """
    Yeh dashboard aapke **Supplier Listed Price (Incl. GST + Commission)** 
    aur **Supplier Discounted Price (Incl GST and Commision)** ke beech ka 
    discount amount (₹) aur discount percentage (%) calculate karta hai.
    """
)

# File upload
uploaded_file = st.file_uploader("Apna Orders CSV file upload karein", type=["csv"])

if uploaded_file is not None:
    # Read CSV
    try:
        df = pd.read_csv(uploaded_file)
    except Exception as e:
        st.error(f"CSV read karne mein error: {e}")
        st.stop()

    # Column name mapping (exact from your file)
    COL_ORDER_DATE = "Order Date"
    COL_SKU = "SKU"
    COL_PRODUCT = "Product Name"
    COL_LIST_PRICE = "Supplier Listed Price (Incl. GST + Commission)"
    COL_DISC_PRICE = "Supplier Discounted Price (Incl GST and Commision)"

    # Basic validation
    required_cols = [COL_ORDER_DATE, COL_SKU, COL_PRODUCT, COL_LIST_PRICE, COL_DISC_PRICE]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        st.error(f"Yeh columns file mein nahin mile: {missing}")
        st.stop()

    # Convert Order Date to datetime
    df[COL_ORDER_DATE] = pd.to_datetime(df[COL_ORDER_DATE], errors="coerce")

    # Numeric conversion for prices
    df[COL_LIST_PRICE] = pd.to_numeric(df[COL_LIST_PRICE], errors="coerce")
    df[COL_DISC_PRICE] = pd.to_numeric(df[COL_DISC_PRICE], errors="coerce")

    # Calculate discount amount and percentage
    df["Discount Amount (₹)"] = df[COL_LIST_PRICE] - df[COL_DISC_PRICE]
    # Handle division by zero / NaN
    df["Discount %"] = (df["Discount Amount (₹)"] / df[COL_LIST_PRICE].replace(0, pd.NA)) * 100

    # Sidebar filters
    st.sidebar.header("Filters")

    # Date range filter
    min_date = df[COL_ORDER_DATE].min()
    max_date = df[COL_ORDER_DATE].max()

    start_date, end_date = st.sidebar.date_input(
        "Order Date Range",
        value=(min_date.date() if pd.notna(min_date) else datetime.today().date(),
               max_date.date() if pd.notna(max_date) else datetime.today().date()),
    )

    if isinstance(start_date, datetime):
        start_date = start_date.date()
    if isinstance(end_date, datetime):
        end_date = end_date.date()

    # SKU filter
    all_skus = sorted(df[COL_SKU].dropna().unique().tolist())
    selected_skus = st.sidebar.multiselect(
        "SKU filter (optional)", options=all_skus, default=all_skus
    )

    # Apply filters
    mask_date = (df[COL_ORDER_DATE].dt.date >= start_date) & (df[COL_ORDER_DATE].dt.date <= end_date)
    mask_sku = df[COL_SKU].isin(selected_skus) if selected_skus else True

    filtered_df = df[mask_date & mask_sku].copy()

    st.subheader("Filtered Data Summary")

    # Summary metrics
    total_discount_amount = filtered_df["Discount Amount (₹)"].sum(skipna=True)
    avg_discount_percent = filtered_df["Discount %"].mean(skipna=True)
    total_rows_with_discount = (filtered_df["Discount Amount (₹)"] > 0).sum()
    total_orders = len(filtered_df)
    total_revenue_after_discount = filtered_df[COL_DISC_PRICE].sum(skipna=True)

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Orders (Filtered)", total_orders)
    col2.metric("Total Discount Amount (₹)", f"{total_discount_amount:,.2f}")
    col3.metric("Average Discount (%)", f"{avg_discount_percent:,.2f}")
    col4.metric("Items With Discount", int(total_rows_with_discount))
    col5.metric("Revenue After Discount (₹)", f"{total_revenue_after_discount:,.2f}")

    st.markdown("---")
    st.subheader("Detailed Discount Table")

    # Display table with selected columns
    display_cols = [
        COL_ORDER_DATE,
        COL_SKU,
        COL_PRODUCT,
        COL_LIST_PRICE,
        COL_DISC_PRICE,
        "Discount Amount (₹)",
        "Discount %",
    ]

    # Round percentage for display
    filtered_df["Discount %"] = filtered_df["Discount %"].round(2)
    filtered_df["Discount Amount (₹)"] = filtered_df["Discount Amount (₹)"].round(2)

    st.dataframe(filtered_df[display_cols], use_container_width=True)

    st.markdown("---")
    st.subheader("Download Summary as CSV (PDF ke liye input)")

    # Export-friendly summary CSV (aap isko baad mein PDF me convert kar sakte hain)
    export_df = filtered_df[display_cols].copy()

    csv_buffer = io.StringIO()
    export_df.to_csv(csv_buffer, index=False)
    csv_bytes = csv_buffer.getvalue().encode("utf-8")

    st.download_button(
        label="Download Summary CSV",
        data=csv_bytes,
        file_name=f"discount_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
    )

else:
    st.info("Kripya sabse pehle apna Orders CSV upload karein.")
