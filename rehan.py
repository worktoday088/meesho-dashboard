import streamlit as st
import hashlib

# =========================
# PAGE CONFIG (SIDEBAR LOCK)
# =========================
st.set_page_config(
    page_title="Meesho Order Matcher",
    layout="wide",
    initial_sidebar_state="collapsed"  # 🔒 login se pehle sidebar band
)

# =========================
# SESSION STATE
# =========================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "user_role" not in st.session_state:
    st.session_state.user_role = None

# =========================
# PASSWORD HASH FUNCTION
# =========================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# =========================
# USERS DATABASE (STATIC)
# =========================
USERS = {
    "admin@meesho.com": {
        "password": hash_password("Admin@123"),
        "role": "admin"
    },
    "client1@meesho.com": {
        "password": hash_password("Client@123"),
        "role": "client"
    },
    "client2@meesho.com": {
        "password": hash_password("Client@123"),
        "role": "client"
    },
    "client3@meesho.com": {
        "password": hash_password("Client@123"),
        "role": "client"
    },
    "client4@meesho.com": {
        "password": hash_password("Client@123"),
        "role": "client"
    },
    "client5@meesho.com": {
        "password": hash_password("Client@123"),
        "role": "client"
    }
}

# =========================
# LOGIN PAGE
# =========================
def login_page():
    st.markdown(
        """
        <style>
        .login-box {
            max-width: 400px;
            margin: auto;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 0 25px rgba(0,0,0,0.15);
            background-color: #ffffff;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    st.markdown("<br><br>", unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.markdown("## 🔐 Meesho Order Matcher")

        email = st.text_input("📧 Email ID")
        password = st.text_input("🔑 Password", type="password")

        if st.button("🚀 LOGIN"):
            if email in USERS and USERS[email]["password"] == hash_password(password):
                st.session_state.logged_in = True
                st.session_state.user_role = USERS[email]["role"]
                st.success("Login successful")
                st.rerun()
            else:
                st.error("Invalid Email or Password")

        st.markdown("</div>", unsafe_allow_html=True)

# =========================
# LOGIN CHECK (GLOBAL LOCK)
# =========================
if not st.session_state.logged_in:
    login_page()
    st.stop()  # 🔒 LOGIN KE BINA KUCHH BHI LOAD NAHI HOGA

# =========================
# SIDEBAR (AFTER LOGIN)
# =========================
st.sidebar.success("✅ Logged in")

if st.session_state.user_role == "admin":
    st.sidebar.info("👑 Role: Admin")
else:
    st.sidebar.info("👤 Role: Client")

if st.sidebar.button("🚪 Logout"):
    st.session_state.logged_in = False
    st.session_state.user_role = None
    st.rerun()

# =========================
# MAIN DASHBOARD HOME
# =========================
st.title("📊 Meesho Dashboard")
st.write("Login ke baad hi ye dashboard accessible hai.")

st.success("🎉 Sidebar + Pages ab fully protected hain")
