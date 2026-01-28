import streamlit as st
from utils.data_loader import load_latest_results
from components.charts import tier_distribution_chart, tags_frequency_chart, cost_vs_volume_chart
from components.metrics import display_kpis

st.set_page_config(page_title="Overview", page_icon="📊", layout="wide")

st.title("📊 Pipeline Overview")

# Load Data
df = load_latest_results()

if df.empty:
    st.warning("No data found. Please run the pipeline first or check outputs/ directory.")
else:
    # KPIs
    display_kpis(df)
    
    st.divider()
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Tier Distribution")
        tier_distribution_chart(df)
        
    with col2:
        st.subheader("Top Extracted Tags")
        tags_frequency_chart(df)
    
    st.divider()
    
    st.subheader("Cost & Performance Analysis")
    cost_vs_volume_chart(df)
