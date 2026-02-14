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
from typing import Dict, Optional

import pandas as pd
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from api.schemas import BatchTask
from src.pipeline_async import AsyncPipeline
from src.text_cleaner import MultilingualTextCleaner, PIIEnforcer
from config.production import settings
from api.redis_client import BatchTaskStore, RedisCache
from api.container import get_pipeline as get_pipeline_instance

logger = logging.getLogger("lvmh-api.batch")
router = APIRouter()

# Redis-backed task store
_redis_available = True

# Queue and workers
_batch_queue: Optional[asyncio.Queue] = None
_batch_workers: list[asyncio.Task] = []
_workers_bootstrapped = False


def _normalize_batch_profile(profile: Optional[str]) -> str:
    normalized = str(profile or settings.batch_csv_profile.name).strip().lower()
    allowed = {settings.batch_csv_profile.name, settings.fast_batch_profile.name}
    if normalized not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid profile '{profile}'. Allowed: {sorted(allowed)}",
        )
    return normalized


def _profile_save_to_cache(profile: str) -> bool:
    if profile == settings.fast_batch_profile.name:
        return settings.fast_batch_profile.save_to_cache
    return settings.batch_csv_profile.save_to_cache


def get_pipeline():
    return get_pipeline_instance()


def _get_batch_queue() -> asyncio.Queue:
    global _batch_queue
    if _batch_queue is None:
        _batch_queue = asyncio.Queue(maxsize=settings.batch_queue_max_size)
    return _batch_queue


async def _batch_worker_loop(worker_id: int):
    queue = _get_batch_queue()
    logger.info("Batch worker %s started", worker_id)
    while True:
        task_id, df, profile = await queue.get()
        try:
            await process_batch_async(task_id, df, profile)
        except Exception as exc:
            logger.error("Batch worker %s failed task %s: %s", worker_id, task_id, exc)
            await _update_task(task_id, {"status": "error", "error": str(exc)})
        finally:
            queue.task_done()


def ensure_batch_workers() -> None:
    global _workers_bootstrapped
    if _workers_bootstrapped:
        return
    worker_count = max(1, int(settings.batch_worker_count))
    for idx in range(worker_count):
        _batch_workers.append(asyncio.create_task(_batch_worker_loop(idx + 1)))
    _workers_bootstrapped = True
    logger.info("Batch queue initialized with %s workers", worker_count)


async def _update_task(task_id: str, data: dict):
    """Update task in Redis or memory."""
    global _redis_available
    if _redis_available:
        try:
            task = await BatchTaskStore.get(task_id) or {}
            task.update(data)
            await BatchTaskStore.save(task_id, task)
        except Exception:
            _redis_available = False


async def process_batch_async(task_id: str, df: pd.DataFrame, profile: str):
    """Process batch in background with progress updates."""
    
    await _update_task(task_id, {"status": "processing"})
    pipeline = get_pipeline()
    save_to_cache = _profile_save_to_cache(profile)
    results = []
    
    try:
        for idx, row in df.iterrows():
            # Process note
            result = await pipeline.process_note({
                'ID': row.get('ID', f'BATCH_{idx}'),
                'Transcription': row.get('Transcription', row.get('text', '')),
                'Language': row.get('Language', 'FR')
            }, profile=profile, save_to_cache=save_to_cache)
            if result is None:
                results.append({
                    "id": row.get('ID', f'BATCH_{idx}'),
                    "tags": [],
                    "tier": None,
                    "confidence": 0.0,
                    "error": "processing_failed",
                    "mode": profile,
                })
                await _update_task(task_id, {"progress": idx + 1, "results": results})
                continue
            
            # Update progress
            results.append({
                "id": result.id,
                "tags": result.extraction.tags if hasattr(result.extraction, 'tags') else [],
                "tier": result.routing.tier,
                "confidence": result.routing.confidence,
                "profile": result.profile,
                "stage_timings_ms": result.stage_timings_ms,
                "mode": profile,
            })
            await _update_task(task_id, {"progress": idx + 1, "results": results})
             
            # Small delay to avoid rate limits
            await asyncio.sleep(0.05)
        
        await _update_task(task_id, {"status": "complete", "results": results})
        logger.info("Batch %s completed: %s notes processed (profile=%s)", task_id, len(df), profile)
        
    except Exception as e:
        await _update_task(task_id, {"status": "error", "error": str(e)})
        logger.error(f"Batch {task_id} error: {e}")


@router.post("/batch")
async def start_batch(
    file: UploadFile = File(...),
    profile: str = "batch_csv",
):
    """
    Start batch processing in background.
    Returns task_id to track progress via SSE stream.
    """
    
    selected_profile = _normalize_batch_profile(profile)

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
    task_data = {
        "task_id": task_id,
        "status": "pending",
        "progress": 0,
        "total": len(df),
        "profile": selected_profile,
        "created_at": datetime.now().isoformat(),
        "results": [],
        "error": None
    }
    
    await BatchTaskStore.save(task_id, task_data)
    
    ensure_batch_workers()
    queue = _get_batch_queue()
    if queue.full():
        await _update_task(task_id, {"status": "error", "error": "batch_queue_full"})
        raise HTTPException(503, "Batch queue is full, retry later")
    await queue.put((task_id, df, selected_profile))
    
    logger.info("Batch %s started: %s notes (profile=%s)", task_id, len(df), selected_profile)
    
    return {"task_id": task_id, "total": len(df), "profile": selected_profile}


@router.get("/batch/{task_id}")
async def get_batch_status(task_id: str):
    """Get batch processing status (polling)."""
    
    task = await BatchTaskStore.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    
    return task


@router.get("/batch-workers/status")
async def get_batch_workers_status():
    """Operational view for batch queue and worker runtime."""
    queue = _get_batch_queue()
    pipeline = get_pipeline()
    
    tasks_list = []
    if _redis_available:
        try:
            task_ids = await BatchTaskStore.list_tasks()
            for tid in task_ids:
                task = await BatchTaskStore.get(tid)
                if task:
                    tasks_list.append(task)
        except Exception:
            pass
    
    return {
        "workers_configured": int(settings.batch_worker_count),
        "workers_running": len([w for w in _batch_workers if not w.done()]),
        "supported_profiles": [settings.batch_csv_profile.name, settings.fast_batch_profile.name],
        "queue_size": queue.qsize(),
        "queue_max_size": queue.maxsize,
        "tasks_total": len(tasks_list),
        "tasks_pending": len([t for t in tasks_list if t.get("status") == "pending"]),
        "tasks_processing": len([t for t in tasks_list if t.get("status") == "processing"]),
        "tasks_complete": len([t for t in tasks_list if t.get("status") == "complete"]),
        "tasks_error": len([t for t in tasks_list if t.get("status") == "error"]),
        "profile_metrics": pipeline.get_profile_metrics(),
    }


@router.get("/batch/{task_id}/stream")
async def stream_batch_progress(task_id: str):
    """
    Server-Sent Events stream for real-time progress updates.
    Connect via EventSource in frontend.
    """
    
    task = await BatchTaskStore.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    
    async def event_generator():
        while True:
            task = await BatchTaskStore.get(task_id)
            
            if not task:
                break
            
            # Send progress update as SSE event
            yield f"data: {json.dumps(task)}\n\n"
            
            if task.get("status") in ("complete", "error"):
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
    
    task = await BatchTaskStore.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    
    await _update_task(task_id, {"status": "cancelled"})
    
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
