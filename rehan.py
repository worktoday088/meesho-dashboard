import streamlit as st
from users import USERS, hash_password

st.set_page_config(page_title="Meesho Dashboard", layout="wide")

# ---------- SESSION ----------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.role = None


# ---------- LOGIN ----------
def login():
    st.markdown("<h2 style='text-align:center'>🔐 Meesho Order Matcher</h2>", unsafe_allow_html=True)

    email = st.text_input("📧 Email ID")
    password = st.text_input("🔑 Password", type="password")

    if st.button("🚀 LOGIN"):
        if email in USERS:
            if USERS[email]["password"] == hash_password(password):
                st.session_state.logged_in = True
                st.session_state.user = email
                st.session_state.role = USERS[email]["role"]
                st.rerun()
            else:
                st.error("❌ Wrong password")
        else:
            st.error("❌ User not found")


# ---------- LOGOUT ----------
def logout():
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.role = None
    st.rerun()


# ---------- GATE ----------
if not st.session_state.logged_in:
    login()
    st.stop()


# ---------- SIDEBAR ----------
st.sidebar.success(f"👋 Welcome {st.session_state.user}")

if st.sidebar.button("🔓 Logout"):
    logout()


# ---------- DASHBOARD HOME ----------
st.title("📊 Meesho Analytics Dashboard")

if st.session_state.role == "admin":
    st.info("👑 Admin Access Enabled")
else:
    st.info("👤 Client Access Enabled")

st.write("⬅️ Sidebar se reports select karein")            st.dataframe(courier_summary, use_container_width=True)

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

