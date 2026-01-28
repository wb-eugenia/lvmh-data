"""
LVMH Voice to Tag - Intelligence Dashboard
Streamlit web interface for tag extraction and analysis.
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
from src.taxonomy import Taxonomy
from src.utils import detect_language

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="LVMH Voice to Tag | Intelligence Dashboard",
    page_icon="👜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- LVMH CUSTOM STYLING ---
st.markdown("""
    <style>
    /* Main theme - LVMH Minimalist */
    .main {
        background-color: #FAFAFA;
    }
    
    /* Typography */
    h1 {
        color: #000000;
        font-family: 'Helvetica Neue', sans-serif;
        font-weight: 300;
        letter-spacing: 1px;
    }
    
    h2, h3 {
        color: #333333;
        font-family: 'Helvetica Neue', sans-serif;
        font-weight: 300;
    }
    
    /* Buttons - LVMH Black */
    .stButton>button {
        background-color: #000000;
        color: white;
        border-radius: 0px;
        border: none;
        padding: 0.5rem 2rem;
        font-family: 'Helvetica Neue', sans-serif;
        font-weight: 500;
        letter-spacing: 0.5px;
        transition: all 0.3s ease;
    }
    
    .stButton>button:hover {
        background-color: #333333;
        border: none;
    }
    
    /* Metrics - Clean cards */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        color: #000000;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E0E0E0;
    }
    
    /* Tags display */
    .tag-badge {
        display: inline-block;
        background-color: #000000;
        color: white;
        padding: 4px 12px;
        margin: 4px;
        border-radius: 2px;
        font-size: 0.85rem;
        font-family: 'Helvetica Neue', sans-serif;
    }
    
    /* Info boxes */
    .stAlert {
        border-radius: 0px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- INITIALIZATION ---
@st.cache_resource
def load_extractor():
    """Load the tag extractor (cached for performance)."""
    try:
        extractor = TagExtractor(
            taxonomy_path="config/taxonomy_v1.json",
            model="gpt-4o-mini",
            temperature=0.0,
            cache_dir="cache"
        )
        return extractor, None
    except Exception as e:
        return None, str(e)

@st.cache_resource
def load_taxonomy():
    """Load taxonomy (cached)."""
    try:
        taxonomy = Taxonomy("config/taxonomy_v1.json")
        return taxonomy, None
    except Exception as e:
        return None, str(e)

# Load resources
extractor, extractor_error = load_extractor()
taxonomy, taxonomy_error = load_taxonomy()

# --- SIDEBAR ---
st.sidebar.title("🛠️ LVMH Voice to Tag")
st.sidebar.markdown("---")

# Status indicators
if extractor:
    st.sidebar.success("✅ Moteur IA chargé (v2.0)")
    st.sidebar.caption(f"Modèle: {extractor.model}")
    st.sidebar.caption(f"Taxonomie: {extractor.taxonomy.num_tags} tags | {extractor.taxonomy.num_categories} catégories")
else:
    st.sidebar.error(f"❌ Erreur: {extractor_error}")

st.sidebar.markdown("---")

# Navigation
mode = st.sidebar.radio(
    "Mode de navigation",
    ["🔍 Analyse en Direct", "📊 Dashboard Dataset", "⚙️ Configuration", "🌐 Espace Client 3D"],
    label_visibility="collapsed"
)

st.sidebar.markdown("---")
st.sidebar.caption("LVMH Fashion & Leather Goods")
st.sidebar.caption("Janvier 2026 • v2.0")

# --- PAGE 1: LIVE ANALYSIS ---
if mode == "🔍 Analyse en Direct":
    st.title("🔍 Analyse de Transcription Unitaire")
    st.markdown("Testez l'extraction de tags sur une note vocale spécifique.")
    st.markdown("---")
    
    if not extractor:
        st.error("Le moteur d'extraction n'est pas disponible. Vérifiez votre configuration.")
    else:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Language selector with explicit handling
            language = st.selectbox(
                "Langue de la transcription",
                ["FR", "EN", "IT", "ES", "DE"],
                index=0,
                help="Sélectionnez la langue pour optimiser l'extraction"
            )
            
            text_input = st.text_area(
                "Saisissez une note vocale transcrite :",
                height=250,
                placeholder="Ex: Cliente VIC très intéressée par la nouvelle collection Capucines. Elle pratique le golf régulièrement et cherche un cadeau d'anniversaire pour son mari qui collectionne les montres..."
            )
            
            analyze_btn = st.button("🚀 Lancer l'extraction", use_container_width=True)
        
        with col2:
            st.markdown("### 💡 Conseils")
            st.info(
                "**Notes efficaces contiennent:**\n"
                "- Intérêts et hobbies\n"
                "- Occasions d'achat\n"
                "- Préférences produits\n"
                "- Budget mentionné\n"
                "- Allergies/régimes"
            )
        
        if analyze_btn and text_input:
            with st.spinner('🤖 Analyse sémantique en cours via GPT-4o-mini...'):
                # Call extractor with explicit language parameter
                result = extractor.extract(
                    transcription=text_input,
                    language=language,  # Pass explicitly
                    client_id=None,
                    use_cache=False  # Live analysis = always fresh
                )
            
            # Display results
            st.markdown("---")
            st.subheader("📋 Résultats de l'Extraction")
            
            col_r1, col_r2, col_r3 = st.columns(3)
            
            with col_r1:
                st.metric(
                    "Score de Confiance",
                    f"{result.get('confidence', 0)*100:.0f}%",
                    help="Fiabilité de l'extraction"
                )
            
            with col_r2:
                budget = result.get('budget_range', 'Non détecté')
                st.metric("Budget Range", budget)
            
            with col_r3:
                status = result.get('client_status', 'Non détecté')
                st.metric("Statut Client", status)
            
            # Tags display (premium styling)
            st.markdown("### 🏷️ Tags Identifiés")
            tags = result.get('tags', [])
            
            if tags:
                # Group tags by category for better visualization
                tags_by_cat = {}
                for tag in tags:
                    cat = taxonomy.get_category_for_tag(tag)
                    if cat:
                        if cat not in tags_by_cat:
                            tags_by_cat[cat] = []
                        tags_by_cat[cat].append(tag)
                
                for category, cat_tags in tags_by_cat.items():
                    with st.expander(f"**{category}** ({len(cat_tags)} tags)", expanded=True):
                        tags_html = "".join([f'<span class="tag-badge">🏷️ {tag}</span>' for tag in cat_tags])
                        st.markdown(tags_html, unsafe_allow_html=True)
            else:
                st.warning("Aucun tag détecté dans cette transcription.")
            
            # Additional info
            col_a1, col_a2 = st.columns(2)
            
            with col_a1:
                # Allergies with severity
                allergies = result.get('allergies', [])
                severity_map = result.get('allergy_severity', {})
                
                if allergies:
                    st.warning("⚠️ **Allergies & Santé**")
                    for allergy in allergies:
                        severity = severity_map.get(allergy, 'moderate')
                        st.markdown(f"- **{allergy}** (Sévérité: `{severity}`)")
                
                if result.get('dietary'):
                    st.info(f"🥗 **Régimes alimentaires:** {', '.join(result['dietary'])}")
            
            with col_a2:
                # Relationship Context
                rel_context = result.get('relationship_context', {})
                shopping_with = rel_context.get('shopping_with', [])
                gift_for = rel_context.get('gift_for', [])
                
                if shopping_with or gift_for:
                    st.success("👥 **Contexte Relationnel**")
                    if shopping_with:
                        st.markdown(f"**Accompagné(e) de:** {', '.join(shopping_with)}")
                    if gift_for:
                        st.markdown(f"**Cadeau pour:** {', '.join(gift_for)}")
                
                if result.get('profession'):
                    st.caption(f"👔 **Profession:** {result['profession']}")
                
                if result.get('referral_potential'):
                    st.caption(f"📢 **Potentiel référent:** {result['referral_potential']}")
            
            # Reasoning
            if result.get('reasoning'):
                with st.expander("🧠 Raisonnement du modèle"):
                    st.write(result['reasoning'])
            
            # Full JSON output
            with st.expander("📄 Structure JSON complète"):
                st.json(result)

# --- PAGE 2: DATASET DASHBOARD ---
elif mode == "📊 Dashboard Dataset":
    st.title("📊 Vue d'ensemble du Dataset")
    st.markdown("Analysez les résultats d'extraction en batch.")
    st.markdown("---")
    
    # File uploader
    uploaded_file = st.file_uploader(
        "Charger un fichier de résultats",
        type=["csv", "xlsx"],
        help="Fichier généré par run_extraction.py"
    )
    
    df = None
    
    # Try to load file
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            st.success(f"✅ Fichier chargé: {uploaded_file.name}")
        except Exception as e:
            st.error(f"Erreur de chargement: {e}")
    else:
        # Auto-load default output if exists
        default_path = "outputs/wave1_tagged_dataset.xlsx"
        if os.path.exists(default_path):
            try:
                df = pd.read_excel(default_path)
                st.info(f"📂 Fichier chargé automatiquement: {default_path}")
            except Exception as e:
                st.warning(f"Impossible de charger le fichier par défaut: {e}")
    
    if df is not None:
        # --- CRITICAL: Parse list columns (Point de vigilance #1) ---
        list_columns = ['tags', 'invalid_tags', 'dietary', 'allergies']
        for col in list_columns:
            if col in df.columns:
                # Convert string representation of lists to actual lists
                df[col] = df[col].apply(lambda x: 
                    ast.literal_eval(x) if isinstance(x, str) and x.startswith('[') 
                    else (x if isinstance(x, list) else [])
                )
        
        # --- KPIs ---
        st.subheader("📈 Indicateurs Clés")
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        
        with kpi1:
            st.metric("Notes Analysées", len(df))
        
        with kpi2:
            if 'confidence' in df.columns:
                avg_conf = df['confidence'].mean()
                st.metric("Confiance Moyenne", f"{avg_conf:.1%}")
            else:
                st.metric("Confiance Moyenne", "N/A")
        
        with kpi3:
            if 'tags' in df.columns:
                total_tags = df['tags'].apply(lambda x: len(x) if isinstance(x, list) else 0).sum()
                st.metric("Tags Extraits", f"{total_tags:,}")
            else:
                st.metric("Tags Extraits", "N/A")
        
        with kpi4:
            if 'num_tags' in df.columns:
                avg_tags = df['num_tags'].mean()
                st.metric("Tags Moy./Note", f"{avg_tags:.1f}")
            else:
                st.metric("Tags Moy./Note", "N/A")
        
        st.markdown("---")
        
        # --- FILTERS ---
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            search_query = st.text_input(
                "🔍 Rechercher dans les transcriptions",
                placeholder="Ex: golf, montres..."
            )
        
        with col_f2:
            if 'Language' in df.columns:
                lang_filter = st.multiselect(
                    "Filtrer par langue",
                    options=df['Language'].unique(),
                    default=None
                )
                if lang_filter:
                    df = df[df['Language'].isin(lang_filter)]
        
        if search_query and 'Transcription' in df.columns:
            df = df[df['Transcription'].str.contains(search_query, case=False, na=False)]
        
        # --- DATA TABLE ---
        st.subheader("📋 Données Complètes")
        
        # Configure column display
        column_config = {}
        if 'tags' in df.columns:
            column_config['tags'] = st.column_config.ListColumn("Tags Identifiés")
        if 'confidence' in df.columns:
            column_config['confidence'] = st.column_config.ProgressColumn(
                "Confiance",
                format="%.2f",
                min_value=0,
                max_value=1
            )
        
        st.dataframe(
            df,
            use_container_width=True,
            column_config=column_config,
            height=400
        )
        
        st.markdown("---")
        
        # --- VISUALIZATIONS (Premium Plotly - Point de vigilance #3) ---
        st.subheader("📊 Visualisations")
        
        viz_col1, viz_col2 = st.columns(2)
        
        with viz_col1:
            # Tag frequency analysis
            st.markdown("#### Distribution des Tags")
            
            if 'tags' in df.columns:
                # Flatten all tags
                all_tags = []
                for tags_list in df['tags']:
                    if isinstance(tags_list, list):
                        all_tags.extend(tags_list)
                
                if all_tags:
                    tag_counts = pd.Series(all_tags).value_counts().head(15)
                    
                    # Premium Plotly bar chart with tooltips
                    fig_tags = px.bar(
                        x=tag_counts.values,
                        y=tag_counts.index,
                        orientation='h',
                        labels={'x': 'Fréquence', 'y': 'Tag'},
                        title="Top 15 Tags les Plus Fréquents"
                    )
                    fig_tags.update_traces(
                        marker_color='#000000',
                        hovertemplate='<b>%{y}</b><br>Fréquence: %{x}<extra></extra>'
                    )
                    fig_tags.update_layout(
                        showlegend=False,
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        font=dict(family='Helvetica Neue', color='#333333')
                    )
                    st.plotly_chart(fig_tags, use_container_width=True)
                else:
                    st.info("Aucun tag à visualiser")
            else:
                st.warning("Colonne 'tags' non trouvée")
        
        with viz_col2:
            # Confidence distribution
            st.markdown("#### Distribution de la Confiance")
            
            if 'confidence' in df.columns:
                fig_conf = px.histogram(
                    df,
                    x='confidence',
                    nbins=20,
                    labels={'confidence': 'Score de Confiance', 'count': 'Nombre de Notes'},
                    title="Répartition des Scores de Confiance"
                )
                fig_conf.update_traces(
                    marker_color='#000000',
                    hovertemplate='Confiance: %{x:.0%}<br>Notes: %{y}<extra></extra>'
                )
                fig_conf.update_layout(
                    showlegend=False,
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(family='Helvetica Neue', color='#333333')
                )
                st.plotly_chart(fig_conf, use_container_width=True)
            else:
                st.warning("Colonne 'confidence' non trouvée")
        
        # Category distribution (full width)
        st.markdown("#### Distribution par Catégorie")
        
        if 'tags' in df.columns and taxonomy:
            # Count tags by category
            category_counts = {}
            for tags_list in df['tags']:
                if isinstance(tags_list, list):
                    for tag in tags_list:
                        cat = taxonomy.get_category_for_tag(tag)
                        if cat:
                            category_counts[cat] = category_counts.get(cat, 0) + 1
            
            if category_counts:
                fig_cat = px.pie(
                    values=list(category_counts.values()),
                    names=list(category_counts.keys()),
                    title="Répartition des Tags par Catégorie",
                    hole=0.4  # Donut chart for elegance
                )
                fig_cat.update_traces(
                    textposition='inside',
                    textinfo='percent+label',
                    hovertemplate='<b>%{label}</b><br>Tags: %{value}<br>%{percent}<extra></extra>',
                    marker=dict(colors=px.colors.sequential.gray[::-1])
                )
                fig_cat.update_layout(
                    font=dict(family='Helvetica Neue', color='#333333')
                )
                st.plotly_chart(fig_cat, use_container_width=True)
        
    else:
        # No data loaded
        st.info(
            "👆 **Aucun dataset chargé**\n\n"
            "Pour charger des données:\n"
            "1. Uploadez un fichier Excel/CSV généré par le pipeline\n"
            "2. Ou lancez `python scripts/run_extraction.py` pour générer des résultats"
        )

# --- PAGE 3: CONFIGURATION ---
elif mode == "⚙️ Configuration":
    st.title("⚙️ Configuration & Taxonomie")
    st.markdown("Visualisation de la structure de tags.")
    st.markdown("---")
    
    if taxonomy:
        # Metadata
        st.subheader("📋 Métadonnées")
        col_m1, col_m2, col_m3 = st.columns(3)
        
        with col_m1:
            st.metric("Version", taxonomy.version)
        with col_m2:
            st.metric("Catégories", taxonomy.num_categories)
        with col_m3:
            st.metric("Tags Total", taxonomy.num_tags)
        
        st.markdown("---")
        
        # Taxonomy structure
        st.subheader("🏗️ Structure de la Taxonomie")
        
        # Load raw taxonomy
        with open('config/taxonomy_v1.json', 'r', encoding='utf-8') as f:
            tax_data = json.load(f)
        
        # Display by category with expandable sections
        for category_name in taxonomy.get_categories():
            tags = taxonomy.get_tags_by_category(category_name)
            category_data = tax_data['categories'][category_name]
            
            with st.expander(f"**{category_name}** ({len(tags)} tags)", expanded=False):
                st.caption(category_data.get('description', ''))
                
                # Display tags in columns for better layout
                num_cols = 3
                cols = st.columns(num_cols)
                
                for idx, tag in enumerate(tags):
                    with cols[idx % num_cols]:
                        st.markdown(f"• `{tag}`")
        
        st.markdown("---")
        
        # Full JSON view
        with st.expander("📄 Fichier JSON Complet"):
            st.json(tax_data)
    
    else:
        st.error(f"Impossible de charger la taxonomie: {taxonomy_error}")

# --- PAGE 4: 3D CLIENT SPACE ---
elif mode == "🌐 Espace Client 3D":
    st.title("🌐 Espace Client 3D")
    st.markdown("Visualisation sémantique de la base client.")
    st.markdown("---")
    
    # Check if dataset is loaded
    default_path = "outputs/wave1_tagged_dataset.xlsx"
    df = None
    
    if os.path.exists(default_path):
        try:
            df = pd.read_excel(default_path)
            # Parse tags if needed
            if 'tags' in df.columns:
                df['tags'] = df['tags'].apply(lambda x: 
                    ast.literal_eval(x) if isinstance(x, str) and x.startswith('[') 
                    else (x if isinstance(x, list) else [])
                )
        except Exception as e:
            st.error(f"Erreur chargement dataset: {e}")
    
    if df is None:
        st.warning("⚠️ Veuillez d'abord générer ou charger un dataset (Page Dashboard).")
    else:
        st.info(f"""
        **Concept:** Cette visualisation projette chaque client dans un espace 3D basé sur le contenu de ses notes.
        - Les points proches = clients aux profils similaires
        - Les couleurs = clusters automatiques ou confiance
        """)
        
        col_ctrl1, col_ctrl2 = st.columns([1, 2])
        
        with col_ctrl1:
            st.subheader("Paramètres")
            n_clusters = st.slider("Nombre de Clusters (Profils)", 2, 10, 6)
            
            # Estimate time
            est_time = len(df) * 0.15
            st.caption(f"Temps estimé: ~{est_time:.1f}s")
            
            generate_btn = st.button("🚀 Générer l'Espace 3D", use_container_width=True)
            
        with col_ctrl2:
            if generate_btn:
                with st.spinner("🧠 Analyse sémantique en cours (Embeddings + UMAP + KMeans)..."):
                    try:
                        from src.embedding_viz import EmbeddingVisualizer
                        
                        viz = EmbeddingVisualizer()
                        
                        # 1. Embeddings (Cached)
                        embeddings = viz.generate_embeddings(df)
                        
                        # 2. UMAP
                        coords = viz.reduce_dimensions(embeddings)
                        
                        # 3. Clustering
                        clusters = viz.discover_profiles(embeddings, n_clusters=n_clusters)
                        
                        # 4. Viz
                        fig = viz.create_interactive_viz(df, coords, clusters)
                        
                        # 5. Insights
                        insights = viz.analyze_cluster_characteristics(df, clusters)
                        
                        # Save to session state to persist
                        st.session_state['viz_fig'] = fig
                        st.session_state['viz_insights'] = insights
                        st.session_state['viz_generated'] = True
                        
                    except Exception as e:
                        st.error(f"Erreur lors de la génération: {str(e)}")
                        import traceback
                        st.code(traceback.format_exc())
        
        # Display results if generated
        if st.session_state.get('viz_generated'):
            st.markdown("---")
            st.plotly_chart(st.session_state['viz_fig'], use_container_width=True)
            
            # Download button
            with open("outputs/client_space_3d.html", "rb") as f:
                st.download_button(
                    "📥 Télécharger la vue interactive (HTML)",
                    f,
                    "client_space_3d.html",
                    "text/html"
                )
            
            # Cluster Insights
            st.markdown("### 🔍 Analyse des Profils Découverts")
            
            insights = st.session_state['viz_insights']
            cols = st.columns(3)
            
            for idx, (name, data) in enumerate(insights.items()):
                with cols[idx % 3]:
                    with st.container(border=True):
                        st.markdown(f"#### {name}")
                        st.caption(f"{data['size']} clients")
                        
                        st.markdown("**Tags Dominants:**")
                        for tag, count in data['top_tags'].items():
                            st.markdown(f"- {tag} ({count})")
                            
                        st.markdown(f"**Budget:** {data['dominant_budget']}")
                        st.progress(data['avg_confidence'], text=f"Confiance: {data['avg_confidence']:.0%}")
