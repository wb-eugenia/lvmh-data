"""
Batch router - Batch processing with SSE streaming progress.
"""

import sys
import os
import uuid
import json
import asyncio
import logging
from datetime import datetime
from typing import Dict

import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from api.schemas import BatchTask
from src.pipeline_async import AsyncPipeline

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
        "created_at": datetime.utcnow().isoformat(),
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
