# -*- coding: utf-8 -*-
# Final Streamlit App: Multi-file Merge → Color (Compound) + Style ID → Pivots → Excel & Portrait PDF

import streamlit as st
import pandas as pd
import unicodedata, re
from io import BytesIO
from typing import List, Tuple
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

st.set_page_config(page_title='SKU Processor', layout='wide')

# ---------------- Compound & Color Lists ----------------
COMPOUND_COLORS: List[str] = ['WHITE-RED','WHITE-BLUE','BLACK-YELLOW','BLACK-RED']
COLOR_LIST: List[str] = [
    *COMPOUND_COLORS,
    'BLACK','WHITE','GREY','PINK','PURPLE','WINE','BOTTLE GREEN','PEACH','CREAM','BROWN',
    'BLUE','RED','YELLOW','NAVY','NAVY BLUE','PETROL','MUSTARD','MAROON','OLIVE','SKY BLUE',
    'ORANGE','BEIGE','FUCHSIA','MAGENTA','SEA GREEN','TEAL','TURQUOISE','VIOLET','OFF WHITE',
    'GOLD','SILVER','CHARCOAL','RUST','MINT','LAVENDER','BURGUNDY','KHAKI','CAMEL','IVORY',
    'CORAL','COPPER','MULTICOLOR','GREEN','DARK GREEN','LIGHT GREEN','DARK BLUE','LIGHT BLUE',
    'DARK GREY','LIGHT GREY','SKIN','STONE'
]

# ---------------- Helpers: normalize/keys ----------------
def normalize(s: str) -> str:
    if pd.isna(s): return ''
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii','ignore').decode('ascii')
    s = s.replace('\u200b',' ')
    s = s.replace('_',' ').replace('-', ' ')
    s = re.sub(r'[^A-Za-z0-9\s]',' ', s)
    s = ' '.join(s.split()).lower()
    return s

def key(s: str) -> str:
    return normalize(s).replace(' ', '')

# ---------------- Color Extraction ----------------
def extract_color_from_row(row: pd.Series) -> str:
    all_text = f"{row.get('SKU','')} {row.get('Product Name','')}"
    t = key(all_text)
    found = []
    for comp in COMPOUND_COLORS:  # compounds first
        if key(comp) in t:
            found.append(comp)
    compound_components = set()
    for comp in found:
        for p in comp.split('-'):
            compound_components.add(p.strip().upper())
    for col in COLOR_LIST:
        if col in COMPOUND_COLORS: 
            continue
        if key(col) in t:
            if col.upper() in compound_components:
                continue
            found.append(col)
    seen=set(); unique=[]
    for c in found:
        if c not in seen:
            unique.append(c); seen.add(c)
    return ', '.join(unique)

# ---------------- Style ID Rules ----------------
def derive_style_id(row: pd.Series) -> str:
    txt = f"{row.get('SKU','')} {row.get('Product Name','')}"
    tnorm = normalize(txt)
    tkey  = key(txt)
    if (' of ' in f" {tnorm} ") or ('-2-s' in txt.lower()):
        return '2 TAPE COMBO'
    if any(k in tkey for k in ['2tape','2strip']):
        return '2 TAPE PANT'
    if ('2pc' in tkey) or ('2-pc' in tnorm) or ('zeme01' in tkey) or ('zeme-01-' in txt.upper()):
        return '2-PCS-JUMPSUIT'
    if 'crop' in tnorm:
        return 'CROP HOODIE'
    if 'fruit' in tnorm:
        return 'FRUIT DREES'
    if 'plain trouser' in tnorm or 'plaintrouser' in tkey:
        return 'PLAIN-TROUSER'
    return ''

# ---------------- Read & Merge ----------------
def read_one(upload) -> pd.DataFrame:
    name = upload.name.lower()
    try:
        if name.endswith(('.xlsx','.xls')):
            return pd.read_excel(upload)
        return pd.read_csv(upload, encoding='utf-8', on_bad_lines='skip')
    except Exception:
        upload.seek(0)
        return pd.read_csv(upload, encoding='latin1', on_bad_lines='skip')

def drop_header_like_rows(df: pd.DataFrame, header_cols: List[str]) -> pd.DataFrame:
    try:
        mask = (df.astype(str).apply(lambda r: list(r.values), axis=1).astype(str) == str(header_cols))
        return df.loc[~mask].copy()
    except Exception:
        return df

def merge_files(files) -> pd.DataFrame:
    base = None
    for idx, f in enumerate(files):
        cur = read_one(f)
        cur.columns = cur.columns.astype(str).str.strip()
        if base is None:
            base = cur.copy()
        else:
            cur = drop_header_like_rows(cur, list(base.columns))
            for c in base.columns:
                if c not in cur.columns:
                    cur[c] = pd.NA
            cur = cur[base.columns]
            base = pd.concat([base, cur], ignore_index=True)
    return base if base is not None else pd.DataFrame()

# ---------------- Pivots ----------------
def master_pivot(df: pd.DataFrame) -> pd.DataFrame:
    if 'Reason for Credit Entry' not in df.columns:
        return pd.DataFrame()
    sub = df[df['Reason for Credit Entry'].isin(['PENDING','READY_TO_SHIP'])].copy()
    keep = ['Reason for Credit Entry','Style ID','Size','Color','Quantity']
    keep = [c for c in keep if c in sub.columns]
    sub['Quantity'] = pd.to_numeric(sub['Quantity'], errors='coerce').fillna(0)
    pv = pd.pivot_table(
        sub,
        index=['Style ID','Size','Color'],
        columns=['Reason for Credit Entry'],
        values='Quantity',
        aggfunc='sum',
        fill_value=0,
        margins=True, margins_name='Grand Total'
    ).reset_index()
    # ensure bottom grand total row
    is_total = pv['Style ID'].astype(str).str.strip().eq('Grand Total')
    total_rows = pv[is_total].copy()
    data_rows  = pv[~is_total].copy().sort_values(['Style ID','Size','Color']).reset_index(drop=True)
    pv_final   = pd.concat([data_rows, total_rows], ignore_index=True) if not total_rows.empty else data_rows
    return pv_final

def add_right_grand_total_column(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty: return df
    num_cols = [c for c in df.columns if c not in ['Style ID','Size','Color']]
    sums = df[num_cols].apply(pd.to_numeric, errors='coerce').fillna(0).sum(axis=1)
    out = df.copy()
    out['Grand Total'] = sums
    return out

def stylewise_pivots(df: pd.DataFrame) -> List[Tuple[str, pd.DataFrame]]:
    out=[]
    if 'Style ID' not in df.columns or 'Reason for Credit Entry' not in df.columns:
        return out
    styles = df['Style ID'].dropna().unique().tolist()
    for s in styles:
        sub = df[(df['Style ID']==s) & (df['Reason for Credit Entry'].isin(['PENDING','READY_TO_SHIP']))].copy()
        if sub.empty: 
            continue
        keep = ['Reason for Credit Entry','Style ID','Size','Color','Quantity']
        keep = [c for c in keep if c in sub.columns]
        sub['Quantity'] = pd.to_numeric(sub['Quantity'], errors='coerce').fillna(0)
        pv = pd.pivot_table(
            sub,
            index=['Style ID','Size','Color'],
            columns=['Reason for Credit Entry'],
            values='Quantity',
            aggfunc='sum',
            fill_value=0,
            margins=False
        ).reset_index()
        pv = pv.sort_values(['Style ID','Size','Color']).reset_index(drop=True)
        pv = add_right_grand_total_column(pv)
        out.append((s, pv))
    return out

def add_single_subtotal(df: pd.DataFrame, group_col='Style ID') -> pd.DataFrame:
    if df.empty or group_col not in df.columns:
        return df
    num_cols = df.select_dtypes(include='number').columns.tolist()
    totals = {c: '' for c in df.columns}
    totals[group_col] = 'Grand Total'
    for c in num_cols:
        totals[c] = df[c].sum()
    return pd.concat([df, pd.DataFrame([totals], columns=df.columns)], ignore_index=True)

# ---------------- Excel Writer ----------------
def to_excel_bytes(sheets: dict) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as w:
        for name, d in sheets.items():
            (d if isinstance(d, pd.DataFrame) else pd.DataFrame()).to_excel(w, index=False, sheet_name=name[:31])
    return buf.getvalue()

# ---------------- PDF (Portrait, centered titles, bottom totals) ----------------
def pivots_to_pdf_portrait(style_pivots: List[Tuple[str, pd.DataFrame]], master_pivot_df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=18, leftMargin=18, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()
    title_style   = ParagraphStyle(name='CenteredH',  parent=styles['Heading1'], alignment=1)
    section_style = ParagraphStyle(name='CenteredH2', parent=styles['Heading2'], alignment=1)
    elems = [Paragraph('Pivots Report', title_style), Spacer(1, 12)]

    def paint(title, df):
        elems.append(Paragraph(title, section_style))
        elems.append(Spacer(1, 6))
        data = [df.columns.tolist()] + df.values.tolist()
        t = Table(data, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0), colors.lightgrey),
            ('GRID',(0,0),(-1,-1), 0.35, colors.grey),
            ('ALIGN',(0,0),(-1,-1),'CENTER'),
            ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
            ('FONTSIZE',(0,0),(-1,-1),8),
            ('ROWBACKGROUNDS',(0,1),(-1,-1), [colors.whitesmoke, colors.lightcyan]),
        ]))
        # highlight bottom grand total row
        last = len(data) - 1
        if last >= 1:
            t.setStyle(TableStyle([
                ('BACKGROUND',(0,last),(-1,last), colors.HexColor('#E8F5E9')),
                ('FONTNAME',(0,last),(-1,last),'Helvetica-Bold')
            ]))
        elems.append(t)
        elems.append(Spacer(1, 14))

    # Master pivot already organized with bottom grand total
    paint('Master Pivot (PENDING & READY_TO_SHIP)', master_pivot_df)

    # Style-wise pivots: right-column grand total + bottom row grand total
    for s, pv in stylewise_pivots_df_for_pdf(style_pivots):
        paint(f'Style: {s}', pv)

    doc.build(elems)
    return buf.getvalue()

def stylewise_pivots_df_for_pdf(style_pivots: List[Tuple[str, pd.DataFrame]]) -> List[Tuple[str, pd.DataFrame]]:
    out=[]
    for s, pv in style_pivots:
        pv1 = add_single_subtotal(pv, group_col='Style ID')
        out.append((s, pv1))
    return out

# ---------------- App ----------------
def main():
    st.title('Multi-file Merge → Color (Compound) + Style ID → Pivots → Excel & PDF')

    uploads = st.file_uploader('Upload multiple CSV/XLSX files', type=['csv','xlsx','xls'], accept_multiple_files=True)
    if not uploads:
        st.info('Upload one or more files to begin')
        return

    df = merge_files(uploads)
    if df.empty:
        st.error('Merged data is empty.')
        return

    df.columns = df.columns.astype(str).str.strip()
    if 'SKU' not in df.columns: df['SKU'] = ''
    if 'Product Name' not in df.columns: df['Product Name'] = ''
    if 'Quantity' in df.columns:
        df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').fillna(0)

    with st.spinner('Extracting Color and Style ID...'):
        df['Color'] = df.apply(extract_color_from_row, axis=1)
        df['Style ID'] = df.apply(derive_style_id, axis=1)

    with st.spinner('Building pivots...'):
        pv_master = master_pivot(df)
        pv_styles = stylewise_pivots(df)

    tab1, tab2, tab3 = st.tabs(['Data', 'Master Pivot', 'Style-wise Pivots'])
    with tab1:
        st.dataframe(df.head(300), use_container_width=True)
    with tab2:
        st.dataframe(pv_master, use_container_width=True)
    with tab3:
        if not pv_styles:
            st.info('No style-specific pivots available.')
        else:
            for s, pv in pv_styles:
                st.markdown(f'### {s}')
                st.dataframe(add_single_subtotal(pv), use_container_width=True)

    # Excel download (Data + Pivots)
    sheets = {'Data': df, 'Pivot_Master': pv_master}
    for s, pv in pv_styles:
        sheets[f'Pivot_{s}'] = add_single_subtotal(pv)
    excel_bytes = to_excel_bytes(sheets)
    st.download_button('Download Excel (Data + Pivots)', data=excel_bytes,
                       file_name='Merged_Color_StyleID_Pivots.xlsx',
                       mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    # PDF download (Portrait)
    try:
        pdf_bytes = pivots_to_pdf_portrait(pv_styles, pv_master)
        st.download_button('Download PDF (All Pivots, Portrait)', data=pdf_bytes,
                           file_name='Pivots_Report.pdf', mime='application/pdf')
    except Exception as e:
        st.warning(f'PDF export needs reportlab. Install via: pip install reportlab. Error: {e}')

    st.success('Completed: merge, clean, color & style extraction, pivots, and downloads ready.')

if __name__ == '__main__':
    main()
