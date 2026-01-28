import streamlit as st
from utils.data_loader import load_latest_results

st.set_page_config(page_title="Data Explorer", page_icon="🔍", layout="wide")

st.title("🔍 Data Explorer")

df = load_latest_results()

if df.empty:
    st.warning("No data found.")
else:
    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        tier_filter = st.multiselect("Filter by Tier", [1, 2, 3], default=[1, 2, 3])
    with col2:
        search = st.text_input("Search in Text", "")
    with col3:
        show_sensitive = st.checkbox("Show Only Sensitive (RGPD)", value=False)
    
    # Apply filters
    filtered_df = df[df['routing.tier'].isin(tier_filter)]
    if search:
        filtered_df = filtered_df[filtered_df['original_text'].str.contains(search, case=False, na=False)]
    if show_sensitive and 'rgpd.contains_sensitive' in df.columns:
        filtered_df = filtered_df[filtered_df['rgpd.contains_sensitive'] == True]
        
    st.markdown(f"**Showing {len(filtered_df)} notes**")
    
    # Main Table
    st.dataframe(
        filtered_df[['id', 'routing.tier', 'routing.confidence', 'original_text', 'extraction.tags']],
        use_container_width=True,
        height=400
    )
    
    # Detail View
    st.divider()
    st.subheader("📝 Note Details")
    
    selected_id = st.selectbox("Select Note ID to inspect", filtered_df['id'].unique())
    
    if selected_id:
        row = filtered_df[filtered_df['id'] == selected_id].iloc[0]
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### Original Text")
            st.info(row['original_text'])
            
            st.markdown("### Extraction")
            st.write(row['extraction.tags'])
            
        with col2:
            st.markdown("### Metadata")
            st.json({
                'Tier': int(row['routing.tier']),
                'Confidence': row['routing.confidence'],
                'Processing Time': f"{row['processing_time_ms']:.1f}ms",
                'RGPD Sensitive': row.get('rgpd.contains_sensitive', False)
            })
            
            if 'rgpd.anonymized_text' in row and row['rgpd.anonymized_text']:
                st.markdown("### Anonymized Text")
                st.text(row['rgpd.anonymized_text'])
