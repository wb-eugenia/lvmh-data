import streamlit as st
from utils.data_loader import load_latest_results

st.set_page_config(
    page_title="LVMH Voice-to-Tag Dashboard",
    page_icon="🏷️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🚀 LVMH Voice-to-Tag Pipeline Dashboard")

st.markdown("""
### **Extension MaIA LVMH** - Multi-Tier Hybrid Pipeline

Transforme notes vocales CA → Tags CRM structurés avec RGPD contextuel.

#### 🏗️ Architecture
- **Tier 1 (Rules)**: Regex ultra-rapide (0€)
- **Tier 2 (Local)**: Ollama Qwen 2.5 (0€)
- **Tier 3 (Cloud)**: GPT-4o-mini (Fallback sécurité)

#### 🧭 Navigation
Utilisez la barre latérale pour naviguer :
- **📊 Overview**: KPIs et distribution
- **🔍 Explorer**: Fouille de données
- **🧪 Simulator**: Test temps réel
- **🛡️ RGPD**: Conformité et Privacy
- **💰 Cost**: Analyse ROI
""")

# Sidebar
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/d/d0/LVMH_Logo.svg/1200px-LVMH_Logo.svg.png", width=150)
    
    st.markdown("### 📊 Quick Stats")
    
    # Load latest results
    df = load_latest_results()
    
    if not df.empty:
        st.metric("Notes Processed", len(df))
        st.metric("Précision Globale", f"{df['routing.confidence'].mean():.0%}")
        st.metric("Coût Total", f"{df['cost_eur'].sum():.4f}€")
    else:
        st.warning("No data loaded")
    
    st.divider()
    
    st.markdown("### ⚙️ Settings")
    
    dataset = st.selectbox("Dataset", [
        "Wave 2 (300 notes)",
        "Wave 1 (100 notes)",
        "Custom Upload"
    ])
    
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()
