# -*- coding: utf-8 -*-
# Streamlit App: Multi-file Merge → Color + Style (Search) → Filtered Pivots → Excel & PDFs

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
    if pd.isna(s): return ''
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii','ignore').decode('ascii')
    s = s.replace('​',' ')
    s = s.replace('_',' ').replace('-', ' ')
    s = re.sub(r'[^A-Za-z0-9s]',' ', s)
    s = ' '.join(s.split()).lower()
    return s

def key(s: str) -> str:
    return normalize(s).replace(' ', '')

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
    for f in files:
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

# ---------------- Filtering ----------------
def filter_by_status(df: pd.DataFrame, statuses: List[str]) -> pd.DataFrame:
    if 'Reason for Credit Entry' not in df.columns:
        return df
    if not statuses:
        return df.iloc[0:0]
    return df[df['Reason for Credit Entry'].isin(statuses)].copy()

def filter_by_packetid(df: pd.DataFrame, packet_ids: List[str]) -> pd.DataFrame:
    if 'Packet Id' not in df.columns:
        return df
    if not packet_ids:
        return df.iloc[0:0]
    # Include blanks when 'Blank' selected
    mask_blank = df['Packet Id'].astype(str).str.strip().eq('') | df['Packet Id'].isna()
    mask_selected = df['Packet Id'].astype(str).isin([x for x in packet_ids if x != 'Blank'])
    if 'Blank' in packet_ids:
        combined_mask = mask_selected | mask_blank
    else:
        combined_mask = mask_selected
    return df[combined_mask].copy()

# ---------------- Pivot Table ----------------
def master_pivot(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    sub = df.copy()
    if 'Quantity' in sub.columns:
        sub['Quantity'] = pd.to_numeric(sub['Quantity'], errors='coerce').fillna(0)
    pv = pd.pivot_table(
        sub,
        index=['Style ID','Size','Color'],
        columns=['Reason for Credit Entry'] if 'Reason for Credit Entry' in sub.columns else None,
        values='Quantity' if 'Quantity' in sub.columns else None,
        aggfunc='sum',
        fill_value=0,
        margins=True, margins_name='Grand Total'
    ).reset_index()
    if 'Style ID' in pv.columns:
        data_rows = pv[~pv['Style ID'].astype(str).eq('Grand Total')]
        total_rows = pv[pv['Style ID'].astype(str).eq('Grand Total')]
        pv = pd.concat([data_rows, total_rows], ignore_index=True)
    return pv

# ---------------- App ----------------
def main():
    st.title('Order List Dashboard with Packet Id Blank Filter')

    uploads = st.file_uploader('Upload CSV/XLSX files', type=['csv','xlsx','xls'], accept_multiple_files=True)
    if not uploads:
        st.info('कृपया एक या अधिक फ़ाइल अपलोड करें।')
        return

    df = merge_files(uploads)
    if df.empty:
        st.error('डेटा खाली है।')
        return

    df.columns = df.columns.astype(str).str.strip()

    # Filter: Packet Id
    st.subheader('Packet Id Filter')
    if 'Packet Id' in df.columns:
        all_packets = df['Packet Id'].fillna('').astype(str).unique().tolist()
        all_packets = sorted([x for x in all_packets if x.strip() != '']) + ['Blank']
        sel_packets = st.multiselect('Packet Id चुनें (जिसमें Blank भी शामिल)', all_packets, default=[])
    else:
        sel_packets = []
    
    # Filter: Reason for Credit Entry
    st.subheader('Reason for Credit Entry Filter')
    all_status = []
    if 'Reason for Credit Entry' in df.columns:
        all_status = sorted(df['Reason for Credit Entry'].dropna().astype(str).unique().tolist())
    sel_status = st.multiselect('Select Credit Entry Reasons', options=all_status, default=[])

    # Apply filters
    df_filtered = df.copy()
    if 'Packet Id' in df.columns:
        df_filtered = filter_by_packetid(df_filtered, sel_packets)
    if 'Reason for Credit Entry' in df.columns:
        df_filtered = filter_by_status(df_filtered, sel_status)
    
    st.write('Filtered Data:')
    st.dataframe(df_filtered.head(2000), use_container_width=True)
    
    # Pivot
    pv_master = master_pivot(df_filtered)
    st.markdown('## Master Pivot Table')
    st.dataframe(pv_master, use_container_width=True)

    excel_bytes = BytesIO()
    with pd.ExcelWriter(excel_bytes, engine='openpyxl') as writer:
        df_filtered.to_excel(writer, sheet_name='Filtered_Data', index=False)
        pv_master.to_excel(writer, sheet_name='Master_Pivot', index=False)
    st.download_button('Download Excel', data=excel_bytes.getvalue(), file_name='Filtered_Report.xlsx')

if __name__ == '__main__':
    main()            found.append(comp)

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
    for f in files:
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

# ---------------- Filtering + Pivots ----------------
def filter_by_status(df: pd.DataFrame, statuses: List[str]) -> pd.DataFrame:
    if 'Reason for Credit Entry' not in df.columns:
        return df
    if not statuses:
        return df.iloc[0:0]
    return df[df['Reason for Credit Entry'].isin(statuses)].copy()

def master_pivot(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    sub = df.copy()
    if 'Quantity' in sub.columns:
        sub['Quantity'] = pd.to_numeric(sub['Quantity'], errors='coerce').fillna(0)
    pv = pd.pivot_table(
        sub,
        index=['Style ID','Size','Color'],
        columns=['Reason for Credit Entry'] if 'Reason for Credit Entry' in sub.columns else None,
        values='Quantity' if 'Quantity' in sub.columns else None,
        aggfunc='sum',
        fill_value=0,
        margins=True, margins_name='Grand Total'
    ).reset_index()
    is_total = pv['Style ID'].astype(str).str.strip().eq('Grand Total') if 'Style ID' in pv.columns else pd.Series(False, index=pv.index)
    total_rows = pv[is_total].copy()
    data_rows = pv[~is_total].copy()
    if {'Style ID','Size','Color'}.issubset(data_rows.columns):
        data_rows = data_rows.sort_values(['Style ID','Size','Color']).reset_index(drop=True)
    pv_final = pd.concat([data_rows, total_rows], ignore_index=True) if not total_rows.empty else data_rows
    return pv_final

def add_right_grand_total_column(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty: return df
    non_num = ['Style ID','Size','Color']
    num_cols = [c for c in df.columns if c not in non_num]
    sums = df[num_cols].apply(pd.to_numeric, errors='coerce').fillna(0).sum(axis=1)
    out = df.copy()
    out['Grand Total'] = sums
    return out

def stylewise_pivots(df: pd.DataFrame) -> List[Tuple[str, pd.DataFrame]]:
    out=[]
    if df.empty or 'Style ID' not in df.columns:
        return out
    styles = df['Style ID'].dropna().astype(str).unique().tolist()
    for s in styles:
        sub = df[df['Style ID']==s].copy()
        if sub.empty:
            continue
        if 'Quantity' in sub.columns:
            sub['Quantity'] = pd.to_numeric(sub['Quantity'], errors='coerce').fillna(0)
        pv = pd.pivot_table(
            sub,
            index=['Style ID','Size','Color'],
            columns=['Reason for Credit Entry'] if 'Reason for Credit Entry' in sub.columns else None,
            values='Quantity' if 'Quantity' in sub.columns else None,
            aggfunc='sum',
            fill_value=0,
            margins=False
        ).reset_index()
        if {'Style ID','Size','Color'}.issubset(pv.columns):
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

# ---------------- Excel/PDF Utilities ----------------
def to_excel_bytes(sheets: Dict[str, pd.DataFrame]) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as w:
        for name, d in sheets.items():
            (d if isinstance(d, pd.DataFrame) else pd.DataFrame()).to_excel(w, index=False, sheet_name=name[:31])
    return buf.getvalue()

def df_to_pdf_bytes(title: str, df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=18, leftMargin=18, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(name='CenteredH', parent=styles['Heading1'], alignment=1)
    elems = [Paragraph(title, title_style), Spacer(1, 8)]
    data = [df.columns.tolist()] + df.astype(str).values.tolist()
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0), colors.lightgrey),
        ('GRID',(0,0),(-1,-1), 0.35, colors.grey),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),8),
        ('ROWBACKGROUNDS',(0,1),(-1,-1), [colors.whitesmoke, colors.lightcyan]),
    ]))
    last = len(data) - 1
    if last >= 1:
        t.setStyle(TableStyle([
            ('BACKGROUND',(0,last),(-1,last), colors.HexColor('#E8F5E9')),
            ('FONTNAME',(0,last),(-1,last),'Helvetica-Bold')
        ]))
    elems.append(t)
    doc.build(elems)
    return buf.getvalue()

# ---------------- App ----------------
def main():
    st.title('Multi-file Merge → Color + Style (Search) → Filtered Pivots → Excel & PDFs')

    # Expandable: Upload section
    with st.expander('[translate:Upload files]'):
        uploads = st.file_uploader('Upload multiple CSV/XLSX files', type=['csv','xlsx','xls'], accept_multiple_files=True)

    # Expandable: Style Search / Manual keywords
    with st.expander('[translate:Style Search]'):
        use_user_rules_first = st.toggle('[translate:Manual keywords first]', value=True)
        user_rules_text = st.text_area(
            '[translate:Enter "search keywords => Style ID" (one per line)]',
            value=(
                "of, -2-s => 2 TAPE COMBO\n"
                "2tape, 2strip => 2 TAPE PANT\n"
                "2pc, 2-pc, zeme01, zeme-01- => 2-PCS-JUMPSUIT\n"
                "crop => CROP HOODIE\n"
            ),
            height=160
        )
        user_rules = parse_user_style_mapping(user_rules_text)

    if not uploads:
        st.info('[translate:Upload one or more files to begin]')
        return

    df = merge_files(uploads)
    if df.empty:
        st.error('[translate:Merged data is empty.]')
        return

    df.columns = df.columns.astype(str).str.strip()
    if 'SKU' not in df.columns: df['SKU'] = ''
    if 'Product Name' not in df.columns: df['Product Name'] = ''
    if 'Quantity' in df.columns:
        df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').fillna(0)

    # Status filter
    st.subheader('[translate:Status filter]')
    all_status = []
    if 'Reason for Credit Entry' in df.columns:
        all_status = sorted(df['Reason for Credit Entry'].dropna().astype(str).unique().tolist())
    default_pick = [s for s in all_status if s in ['PENDING','READY_TO_SHIP']]
    sel_status = st.multiselect('[translate:Select status]', options=all_status, default=default_pick)

    with st.spinner('Extracting Color and Style ID...'):
        df['Color'] = df.apply(extract_color_from_row, axis=1)
        df['Style ID'] = df.apply(
            lambda r: derive_style_id_with_user_rules(
                r,
                user_rules=user_rules,
                fallback=not use_user_rules_first
            ),
            axis=1
        )
        if use_user_rules_first:
            mask_blank = df['Style ID'].astype(str).eq('')
            if mask_blank.any():
                df.loc[mask_blank, 'Style ID'] = df.loc[mask_blank].apply(
                    lambda r: derive_style_id_with_user_rules(r, user_rules=[], fallback=True),
                    axis=1
                )

    # Apply status filter
    df_filtered = filter_by_status(df, sel_status) if 'Reason for Credit Entry' in df.columns else df.copy()

    with st.spinner('Building pivots...'):
        pv_master = master_pivot(df_filtered)
        pv_styles = stylewise_pivots(df_filtered)

    tab1, tab2, tab3, tab4 = st.tabs(['Data', 'Master Pivot', 'Style-wise Pivots', 'Master List'])
    with tab1:
        st.dataframe(df_filtered.head(2000), use_container_width=True)

    with tab2:
        st.dataframe(pv_master, use_container_width=True)
        colA, colB = st.columns(2)
        with colA:
            mp_bytes = to_excel_bytes({'Pivot_Master': pv_master})
            st.download_button('[translate:Download Master Pivot (Excel)]', data=mp_bytes,
                               file_name='Pivot_Master.xlsx',
                               mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        with colB:
            mp_pdf = df_to_pdf_bytes('Master Pivot', pv_master)
            st.download_button('[translate:Download Master Pivot (PDF)]', data=mp_pdf,
                               file_name='Pivot_Master.pdf', mime='application/pdf')

    with tab3:
        if not pv_styles:
            st.info('[translate:No style-specific pivots available.]')
        else:
            for s, pv in pv_styles:
                st.markdown(f'### {s}')
                pv_show = add_single_subtotal(pv)
                st.dataframe(pv_show, use_container_width=True)
                c1, c2 = st.columns(2)
                with c1:
                    one_xlsx = to_excel_bytes({f'Pivot_{s}': pv_show})
                    st.download_button(f'[translate:Download Excel] ({s})', data=one_xlsx,
                                       file_name=f'Pivot_{s}.xlsx',
                                       mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                                       key=f'xl_{s}')
                with c2:
                    one_pdf = df_to_pdf_bytes(f'Style: {s}', pv_show)
                    st.download_button(f'[translate:Download PDF] ({s})', data=one_pdf,
                                       file_name=f'Pivot_{s}.pdf', mime='application/pdf',
                                       key=f'pdf_{s}')

    with tab4:
        st.markdown('#### [translate:Master Style List]')
        cols = ['Style ID','Size','Color','Reason for Credit Entry','Quantity']
        cols = [c for c in cols if c in df_filtered.columns]
        master_list = df_filtered[cols].copy()
        st.dataframe(master_list, use_container_width=True, height=420)

        mcol1, mcol2 = st.columns(2)
        with mcol1:
            m_xlsx = to_excel_bytes({'Master_List': master_list})
            st.download_button('[translate:Download Master List (Excel)]', data=m_xlsx,
                               file_name='Master_List.xlsx',
                               mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        with mcol2:
            m_pdf = df_to_pdf_bytes('Master List', master_list)
            st.download_button('[translate:Download Master List (PDF)]', data=m_pdf,
                               file_name='Master_List.pdf', mime='application/pdf')

    sheets = {'Data_Filtered': df_filtered, 'Pivot_Master': pv_master}
    for s, pv in pv_styles:
        sheets[f'Pivot_{s}'] = add_single_subtotal(pv)
    excel_bytes = to_excel_bytes(sheets)
    st.download_button('[translate:Download Excel (All Sheets)]', data=excel_bytes,
                       file_name='All_Data_Pivots.xlsx',
                       mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    st.success('[translate:Completed: merge, filters, color & style extraction, pivots, and downloads ready.]')

if __name__ == '__main__':
    main()
