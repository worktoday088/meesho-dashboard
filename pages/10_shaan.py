import streamlit as st
import pandas as pd
import numpy as np
import re
import io

st.set_page_config(
    page_title="Merger + RCE Filter + 2‑pc/Zeme + Color Normalize + Pivot-like",
    layout="wide"
)
st.title("Orders Merger + Clean 2‑PC/Zeme + Color Normalization + Pivot-like")

uploaded_files = st.file_uploader(
    "Select multiple CSV/Excel files",
    type=["csv", "xls", "xlsx"],
    accept_multiple_files=True,
    key="uploader_final_v3"
)

REQUIRED_COLS = ["Reason for Credit Entry", "SKU", "Size", "Quantity"]

COLOR_MAP = {
    r"\bBLACK\b|BLK": "BLACK",
    r"\bGREY\b|\bGRAY\b": "GREY",
    r"\bBROWN\b": "BROWN",
    r"\bPINK\b": "PINK",
    r"\bBOTTLE\s*GREEN\b": "BOTTLE GREEN",
    r"\bWINE\b": "WINE",
    r"\bCREAM\b": "CREAM",
    r"\bPURPLE\b": "PURPLE",
    r"\bSKIN\b": "SKIN",
    r"\bBLUE\b": "BLUE",
    r"\bRED\b": "RED",
    r"\bWHITE\b": "WHITE",
    r"\bOLIVE\b": "OLIVE",
    r"\bBEIGE\b": "BEIGE",
    r"\bCOFFEE\b": "COFFEE",
    r"\bNAVY\b": "NAVY",
    r"\bMAROON\b": "MAROON",
    r"\bGREEN\b": "GREEN",
    r"\bORANGE\b": "ORANGE",
    r"\bYELLOW\b": "YELLOW"
}

def read_any(path_or_buffer, filename):
    if filename.lower().endswith(".csv"):
        df = pd.read_csv(path_or_buffer, dtype=str, keep_default_na=False, encoding_errors="ignore")
        return [(filename, df)]
    else:
        xls = pd.ExcelFile(path_or_buffer)
        return [(s, pd.read_excel(xls, sheet_name=s, dtype=str, keep_default_na=False))
                for s in xls.sheet_names]

def normalize_headers(df):
    df.columns = [str(c).strip() for c in df.columns]
    return df

def headers_match(row_values, master_header):
    return [str(v).strip() for v in row_values] == master_header

def do_merge(files):
    if not files: return None, None
    frames, master = [], None
    for uf in files:
        buf = io.BytesIO(uf.read())
        try:
            items = read_any(buf, uf.name)
        except Exception as e:
            st.error(f"Failed reading {uf.name}: {e}")
            continue
        for _, df in items:
            if df is None or df.empty: continue
            df = normalize_headers(df)
            if master is None: master = list(df.columns)
            if not df.empty and headers_match(df.iloc[0].tolist(), master):
                df = df.iloc[1:].reset_index(drop=True)
            common = [c for c in df.columns if c in master]
            aligned = pd.DataFrame(columns=master)
            if common: aligned[common] = df[common]
            frames.append(aligned.fillna(""))
    if not frames or master is None: return None, None
    return pd.concat(frames, ignore_index=True), master

def select_clean_cols(df):
    cols = [c for c in REQUIRED_COLS if c in df.columns]
    out = df[cols].copy()
    if "Quantity" in out.columns:
        out["Quantity"] = pd.to_numeric(out["Quantity"], errors="coerce").fillna(0)
    for c in ["Reason for Credit Entry","SKU","Size"]:
        if c in out.columns:
            out[c] = out[c].astype(str).str.strip()
    return out

def filter_rce_pending_rts(df):
    if "Reason for Credit Entry" not in df.columns:
        return df.iloc[0:0].copy()
    rce_std = df["Reason for Credit Entry"].astype(str).str.strip().str.upper().str.replace(" ", "_")
    mask = rce_std.isin(["PENDING","READY_TO_SHIP"])
    return df[mask].copy()

def normalize_sku_color(text: str) -> str:
    if not isinstance(text, str):
        return text
    s = text
    for pat, repl in COLOR_MAP.items():
        s = re.sub(pat, repl, s, flags=re.IGNORECASE)
    s = re.sub(r"\(\d+\)", "", s)
    s = re.sub(r"[-_]\d+\b", "", s)
    s = re.sub(r"\s{2,}", " ", s).strip(" -_")
    return s

def build_combined_subset_with_color(df_rce_filtered):
    if "SKU" not in df_rce_filtered.columns:
        return df_rce_filtered.iloc[0:0].copy()
    sku = df_rce_filtered["SKU"].astype(str)
    pat_2pc = r"2[\s-]?pc"
    pat_zeme = r"zeme[\s-]?01[\s-]"
    mask = sku.str.contains(pat_2pc, case=False, na=False, regex=True) | \
           sku.str.contains(pat_zeme, case=False, na=False, regex=True)
    subset = df_rce_filtered[mask].copy()
    subset = select_clean_cols(subset)
    subset["SKU"] = subset["SKU"].apply(normalize_sku_color)
    subset = subset.drop_duplicates()
    return subset

def make_pivot_like(df_filtered_with_color):
    base = select_clean_cols(df_filtered_with_color).copy()
    base["SKU"] = base["SKU"].apply(normalize_sku_color)
    base["RCE_STD"] = base["Reason for Credit Entry"].str.upper().str.replace(" ", "_")
    base = base[base["RCE_STD"].isin(["PENDING","READY_TO_SHIP"])]
    pending = base[base["RCE_STD"]=="PENDING"].groupby(["SKU","Size"], dropna=False)["Quantity"].sum()
    rts = base[base["RCE_STD"]=="READY_TO_SHIP"].groupby(["SKU","Size"], dropna=False)["Quantity"].sum()
    idx = sorted(set(pending.index).union(set(rts.index)))
    pending = pending.reindex(idx, fill_value=0)
    rts = rts.reindex(idx, fill_value=0)
    out = pd.DataFrame({"PENDING": pending, "READY_TO_SHIP": rts}).reset_index()
    out["Grand Total"] = out["PENDING"] + out["READY_TO_SHIP"]
    grand_row = pd.DataFrame({
        "SKU": ["Grand Total"], "Size": [""],
        "PENDING": [out["PENDING"].sum()],
        "READY_TO_SHIP": [out["READY_TO_SHIP"].sum()],
        "Grand Total": [out["Grand Total"].sum()]
    })
    return pd.concat([out, grand_row], ignore_index=True)

if uploaded_files:
    merged, _ = do_merge(uploaded_files)
    if merged is None:
        st.warning("No valid data merged. Please check files.")
    else:
        st.subheader("All_Merged")
        st.dataframe(merged, use_container_width=True)
        rce_filtered = filter_rce_pending_rts(merged)
        st.subheader("RCE Filtered (PENDING + READY_TO_SHIP)")
        st.dataframe(rce_filtered, use_container_width=True)
        two_piece_union = build_combined_subset_with_color(rce_filtered)
        st.subheader("Two Piece Jumpsuit (2‑pc ∪ Zeme‑01‑, normalized colors, only 4 columns)")
        st.dataframe(two_piece_union, use_container_width=True)
        pivot_like = make_pivot_like(rce_filtered)
        st.subheader("Pivot-like: SKU→Size; Columns: PENDING, READY_TO_SHIP, Grand Total")
        st.dataframe(pivot_like, use_container_width=True)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            merged.to_excel(writer, index=False, sheet_name="All_Merged")
            rce_filtered.to_excel(writer, index=False, sheet_name="Filtered_Pending_RTS")
            two_piece_union.to_excel(writer, index=False, sheet_name="Two Piece Jumpsuit")
            pivot_like.to_excel(writer, index=False, sheet_name="Pivot_RCE_SKU_Size_Qty")
        output.seek(0)
        st.download_button(
            "Download Excel (All + RCE Filter + 2‑pc/Zeme + Color-Normalized Pivot-like)",
            data=output,
            file_name="merged_clean_2pc_zeme_pivot.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_final_v3"
        )
else:
    st.info("Upload multiple CSV/Excel files to begin.")
