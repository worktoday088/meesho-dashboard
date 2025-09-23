import streamlit as st
import pandas as pd
from io import BytesIO

def generate_reports_and_stats(old_df, new_df):
    """
    यह फ़ंक्शन डेटा का विश्लेषण करता है, रिपोर्ट बनाता है, और डैशबोर्ड के लिए
    प्रमुख मैट्रिक्स की गणना करता है।
    """
    unique_col = "Sub Order No"
    status_col = "Live Order Status"
    amount_col = "Final Settlement Amount"

    # डेटा की सफाई
    old_df[amount_col] = pd.to_numeric(old_df[amount_col].astype(str).str.replace(',', '').str.strip(), errors='coerce').fillna(0)
    new_df[amount_col] = pd.to_numeric(new_df[amount_col].astype(str).str.replace(',', '').str.strip(), errors='coerce').fillna(0)

    # डेटा को मर्ज करना
    merged_df = pd.merge(
        old_df[[unique_col, status_col, amount_col]].rename(columns={status_col: "Old Status", amount_col: "Old Amount"}),
        new_df[[unique_col, status_col, amount_col]].rename(columns={status_col: "New Status", amount_col: "New Amount"}),
        on=unique_col, how="outer"
    ).fillna(0)

    # विश्लेषण
    merged_df["Difference (Old - New)"] = merged_df["Old Amount"] - merged_df["New Amount"]
    merged_df["Remarks"] = "Present in Both"
    merged_df.loc[merged_df["Old Status"] == 0, "Remarks"] = "New Order"
    merged_df.loc[merged_df["New Status"] == 0, "Remarks"] = "Payout Settlement Amount"
    
    main_data = merged_df[merged_df[unique_col] != 0].copy()
    
    # --- डैशबोर्ड मैट्रिक्स की गणना ---
    payout_df = main_data[main_data["Remarks"] == "Payout Settlement Amount"].copy()
    new_order_df = main_data[main_data["Remarks"] == "New Order"].copy()
    
    # 'Present in Both' से समायोजन राशि की गणना
    present_in_both_df = main_data[(main_data["Remarks"] == "Present in Both") & (main_data["Difference (Old - New)"] != 0)].copy()
    discrepancy_sum = present_in_both_df['Difference (Old - New)'].sum()

    old_data_count = len(old_df)
    old_data_sum = old_df[amount_col].sum()

    payout_count = len(payout_df)
    payout_sum = payout_df["Difference (Old - New)"].sum()

    remaining_count = old_data_count - payout_count
    remaining_sum = old_data_sum - payout_sum
    
    new_orders_count = len(new_order_df)
    new_orders_sum = new_order_df["New Amount"].sum()
    
    final_total_count = remaining_count + new_orders_count
    final_total_sum = remaining_sum + new_orders_sum
    
    # अंतिम शुद्ध देय राशि
    clean_final_due = final_total_sum - discrepancy_sum
    
    stats = {
        "old_count": old_data_count, "old_sum": old_data_sum,
        "payout_count": payout_count, "payout_sum": payout_sum,
        "remaining_count": remaining_count, "remaining_sum": remaining_sum,
        "new_count": new_orders_count, "new_sum": new_orders_sum,
        "final_count": final_total_count, "final_sum": final_total_sum,
        "discrepancy_sum": discrepancy_sum,
        "clean_final_due": clean_final_due,
    }

    reports = {
        "Full Report": main_data, "Discrepancy_Details": present_in_both_df,
        "Old Data Sheet": old_df, "New Data Sheet": new_df
    }
    
    return reports, stats

def to_excel(reports):
    """एक्सेल फ़ाइल बनाने के लिए फ़ंक्शन"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet_name, df in reports.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    return output.getvalue()

# --- Streamlit App UI ---
st.set_page_config(page_title="Advanced Payment Reconciliation Tool", layout="wide")
st.title("📊 Advanced Payment Reconciliation Tool")

# --- फ़ाइल अपलोड सेक्शन ---
with st.expander("📂 Step 1: Upload Your Files", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        old_file = st.file_uploader("1. Upload Old Data File ('Order Payments' शीट)", type=["xlsx"])
    with col2:
        new_file = st.file_uploader("2. Upload New Data File ('Order Payments' शीट)", type=["xlsx"])

if old_file and new_file:
    try:
        old_df = pd.read_excel(old_file, sheet_name="Order Payments", dtype=str)
        new_df = pd.read_excel(new_file, sheet_name="Order Payments", dtype=str)
        st.success("✅ फ़ाइलें सफलतापूर्वक अपलोड हो गईं! रिपोर्ट तैयार है...")

        reports, stats = generate_reports_and_stats(old_df, new_df)
        excel_data = to_excel(reports)

        # --- Key Metrics Dashboard ---
        st.header("📊 Key Metrics Dashboard")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.subheader("पुराना हिसाब")
            st.metric("कुल पुराने ऑर्डर", f"{stats['old_count']}", f"₹{stats['old_sum']:,.2f}")
            st.metric("भुगतान हुए ऑर्डर", f"- {stats['payout_count']}", f"- ₹{stats['payout_sum']:,.2f}", delta_color="inverse")
            st.metric("बकाया पुराने ऑर्डर", f"{stats['remaining_count']}", f"₹{stats['remaining_sum']:,.2f}")
        
        with col2:
            st.subheader("नया हिसाब")
            st.metric("कुल नए ऑर्डर", f"{stats['new_count']}", f"₹{stats['new_sum']:,.2f}")
        
        with col3:
            st.subheader("कुल बकाया")
            st.metric("कुल बकाया ऑर्डर", f"{stats['final_count']}", f"₹{stats['final_sum']:,.2f}")

        with col4:
            st.subheader("अंतिम देय राशि")
            st.metric("अन्य समायोजन", f"- ₹{stats['discrepancy_sum']:,.2f}", delta_color="inverse")
            st.metric("अंतिम शुद्ध देय राशि", f"₹{stats['clean_final_due']:,.2f}")

        # --- समायोजन विवरण तालिका ---
        st.header("📋 समायोजन विवरण (Discrepancy Details)")
        discrepancy_table = reports['Discrepancy_Details'].copy()
        
        if not discrepancy_table.empty:
            grand_total_row = pd.DataFrame([{
                'Sub Order No': 'Grand Total',
                'Difference (Old - New)': discrepancy_table['Difference (Old - New)'].sum()
            }])
            discrepancy_table = pd.concat([discrepancy_table, grand_total_row], ignore_index=True)
            discrepancy_table.insert(0, 'S.No', range(1, len(discrepancy_table) + 1))
            st.dataframe(discrepancy_table.fillna(''))
        else:
            st.info("कोई समायोजन विवरण नहीं मिला।")

        # --- Download Button ---
        st.header("📥 Download Full Data")
        st.download_button(
            label="Download Complete Report (Excel)",
            data=excel_data,
            file_name="complete_reconciliation_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"एक त्रुटि हुई: {e}. कृपया अपनी फ़ाइलों, शीट के नाम ('Order Payments') और कॉलम के नाम की जाँच करें।")
else:
    st.info("👆 तुलना शुरू करने के लिए कृपया पुरानी और नई दोनों डेटा फ़ाइलें अपलोड करें।")

