import streamlit as st
import pandas as pd
import unicodedata, re
from io import BytesIO
from typing import List

# ---------------- Compound colors kept AS-IS ----------------
COMPOUND_COLORS: List[str] = [
    'WHITE-RED', 'WHITE-BLUE', 'BLACK-YELLOW', 'BLACK-RED'
]

# ---------------- Master color list (include compounds) ----------------
COLOR_LIST: List[str] = [
    'WHITE-RED', 'WHITE-BLUE', 'BLACK-YELLOW', 'BLACK-RED',
    'BLACK', 'WHITE', 'GREY', 'PINK', 'PURPLE', 'WINE', 'BOTTLE GREEN', 'PEACH',
    'CREAM', 'BROWN', 'BLUE', 'RED', 'YELLOW', 'NAVY', 'NAVY BLUE', 'PETROL',
    'MUSTARD', 'MAROON', 'OLIVE', 'SKY BLUE', 'ORANGE', 'BEIGE', 'FUCHSIA', 'MAGENTA',
    'SEA GREEN', 'TEAL', 'TURQUOISE', 'VIOLET', 'OFF WHITE', 'GOLD', 'SILVER',
    'CHARCOAL', 'RUST', 'MINT', 'LAVENDER', 'BURGUNDY', 'KHAKI', 'CAMEL',
    'IVORY', 'CORAL', 'COPPER', 'MULTICOLOR', 'GREEN', 'DARK GREEN', 'LIGHT GREEN',
    'DARK BLUE', 'LIGHT BLUE', 'DARK GREY', 'LIGHT GREY', 'SKIN', 'STONE'
]

# ---------------- Normalization helpers ----------------
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

# ---------------- Color extraction ----------------
def extract_color_from_row(row: pd.Series) -> str:
    all_text = f"{row.get('SKU','')} {row.get('Product Name','')}"
    t = key(all_text)
    found = []

    # compounds first
    for comp in COMPOUND_COLORS:
        if key(comp) in t:
            found.append(comp)

    # components to skip duplicates
    compound_components = set()
    for comp in found:
        for p in comp.split('-'):
            compound_components.add(p.strip().upper())

    # rest colors
    for col in COLOR_LIST:
        if col in COMPOUND_COLORS:
            continue
        if key(col) in t:
            if col.upper() in compound_components:
                continue
            found.append(col)

    # unique keep order
    seen=set(); unique=[]
    for c in found:
        if c not in seen:
            unique.append(c); seen.add(c)
    return ', '.join(unique)

# ---------------- Style ID rules ----------------
def derive_style_id(row: pd.Series) -> str:
    txt = f"{row.get('SKU','')} {row.get('Product Name','')}"
    tnorm = normalize(txt)
    tkey  = key(txt)

    # 1) 2 TAPE COMBO (most specific)
    if (' of ' in f" {tnorm} ") or ('-2-s' in txt.lower()):
        return '2 TAPE COMBO'

    # 2) 2 TAPE PANT (2 TAPE / 2-TAPE / 2 STRIP / 2-STRIP)
    tape_keys = ['2tape','2 tape','2strip','2 strip']
    if any(k.replace(' ','') in tkey for k in tape_keys):
        return '2 TAPE PANT'

    # 3) 2-PCS-JUMPSUIT (2-PC or ZEME-01-)
    if ('2pc' in tkey) or ('2-pc' in tnorm) or ('zeme01' in tkey) or ('zeme-01-' in txt.upper()):
        return '2-PCS-JUMPSUIT'

    # 4) CROP HOODIE
    if 'crop' in tnorm:
        return 'CROP HOODIE'

    # 5) FRUIT DREES
    if 'fruit' in tnorm:
        return 'FRUIT DREES'

    # 6) PLAIN-TROUSER
    # search keyword: PLAIN-TROUSER anywhere
    if 'plain trouser' in tnorm or 'plaintrouser' in tkey:
        return 'PLAIN-TROUSER'

    return ''

# ---------------- File IO ----------------
def read_any(upload) -> pd.DataFrame:
    try:
        if upload.name.lower().endswith(('.xlsx','.xls')):
            return pd.read_excel(upload)
        return pd.read_csv(upload, encoding='utf-8', on_bad_lines='skip')
    except Exception:
        upload.seek(0)
        return pd.read_csv(upload, encoding='latin1', on_bad_lines='skip')

def to_excel_bytes(dfs: dict) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as w:
        for sheet, df in dfs.items():
            df.to_excel(w, index=False, sheet_name=sheet[:31])
    return buf.getvalue()

# ---------------- Build Pivot-like table (as per screenshot) ----------------
def make_pivot_view(df: pd.DataFrame) -> pd.DataFrame:
    # Filter Reason for Credit Entry for PENDING and READY_TO_SHIP
    if 'Reason for Credit Entry' not in df.columns:
        return pd.DataFrame()
    sub = df[df['Reason for Credit Entry'].isin(['PENDING','READY_TO_SHIP'])].copy()

    # Keep only needed columns
    cols = ['Reason for Credit Entry','Style ID','Size','Color','Quantity']
    cols = [c for c in cols if c in sub.columns]
    sub = sub[cols]

    # Build pivot: Columns=Reason for Credit Entry; Rows=Style ID, Size, Color; Values=Sum of Quantity
    pv = pd.pivot_table(
        sub,
        index=['Style ID','Size','Color'],
        columns=['Reason for Credit Entry'],
        values='Quantity',
        aggfunc='sum',
        fill_value=0,
        margins=True,
        margins_name='Grand Total'
    )
    pv = pv.reset_index()
    # Optional: sort rows
    pv = pv.sort_values(by=['Style ID','Size','Color']).reset_index(drop=True)
    return pv

# ---------------- Streamlit App ----------------
def main():
    st.title('SKU → Color (Compound) + Style ID + Pivot Report')

    up = st.file_uploader('Upload CSV/XLSX', type=['csv','xlsx','xls'])
    if not up:
        st.info('Upload a file to start')
        return

    try:
        df = read_any(up)
    except Exception as e:
        st.error(f'Read error: {e}')
        return

    df.columns = df.columns.astype(str).str.strip()
    if 'SKU' not in df.columns: df['SKU'] = ''
    if 'Product Name' not in df.columns: df['Product Name'] = ''

    # Color & Style ID
    df['Color'] = df.apply(extract_color_from_row, axis=1)
    df['Style ID'] = df.apply(derive_style_id, axis=1)

    # Pivot-like view
    pv = make_pivot_view(df)

    st.subheader('Main Data (with Color & Style ID)')
    st.dataframe(df.head(200), use_container_width=True)

    st.subheader('Pivot (Reason for Credit Entry = PENDING / READY_TO_SHIP)')
    if pv.empty:
        st.warning('Pivot not available (Reason for Credit Entry column missing or no matching rows).')
    else:
        st.dataframe(pv, use_container_width=True)

    # Downloads: main + pivot both as sheets
    excel_bytes = to_excel_bytes({'Data': df, 'Pivot': pv if not pv.empty else pd.DataFrame()})
    st.download_button('Download Excel (Data + Pivot)', data=excel_bytes,
                       file_name='Cleaned_Color_StyleID_Pivot.xlsx',
                       mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    st.download_button('Download CSV (Main Data)', data=df.to_csv(index=False).encode('utf-8'),
                       file_name='Cleaned_Color_StyleID.csv', mime='text/csv')

    st.success('Done: compound colors kept; Style ID rules applied; Pivot generated.')

if __name__ == '__main__':
    main()
