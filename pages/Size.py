import streamlit as st
import PyPDF2
import re
import io

st.set_page_config(page_title="PDF Sorter V3 (Final)", layout="wide")

st.title("🎯 Accurate PDF Sorter (Size + Qty Logic)")
st.markdown("""
**Logic V3:** Ye code SKU ki lambai se confuse nahi hoga. 
Ye **'Product Details'** ke neeche **Size aur Qty (Example: 'S 1' ya 'XL 1')** ke jod (pair) ko dhoondta hai.
""")

uploaded_file = st.file_uploader("Apni PDF File Upload Karein", type=["pdf"])

if uploaded_file is not None:
    st.success("File Received. Processing Started...")
    
    try:
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        total_pages = len(pdf_reader.pages)
        st.write(f"**Total Pages Detected:** {total_pages}")
        
        # Data Containers
        sorted_pages = {
            "S": [], "M": [], "L": [], "XL": [], "XXL": [], 
            "XS": [], "XXS": [], "3XL": [], "4XL": [], "5XL": [],
            "Free": [], "Unknown": []
        }
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # --- MAIN LOGIC ---
        for i, page in enumerate(pdf_reader.pages):
            text = page.extract_text()
            
            # Step 1: Sirf 'Product Details' ke baad ka hissa dekhein
            # (Taki Invoice section ka 'Size S' galti se na pakda jaye)
            split_text = text.split("Product Details")
            if len(split_text) > 1:
                relevant_text = split_text[1] # Sirf Product Details section
            else:
                relevant_text = text # Agar section nahi mila to poora page dekho
            
            # Step 2: Regex Jo Size + Qty ke pair ko dhoondta hai
            # Ye pattern kehta hai: "Size (S/M/L...) dhoondo jiske baad space/comma ho aur phir ek Number ho"
            # Pattern Explain:
            # \b         -> Word boundary (start of word)
            # (S|M|...)  -> Valid Sizes
            # \b         -> Word boundary
            # [\s,]* -> Beech mein Space ya Comma ho sakta hai
            # \d+        -> Phir Number (Qty) aana zaroori hai
            
            pattern = r'\b(S|M|L|XL|XXL|XS|XXS|3XL|4XL|5XL|Free)\b[\s,"]+(\d+)\b'
            
            match = re.search(pattern, relevant_text, re.IGNORECASE)
            
            found_size = "Unknown"
            if match:
                found_size = match.group(1).upper() # Size mil gaya (e.g., S)
                
                # Double Check: Agar 'Free' size hai to 'Free Size' handle karein
                if found_size == "FREE":
                    found_size = "Free Size"
            
            # Step 3: Store Data
            if found_size in sorted_pages:
                sorted_pages[found_size].append(page)
            elif found_size == "Free Size":
                 if "Free" not in sorted_pages: sorted_pages["Free"] = []
                 sorted_pages["Free"].append(page)
            else:
                # Agar list mein nahi hai (e.g. Free Size), to 'Unknown' ya naya key
                sorted_pages["Unknown"].append(page)
                
            # Progress Update
            if i % 50 == 0 or i == total_pages - 1:
                progress_bar.progress((i + 1) / total_pages)
                status_text.text(f"Scanning Page {i+1}/{total_pages}...")

        status_text.success("✅ Scanning Complete!")
        
        # --- DOWNLOAD SECTION ---
        st.write("---")
        
        # Grid Layout for Buttons
        cols = st.columns(4)
        col_idx = 0
        
        # Sirf wahi folder dikhao jisme pages hain
        for size, pages in sorted_pages.items():
            if pages:
                pdf_writer = PyPDF2.PdfWriter()
                for p in pages:
                    pdf_writer.add_page(p)
                
                output_pdf = io.BytesIO()
                pdf_writer.write(output_pdf)
                output_pdf.seek(0)
                
                with cols[col_idx % 4]:
                    st.download_button(
                        label=f"📂 Size {size} ({len(pages)})",
                        data=output_pdf,
                        file_name=f"Sorted_{size}.pdf",
                        mime="application/pdf"
                    )
                col_idx += 1
        
        # --- DEBUG SECTION (Agar abhi bhi galti ho) ---
        if len(sorted_pages["Unknown"]) > 0:
            st.error(f"{len(sorted_pages['Unknown'])} pages samajh nahi aaye. Neeche dekhein kyun:")
            with st.expander("Unknown Pages Analysis"):
                st.write("First Unknown Page Text:")
                st.text(sorted_pages["Unknown"][0].extract_text())

    except Exception as e:
        st.error(f"Error: {e}")