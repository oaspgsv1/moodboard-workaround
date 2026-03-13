import streamlit as st
import pandas as pd
import os
from backend import analyze_moodboard, generate_ai_moodboard 

# --- PAGE SETUP ---
st.set_page_config(page_title="Production Bible Generator", layout="wide")

# --- CUSTOM STYLING ---
st.markdown("""
    <style>
    .header-style { font-size: 22px; font-weight: bold; color: #1E1E1E; margin-top: 20px; }
    .sub-header-style { font-size: 18px; font-weight: 600; color: #444; margin-top: 10px; margin-bottom: 5px; }
    div[data-testid="stExpander"] details summary p { font-size: 1.1rem; font-weight: 600; }
    </style>
""", unsafe_allow_html=True)

# --- STATE MANAGEMENT ---
if 'generated_image_path' not in st.session_state:
    st.session_state.generated_image_path = None
if 'analysis_result' not in st.session_state:
    st.session_state.analysis_result = None

# --- MAIN APP ---
st.title("The Production Prop List Generator")
st.markdown("Generates an exhaustive, multi-scenario procurement list from a single moodboard.")

tab1, tab2 = st.tabs(["Upload existing Moodboard", "Generate AI Moodboard (Unsplash)"])

with tab1:
    st.header("Upload Creative Brief")
    uploaded_file = st.file_uploader("Upload Moodboard", type=["jpg", "png", "jpeg"])
    
    if uploaded_file is not None:
        # Show image in an expander to keep UI clean
        with st.expander("View Reference Image", expanded=False):
            st.image(uploaded_file, width=400)
        
        if st.button("Generate Detailed Manifest from Upload"):
            with st.status("Analyzing visual themes...", expanded=True) as status:
                st.write("Detecting sub-themes (Pastel, Dark, Lifestyle)...")
                result_data = analyze_moodboard(uploaded_file)
                st.session_state.analysis_result = result_data
                st.write("Calculating local market pricing...")
                status.update(label="Analysis Complete!", state="complete", expanded=False)

with tab2:
    st.header("Generate Moodboard from Keywords")
    st.markdown("Describe the vibe, lighting, or setting of your shoot. We'll pull high-quality real reference images from Unsplash to build a custom moodboard.")
    
    prompt = st.text_input("Vibe / Setting (e.g. 'cyberpunk neon desk setup', 'soft pastel studio flatlay')", "")
    
    if st.button("Generate Moodboard"):
        if prompt:
            with st.spinner("Fetching images and building collage..."):
                result = generate_ai_moodboard(prompt)
                if isinstance(result, dict) and "error" in result:
                    st.error(result["error"])
                else:
                    st.session_state.generated_image_path = result
                    st.success("Moodboard generated!")
        else:
            st.warning("Please enter a prompt first.")
            
    if st.session_state.generated_image_path and os.path.exists(st.session_state.generated_image_path):
        st.image(st.session_state.generated_image_path, caption="Generated Moodboard Collage", use_container_width=True)
        
        if st.button("Generate Detailed Manifest from AI Moodboard"):
            with st.status("Analyzing visual themes...", expanded=True) as status:
                st.write("Detecting sub-themes (Pastel, Dark, Lifestyle)...")
                result_data = analyze_moodboard(st.session_state.generated_image_path)
                st.session_state.analysis_result = result_data
                st.write("Calculating local market pricing...")
                status.update(label="Analysis Complete!", state="complete", expanded=False)

# --- RESULTS DISPLAY ---
# Display results if they exist in session state (regardless of which tab triggered it)
if st.session_state.analysis_result:
    result_data = st.session_state.analysis_result
            
    if "error" in result_data:
        st.error(f"Error: {result_data['error']}")
    else:
        # --- PARSE DATA FOR CSV (FLATTENING) ---
        flat_rows = []
        
        # --- DISPLAY LOOP ---
        categories = result_data.get("categories", [])
        
        # Create Tabs for the Main Categories to keep it organized
        # We map the categories to tabs dynamically
        tab_names = [cat['title'].split('.')[1].strip() if '.' in cat['title'] else cat['title'] for cat in categories]
        if tab_names:
            tabs = st.tabs(tab_names)
            
            total_est_cost = 0

            for i, category in enumerate(categories):
                with tabs[i]:
                    st.markdown(f"### {category['title']}")
                    
                    for subsection in category.get("subsections", []):
                        st.markdown(f"<div class='sub-header-style'>{subsection['name']}</div>", unsafe_allow_html=True)
                        
                        # Create a DataFrame for this specific subsection
                        items = subsection.get("items", [])
                        if items:
                            df_sub = pd.DataFrame(items)
                            
                            # Add to flat list for CSV export later
                            for item in items:
                                flat_rows.append({
                                    "Category": category['title'],
                                    "Sub-Theme": subsection['name'],
                                    "Item Name": item['name'],
                                    "Notes/Context": item.get('note', ''),
                                    "Source": item.get('source', 'Buy'),
                                    "Est. Price (INR)": item.get('price', 0)
                                })
                                total_est_cost += item.get('price', 0)

                            # Display Table
                            st.dataframe(
                                df_sub, 
                                column_config={
                                    "name": st.column_config.TextColumn("Item Name", width="large"),
                                    "note": "Context",
                                    "price": st.column_config.NumberColumn("INR Price", format="₹%d"),
                                    "source": "Action"
                                },
                                hide_index=True,
                                use_container_width=True
                            )

            # --- METRICS & EXPORT SECTION ---
            st.markdown("---")
            col1, col2 = st.columns([1, 2])
            
            with col1:
                 st.metric("Total Project Estimate", f"₹{total_est_cost:,.2f}")
            
            with col2:
                # Convert Flat List to Master CSV
                master_df = pd.DataFrame(flat_rows)
                csv = master_df.to_csv(index=False).encode('utf-8')
                
                st.download_button(
                    label="Download Full Production sheet (Excel/CSV)",
                    data=csv,
                    file_name="Master_Production_sheet.csv",
                    mime="text/csv",
                    type="primary"
                )