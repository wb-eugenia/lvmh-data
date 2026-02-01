from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, WebSocket
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import time
import asyncio
import uuid
from pathlib import Path
from tqdm import tqdm
import os
import pandas as pd

# Pipeline & Auth
from src.pipeline_batch import PipelineBatchV2
from src.auth import get_current_user, check_role, UserProfile

from fastapi.middleware.cors import CORSMiddleware
import json

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI(title="LVMH Voice-to-Tag V2.2 Professional")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global pipeline & data
pipeline = PipelineBatchV2(use_cache=True)
HISTRY_DATA = []

# Mount React Frontend
DIST_DIR = Path("frontend-v2/dist")
if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")

@app.get("/")
@app.get("/advisor")
@app.get("/manager")
async def serve_index():
    return FileResponse(DIST_DIR / "index.html")


def _load_history():
    """Load historical data from output/ for search/stats demo"""
    global HISTRY_DATA
    HISTRY_DATA = []
    output_dir = Path('output')
    if output_dir.exists():
        for f in output_dir.glob("batch_results_*.csv"):
            try:
                df = pd.read_csv(f)
                records = df.to_dict('records')
                # Parse JSON strings back to dicts
                for r in records:
                    for field in ['meta_analysis', 'pilier_1_univers_produit', 'pilier_2_profil_client', 'pilier_3_hospitalite_care', 'pilier_4_action_business']:
                        if field in r and isinstance(r[field], str):
                            try:
                                r[field] = json.loads(r[field].replace("'", '"'))
                            except: pass
                HISTRY_DATA.extend(records)
            except: pass
    print(f"📈 Loaded {len(HISTRY_DATA)} historical records for UI.")

_load_history()

class VoiceNoteEvent(BaseModel):
    id: Optional[str] = None
    transcription: str
    language: str = "FR"
    advisor_id: str
    store_id: str

@app.get("/health")
async def health():
    return {"status": "ok", "pipeline_active": pipeline is not None, "records": len(HISTRY_DATA)}

@app.post("/ingest")
async def ingest_note(event: VoiceNoteEvent, user: UserProfile = Depends(get_current_user)):
    """Handle real-time note ingestion."""
    start_time = time.time()
    note_id = event.id or str(uuid.uuid4())
    
    note_dict = {
        "ID": note_id,
        "Transcription": event.transcription,
        "Language": event.language,
        "advisor_id": event.advisor_id,
        "store_id": event.store_id
    }
    
    try:
        results = await pipeline.process_batch_async([note_dict])
        if not results:
            raise HTTPException(status_code=500, detail="Pipeline returned no results")
            
        result = results[0]
        HISTRY_DATA.append(result) # Add to session memory
        
        return {
            "status": "success",
            "processing_time_ms": (time.time() - start_time) * 1000,
            "data": result,
            "advisor_notification": result.get("meta_analysis", {}).get("advisor_feedback", "Note traitée !")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- UI & DASHBOARD API ---

@app.get("/api/search")
async def search_clients(q: str, user: UserProfile = Depends(get_current_user)):
    """Search historical records by name or tags"""
    q = q.lower()
    results = [
        r for r in HISTRY_DATA 
        if q in str(r.get('ID', '')).lower() or 
           any(q in str(t).lower() for t in r.get('tags', []))
    ]
    return {"results": results[:20], "total": len(results)}

def _get_live_leaderboard():
    leaderboard = {}
    for r in HISTRY_DATA:
        adv = r.get('advisor_id', 'Unknown')
        score = r.get('meta_analysis', {}).get('quality_score', 0)
        if adv not in leaderboard:
            leaderboard[adv] = {"points": 0, "notes": 0}
        leaderboard[adv]["points"] += score
        leaderboard[adv]["notes"] += 1
    
    sorted_lb = [
        {"id": k, "score": round(v["points"], 0), "notes": v["notes"]} 
        for k, v in leaderboard.items()
    ]
    sorted_lb.sort(key=lambda x: x["score"], reverse=True)
    return sorted_lb[:10]

@app.get("/api/leaderboard")
async def get_leaderboard(user: UserProfile = Depends(get_current_user)):
    """Get advisor ranking (REST)"""
    return _get_live_leaderboard()

@app.websocket("/ws/leaderboard")
async def leaderboard_websocket(websocket: WebSocket):
    """Live leaderboard updates via WebSocket"""
    await websocket.accept()
    try:
        while True:
            data = _get_live_leaderboard()
            await websocket.send_json(data)
            await asyncio.sleep(5) 
    except:
        pass 

@app.get("/api/stats")
async def get_store_stats(user: UserProfile = Depends(get_current_user)):
    """Aggregate stats for Manager Dashboard"""
    check_role(user, ["Manager", "Admin"])
    
    total = len(HISTRY_DATA)
    tier_dist = {1:0, 2:0, 3:0}
    
    if total == 0: 
        return {
            "total_notes": 0, 
            "avg_quality": 0, 
            "tier_distribution": tier_dist,
            "store_id": user.boutique_id
        }
    
    avg_quality = sum(r.get('meta_analysis', {}).get('quality_score', 0) for r in HISTRY_DATA) / total
    for r in HISTRY_DATA:
        t = r.get('tier')
        if t in tier_dist: tier_dist[t] += 1
        
    return {
        "total_notes": total,
        "avg_quality": round(avg_quality, 1),
        "tier_distribution": tier_dist,
        "store_id": user.boutique_id
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
