import streamlit as st
import pandas as pd
from io import BytesIO
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
# यह वह लाइन है जो पहले मिसिंग थी और अब जोड़ दी गई है
from reportlab.platypus.tables import TableStyle

def generate_reports_and_stats(old_df, new_df, payout_df):
    """
    यह फ़ंक्शन तीन डेटाफ़्रेम लेता है, विश्लेषण करता है, और सभी रिपोर्ट तथा
    डैशबोर्ड मैट्रिक्स की गणना करता है।
    """
    unique_col = "Sub Order No"
    status_col = "Live Order Status"
    amount_col = "Final Settlement Amount"

    # --- डेटा की सफाई ---
    for df in [old_df, new_df, payout_df]:
        if amount_col in df.columns:
            df[amount_col] = pd.to_numeric(df[amount_col].astype(str).str.replace(',', '').str.strip(), errors='coerce').fillna(0)

    # --- 1. Full Report (पुरानी vs नई फ़ाइल) ---
    full_report_df = pd.merge(
        old_df[[unique_col, status_col, amount_col]].rename(columns={status_col: "Old Status", amount_col: "Old Amount"}),
        new_df[[unique_col, status_col, amount_col]].rename(columns={status_col: "New Status", amount_col: "New Amount"}),
        on=unique_col, how="outer"
    ).fillna(0)
    full_report_df["Difference (Old - New)"] = full_report_df["Old Amount"] - full_report_df["New Amount"]
    full_report_df["Remarks"] = "Present in Both"
    full_report_df.loc[full_report_df["Old Status"] == 0, "Remarks"] = "New Order"
    
    # --- 2. समायोजन विवरण (Old vs Payout) ---
    discrepancy_payout_df = pd.merge(
        old_df[[unique_col, status_col, amount_col]].rename(columns={status_col: "Old Status", amount_col: "Old Amount"}),
        payout_df[[unique_col, status_col, amount_col]].rename(columns={status_col: "Payout Status", amount_col: "Payout Amount"}),
        on=unique_col, how="inner" # सिर्फ कॉमन ऑर्डर
    )
    discrepancy_payout_df["Difference (Old - Payout)"] = discrepancy_payout_df["Old Amount"] - discrepancy_payout_df["Payout Amount"]
    discrepancy_payout_details = discrepancy_payout_df[discrepancy_payout_df["Difference (Old - Payout)"].abs() > 0.01].copy()

    # --- 3. समायोजन विवरण (Old vs New) ---
    discrepancy_new_df = full_report_df[full_report_df["Remarks"] == "Present in Both"].copy()
    discrepancy_new_details = discrepancy_new_df[discrepancy_new_df["Difference (Old - New)"].abs() > 0.01].copy()
    
    # --- 4. डैशबोर्ड मैट्रिक्स की गणना ---
    payout_count = len(payout_df)
    payout_sum = payout_df[amount_col].sum() if amount_col in payout_df.columns else 0

    new_order_df = full_report_df[full_report_df["Remarks"] == "New Order"]
    new_orders_count = len(new_order_df)
    new_orders_sum = new_order_df["New Amount"].sum()
    
    old_data_count = len(old_df)
    old_data_sum = old_df[amount_col].sum() if amount_col in old_df.columns else 0
    
    remaining_count = old_data_count - payout_count
    remaining_sum = old_data_sum - payout_sum

    final_total_count = remaining_count + new_orders_count
    final_total_sum = remaining_sum + new_orders_sum

    # अन्य समायोजन = (Old vs Payout का अंतर) + (Old vs New का अंतर)
    sum_payout_diff = discrepancy_payout_details['Difference (Old - Payout)'].sum()
    sum_new_diff = discrepancy_new_details['Difference (Old - New)'].sum()
    other_adjustment = sum_payout_diff + sum_new_diff
    
    clean_final_due = final_total_sum - other_adjustment

    stats = {
        "old_count": old_data_count, "old_sum": old_data_sum, "payout_count": payout_count, "payout_sum": payout_sum,
        "remaining_count": remaining_count, "remaining_sum": remaining_sum, "new_count": new_orders_count, "new_sum": new_orders_sum,
        "final_count": final_total_count, "final_sum": final_total_sum, "other_adjustment": other_adjustment, "clean_final_due": clean_final_due
    }

    reports = {
        "Full Report": full_report_df, "Discrepancy (Old vs Payout)": discrepancy_payout_details, "Discrepancy (Old vs New)": discrepancy_new_details,
        "Old Data Sheet": old_df, "New Data Sheet": new_df, "Payout Data Sheet": payout_df
    }
    
    return reports, stats

def to_excel(reports):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet_name, df in reports.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    return output.getvalue()

def generate_pdf(df, title):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    elements = [Paragraph(title, getSampleStyleSheet()['h1'])]
    data = [df.columns.to_list()] + df.values.tolist()
    table = Table(data)
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ])
    table.setStyle(style)
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer

# --- Streamlit App UI ---
st.set_page_config(page_title="Reconciliation Tool", layout="wide")
st.title("📊 Reconciliation Tool")

with st.expander("📂 Step 1: Upload Files", expanded=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        old_file = st.file_uploader("1. Upload Old Data File", type=["xlsx"])
    with col2:
        new_file = st.file_uploader("2. Upload New Data File", type=["xlsx"])
    with col3:
        payout_file = st.file_uploader("3. Upload Payout Data File", type=["xlsx"])

if old_file and new_file and payout_file:
    try:
        old_df = pd.read_excel(old_file, sheet_name=0, dtype=str)
        new_df = pd.read_excel(new_file, sheet_name=0, dtype=str)
        payout_df = pd.read_excel(payout_file, sheet_name=0, dtype=str)
        
        st.success("✅ तीनों फ़ाइलें सफलतापूर्वक अपलोड हो गईं! रिपोर्ट तैयार है...")

        reports, stats = generate_reports_and_stats(old_df, new_df, payout_df)
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
            st.metric("अन्य समायोजन", f"- ₹{stats['other_adjustment']:,.2f}", delta_color="inverse")
            st.metric("अंतिम शुद्ध देय राशि", f"₹{stats['clean_final_due']:,.2f}")

        # --- समायोजन विवरण (Old vs Payout) ---
        st.header("📋 समायोजन विवरण (Old vs Payout)")
        discrepancy_payout_table = reports['Discrepancy (Old vs Payout)'].copy()
        if not discrepancy_payout_table.empty:
            grand_total_row = pd.DataFrame([{'Sub Order No': 'Grand Total', 'Difference (Old - Payout)': discrepancy_payout_table['Difference (Old - Payout)'].sum()}])
            table_for_display = pd.concat([discrepancy_payout_table, grand_total_row], ignore_index=True).fillna('')
            table_for_display.insert(0, 'S.No', range(1, len(table_for_display) + 1))
            pdf_buffer = generate_pdf(table_for_display, "समायोजन विवरण (Old vs Payout)")
            st.download_button("📄 Download as PDF (Old vs Payout)", pdf_buffer, "discrepancy_payout.pdf", "application/pdf", key="payout_pdf")
            st.dataframe(table_for_display)
        else:
            st.info("पुरानी और भुगतान फ़ाइलों के बीच कोई राशि का अंतर नहीं मिला।")
        
        # --- समायोजन विवरण (Old vs New) ---
        st.header("📋 समायोजन विवरण (Old vs New)")
        discrepancy_new_table = reports['Discrepancy (Old vs New)'].copy()
        if not discrepancy_new_table.empty:
            grand_total_row_new = pd.DataFrame([{'Sub Order No': 'Grand Total', 'Difference (Old - New)': discrepancy_new_table['Difference (Old - New)'].sum()}])
            table_for_display_new = pd.concat([discrepancy_new_table, grand_total_row_new], ignore_index=True).fillna('')
            table_for_display_new.insert(0, 'S.No', range(1, len(table_for_display_new) + 1))
            pdf_buffer_new = generate_pdf(table_for_display_new, "समायोजन विवरण (Old vs New)")
            st.download_button("📄 Download as PDF (Old vs New)", pdf_buffer_new, "discrepancy_new.pdf", "application/pdf", key="new_pdf")
            st.dataframe(table_for_display_new)
        else:
            st.info("पुरानी और नई फ़ाइलों में कॉमन ऑर्डर्स के बीच कोई राशि का अंतर नहीं मिला।")

        # --- Excel Download ---
        st.header("📥 Download Full Report Pack")
        st.download_button("Download All Sheets (Excel)", excel_data, "complete_report_pack.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        
    except Exception as e:
        st.error(f"एक त्रुटि हुई: {e}. कृपया अपनी फ़ाइलों और कॉलम के नामों की जाँच करें।")
else:
    st.info("👆 कृपया विश्लेषण शुरू करने के लिए तीनों डेटा फ़ाइलें अपलोड करें।")

