import streamlit as st
import pandas as pd
from io import BytesIO
from fpdf import FPDF
import tempfile

# ----------------- Streamlit Config -----------------
st.set_page_config(
    page_title="Courier Partner Delivery & Return Analysis",
    layout="wide"
)
st.title("📦 Courier Partner Delivery & Return Analysis")

HEADER_ROW_INDEX = 7


# ----------------- Helper Functions -----------------

def add_grand_totals(df: pd.DataFrame) -> pd.DataFrame:
    """Add 'Grand Total' column and row for generic pivot tables."""
    df["Grand Total"] = df.sum(axis=1, numeric_only=True)
    total_row = df.sum(axis=0, numeric_only=True)
    total_row.name = "Grand Total"
    df = pd.concat([df, pd.DataFrame([total_row])], axis=0)
    return df


def pivot_to_pdf(pivot_df: pd.DataFrame, title: str = "Summary") -> bytes:
    """Generic summary tables के लिए simple PDF (सारे नंबर integer)."""
    pivot_df = pivot_df.astype(int)

    max_cols = len(pivot_df.columns) + 1
    orientation = "L" if max_cols > 7 else "P"
    pdf_width = 297 if orientation == "L" else 210

    pdf = FPDF(orientation=orientation, unit="mm", format="A4")
    pdf.add_page()

    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, title, ln=1, align="C")
    pdf.ln(3)

    pdf.set_font("Arial", "", 8)
    margin_lr = 10
    usable_width = pdf_width - 2 * margin_lr
    col_width = max(15, usable_width // max_cols)

    col_names = [""] + list(pivot_df.columns)
    data = [col_names]

    for idx, row in pivot_df.iterrows():
        data.append([str(idx)] + [str(int(x)) for x in row])

    for row in data:
        for val in row:
            pdf.cell(col_width, 7, str(val)[:20], border=1, align="C")
        pdf.ln()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf.output(tmp.name)
        tmp.seek(0)
        pdf_bytes = tmp.read()

    return pdf_bytes


def pivot_to_pdf_stylegroup(
    pivot_df: pd.DataFrame,
    title: str = "Style Group Reason Summary",
    grand_total: int = 0
) -> bytes:
    """Style Group reasons के लिए special PDF (reason wide + wrapping)."""
    pivot_df = pivot_df.astype(int)

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()

    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, title, ln=1, align="C")
    pdf.ln(3)

    pdf_width = 297
    margin = 8
    usable_width = pdf_width - 2 * margin

    reason_col_width = 120
    other_col_width = (usable_width - reason_col_width) / max(1, len(pivot_df.columns))

    # Header
    pdf.set_font("Arial", "B", 9)
    pdf.set_fill_color(220, 220, 220)

    pdf.cell(reason_col_width, 8, "Detailed Return Reason", border=1, align="C", fill=True)
    for col in pivot_df.columns:
        pdf.cell(other_col_width, 8, str(col)[:20], border=1, align="C", fill=True)
    pdf.ln()

    # Data rows
    pdf.set_font("Arial", "", 8)
    max_chars_per_line = 50
    line_height = 5

    for idx, row in pivot_df.iterrows():
        reason_text = str(idx)

        lines = []
        for i in range(0, len(reason_text), max_chars_per_line):
            lines.append(reason_text[i:i + max_chars_per_line])

        cell_height = line_height * max(1, len(lines))

        x_start = pdf.get_x()
        y_start = pdf.get_y()

        pdf.multi_cell(
            reason_col_width,
            line_height,
            "\n".join(lines),
            border=1,
            align="L"
        )

        pdf.set_xy(x_start + reason_col_width, y_start)

        for val in row:
            txt = str(int(val))
            pdf.cell(other_col_width, cell_height, txt, border=1, align="C")

        pdf.ln(cell_height)

    # TOTAL row
    if grand_total > 0:
        pdf.set_font("Arial", "B", 9)
        pdf.set_fill_color(200, 200, 200)
        pdf.cell(reason_col_width, 10, "TOTAL", border=1, align="C", fill=True)
        pdf.cell(other_col_width, 10, str(int(grand_total)), border=1, align="C", fill=True)
        pdf.ln()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf.output(tmp.name)
        tmp.seek(0)
        pdf_bytes = tmp.read()

    return pdf_bytes


# ----------------- Upload Section -----------------

with st.expander("📁 Upload CSV/XLSX Files", expanded=True):
    uploaded_files = st.file_uploader(
        "Upload CSV/XLSX Files",
        accept_multiple_files=True,
        type=["csv", "xlsx", "xls"],
    )

if uploaded_files:
    dfs = []
    for f in uploaded_files:
        if f.name.endswith(".csv"):
            df = pd.read_csv(f, skiprows=HEADER_ROW_INDEX)
        else:
            df = pd.read_excel(f, skiprows=HEADER_ROW_INDEX)
        dfs.append(df)

    df_all = pd.concat(dfs, ignore_index=True)

    # Normalise Courier Partner names
    if "Courier Partner" in df_all.columns:
        df_all["Courier Partner"] = df_all["Courier Partner"].apply(
            lambda x: "Valmo"
            if pd.notna(x) and ("PocketShip" in str(x) or "Valmo" in str(x))
            else x
        )

    # Delivered Date
    if "Delivered Date" in df_all.columns:
        df_all["Delivered Date"] = pd.to_datetime(
            df_all["Delivered Date"],
            errors="coerce"
        ).dt.date

    # ----------------- Sidebar Filters -----------------
    st.sidebar.header("🔍 Filters")

    # Date filter
    if "Delivered Date" in df_all.columns:
        all_dates = sorted(str(x) for x in df_all["Delivered Date"].dropna().unique())
        search_date = st.sidebar.text_input("Search Date (YYYY-MM-DD)")
        filtered_dates = [d for d in all_dates if search_date in d] if search_date
