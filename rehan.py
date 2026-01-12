import streamlit as st
import streamlit_authenticator as stauth
import yaml
from pathlib import Path
import time

# === LOGIN SYSTEM ===
st.set_page_config(page_title="Meesho Dashboard", layout="wide")

config_file = Path("config.yaml")
if not config_file.exists():
    st.error("🔒 Config file missing! Contact Admin.")
    st.stop()

with open(config_file) as file:
    config = yaml.safe_load(file)

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days'],
    config['preauthorized']
)

name, authentication_status, username = authenticator.login(
    '🔐 Meesho Dashboard - Secure Login', 
    'main',
    location='sidebar'
)

if authentication_status == False:
    st.error('❌ Username/password galat hai!')
    st.stop()
    
elif authentication_status == None:
    st.markdown("""
    # 🎯 Meesho Dashboard
    ### 🔐 Authorized Access Only
    **Admin:** admin@meesho.com / Admin@123  
    **Clients:** client1@meesho.com / Client@123
    """)
    st.stop()

# ✅ LOGIN SUCCESS
st.sidebar.success(f'✅ Welcome **{name}**')
st.sidebar.markdown("---")
authenticator.logout('🚪 Logout', 'sidebar')

# === AAPKA ORIGINAL DASHBOARD CODE YAHAN ===
st.title(f"📊 Meesho Dashboard - {name}")
# Sidebar navigation + pages code...
