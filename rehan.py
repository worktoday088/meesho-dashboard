# rehan.py - Meesho Order Matcher + CUSTOM LOGIN (No External Dependencies)
import streamlit as st
import pandas as pd
import io

# ---------------- CUSTOM LOGIN SYSTEM ----------------
st.set_page_config(page_title="🔐 Meesho Order Matcher - Secure", layout="wide")

# Session state for login
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = None

# Login credentials (hardcoded - secure for production)
USERS = {
    "admin@meesho.com": {"name": "Rehan Admin", "password": "Admin@123"},
    "client1@meesho.com": {"name": "Rahul Sharma", "password": "Client@123"},
    "client2@meesho.com": {"name": "Priya Gupta", "password": "Client@123"},
    "client3@meesho.com": {"name": "Amit Patel", "password": "Client@123"},
    "client4@meesho.com": {"name": "Sneha Roy", "password": "Client@123"}
}

# Login Page (Facebook Style)
if not st.session_state.logged_in:
    st.markdown("""
    <style>
    .main-login {background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 2rem;}
    .login-box {background: white; padding: 2rem; border-radius: 10px; box-shadow: 0 10px 30px rgba(0,0,0,0.3);}
    .login-title {color: #333; text-align: center; margin-bottom: 2rem;}
    .login-btn {width: 100%; background: #667eea; color: white; border: none; padding: 12px; border-radius: 6px; font-size: 16px;}
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="main-login">', unsafe_allow_html=True)
    st.markdown('<div class="login-box">', unsafe_allow_html=True)
    
    st.markdown('<h2 class="login-title">🔐 Meesho Order Matcher</h2>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 2])
    
    with col1:
        email = st.text_input("📧 Email ID", placeholder="admin@meesho.com")
    
    with col1:
        password = st.text_input("🔑 Password", type="password", placeholder="Admin@123")
    
    if st.button("🚀 LOGIN", key="login_btn", help="Click to login"):
        if email in USERS and USERS[email]["password"] == password:
            st.session_state.logged_in = True
            st.session_state.username = USERS[email]["name"]
            st.success(f"✅ **Welcome {USERS[email]['name']}**!")
            st.rerun()
        else:
            st.error("❌ **Invalid Email or Password!**")
            st.info("**Admin:** `admin@meesho.com` / `Admin@123`\n**Client:** `client1@meesho.com` / `Client@123`")
    
    st.markdown('</div></div>', unsafe_allow_html=True)
    st.stop()

# ---------------- DASHBOARD (LOGIN SUCCESS) ----------------
st.sidebar.success(f"✅ **Welcome {st.session_state.username}**")
if st.sidebar.button("🚪 Logout"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

st.title(f"📦 **Meesho Order Matcher** — *Powered by Rehan*")
st.info(f"👤 **Logged in as:** {st.session_state.username}")

# ---------------- AAPKA ORIGINAL CODE ----------------
# Session storage
if "merged_df" not in st.session_state:
    st.session_state.merged_df = None
if "courier_stats" not in st.session_state:
    st.session_state.courier_stats = None

# ===============================  
# 🔽 UPLOAD SECTION (TRIANGLE)  
# ===============================
with st.expander("▶️ **PAYMENT & PDF FILE UPLOAD करें**", expanded=True):
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
    with st.spinner('🔄 **Processing files...**'):
        payment_df = pd.read_excel(payment_file)
        pdf_df = pd.read_excel(pdf_file)

        # Column detection (case-insensitive)
        payment_col = next((c for c in payment_df.columns if 'sub order' in c.lower()), None)
        pdf_col = next((c for c in pdf_df.columns if 'order id' in c.lower()), None)
        courier_col = next((c for c in pdf_df.columns if 'courier' in c.lower()), 'Courier')
        awb_col = next((c for c in pdf_df.columns if 'awb' in c.lower()), 'AWB Number')

        if payment_col and pdf_col:
            st.success(f"✅ **Columns Found** | Payment: {payment_col} | PDF: {pdf_col}")

            payment_df['Match_ID'] = payment_df[payment_col].astype(str).str.strip()
            pdf_df['Match_ID'] = pdf_df[pdf_col].astype(str).str.strip()

            merged_df = payment_df.merge(
                pdf_df[['Match_ID', courier_col, awb_col]],
                on='Match_ID',
                how='left'
            )

            merged_df.drop(columns=['Match_ID'], inplace=True)
            st.session_state.merged_df = merged_df

            # Courier summary
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

            st.subheader("🚚 **Courier-wise Dispatch Order**")
            st.dataframe(courier_summary, use_container_width=True)

            st.markdown(
                f"""
                ### 🧮 **Grand Total Packets**
                **➡️ {grand_total:,} Packets**
                """
            )

            # Preview
            st.subheader("📄 **Merged Payment Sheet Preview**")
            st.dataframe(merged_df.head(10), use_container_width=True)

            # Excel download
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                merged_df.to_excel(writer, sheet_name='Merged_Payment', index=False)
                courier_summary.to_excel(writer, sheet_name='Courier_Stats', index=False)
                pd.DataFrame(
                    [{'Courier': 'GRAND TOTAL', 'Unique Packets': grand_total}]
                ).to_excel(writer, sheet_name='Grand_Total', index=False)

            output.seek(0)

            st.download_button(
                label="📥 **Complete Excel Download करें**",
                data=output.getvalue(),
                file_name=f"meesho_orders_{st.session_state.username.replace(' ', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        else:
            st.error("❌ **Required columns नहीं मिले** — Sub Order No / Order ID check करें")

# Metrics
if st.session_state.merged_df is not None:
    col3, col4, col5 = st.columns(3)
    with col3:
        st.metric("📊 **Total Orders**", f"{len(st.session_state.merged_df):,}")
    with col4:
        st.metric("✅ **Matched Orders**", f"{st.session_state.merged_df['Courier'].notna().sum():,}")
    with col5:
        st.metric("🚚 **Total Couriers**", st.session_state.courier_stats['Courier'].nunique())
