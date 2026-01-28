import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Cost & ROI", page_icon="💰", layout="wide")

st.title("💰 Cost & ROI Dashboard")

# Cost Breakdown
st.subheader("Cost Distribution by Tier")
cost_data = {
    'Tier': ['Tier 1 (Rules)', 'Tier 2 (Ollama)', 'Tier 3 (GPT)'],
    'Notes': [90, 161, 49], # Example data matching user request
    'Cost per Note': [0, 0, 0.0001],
    'Total Cost': [0, 0, 4.9]
}
cost_df = pd.DataFrame(cost_data)

fig = px.sunburst(
    cost_df,
    path=['Tier'],
    values='Notes',
    color='Total Cost',
    title='Cost Distribution by Tier (Color = Cost)'
)
st.plotly_chart(fig, use_container_width=True)

st.divider()

# Projection
st.subheader("📈 Projection Annuelle (68M notes)")

projection = pd.DataFrame({
    'Solution': ['100% GPT-4o', '100% NLP Local', 'Notre Hybride'],
    'Coût Annuel (€)': [6800, 1900, 2600],
    'Précision (%)': [94, 78, 87],
    'RGPD FP (%)': [3, 45, 2.7]
})

fig2 = px.scatter(
    projection,
    x='Précision (%)',
    y='Coût Annuel (€)',
    size='RGPD FP (%)',
    color='Solution',
    title='Coût vs Précision vs RGPD (Taille = Faux Positifs)',
    size_max=60
)
st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ROI Calculator
st.subheader("🎯 ROI Business Case")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Coût Pipeline", "2,600€/an")
    
with col2:
    ventes_additionnelles = st.slider(
        "Ventes VIC additionnelles/jour grâce CRM enrichi",
        min_value=0,
        max_value=10,
        value=1
    )
    
with col3:
    panier_moyen = st.number_input(
        "Panier moyen VIC (€)",
        value=15000,
        step=1000
    )

revenue_annuel = ventes_additionnelles * panier_moyen * 365
roi = (revenue_annuel - 2600) / 2600 * 100 if revenue_annuel > 0 else 0

st.success(f"""
### 💰 ROI Calculé

- **Revenue annuel**: {revenue_annuel:,.0f}€
- **Coût pipeline**: 2,600€
- **Profit net**: {revenue_annuel - 2600:,.0f}€
- **ROI**: {roi:,.0f}%

**Breakeven**: Atteint en {2600 / (ventes_additionnelles * panier_moyen) if ventes_additionnelles > 0 else 0:.1f} jours
""")
