import streamlit as st

# डमी लॉगिन डिटेल्स आप अपनी जरूरत के हिसाब से बदल सकते हैं
user_data = {
    "sarita.light@gmail.com": "sarita@123",
    "megethalf@gmail.com": "meget@456"
}

def login_page():
    st.title("लॉगिन पेज")
    email = st.text_input("Gmail आईडी", placeholder="आपकी Gmail आईडी डालें")
    password = st.text_input("पासवर्ड", type="password", placeholder="पासवर्ड डालें")
    login_btn = st.button("लॉगिन करें")

    if login_btn:
        if email in user_data and user_data[email] == password:
            st.success("लॉगिन सफल!")
            st.session_state['logged_in'] = True
        else:
            st.error("गलत आईडी या पासवर्ड!")

# मुख्य पेज (लॉगिन के बाद दिखाने के लिए)
def main_page():
    st.title("आपका वेबसाइट लोगो पेज")
    st.write("यह मुख्य पेज है, जहां सिर्फ सफल लॉगिन के बाद ही यूज़र पहुंच सकता है।")

# सेशन स्टेट का इस्तेमाल करके लॉगिन को ट्रैक करें
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    login_page()
else:
    main_page()
    if st.button("लॉगआउट"):
        st.session_state['logged_in'] = False
