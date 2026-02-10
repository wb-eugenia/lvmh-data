"""
Results router - Browse and filter extraction results.
"""

import os
import sys
import logging
from typing import Optional, List
from pathlib import Path

import pandas as pd
from api.database import get_db
from api.models_sql import User, Note, Client
from sqlalchemy.orm import Session
from fastapi import APIRouter, Query, HTTPException, Depends
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from api.schemas import PaginatedResults, ExtractionResult, ExtractionTags, RoutingInfo, RGPDInfo, MetaAnalysis

logger = logging.getLogger("lvmh-api.results")
router = APIRouter()

# === Batch CSV Results ===
OUTPUT_DIR = (Path(__file__).parent.parent.parent / "output").resolve()

@router.get("/batch-results")
async def get_batch_results(
    file: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """
    List available batch CSV files or load data from a specific file.
    """
    logger.info(f"🔍 Checking batch results in: {OUTPUT_DIR}")
    
    if not OUTPUT_DIR.exists():
        logger.warning(f"⚠️ Output directory not found: {OUTPUT_DIR}")
        return {"files": [], "data": [], "total": 0, "page": page}
    
    # List all CSV files
    csv_files = sorted(
        [f.name for f in OUTPUT_DIR.glob("*.csv")],
        key=lambda x: x,
        reverse=True  # Most recent first
    )
    
    logger.info(f"📂 Found {len(csv_files)} CSV files")
    
    # If no file specified, just return the list
    if not file:
        return {"files": csv_files, "data": [], "total": 0, "page": page}
    
    # Load specific file
    file_path = OUTPUT_DIR / file
    if not file_path.exists():
        raise HTTPException(404, f"File {file} not found")
    
    try:
        df = pd.read_csv(file_path)
        
        # Pagination
        total = len(df)
        start = (page - 1) * limit
        end = start + limit
        page_df = df.iloc[start:end]
        
        # Convert to list of dicts, handling NaN values
        data = []
        for _, row in page_df.iterrows():
            item = {
                "id": str(row.get("ID", row.get("note_id", ""))),
                "tags": parse_list_column(row.get("tags", [])),
                "tier": int(row.get("tier", 1)) if pd.notna(row.get("tier")) else 1,
                "budget_range": row.get("budget_range", "") if pd.notna(row.get("budget_range")) else "",
                "confidence": float(row.get("confidence", 0)) if pd.notna(row.get("confidence")) else 0,
                "client_status": row.get("client_status", "") if pd.notna(row.get("client_status")) else "",
                "processing_tier": row.get("processing_tier", "") if pd.notna(row.get("processing_tier")) else "",
                "reasoning": row.get("reasoning", "") if pd.notna(row.get("reasoning")) else ""
            }
            data.append(item)
        
        return {
            "files": csv_files,
            "data": data,
            "total": total,
            "page": page,
            "total_pages": (total + limit - 1) // limit
        }
        
    except Exception as e:
        logger.error(f"Error loading CSV {file}: {e}")
        raise HTTPException(500, f"Error loading file: {str(e)}")

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


@router.get("/search")
async def search_notes(
    q: Optional[str] = Query(""),
    db: Session = Depends(get_db)
):
    """Search notes in SQL database."""
    query = db.query(Note)
    if q:
        query = query.filter(Note.transcription.ilike(f"%{q}%"))
    
    notes = query.order_by(Note.timestamp.desc()).limit(50).all()
    
    results = []
    for n in notes:
        try:
            analysis = json.loads(n.analysis_json)
            # Flatten some fields for the UI
            item = {
                "id": n.id,
                "ID": f"N{n.id}", # UI expects ID
                "Transcription": n.transcription,
                "tier": analysis.get('routing', {}).get('tier', 1),
                "pilier_4_action_business": analysis.get('extraction', {}).get('pilier_4_action_business', {}),
                "pilier_1_univers_produit": analysis.get('extraction', {}).get('pilier_1_univers_produit', {}),
                "advisor": n.advisor.full_name if n.advisor else "Inconnu",
                "client": n.client.name if n.client else "Inconnu",
                "timestamp": n.timestamp.isoformat(),
                "tags": analysis.get('extraction', {}).get('pilier_1_univers_produit', {}).get('categories', []),
                "matched_products": analysis.get('extraction', {}).get('pilier_1_univers_produit', {}).get('matched_products', [])
            }
            results.append(item)
        except:
            pass
            
    return {"results": results}

@router.get("/clients/search")
async def search_clients(
    q: Optional[str] = Query(""),
    db: Session = Depends(get_db)
):
    """Search clients in SQL database."""
    query = db.query(Client)
    if q:
        query = query.filter(Client.name.ilike(f"%{q}%"))
    
    clients = query.limit(20).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "vic_status": c.vic_status,
            "total_notes": len(c.notes)
        }
        for c in clients
    ]

@router.get("/results/{note_id}")
async def get_result_detail(note_id: int, db: Session = Depends(get_db)):
    """Get full details for a specific note from SQL."""
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(404, f"Note {note_id} not found")
    
    return json.loads(note.analysis_json)


@router.get("/recordings")
async def get_all_recordings(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    advisor_id: Optional[int] = None,
    tier: Optional[int] = None
):
    """
    Get all recordings for manager view with full pipeline results.
    Includes: transcription, tags, RAG products, NBA, advisor info.
    """
    query = db.query(Note).join(User).join(Client)
    
    # Apply filters
    if search:
        query = query.filter(Note.transcription.ilike(f"%{search}%"))
    
    if advisor_id:
        query = query.filter(Note.advisor_id == advisor_id)
    
    # Get total count before pagination
    total = query.count()
    
    # Apply pagination
    notes = query.order_by(Note.timestamp.desc()).offset((page - 1) * limit).limit(limit).all()
    
    recordings = []
    for note in notes:
        try:
            analysis = json.loads(note.analysis_json) if note.analysis_json else {}
            routing = analysis.get('routing', {})
            extraction = analysis.get('extraction', {})
            
            # Filter by tier if specified
            note_tier = routing.get('tier', 1)
            if tier and note_tier != tier:
                continue
            
            # Extract tags from pilier 1 categories if tags not present
            p1 = extraction.get('pilier_1_univers_produit', {})
            tags = extraction.get('tags', []) or p1.get('categories', [])
            
            recordings.append({
                "id": note.id,
                "advisor": {
                    "id": note.advisor.id if note.advisor else None,
                    "name": note.advisor.full_name if note.advisor else "Inconnu",
                    "store": note.advisor.store if note.advisor else None
                },
                "client": {
                    "id": note.client.id if note.client else None,
                    "name": note.client.name if note.client else "Inconnu",
                    "vic_status": note.client.vic_status if note.client else "Standard"
                },
                "timestamp": note.timestamp.isoformat(),
                "transcription": note.transcription,
                "points_awarded": note.points_awarded,
                "tier": note_tier,
                "confidence": routing.get('confidence', 0),
                "tags": tags,
                "pilier_1_univers_produit": p1,
                "pilier_2_profil_client": extraction.get('pilier_2_profil_client', {}),
                "pilier_3_hospitalite_care": extraction.get('pilier_3_hospitalite_care', {}),
                "pilier_4_action_business": extraction.get('pilier_4_action_business', {}),
                "matched_products": extraction.get('pilier_1_univers_produit', {}).get('matched_products', []),
                "next_best_action": extraction.get('pilier_4_action_business', {}).get('next_best_action', {}),
                "rgpd": analysis.get('rgpd', {}),
                "meta_analysis": extraction.get('meta_analysis', {}),
                "processing_time_ms": analysis.get('processing_time_ms', 0)
            })
        except Exception as e:
            logger.error(f"Error parsing note {note.id}: {e}")
            continue
    
    return {
        "recordings": recordings,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit
    }


