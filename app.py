"""
LVMH Voice to Tag - Intelligence Dashboard
Streamlit web interface for tag extraction and analysis.
Powered by Mistral AI.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import ast
from pathlib import Path
from typing import Dict, List

from src.extractor import TagExtractor
from src.vectorizer import TagClassifier
from src.taxonomy import Taxonomy, load_taxonomy
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="LVMH Voice to Tag | Mistral AI",
    page_icon="👜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- LVMH CUSTOM STYLING ---
st.markdown("""
    <style>
    /* LVMH Dark Elegance */
    
    /* Typography */
    h1, h2, h3, h4, h5, h6, p, span, div, label, .stMarkdown {
        font-family: 'Helvetica Neue', sans-serif !important;
        font-weight: 300 !important;
        letter-spacing: 0.5px !important;
        color: #FAFAFA !important;
    }
    
    h1 {
        font-weight: 200 !important;
        letter-spacing: 1.5px !important;
        color: #D4AF37 !important; /* Gold Title */
    }
    
    /* Buttons - Gold Accent */
    .stButton>button {
        background-color: #D4AF37 !important;
        color: #0E1117 !important;
        border-radius: 2px !important;
        border: none !important;
        padding: 0.5rem 2rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        transition: all 0.3s ease !important;
    }
    
    .stButton>button:hover {
        background-color: #C5A028 !important;
        box-shadow: 0 4px 12px rgba(212, 175, 55, 0.2) !important;
    }
    
    /* Input Fields Integration */
    .stTextInput input, .stSelectbox [data-baseweb="select"] {
        background-color: #262730 !important;
        color: #FAFAFA !important;
        border-color: #4A4A4A !important;
    }
    
    /* JSON Viewer */
    [data-testid="stJson"], .stJson, pre[class*="json"] {
        background-color: #16181F !important;
        border: 1px solid #333 !important;
        border-radius: 8px !important;
        padding: 16px !important;
    }
    
    /* Sidebar Border */
    [data-testid="stSidebar"] {
        background-color: #262730 !important;
        border-right: 1px solid #333 !important;
    }
    
    /* Messages & Alerts - Dark Theme Friendly */
    .stAlert {
        background-color: #262730 !important;
        border: 1px solid #444 !important;
    }
    
    /* Success */
    .stSuccess, [data-testid="stSuccess"], .stAlert[data-baseweb="alert"] {
         color: #4CAF50 !important; 
    }
    /* Error */
    .stError {
        color: #FF5252 !important;
    }
    
    /* Hide Deploy Button */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- INITIALIZATION ---
@st.cache_resource
def load_components(api_key: str):
    """Load extractor and classifier with provided API key."""
    try:
        # Set environment variable for Mistral SDK
        os.environ["MISTRAL_API_KEY"] = api_key
        
        # Load Extractor (for generating tags)
        extractor = TagExtractor(
            taxonomy_path="config/taxonomy_v2.json",
            model="mistral-small-latest",
            api_key=api_key
        )
        
        # Load Classifier (for embeddings)
        classifier = TagClassifier(
            taxonomy_path="config/taxonomy_v2.json",
            model="mistral-embed",
            api_key=api_key
        )
        
        return extractor, classifier, None
    except Exception as e:
        return None, None, str(e)

# --- SIDEBAR ---
st.sidebar.title("👜 LVMH Voice to Tag")
st.sidebar.caption("Powered by Mistral AI")
st.sidebar.markdown("---")

# API Configuration
st.sidebar.subheader("🔑 Configuration")

# Check for .env API Key
# Force reload of environment variables
from dotenv import load_dotenv
load_dotenv(override=True)

env_api_key = os.getenv("MISTRAL_API_KEY", "").strip()

# Load pipeline
extractor = None
classifier = None
error_msg = None

if env_api_key:
    st.sidebar.success("Clé API chargée depuis .env")
    extractor, classifier, error_msg = load_components(env_api_key)
else:
    st.sidebar.error("⚠️ Clé MISTRAL_API_KEY manquante dans .env")
    st.sidebar.info("Veuillez configurer votre fichier .env")

if extractor and classifier:
    st.sidebar.success("✅ Pipeline Mistral Actif")
    st.sidebar.caption(f"Extraction: {extractor.model}")
    st.sidebar.caption(f"Embeddings: {classifier.model}")
    st.sidebar.caption(f"Taxonomie v2: {extractor.taxonomy.num_categories} catégories")
elif error_msg:
    st.sidebar.error(f"Erreur: {error_msg}")
else:
    st.sidebar.warning("Veuillez configurer votre clé API")

st.sidebar.markdown("---")

# Navigation
mode = st.sidebar.radio(
    "Navigation",
    ["Pipeline Complet", "🧪 Test Rapide", "Explorateur Taxonomie"],
    label_visibility="collapsed"
)

# --- PAGE 1: PIPELINE COMPLET ---
if mode == "Pipeline Complet":
    st.title("🚀 Pipeline Extraction & Embeddings")
    st.markdown("Extraction de tags factuels (Mistral Small) + Classification via Embeddings (Mistral Embed).")
    
    
    # Initialize session state for persistence
    if 'analysis_results' not in st.session_state:
        st.session_state.analysis_results = None
        
    uploaded_file = st.file_uploader("Importer un fichier CSV (avec colonne 'Transcription')", type=['csv'])
    
    # Reset button (only show if we have results)
    if st.session_state.analysis_results is not None:
        if st.button("🗑️ Nouvelle Analyse (Effacer Résultats)"):
            st.session_state.analysis_results = None
            st.rerun()

    
    # Logic to handle new analysis if file is present
    if uploaded_file and extractor and classifier:
        df = pd.read_csv(uploaded_file)
        
        # Identify text column
        possible_cols = ['Transcription', 'transcript', 'text', 'note', 'texte']
        text_col = next((col for col in possible_cols if col in df.columns), None)
        
        if text_col:
            # Show analysis button only if results are not already stored
            if st.session_state.analysis_results is None:
                st.info(f"Fichier chargé : {len(df)} entrées prêtes à l'analyse.")
                
                if st.button("🚀 Lancer l'Analyse"):
                    progress_bar = st.progress(0)
                    results_data = []
                    
                    for i, row in df.iterrows():
                        text = row[text_col]
                        if pd.isna(text):
                            continue
                            
                        # 1. Extraction (Mistral Small)
                        raw_tags = extractor.extract_tags_simple(text)
                        
                        # 2. Classification (Mistral Embed)
                        for tag in raw_tags:
                            classification = classifier.classify_tag(tag)
                            
                            results_data.append({
                                "Original_Transcript": text,
                                "Tag": tag,
                                "Category": classification['category'],
                                "Sub_Category": classification['sub_category'],
                                "Confidence": classification['score'],
                                "Status": classification.get('status', 'classified')
                            })
                        
                        progress_bar.progress((i + 1) / len(df))
                    
                    # Store Result DataFrame in Session State
                    st.session_state.analysis_results = pd.DataFrame(results_data)
                    st.success("Analyse terminée et sauvegardée en session !")
                    st.rerun()
    
    # --- VISUALIZATION SECTION (Persistent) ---
    # This section runs regardless of file uploader state, as long as we have results in session
    if st.session_state.analysis_results is not None and not st.session_state.analysis_results.empty:
        result_df = st.session_state.analysis_results
        
        st.markdown("---")
        st.subheader("📊 Répartition Hiérarchique Interactive")
        
        # LVMH Custom Color mapping
        color_map = {
            'CLIENT_PROFILE': '#D4AF37',  # Gold
            'PRODUCT': '#A58B5E',         # Muted Gold
            'OCCASION': '#4A4A4A',        # Dark Grey
            'PREFERENCES': '#8C8C8C',     # Medium Grey
            'BUDGET': '#E0E0E0',          # Light Grey
            'Uncategorized': '#FF5252'    # Alert Red
        }

        # Sunburst Chart with detailed interactivity
        fig = px.sunburst(
            result_df,
            path=['Category', 'Sub_Category', 'Tag'],
            values='Confidence',
            color='Category',
            color_discrete_map=color_map,
            title="<b>Taxonomie Dynamique LVMH</b><br><span style='font-size:14px;color:#888'>Cliquer pour explorer les segments</span>",
            hover_data={'Confidence': ':.2f'}
        )
        
        # Customizing layout for Dark Theme & Interactions
        fig.update_traces(
            hovertemplate="<b>%{label}</b><br>Score: %{value:.2f}<extra></extra>",
            textfont=dict(family="Helvetica Neue", size=14),
            insidetextorientation='radial'
        )
        
        fig.update_layout(
            height=750,
            margin=dict(t=60, l=10, r=10, b=10),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(family="Helvetica Neue", color="#FAFAFA"),
            title_font=dict(size=24, color="#D4AF37"),
            sunburstcolorway=['#D4AF37', '#2C3E50', '#E74C3C', '#ECF0F1', '#3498DB'], # Fallback palette
        )
        
        # Display with container width for responsiveness
        st.plotly_chart(fig, use_container_width=True)
        
        # Data Table
        st.subheader("📋 Résultats Détaillés")
        st.dataframe(result_df, use_container_width=True)
        
        # Download
        csv = result_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "Télécharger les résultats (CSV)",
            csv,
            "lvmh_mistral_results.csv",
            "text/csv"
        )
    elif st.session_state.analysis_results is not None:
         st.warning("Aucun tag n'a été extrait.")

# --- PAGE 2: TEST RAPIDE (PLAYGROUND) ---
elif mode == "🧪 Test Rapide":
    st.title("🧪 Playground & Debug")
    st.markdown("Testez l'extraction sur une phrase unique pour ajuster vos prompts.")
    
    # Input Area
    text_input = st.text_area(
        "Transcription à analyser",
        height=150,
        placeholder="Ex: Le client cherche un sac en cuir noir pour le travail, budget environ 2000 euros."
    )
    
    if st.button("⚡ Analyser le Texte") and text_input and extractor and classifier:
        with st.status("Analyse en cours...", expanded=True) as status:
            
            # 1. Extraction
            st.write("🤖 1. Extraction avec Mistral Small...")
            raw_tags = extractor.extract_tags_simple(text_input)
            st.write(f"✅ Tags bruts : `{raw_tags}`")
            
            # 2. Classification
            st.write("🧠 2. Classification Vectorielle...")
            results_data = []
            for tag in raw_tags:
                classification = classifier.classify_tag(tag)
                results_data.append({
                    "Tag": tag,
                    "Category": classification['category'],
                    "Sub_Category": classification['sub_category'],
                    "Confidence": classification['score'],
                    "Status": classification.get('status', 'classified')
                })
            
            status.update(label="Analyse terminée !", state="complete", expanded=False)
            
        # Results Display
        if results_data:
            res_df = pd.DataFrame(results_data)
            
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.subheader("📋 Classification")
                st.dataframe(res_df, use_container_width=True)
                
            with col2:
                st.subheader("📊 Visualisation")
                # Reuse Color Map
                color_map = {
                    'CLIENT_PROFILE': '#D4AF37', 'PRODUCT': '#A58B5E',
                    'OCCASION': '#4A4A4A', 'PREFERENCES': '#8C8C8C',
                    'BUDGET': '#E0E0E0', 'Uncategorized': '#FF5252'
                }
                
                fig = px.sunburst(
                    res_df,
                    path=['Category', 'Sub_Category', 'Tag'],
                    values='Confidence',
                    color='Category',
                    color_discrete_map=color_map,
                    hover_data={'Confidence': ':.2f'}
                )
                fig.update_layout(
                    height=400,
                    margin=dict(t=0, l=0, r=0, b=0),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(family="Helvetica Neue", color="#FAFAFA"),
                    sunburstcolorway=['#D4AF37', '#2C3E50', '#E74C3C', '#ECF0F1']
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Aucun tag n'a pu être extrait.")

# --- PAGE 3: EXPLORATEUR TAXONOMIE ---
elif mode == "Explorateur Taxonomie":
    st.title("🌳 Explorateur de Taxonomie v2")
    
    if classifier:
        # Load taxonomy data manually to display structure
        with open("config/taxonomy_v2.json", "r") as f:
            tax_data = json.load(f)
            
        categories = tax_data.get('categories', {})
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            selected_cat = st.selectbox("Catégorie Principale", list(categories.keys()))
            
            cat_data = categories[selected_cat]
            st.markdown(f"**Description**: {cat_data.get('description', '')}")
            
        with col2:
            st.subheader(f"Sous-catégories de {selected_cat}")
            subcats = cat_data.get('subcategories', {})
            
            for sub_name, sub_data in subcats.items():
                with st.expander(f"🔹 {sub_name}", expanded=True):
                    st.markdown(f"_{sub_data.get('description', '')}_")
                    
                    examples = sub_data.get('examples', [])
                    st.markdown(f"**Exemples**: {', '.join(examples)}")

    elif error_msg:
        st.error(f"Impossible de charger la taxonomie : {error_msg}")
    else:
        st.info("Veuillez configurer la clé API pour charger la taxonomie.")
