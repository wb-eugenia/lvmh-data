"""
Results router - Browse and filter extraction results.
"""

import os
import sys
import logging
from typing import Optional, List
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Query, HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from api.schemas import PaginatedResults, ExtractionResult, ExtractionTags, RoutingInfo, RGPDInfo

logger = logging.getLogger("lvmh-api.results")
router = APIRouter()

# Default outputs directory
OUTPUTS_DIR = Path(__file__).parent.parent.parent / "outputs"


def load_latest_results() -> pd.DataFrame:
    """Load the most recent results file."""
    
    if not OUTPUTS_DIR.exists():
        return pd.DataFrame()
    
    # Find most recent file
    files = list(OUTPUTS_DIR.glob("*.csv")) + list(OUTPUTS_DIR.glob("*.xlsx"))
    
    if not files:
        return pd.DataFrame()
    
    latest = max(files, key=lambda f: f.stat().st_mtime)
    
    try:
        if latest.suffix == '.csv':
            return pd.read_csv(latest)
        else:
            return pd.read_excel(latest)
    except Exception as e:
        logger.error(f"Failed to load results: {e}")
        return pd.DataFrame()


def parse_list_column(val):
    """Parse string list columns."""
    import ast
    if isinstance(val, list):
        return val
    if pd.isna(val) or val == '':
        return []
    try:
        return ast.literal_eval(val)
    except:
        return []


@router.get("/results", response_model=PaginatedResults)
async def get_results(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tier: Optional[int] = Query(None, ge=1, le=3),
    search: Optional[str] = None,
    sensitive_only: bool = False
):
    """
    Get paginated extraction results with optional filters.
    """
    
    df = load_latest_results()
    
    if df.empty:
        return PaginatedResults(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
            total_pages=0
        )
    
    # Parse list columns
    for col in ['tags', 'extraction.tags']:
        if col in df.columns:
            df[col] = df[col].apply(parse_list_column)
    
    # Apply filters
    if tier and 'routing.tier' in df.columns:
        df = df[df['routing.tier'] == tier]
    
    if search:
        text_col = 'original_text' if 'original_text' in df.columns else 'Transcription'
        if text_col in df.columns:
            df = df[df[text_col].str.contains(search, case=False, na=False)]
    
    if sensitive_only and 'rgpd.contains_sensitive' in df.columns:
        df = df[df['rgpd.contains_sensitive'] == True]
    
    # Pagination
    total = len(df)
    total_pages = (total + page_size - 1) // page_size
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    
    page_df = df.iloc[start_idx:end_idx]
    
    # Convert to response models
    items = []
    for _, row in page_df.iterrows():
        items.append(ExtractionResult(
            id=str(row.get('id', row.get('ID', ''))),
            tags=row.get('extraction.tags', row.get('tags', [])),
            extraction=ExtractionTags(),
            routing=RoutingInfo(
                tier=int(row.get('routing.tier', 1)),
                confidence=float(row.get('routing.confidence', 0))
            ),
            rgpd=RGPDInfo(
                contains_sensitive=bool(row.get('rgpd.contains_sensitive', False))
            ),
            processing_time_ms=float(row.get('processing_time_ms', 0)),
            cache_hit=bool(row.get('cache_hit', False))
        ))
    
    return PaginatedResults(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/results/{note_id}")
async def get_result_detail(note_id: str):
    """Get full details for a specific note."""
    
    df = load_latest_results()
    
    if df.empty:
        raise HTTPException(404, "No results found")
    
    # Find note
    id_col = 'id' if 'id' in df.columns else 'ID'
    row = df[df[id_col].astype(str) == note_id]
    
    if row.empty:
        raise HTTPException(404, f"Note {note_id} not found")
    
    return row.iloc[0].to_dict()
