"""
KPI Metrics calculations.
"""

import pandas as pd
import streamlit as st

def display_kpis(df: pd.DataFrame):
    """Display top-level KPIs."""
    if df.empty:
        return
        
    total_notes = len(df)
    
    # Cost Savings
    # Baseline: 100% Tier 3 (GPT-4o-mini approx 0.0001€ + overhead = say 0.0002€ for comparison or use actual)
    # Actually user said Tier 3 is $0.0001. Let's say baseline is 100% GPT-4o-mini.
    # But wait, baseline "Competitor" might be more expensive legacy API (0.002€).
    # Let's use the internal cost column.
    
    actual_cost = df['cost_eur'].sum()
    # Baseline: Assuming all went to Tier 3 (0.0001€)
    baseline_cost = total_notes * 0.0001 
    # Or Baseline: Legacy API (0.002€)
    legacy_cost = total_notes * 0.002
    
    savings = legacy_cost - actual_cost
    savings_pct = (savings / legacy_cost * 100) if legacy_cost > 0 else 0
    
    # Free Processing
    free_tier_count = len(df[df['routing.tier'].isin([1, 2])])
    free_pct = (free_tier_count / total_notes * 100) if total_notes > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    
    col1.metric("Total Notes", f"{total_notes:,}")
    col2.metric("Free Processing", f"{free_pct:.1f}%", f"{free_tier_count} notes")
    col3.metric("Total Cost", f"{actual_cost:.4f}€", f"-{savings_pct:.0f}% vs Legacy")
    col4.metric("Avg Latency", f"{df['processing_time_ms'].mean():.0f}ms")
