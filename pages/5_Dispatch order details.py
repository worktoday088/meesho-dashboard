import streamlit as st
import pandas as pd
import io

# Page config
st.set_page_config(page_title="Meesho Order Matcher", layout="wide")

# Session storage
if "merged_df" not in st.session_state:
    st.session_state.merged_df = None
if "courier_stats" not in st.session_state:
    st.session_state.courier_stats = None

# ===============================
# 🔽 UPLOAD SECTION (TRIANGLE)
# ===============================
with st.expander("▶️ PAYMENT & PDF FILE UPLOAD करें", expanded=True):
    col1, col2 = st.columns(2)

    with col1:
        payment_file = st.file_uploader(
            "PAYMENT SHEET अपलोड करें (Sub Order No वाला)",
            type=['xlsx', 'xls'],
            key="payment"
        )

    with col2:
        pdf_file = st.file_uploader(
            "PDF SHEET अपलोड करें (Order ID वाला)",
            type=['xlsx', 'xls'],
            key="pdf"
        )

# ===============================
# PROCESSING
# ===============================
if payment_file is not None and pdf_file is not None:

    payment_df = pd.read_excel(payment_file)
    pdf_df = pd.read_excel(pdf_file)

    # Column detection (case-insensitive)
    payment_col = next((c for c in payment_df.columns if 'sub order' in c.lower()), None)
    pdf_col = next((c for c in pdf_df.columns if 'order id' in c.lower()), None)
    courier_col = next((c for c in pdf_df.columns if 'courier' in c.lower()), 'Courier')
    awb_col = next((c for c in pdf_df.columns if 'awb' in c.lower()), 'AWB Number')

    if payment_col and pdf_col:
        st.success(f"Columns Found ✔️ Payment: {payment_col} | PDF: {pdf_col}")

        payment_df['Match_ID'] = payment_df[payment_col].astype(str).str.strip()
        pdf_df['Match_ID'] = pdf_df[pdf_col].astype(str).str.strip()

        merged_df = payment_df.merge(
            pdf_df[['Match_ID', courier_col, awb_col]],
            on='Match_ID',
            how='left'
        )

        merged_df.drop(columns=['Match_ID'], inplace=True)
        st.session_state.merged_df = merged_df

        # ===============================
        # 📊 COURIER SUMMARY (TOP)
        # ===============================
        courier_summary = (
            merged_df
            .dropna(subset=[courier_col, awb_col])
            .groupby(courier_col)[awb_col]
            .nunique()
            .reset_index()
            .rename(columns={awb_col: 'Unique Packets'})
        )

        grand_total = courier_summary['Unique Packets'].sum()

        st.session_state.courier_stats = courier_summary

        st.subheader("🚚 Courier-wise Dispatch order")
        st.dataframe(courier_summary, use_container_width=True)

        st.markdown(
            f"""
            ### 🧮 **Grand Total Packets**
            **➡️ {grand_total}**
            """
        )

        # ===============================
        # 🔍 PREVIEW
        # ===============================
        st.subheader("📄 Merged Payment Sheet Preview")
        st.dataframe(merged_df.head(10), use_container_width=True)

        # ===============================
        # 📥 EXCEL DOWNLOAD
        # ===============================
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            merged_df.to_excel(writer, sheet_name='Merged_Payment', index=False)
            courier_summary.to_excel(writer, sheet_name='Courier_Stats', index=False)
            pd.DataFrame(
                [{'Courier': 'GRAND TOTAL', 'Unique Packets': grand_total}]
            ).to_excel(writer, sheet_name='Grand_Total', index=False)

        output.seek(0)

        st.download_button(
            label="📥 Complete Excel Download करें",
            data=output.getvalue(),
            file_name="merged_orders_with_courier.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    else:
        st.error("❌ Required columns नहीं मिले — Sub Order No / Order ID check करें")

# ===============================
# 📌 METRICS
# ===============================
if st.session_state.merged_df is not None:
    col3, col4, col5 = st.columns(3)

    with col3:
        st.metric("Total Orders", len(st.session_state.merged_df))

    with col4:
        st.metric(
            "Matched Orders",
            st.session_state.merged_df['Courier'].notna().sum()
        )

    with col5:
        st.metric(
            "Total Couriers",
            st.session_state.courier_stats['Courier'].nunique()
        )
