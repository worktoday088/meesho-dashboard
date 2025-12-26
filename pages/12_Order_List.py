# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import unicodedata, re
from io import BytesIO
from typing import List, Tuple, Dict
from dataclasses import dataclass
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

st.set_page_config(page_title='SKU Processor', layout='wide')

# ---------------- Color Lists ----------------
COMPOUND_COLORS: List[str] = ['WHITE-RED','WHITE-BLUE','BLACK-YELLOW','BLACK-RED']
COLOR_LIST: List[str] = [
    *COMPOUND_COLORS,
    'BLACK','WHITE','GREY','PINK','PURPLE','WINE','BOTTLE GREEN','PEACH','CREAM','BROWN',
    'BLUE','RED','YELLOW','NAVY','NAVY BLUE','PETROL','MUSTARD','MAROON','OLIVE','SKY BLUE',
    'ORANGE','BEIGE','FUCHSIA','MAGENTA','SEA GREEN','TEAL','TURQUOISE','VIOLET','OFF WHITE',
    'GOLD','SILVER','CHARCOAL','RUST','MINT','LAVENDER','BURGUNDY','KHAKI','CAMEL','IVORY',
    'CORAL','COPPER','MULTICOLOR','GREEN','DARK GREEN','LIGHT GREEN','DARK BLUE','LIGHT BLUE',
    'DARK GREY','LIGHT GREY','SKIN','STONE','MEHANDI'
]

# ---------------- Helpers ----------------
def normalize(s: str) -> str:
    if pd.isna(s):
        return ''
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii','ignore').decode('ascii')
    s = s.replace('\u200b',' ')
    s = s.replace('_',' ').replace('-', ' ')
    s = re.sub(r'[^A-Za-z0-9\s]', ' ', s)
    s = ' '.join(s.split()).lower()
    return s

def key(s: str) -> str:
    return normalize(s).replace(' ', '')

# ---------------- Grand Total Helpers ----------------
def add_right_grand_total_column(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    non_num = ['Style ID','Size','Color']
    num_cols = [c for c in df.columns if c not in non_num]
    out = df.copy()
    out[num_cols] = out[num_cols].apply(pd.to_numeric, errors='coerce').fillna(0)
    out['Grand Total'] = out[num_cols].sum(axis=1)
    return out

def add_bottom_total_row(df: pd.DataFrame, label_col: str = 'Style ID') -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    num_cols = out.select_dtypes(include='number').columns.tolist()
    total_row = {c: '' for c in out.columns}
    total_row[label_col] = 'Grand Total'
    for c in num_cols:
        total_row[c] = out[c].sum()
    return pd.concat([out, pd.DataFrame([total_row])], ignore_index=True)

# ---------------- Safe utils ----------------
def safe_df_for_display(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame([{'Message':'No data available'}])
    return df

def to_excel_bytes(sheets: Dict[str, pd.DataFrame]) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as w:
        for name, d in sheets.items():
            safe_df_for_display(d).to_excel(w, index=False, sheet_name=name[:31])
    return buf.getvalue()

def df_to_pdf_bytes(title: str, df: pd.DataFrame) -> bytes:
    dd = safe_df_for_display(df)
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    elems = [
        Paragraph(title, ParagraphStyle('h', parent=styles['Heading1'], alignment=1)),
        Spacer(1,8)
    ]
    data = [dd.columns.tolist()] + dd.astype(str).values.tolist()
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([
        ('GRID',(0,0),(-1,-1),0.3,colors.grey),
        ('BACKGROUND',(0,0),(-1,0),colors.lightgrey),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTSIZE',(0,0),(-1,-1),8)
    ]))
    elems.append(t)
    doc.build(elems)
    return buf.getvalue()

# ---------------- Style Logic (UNCHANGED) ----------------
@dataclass
class StyleRule:
    patterns: list
    style_name: str

def parse_user_style_mapping(text: str) -> List[StyleRule]:
    rules=[]
    for l in text.splitlines():
        if '=>' in l:
            a,b=l.split('=>',1)
            rules.append(StyleRule([key(x) for x in a.split(',')], b.strip()))
    return rules

def derive_style_id_default(row):
    txt=key(f"{row.get('SKU','')} {row.get('Product Name','')}")
    if '2tape' in txt or '2strip' in txt: return '2 TAPE PANT'
    if '2pc' in txt: return '2-PCS-JUMPSUIT'
    return ''

def derive_style_id_with_user_rules(row, rules, fallback=True):
    txt=key(f"{row.get('SKU','')} {row.get('Product Name','')}")
    for r in rules:
        if any(p in txt for p in r.patterns):
            return r.style_name
    return derive_style_id_default(row) if fallback else ''

def extract_color_from_row(row):
    txt=key(f"{row.get('SKU','')} {row.get('Product Name','')}")
    return ', '.join([c for c in COLOR_LIST if key(c) in txt])

# ---------------- File merge ----------------
def read_one(f):
    if f.name.lower().endswith(('xlsx','xls')):
        return pd.read_excel(f)
    return pd.read_csv(f, on_bad_lines='skip')

def merge_files(files):
    base=None
    for f in files:
        df=read_one(f)
        base=df if base is None else pd.concat([base,df], ignore_index=True)
    return base if base is not None else pd.DataFrame()

# ---------------- Filters ----------------
def filter_by_packetid(df, packets):
    if 'Packet Id' not in df.columns: return df
    if not packets: return df.iloc[0:0]
    s=df['Packet Id'].fillna('').astype(str)
    return df[s.isin(packets) | (s.eq('') if 'Blank' in packets else False)]

def filter_by_order_date(df, dates):
    if 'Order Date' not in df.columns: return df
    if not dates: return df.iloc[0:0]
    return df[df['Order Date'].astype(str).isin(dates)]

def filter_by_status(df, status):
    if 'Reason for Credit Entry' not in df.columns: return df
    if not status: return df.iloc[0:0]
    return df[df['Reason for Credit Entry'].isin(status)]

# ---------------- Pivot (FIXED – NO DUPLICATE TOTAL) ----------------
def master_pivot(df):
    if df.empty: return pd.DataFrame()
    pv=pd.pivot_table(
        df,
        index=['Style ID','Size','Color'],
        columns='Reason for Credit Entry',
        values='Quantity',
        aggfunc='sum',
        fill_value=0
    ).reset_index()
    pv=add_right_grand_total_column(pv)
    pv=add_bottom_total_row(pv,'Style ID')
    return pv

# ---------------- UI ----------------
def multiselect_with_select_all(label, options, key):
    all_opt='— Select All —'
    sel=st.multiselect(label,[all_opt]+options,key=key)
    return options if all_opt in sel else sel

def main():
    st.title('Order List Dashboard')

    uploads=st.file_uploader('Upload files',accept_multiple_files=True)
    if not uploads: return

    df=merge_files(uploads)
    df['Quantity']=pd.to_numeric(df.get('Quantity',0),errors='coerce').fillna(0)
    df['Color']=df.apply(extract_color_from_row,axis=1)
    df['Style ID']=df.apply(derive_style_id_default,axis=1)

    col1,col2=st.columns(2)

    with col1:
        packets=sorted(df['Packet Id'].dropna().astype(str).unique()) if 'Packet Id' in df else []
        packets+=['Blank']
        sel_packets=multiselect_with_select_all('Packet Id',packets,'pkt')

    with col2:
        dates=sorted(df['Order Date'].dropna().astype(str).unique()) if 'Order Date' in df else []
        sel_dates=multiselect_with_select_all('Order Date',dates,'od')

    status=sorted(df['Reason for Credit Entry'].dropna().astype(str).unique()) if 'Reason for Credit Entry' in df else []
    sel_status=multiselect_with_select_all('Reason for Credit Entry',status,'rs')

    if not (sel_packets and sel_dates and sel_status):
        st.warning('सभी filters चुनें')
        return

    df=filter_by_packetid(df,sel_packets)
    df=filter_by_order_date(df,sel_dates)
    df=filter_by_status(df,sel_status)

    pv=master_pivot(df)
    st.dataframe(pv,use_container_width=True)

    st.download_button(
        'Download Excel',
        to_excel_bytes({'Master Pivot':pv}),
        'Master_Pivot.xlsx'
    )

if __name__=='__main__':
    main()
