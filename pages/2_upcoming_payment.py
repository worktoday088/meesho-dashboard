import streamlit as st
import pandas as pd
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet

# 🔐 LOGIN CHECK (YAHI ADD KARNA HAI)
if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
    st.warning("🔒 Please login first")
    st.stop()

# -------------------------------
# Function to generate Payment Date Summary
# -------------------------------
def generate_summary(order_df, adcost_df):
    summary_list = []
    
    order_df['Payment Date Parsed'] = pd.to_datetime(order_df['Payment Date'], errors="coerce").dt.date
    adcost_df['Deduction Date'] = pd.to_datetime(adcost_df['Deduction Date'], errors="coerce").dt.date
    
    order_df['Payment Date Clean'] = order_df.apply(
        lambda row: row['Payment Date Parsed'] if pd.notnull(row['Payment Date Parsed']) else str(row['Payment Date']),
        axis=1
    )
    
    for date, group in order_df.groupby('Payment Date Clean'):
        status_summary = group.groupby('Live Order Status').agg(
            Status_Count=('Live Order Status', 'count'),
            Sum_Amount=('Final Settlement Amount', 'sum')
        ).reset_index()

        total_count = status_summary['Status_Count'].sum()
        total_amount = status_summary['Sum_Amount'].sum()
        
        ads_cost = 0
        try:
            parsed_date = pd.to_datetime(date, errors="coerce")
            if pd.notnull(parsed_date):
                ads_cost = adcost_df.loc[adcost_df['Deduction Date'] == parsed_date.date(), 'Total Ads Cost'].sum()
        except:
            ads_cost = 0
        
        ads_cost = abs(ads_cost)
        payable = total_amount - ads_cost

        summary_list.append({
            "Payment Date": date,
            "Summary": status_summary,
            "Total Count": total_count,
            "Total Amount": total_amount,
            "Ads Cost": ads_cost,
            "Payable Amount": payable
        })
    
    return summary_list


# -------------------------------
# Function to generate Dispatch Date Summary
# -------------------------------
def generate_dispatch_summary(order_df):
    summary_list = []
    
    order_df['Dispatch Date Parsed'] = pd.to_datetime(order_df['Dispatch Date'], errors="coerce").dt.date
    order_df['Dispatch Date Clean'] = order_df.apply(
        lambda row: row['Dispatch Date Parsed'] if pd.notnull(row['Dispatch Date Parsed']) else str(row['Dispatch Date']),
        axis=1
    )
    
    for date, group in order_df.groupby('Dispatch Date Clean'):
        status_summary = group.groupby('Live Order Status').agg(
            Status_Count=('Live Order Status', 'count'),
            Sum_Amount=('Final Settlement Amount', 'sum')
        ).reset_index()
        
        total_count = status_summary['Status_Count'].sum()
        total_amount = status_summary['Sum_Amount'].sum()
        
        summary_list.append({
            "Dispatch Date": date,
            "Summary": status_summary,
            "Total Count": total_count,
            "Total Amount": total_amount
        })
    
    return summary_list


# -------------------------------
# Function to export PDF
# -------------------------------
def export_pdf(summary_list, dispatch_summary_list, scheduled_amount, total_ads_cost, net_scheduled_payment, unscheduled_amount, upcoming_payment):
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4))
    elements = []
    styles = getSampleStyleSheet()

    # Add Summary Boxes in PDF
    elements.append(Paragraph("📊 Upcoming Payments Summary", styles['Heading1']))
    data = [
        ["Scheduled Payments", f"₹ {scheduled_amount:,.0f}"],
        ["Ads Cost", f"₹ {total_ads_cost:,.0f}"],
        ["Net Scheduled", f"₹ {net_scheduled_payment:,.0f}"],
        ["Unscheduled", f"₹ {unscheduled_amount:,.0f}"],
        ["Upcoming Payment", f"₹ {upcoming_payment:,.0f}"],
    ]
    table = Table(data)
    table.setStyle(TableStyle([('GRID',(0,0),(-1,-1),1,colors.black)]))
    elements.append(table)
    elements.append(Spacer(1, 20))

    # Payment Date Tables
    elements.append(Paragraph("📅 Payment Date Wise Summary", styles['Heading1']))
    for item in summary_list:
        elements.append(Paragraph(f"Payment Date: {item['Payment Date']}", styles['Heading2']))
        df = item["Summary"].copy()
        df.loc[len(df)] = ["Total", item["Total Count"], item["Total Amount"]]
        df.loc[len(df)] = ["Ads Cost", "", -item["Ads Cost"]]
        df.loc[len(df)] = ["Payable Amount", "", item["Payable Amount"]]
        df["Sum_Amount"] = df["Sum_Amount"].apply(lambda x: f"₹ {x:,.0f}")
        data = [df.columns.tolist()] + df.values.tolist()
        t = Table(data, repeatRows=1)
        t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),1,colors.black)]))
        elements.append(t)
        elements.append(Spacer(1, 12))

    # Dispatch Date Tables
    elements.append(Paragraph("🚚 Dispatch Date Wise Summary", styles['Heading1']))
    for item in dispatch_summary_list:
        elements.append(Paragraph(f"Dispatch Date: {item['Dispatch Date']}", styles['Heading2']))
        df = item["Summary"].copy()
        df.loc[len(df)] = ["Total", item["Total Count"], item["Total Amount"]]
        df["Sum_Amount"] = df["Sum_Amount"].apply(lambda x: f"₹ {x:,.0f}")
        data = [df.columns.tolist()] + df.values.tolist()
        t = Table(data, repeatRows=1)
        t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),1,colors.black)]))
        elements.append(t)
        elements.append(Spacer(1, 12))
    
    doc.build(elements)
    output.seek(0)
    return output


# -------------------------------
# Streamlit App
# -------------------------------
st.set_page_config(layout="wide")
st.title("📊 Order Settlement Dashboard")

with st.sidebar:
    st.header("⚙️ Controls")
    uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

if uploaded_file:
    xls = pd.ExcelFile(uploaded_file)
    order_df = pd.read_excel(xls, sheet_name="Order Payments")
    adcost_df = pd.read_excel(xls, sheet_name="Ads Cost")

    # Dashboard Calculations
    order_df['Payment Date Parsed'] = pd.to_datetime(order_df['Payment Date'], errors="coerce").dt.date
    scheduled_df = order_df[order_df['Payment Date Parsed'].notna()]
    unscheduled_df = order_df[order_df['Payment Date Parsed'].isna()]

    scheduled_amount = scheduled_df['Final Settlement Amount'].sum()
    total_ads_cost = abs(adcost_df['Total Ads Cost'].sum())
    net_scheduled_payment = scheduled_amount - total_ads_cost
    unscheduled_amount = unscheduled_df['Final Settlement Amount'].sum()
    upcoming_payment = net_scheduled_payment + unscheduled_amount

    # Dashboard Cards
    col1, col2, col3, col4, col5 = st.columns(5)
    def make_card(title, value, color):
        return f"""
        <div style="background-color:{color};padding:15px;border-radius:15px;text-align:center;box-shadow:2px 2px 10px rgba(0,0,0,0.1);">
            <h4 style="margin:0;">{title}</h4>
            <h2 style="margin:0;color:black;">₹ {value:,.0f}</h2>
        </div>
        """
    with col1: st.markdown(make_card("📅 Scheduled Payments", scheduled_amount, "#d1f2eb"), unsafe_allow_html=True)
    with col2: st.markdown(make_card("📉 Ads Cost", total_ads_cost, "#f9e79f"), unsafe_allow_html=True)
    with col3: st.markdown(make_card("✅ Net Scheduled", net_scheduled_payment, "#abebc6"), unsafe_allow_html=True)
    with col4: st.markdown(make_card("📦 Unscheduled", unscheduled_amount, "#f5b7b1"), unsafe_allow_html=True)
    with col5: st.markdown(make_card("🚀 Upcoming Payment", upcoming_payment, "#d2b4de"), unsafe_allow_html=True)

    # Payment Date Summary
    st.header("📅 Payment Date Wise Summary")
    summary_list = generate_summary(order_df, adcost_df)
    for item in summary_list:
        st.subheader(f"📅 Payment Date: {item['Payment Date']}")
        df = item["Summary"].copy()
        df.loc[len(df)] = ["Total", item["Total Count"], item["Total Amount"]]
        df.loc[len(df)] = ["Ads Cost", "", -item["Ads Cost"]]
        df.loc[len(df)] = ["Payable Amount", "", item["Payable Amount"]]
        df["Sum_Amount"] = df["Sum_Amount"].apply(lambda x: f"₹ {x:,.0f}")
        st.dataframe(df, use_container_width=True)

    # Dispatch Date Summary
    st.header("🚚 Dispatch Date Wise Summary")
    dispatch_summary_list = generate_dispatch_summary(order_df)
    for item in dispatch_summary_list:
        st.subheader(f"🚚 Dispatch Date: {item['Dispatch Date']}")
        df = item["Summary"].copy()
        df.loc[len(df)] = ["Total", item["Total Count"], item["Total Amount"]]
        df["Sum_Amount"] = df["Sum_Amount"].apply(lambda x: f"₹ {x:,.0f}")
        st.dataframe(df, use_container_width=True)

    # Raw Data Viewer
    st.header("📑 Full Raw Data Viewer")
    with st.expander("📂 View / Hide Full Data Table", expanded=False):
        order_df['Dispatch Date Parsed'] = pd.to_datetime(order_df['Dispatch Date'], errors="coerce").dt.date
        available_dates = sorted(order_df['Dispatch Date Parsed'].dropna().unique())
        selected_dates = st.multiselect("📅 Select Dispatch Date(s)", options=available_dates, default=available_dates)
        if selected_dates:
            filtered_df = order_df[order_df['Dispatch Date Parsed'].isin(selected_dates)]
        else:
            filtered_df = order_df.copy()
        st.write(f"Showing {len(filtered_df)} rows")
        st.dataframe(filtered_df, use_container_width=True)

        # Download Original Excel Data
        original_output = BytesIO()
        filtered_df.to_excel(original_output, index=False, engine="openpyxl")
        original_output.seek(0)
        st.download_button("📥 Download Original Excel Data", data=original_output,
                           file_name="Original_Data.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # Download Full PDF Report
    pdf_data = export_pdf(summary_list, dispatch_summary_list, scheduled_amount, total_ads_cost, net_scheduled_payment, unscheduled_amount, upcoming_payment)
    st.download_button("📥 Download Full PDF Report", data=pdf_data, file_name="Full_Report.pdf", mime="application/pdf")

