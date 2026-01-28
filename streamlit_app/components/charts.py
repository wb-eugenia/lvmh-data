"""
Reusable Plotly charts for the dashboard.
"""

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import streamlit as st

def tier_distribution_chart(df: pd.DataFrame):
    """Donut chart of Tier distribution."""
    if 'routing.tier' not in df.columns:
        return st.info("No tier data available")
        
    counts = df['routing.tier'].value_counts().reset_index()
    counts.columns = ['Tier', 'Count']
    counts['Tier'] = counts['Tier'].apply(lambda x: f"Tier {x}")
    
    fig = px.pie(
        counts, 
        values='Count', 
        names='Tier', 
        hole=0.4,
        color='Tier',
        color_discrete_map={
            'Tier 1': '#00CC96', # Green
            'Tier 2': '#636EFA', # Blue
            'Tier 3': '#EF553B'  # Red
        }
    )
    fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=300)
    return st.plotly_chart(fig, use_container_width=True)

def tags_frequency_chart(df: pd.DataFrame):
    """Bar chart of top tags."""
    # Extract all tags
    all_tags = []
    if 'extraction.tags' in df.columns:
        for tags in df['extraction.tags'].dropna():
            if isinstance(tags, list):
                all_tags.extend(tags)
    
    if not all_tags:
        return st.info("No tags data available")
        
    counts = pd.Series(all_tags).value_counts().head(15).reset_index()
    counts.columns = ['Tag', 'Count']
    
    fig = px.bar(
        counts,
        x='Count',
        y='Tag',
        orientation='h',
        color='Count',
        color_continuous_scale='Viridis'
    )
    fig.update_layout(yaxis={'categoryorder':'total ascending'}, margin=dict(t=0, b=0, l=0, r=0), height=400)
    return st.plotly_chart(fig, use_container_width=True)

def cost_vs_volume_chart(df: pd.DataFrame):
    """Scatter plot of Cost vs Confidence."""
    if 'cost_eur' not in df.columns or 'routing.confidence' not in df.columns:
        return
        
    # Ensure numeric types for plotting
    plot_df = df.copy()
    plot_df['processing_time_ms'] = pd.to_numeric(plot_df['processing_time_ms'], errors='coerce').fillna(10)
    plot_df['cost_eur'] = pd.to_numeric(plot_df['cost_eur'], errors='coerce').fillna(0)
    plot_df['routing.confidence'] = pd.to_numeric(plot_df['routing.confidence'], errors='coerce').fillna(0)
    
    fig = px.scatter(
        plot_df,
        x='routing.confidence',
        y='cost_eur',
        color='routing.tier',
        size='processing_time_ms',
        hover_data=['id'],
        title="Cost vs Confidence (Size = Latency)"
    )
    return st.plotly_chart(fig, use_container_width=True)
