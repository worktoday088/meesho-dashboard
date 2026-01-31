import streamlit as st
import re
import io
import zipfile
from pypdf import PdfReader, PdfWriter

# ---------------------------------------------------------
# CONFIGURATION & SETUP
# ---------------------------------------------------------
st.set_page_config(page_title="Meesho Master Sorter V4", layout="wide")

st.title("🚀 All-in-One Meesho PDF Sorter")
st.markdown("""
**Workflow:** Courier Detect ➡️ Style Sort ➡️ Color Sort ➡️ Size Sort  
यह टूल आपके तीनों काम (Courier, Style/Color Grouping, Size) एक साथ करेगा। 
आप साइडबार में अपने **Keywords** खुद सेट कर सकते हैं।
""")

# ---------------------------------------------------------
# SIDEBAR - DYNAMIC CONFIGURATION
# ---------------------------------------------------------
st.sidebar.header("⚙️ Settings & Groups")

# 1. Courier Priority List
default_couriers = "Shadowfax, Xpress Bees, Delhivery, Valmo, Ecom Express"
courier_input = st.sidebar.text_area("Courier Priority (Comma separated)", default_couriers, height=70)
COURIER_PRIORITY = [c.strip() for c in courier_input.split(",") if c.strip()]

# 2. Style Groups (Dynamic)
st.sidebar.subheader("👕 Style Keywords")
default_styles = """Crop Hoodie : crop, @crop
Tape Pant : STRIP, TAPE, -TAPE, -S-, ,OF
Jumpsuit : PC, PCS, ZEME-01
Fruit Print : Fruit
"""
style_input = st.sidebar.text_area(
    "Format: GroupName : keyword1, keyword2", 
    default_styles, 
    height=150,
    help="Format: 'Style Name : keyword1, keyword2' (Har naya style nayi line mein)"
)

# 3. Color Groups (Dynamic)
st.sidebar.subheader("🎨 Color Keywords")
default_colors = """Pink : pink, peach, rose
White : white, off-white
Black : black, dark
Wine : wine, maroon
Blue : blue, navy
"""
color_input = st.sidebar.text_area(
    "Format: GroupName : keyword1, keyword2", 
    default_colors, 
    height=150
)

# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------

def parse_config(text_input):
    """Users ke text input ko dictionary mein badalta hai."""
    config_map = {} # {'GroupName': ['synonym1', 'synonym2']}
    lines = text_input.split('\n')
    for line in lines:
        if ':' in line:
            parts = line.split(':')
            group_name = parts[0].strip()
            synonyms = [s.strip() for s in parts[1].split(',') if s.strip()]
            config_map[group_name] = synonyms
    return config_map

def detect_courier(text, priority_list):
    for c in priority_list:
        if re.search(re.escape(c), text, re.IGNORECASE):
            return c
    return "Other-Courier"

def detect_group(text, config_map, default_name="Unknown"):
    """Text mein synonyms dhoond kar Group Name return karta hai."""
    # Check for keywords
    for group_name, synonyms in config_map.items():
        for syn in synonyms:
            # Use word boundary for cleaner match, but simple search is robust for SKU codes
            if re.search(re.escape(syn), text, re.IGNORECASE):
                return group_name
    return default_name

def detect_size_qty(text):
    """Size logic from V3 (Size + Qty pair)"""
    # 1. Sirf 'Product Details' ke baad ka hissa dekhein
    split_text = text.split("Product Details")
    relevant_text = split_text[1] if len(split_text) > 1 else text
    
    # 2. Regex Pattern
    pattern = r'\b(S|M|L|XL|XXL|XS|XXS|3XL|4XL|5XL|Free)\b[\s,"]+(\d+)\b'
    match = re.search(pattern, relevant_text, re.IGNORECASE)
    
    if match:
        found_size = match.group(1).upper()
        if found_size == "FREE": found_size = "Free-Size"
        return found_size
    return "Unknown-Size"

# ---------------------------------------------------------
# MAIN PROCESSING
# ---------------------------------------------------------

uploaded_file = st.file_uploader("📂 Upload Meesho Label PDF", type=["pdf"])

if uploaded_file is not None:
    # Parse User Configs
    STYLE_MAP = parse_config(style_input)
    COLOR_MAP = parse_config(color_input)
    
    if st.button("Start Sorting ⚡"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            pdf_reader = PdfReader(uploaded_file)
            total_pages = len(pdf_reader.pages)
            
            # Data Structure: We will store pages based on a generated Filename Key
            # Key format: "Courier__Style__Color__Size"
            sorted_data = {} 
            
            status_text.text("Scanning pages...")
            
            for i, page in enumerate(pdf_reader.pages):
                # Text Extraction
                text = page.extract_text() or ""
                
                # 1. Detect Courier
                courier = detect_courier(text, COURIER_PRIORITY)
                
                # 2. Detect Style
                style = detect_group(text, STYLE_MAP, default_name="Other-Style")
                
                # 3. Detect Color
                color = detect_group(text, COLOR_MAP, default_name="Other-Color")
                
                # 4. Detect Size
                size = detect_size_qty(text)
                
                # Generate Key for Grouping
                # Filename logic: Shadowfax_CropHoodie_Pink_Size-L
                key = f"{courier}__{style}__{color}__{size}"
                
                if key not in sorted_data:
                    sorted_data[key] = []
                sorted_data[key].append(page)
                
                # Update Progress
                if i % 10 == 0:
                    progress_bar.progress((i + 1) / total_pages)

            progress_bar.progress(100)
            status_text.success(f"✅ Scanning Done! Sorted into {len(sorted_data)} unique groups.")
            
            # ---------------------------------------------------------
            # GENERATE OUTPUT (ZIP)
            # ---------------------------------------------------------
            # Hum ek ZIP file banayenge kyunki bahut saare PDF ho sakte hain
            
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for key, pages in sorted_data.items():
                    # Key ko filename mein convert karein
                    # Key format: Courier__Style__Color__Size
                    parts = key.split('__')
                    courier, style, color, size = parts[0], parts[1], parts[2], parts[3]
                    
                    # File Name: Courier/Style/Color_Size.pdf rakhna behtar hai ya seedha filename?
                    # User ki requirement: Courier > Style > Color > Size
                    # Let's create a filename that sorts nicely:
                    # Ex: Shadowfax_Crop-Hoodie_Pink_Size-XL.pdf
                    
                    file_name = f"{courier}_{style}_{color}_{size}.pdf"
                    
                    # Create simple PDF in memory
                    writer = PdfWriter()
                    for p in pages:
                        writer.add_page(p)
                    
                    pdf_bytes = io.BytesIO()
                    writer.write(pdf_bytes)
                    
                    # Add to Zip
                    zip_file.writestr(file_name, pdf_bytes.getvalue())
            
            zip_buffer.seek(0)
            
            st.divider()
            st.subheader("📥 Download Results")
            st.write(f"Total PDFs created: **{len(sorted_data)}**")
            
            st.download_button(
                label="📦 Download All Sorted PDFs (ZIP)",
                data=zip_buffer,
                file_name="Sorted_Labels_Master.zip",
                mime="application/zip",
                use_container_width=True
            )
            
            # Optional: Preview Table
            with st.expander("Show Detailed Sorting Summary"):
                summary_data = []
                for key, p_list in sorted_data.items():
                    parts = key.split('__')
                    summary_data.append({
                        "Courier": parts[0],
                        "Style": parts[1],
                        "Color": parts[2],
                        "Size": parts[3],
                        "Pages": len(p_list)
                    })
                st.dataframe(summary_data)

        except Exception as e:
            st.error(f"Error occurred: {e}")
