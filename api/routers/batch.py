"""
Batch router - Batch processing with SSE streaming progress.
"""

import sys
import os
import uuid
import json
import asyncio
import logging
import io
from datetime import datetime
from typing import Dict

import pandas as pd
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from api.schemas import BatchTask
from src.pipeline_async import AsyncPipeline
from src.text_cleaner import MultilingualTextCleaner, PIIEnforcer

logger = logging.getLogger("lvmh-api.batch")
router = APIRouter()

# In-memory task store (use Redis in production!)
batch_tasks: Dict[str, dict] = {}

# Pipeline instance
_pipeline = None


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = AsyncPipeline(use_cache=True)
    return _pipeline


async def process_batch_async(task_id: str, df: pd.DataFrame):
    """Process batch in background with progress updates."""
    
    batch_tasks[task_id]["status"] = "processing"
    pipeline = get_pipeline()
    
    try:
        for idx, row in df.iterrows():
            # Process note
            result = await pipeline.process_note({
                'ID': row.get('ID', f'BATCH_{idx}'),
                'Transcription': row.get('Transcription', row.get('text', '')),
                'Language': row.get('Language', 'FR')
            })
            
            # Update progress
            batch_tasks[task_id]["results"].append({
                "id": result.id,
                "tags": result.extraction.tags if hasattr(result.extraction, 'tags') else [],
                "tier": result.routing.tier,
                "confidence": result.routing.confidence
            })
            batch_tasks[task_id]["progress"] = idx + 1
            
            # Small delay to avoid rate limits
            await asyncio.sleep(0.05)
        
        batch_tasks[task_id]["status"] = "complete"
        logger.info(f"Batch {task_id} completed: {len(df)} notes processed")
        
    except Exception as e:
        batch_tasks[task_id]["status"] = "error"
        batch_tasks[task_id]["error"] = str(e)
        logger.error(f"Batch {task_id} error: {e}")


@router.post("/batch")
async def start_batch(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None
):
    """
    Start batch processing in background.
    Returns task_id to track progress via SSE stream.
    """
    
    # Validate file type
    if not file.filename.endswith(('.csv', '.xlsx')):
        raise HTTPException(400, "File must be CSV or Excel")
    
    # Read file
    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file.file)
        else:
            df = pd.read_excel(file.file)
    except Exception as e:
        raise HTTPException(400, f"Failed to parse file: {e}")
    
    # Validate columns
    required = {'Transcription'} | {'text'}  # Accept either
    if not any(col in df.columns for col in required):
        raise HTTPException(400, "File must have 'Transcription' or 'text' column")
    
    # Create task
    task_id = str(uuid.uuid4())
    batch_tasks[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "progress": 0,
        "total": len(df),
        "created_at": datetime.now().isoformat(),
        "results": [],
        "error": None
    }
    
    # Start background processing
    background_tasks.add_task(process_batch_async, task_id, df)
    
    logger.info(f"Batch {task_id} started: {len(df)} notes")
    
    return {"task_id": task_id, "total": len(df)}


@router.get("/batch/{task_id}")
async def get_batch_status(task_id: str):
    """Get batch processing status (polling)."""
    
    if task_id not in batch_tasks:
        raise HTTPException(404, "Task not found")
    
    return batch_tasks[task_id]


@router.get("/batch/{task_id}/stream")
async def stream_batch_progress(task_id: str):
    """
    Server-Sent Events stream for real-time progress updates.
    Connect via EventSource in frontend.
    """
    
    if task_id not in batch_tasks:
        raise HTTPException(404, "Task not found")
    
    async def event_generator():
        while True:
            if task_id not in batch_tasks:
                break
            
            task = batch_tasks[task_id]
            
            # Send progress update as SSE event
            yield f"data: {json.dumps(task)}\n\n"
            
            if task["status"] in ("complete", "error"):
                break
            
            await asyncio.sleep(0.5)  # Update every 500ms
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )


@router.delete("/batch/{task_id}")
async def cancel_batch(task_id: str):
    """Cancel a running batch task."""
    
    if task_id not in batch_tasks:
        raise HTTPException(404, "Task not found")
    
    batch_tasks[task_id]["status"] = "cancelled"
    
    return {"message": "Task cancelled"}


@router.post("/data-cleaning/preview")
async def data_cleaning_preview(file: UploadFile = File(...)):
    """
    Preview CSV - return columns and sample data before cleaning.
    """
    if not file.filename.endswith(('.csv', '.xlsx')):
        raise HTTPException(400, "File must be CSV or Excel")
    
    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file.file)
        else:
            df = pd.read_excel(file.file)
    except Exception as e:
        raise HTTPException(400, f"Failed to parse file: {e}")
    
    return {
        "columns": list(df.columns),
        "row_count": len(df),
        "sample": df.head(3).where(pd.notna(df), None).to_dict('records')
    }


@router.post("/data-cleaning")
async def data_cleaning(
    file: UploadFile = File(...), 
    text_column: str = Form('Transcription')
):
    """
    Clean CSV data: remove duplicates, empty rows, normalize text.
    Specify the text column to use for duplicate detection and cleaning.
    """
    
    if not file.filename.endswith(('.csv', '.xlsx')):
        raise HTTPException(400, "File must be CSV or Excel")
    
    # Read file
    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file.file)
        else:
            df = pd.read_excel(file.file)
    except Exception as e:
        raise HTTPException(400, f"Failed to parse file: {e}")
    
    original_count = len(df)
    original_columns = list(df.columns)
    
    # Cleaning report
    report = {
        "original_rows": original_count,
        "original_columns": original_columns,
        "duplicates_removed": 0,
        "empty_rows_removed": 0,
        "rows_cleaned": 0,
        "details": [],
        "text_column_used": text_column
    }
    
    # Use the specified column
    transcription_col = text_column if text_column in df.columns else None
    
    if not transcription_col:
        # Try to find a fallback
        fallback_cols = ['Transcription', 'text', 'Note', 'Content', 'transcription']
        for col in fallback_cols:
            if col in df.columns:
                transcription_col = col
                report["text_column_used"] = col
                break
    
    # 1. Remove completely empty rows
    empty_mask = df.isna().all(axis=1)
    empty_rows = empty_mask.sum()
    if empty_rows > 0:
        df = df[~empty_mask]
        report["empty_rows_removed"] = int(empty_rows)
        report["details"].append(f"Supprimé {empty_rows} lignes vides")
    
    # 2. Remove rows with empty/invalid transcription BEFORE cleaning text
    if transcription_col:
        before_count = len(df)
        # Remove rows where transcription is NaN, empty string, or whitespace only
        df = df.dropna(subset=[transcription_col])
        df = df[df[transcription_col].astype(str).str.strip() != '']
        dropped_empty = before_count - len(df)
        if dropped_empty > 0:
            report["empty_rows_removed"] += int(dropped_empty)
            report["details"].append(f"Supprimé {dropped_empty} lignes avec {transcription_col} vide")
    
    # 3. Apply REAL PIPELINE text cleaning + PII on each transcription
    texts_cleaned = 0
    fillers_removed = 0
    pii_rows = 0
    total_pii_count = 0
    
    if transcription_col:
        # NOTE: Use cleaner without semantic dedup for API thread safety
        # Semantic model causes threading issues with FastAPI
        cleaner = MultilingualTextCleaner(use_embeddings=False)
        
        # Detect language if column exists
        lang_col = 'Language' if 'Language' in df.columns else None
        
        cleaned_texts = []
        for idx, row in df.iterrows():
            text = str(row[transcription_col])
            lang = str(row[lang_col]).upper() if lang_col and pd.notna(row[lang_col]) else 'FR'
            
            # Step 1: Apply the REAL pipeline cleaning (fillers, etc.)
            result = cleaner.clean_text(text, language=lang)
            cleaned = result.get('cleaned', text)
            stats = result
            
            # Step 2: Apply PII Enforcer (RGPD compliance)
            cleaned, pii_counts = PIIEnforcer.clean(cleaned, audit=True)
            
            if pii_counts:
                pii_rows += 1
                total_pii_count += sum(pii_counts.values())
            
            cleaned_texts.append(cleaned)
            
            if stats.get('fillers_removed', 0) > 0:
                fillers_removed += stats['fillers_removed']
            if cleaned != text:
                texts_cleaned += 1
        
        df[transcription_col] = cleaned_texts
        
        if texts_cleaned > 0:
            report["rows_cleaned"] = texts_cleaned
            report["details"].append(f"Nettoyé {texts_cleaned} transcriptions avec la pipeline LVMH")
        if fillers_removed > 0:
            report["details"].append(f"Supprimé {fillers_removed} mots de remplissage (euh, bah, etc.)")
        if pii_rows > 0:
            report["pii_rows"] = pii_rows
            report["details"].append(f"[RGPD] Anonymisé données sensibles dans {pii_rows} lignes")
    
    # 4. Remove duplicates based on TRANSCRIPTION content
    if transcription_col:
        before_dedup = len(df)
        # Consider transcription + Language for duplicate detection
        subset_cols = [transcription_col]
        if 'Language' in df.columns:
            subset_cols.append('Language')
        
        df = df.drop_duplicates(subset=subset_cols, keep='first')
        dup_count = before_dedup - len(df)
        
        if dup_count > 0:
            report["duplicates_removed"] = int(dup_count)
            report["details"].append(f"Supprimé {dup_count} doublons de transcription")
    
    # 5. Clean other text columns (strip whitespace only)
    for col in df.select_dtypes(include=['object']).columns:
        if col != transcription_col:
            df[col] = df[col].astype(str).str.strip()
            df[col] = df[col].replace(['nan', 'NaN', 'null', 'NULL', 'None'], pd.NA)
    
    # Final stats
    report["final_rows"] = len(df)
    report["final_columns"] = list(df.columns)
    report["rows_removed_total"] = original_count - len(df)
    report["reduction_percent"] = round(((original_count - len(df)) / original_count) * 100, 2) if original_count > 0 else 0
    
    # Convert to CSV for download
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_content = csv_buffer.getvalue()
    
    return {
        "report": report,
        "cleaned_csv": csv_content,
        "filename": f"cleaned_{file.filename}"
    }
