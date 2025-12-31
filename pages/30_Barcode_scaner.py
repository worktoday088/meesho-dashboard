import streamlit as st
import pandas as pd
import io
import time

# ---------------- CONFIG ----------------
st.set_page_config(
    page_title="Return Packet Scanner PRO",
    layout="wide",
    page_icon="📦"
)

st.title("📦 RETURN PACKET SCANNER – PRO")
st.markdown("### 🔺 High-Speed Warehouse Scanner | Duplicate Alert | Multi CSV Merge")

# ---------------- SESSION STATE ----------------
for k, v in {
    "scanned_counts": {},
    "data_loaded": False,
    "selected_courier": "ALL",
    "last_scan_time": 0,
    "AUTO_SCANNER_BOX": ""
}.items():
    st.session_state.setdefault(k, v)

# ---------------- COURIER MAP ----------------
COURIER_MAP = {
    "pocketship": "Valmo",
    "PocketShip": "Valmo"
}

def normalize_courier(name):
    if pd.isna(name):
        return "Unknown"
    return COURIER_MAP.get(str(name).strip().lower(), name)

# ---------------- CSV SAFE LOADER ----------------
def load_csv_clean(file, header_cols=None):
    raw = file.read().decode("utf-8", errors="ignore")
    lines = raw.split("\n")[6:]  # skip Meesho metadata
    df = pd.read_csv(io.StringIO("\n".join(lines)), engine="python", on_bad_lines="skip")

    if header_cols:
        df.columns = header_cols

    return df

# ---------------- UPLOAD SECTION ----------------
st.subheader("🔺 UPLOAD CSV FILES")
uploaded_files = st.file_uploader(
    "Select one or more CSV files",
    type=["csv"],
    accept_multiple_files=True
)

if uploaded_files and not st.session_state.data_loaded:
    with st.spinner("🔄 Loading & merging files..."):
        master_df = None
        master_headers = None

        for i, file in enumerate(uploaded_files):
            df = load_csv_clean(file, master_headers)
            if i == 0:
                master_headers = df.columns
                master_df = df
            else:
                master_df = pd.concat([master_df, df], ignore_index=True)

        # Detect columns
        courier_col = next(c for c in master_df.columns if "courier" in c.lower())
        awb_col = next(c for c in master_df.columns if "awb" in c.lower())

        master_df[courier_col] = master_df[courier_col].apply(normalize_courier)
        master_df[awb_col] = master_df[awb_col].astype(str).str.strip()

        unique_df = master_df.drop_duplicates(subset=[awb_col])

        st.session_state.update({
            "df": master_df,
            "unique_df": unique_df,
            "courier_col": courier_col,
            "awb_col": awb_col,
            "data_loaded": True
        })
        st.rerun()

# ---------------- MAIN DASHBOARD ----------------
if st.session_state.data_loaded:
    df = st.session_state.unique_df
    courier_col = st.session_state.courier_col
    awb_col = st.session_state.awb_col

    couriers = sorted(df[courier_col].unique())

    col1, col2 = st.columns([1, 2])
    with col1:
        selected = st.selectbox(
            "🎯 Select Courier",
            ["ALL"] + couriers
        )
        st.session_state.selected_courier = selected

    filtered = df if selected == "ALL" else df[df[courier_col] == selected]

    total = len(filtered)
    scanned = len([a for a in st.session_state.scanned_counts if a in filtered[awb_col].str.upper().values])

    with col2:
        st.metric("📦 TOTAL", total)
        st.metric("✅ SCANNED", scanned)
        st.metric("❌ PENDING", total - scanned)

    st.markdown("---")

    # ---------------- SCANNER ----------------
    st.subheader("🔦 AUTO SCAN AREA")

    awb_input = st.text_input(
        "SCAN AWB HERE",
        key="AUTO_SCANNER_BOX",
        placeholder="Scanner input auto...",
    )

    now = time.time()
    if awb_input and now - st.session_state.last_scan_time > 0.4:
        awb = awb_input.strip().upper()
        all_awbs = filtered[awb_col].str.upper()

        if awb in all_awbs.values:
            if awb in st.session_state.scanned_counts:
                st.warning(f"⚠ DUPLICATE SCAN | {awb}")
                st.session_state.scanned_counts[awb] += 1
            else:
                courier = filtered[all_awbs == awb][courier_col].iloc[0]
                st.success(f"✅ {courier} | {awb}")
                st.session_state.scanned_counts[awb] = 1
        else:
            st.error(f"❌ NOT FOUND | {awb}")

        st.session_state.AUTO_SCANNER_BOX = ""
        st.session_state.last_scan_time = now
        st.rerun()

    st.markdown("---")

    # ---------------- RESULTS ----------------
    colA, colB = st.columns(2)

    with colA:
        st.subheader("✅ SCANNED LIST")
        data = []
        for awb, cnt in st.session_state.scanned_counts.items():
            row = df[df[awb_col].str.upper() == awb]
            if not row.empty:
                data.append([row[courier_col].iloc[0], awb, cnt])
        st.dataframe(pd.DataFrame(data, columns=["Courier", "AWB", "Count"]))

    with colB:
        st.subheader("❌ MISSING")
        missing = set(filtered[awb_col].str.upper()) - set(st.session_state.scanned_counts)
        st.dataframe(filtered[filtered[awb_col].str.upper().isin(missing)][[courier_col, awb_col]])

    # ---------------- CONTROLS ----------------
    if st.button("🔄 RESET ALL"):
        st.session_state.scanned_counts = {}
        st.rerun()

else:
    st.info("⬆ Upload CSV files to start")
