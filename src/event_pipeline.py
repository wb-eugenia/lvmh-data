"""
Event-Driven Pipeline Mock (Real-Time).
Simulates a real-time ingestion endpoint (FastAPI) that processes individual notes via the pipeline.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, Optional
import time
import asyncio
import uuid

# Import our pipeline
from src.pipeline_batch import PipelineBatchV2

app = FastAPI(title="LVMH Real-Time Voice-to-Tag Ingestion")

# Global pipeline instance (avoid reloading models every request)
pipeline = PipelineBatchV2(use_cache=True)

class VoiceNoteEvent(BaseModel):
    id: Optional[str] = None
    transcription: str
    language: str = "FR"
    advisor_id: str
    store_id: str

@app.get("/health")
async def health():
    return {"status": "ok", "pipeline_active": pipeline is not None}

@app.post("/ingest")
async def ingest_note(event: VoiceNoteEvent):
    """
    Handle real-time note ingestion.
    Processes the note and returns the result immediately (< 5s target).
    """
    start_time = time.time()
    note_id = event.id or str(uuid.uuid4())
    
    # Construct node for pipeline
    note_dict = {
        "ID": note_id,
        "Transcription": event.transcription,
        "Language": event.language,
        "advisor_id": event.advisor_id,
        "store_id": event.store_id
    }
    
    try:
        # Run pipeline in async mode (single note)
        results = await pipeline.process_batch_async([note_dict])
        
        if not results:
            raise HTTPException(status_code=500, detail="Pipeline returned no results")
            
        result = results[0]
        elapsed = (time.time() - start_time) * 1000
        
        # Enrich with real-time metadata
        return {
            "status": "success",
            "processing_time_ms": elapsed,
            "data": result,
            "advisor_notification": result.get("meta_analysis", {}).get("advisor_feedback", "Note traitée !")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")

# CLI run if direct script
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
