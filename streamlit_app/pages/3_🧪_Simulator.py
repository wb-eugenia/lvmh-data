import asyncio
import time
import streamlit as st
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from src.pipeline_async import AsyncPipeline
from utils.competitor import competitor

st.set_page_config(page_title="Simulator", page_icon="🧪", layout="wide")

st.title("🧪 Real-time Simulator")

# Initialize Pipeline (Cached)
@st.cache_resource
def get_pipeline():
    return AsyncPipeline(use_cache=True)

pipeline = get_pipeline()

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Input")
    
    # Presets
    PRESETS = {
        "Custom...": "",
        "Note Simple (Tier 1)": "Je cherche un sac noir, budget 2000 euros.",
        "Note VIC Complexe (Tier 3)": "Client VIC M. Arnault. Cadeau pour sa fille. Attention allergie sévère aux noix. Budget illimité.",
        "Note RGPD Sensible": "La cliente est en rémission de cancer, elle veut une écharpe douce.",
        "Note Budget Implicite": "Je veux quelque chose de pas trop cher, moins de 5k."
    }
    
    preset_name = st.selectbox("Exemples préconfigurés", list(PRESETS.keys()))
    default_text = PRESETS[preset_name]
    
    note_input = st.text_area(
        "Note vocale client",
        value=default_text,
        height=150,
        placeholder="Ex: Cliente cherche sac cuir vegan..."
    )
    
    process_btn = st.button("🚀 Analyser Note", type="primary")

with col2:
    st.subheader("Configuration")
    show_competitor = st.checkbox("Comparer avec concurrent", value=True)
    show_debug = st.checkbox("Debug Mode", value=True)

if process_btn and note_input:
    with st.spinner("⚙️ Processing..."):
        # Run Async Pipeline
        # We need a new event loop for Streamlit
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(pipeline.process_note({'ID': 'SIM_001', 'Transcription': note_input, 'Language': 'FR'}))
            loop.close()
        except Exception as e:
            st.error(f"Pipeline Error: {e}")
            result = None

        # Run Competitor
        if show_competitor:
            comp_result = competitor.process(note_input)

    if result:
        st.divider()
        
        # Top Metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Tier Utilisé", f"Tier {result.routing.tier}")
        m2.metric("Confidence", f"{result.routing.confidence:.0%}")
        m3.metric("Temps", f"{result.processing_time_ms:.0f}ms")
        
        # Calculate cost
        cost = 0.0
        if result.routing.tier == 3: cost = 0.0001
        m4.metric("Coût", f"{cost:.4f}€")
        
        # Tabs
        t1, t2, t3 = st.tabs(["🏷️ Tags & Data", "⚔️ Comparaison", "🔍 Debug"])
        
        with t1:
            st.subheader("Tags Extraits")
            st.write(result.extraction.tags)
            
            if result.extraction.budget_range:
                st.info(f"💰 Budget: {result.extraction.budget_range}")
                
            if result.extraction.allergies:
                st.error(f"⚠️ Allergies: {result.extraction.allergies} (Severity: {result.extraction.allergy_severity})")
                
            if result.rgpd.contains_sensitive:
                st.warning(f"🛡️ RGPD Sensitive Data Detected: {result.rgpd.categories_detected}")
                st.text_area("Anonymized Text", result.rgpd.anonymized_text)

        with t2:
            if show_competitor:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("### 🟢 Notre Pipeline")
                    st.json(json.loads(result.json()))
                with c2:
                    st.markdown("### 🔴 Concurrent")
                    st.json(comp_result)
                    
        with t3:
            if show_debug:
                st.json(json.loads(result.json()))
import json
