from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Depends, Header, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import json
from sqlalchemy.orm import Session
from sqlalchemy import func

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from src.pipeline_batch_v2 import PipelineBatchV2, VoiceNoteEvent
from src.auth import get_current_user, check_role, UserProfile, get_db
from src.database import init_db, SessionLocal, Interaction, User, Store
from src.tier2_whisper import transcribe_audio

app = FastAPI(title="LVMH Voice-to-Tag V2.2 Professional")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global pipeline
pipeline = PipelineBatchV2(use_cache=True)

@app.on_event("startup")
def startup_event():
    init_db()

# Mount React Frontend
DIST_DIR = Path("frontend-v2/dist")
if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")

@app.get("/")
@app.get("/advisor")
@app.get("/manager")
async def serve_index():
    return FileResponse(DIST_DIR / "index.html")


@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...), user: UserProfile = Depends(get_current_user)):
    """Real-time voice-to-text with Groq Whisper"""
    try:
        text = transcribe_audio(file.file)
        return {"transcription": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
async def ingest_note(event: VoiceNoteEvent, user: UserProfile = Depends(get_current_user), db: Session = Depends(get_db)):
    """Handle real-time note ingestion."""
    start_time = time.time()
    note_id = event.id or str(uuid.uuid4())
    
    # Process
    note_dict = {
        "ID": note_id,
        "Transcription": event.transcription,
        "Language": event.language,
        "advisor_id": user.id, # Use authenticated user
        "store_id": user.boutique_id
    }
    
    try:
        results = await pipeline.process_batch_async([note_dict])
        if not results:
            raise HTTPException(status_code=500, detail="Pipeline returned no results")
            
        result = results[0]
        
        # Save to DB
        interaction = Interaction(
            id=note_id,
            advisor_id=user.id,
            store_id=user.boutique_id,
            transcription=event.transcription,
            meta_analysis=result.get("meta_analysis"),
            pilier_1=result.get("pilier_1_univers_produit"),
            pilier_2=result.get("pilier_2_intention_client"),
            pilier_3=result.get("pilier_3_contexte_client"),
            pilier_4=result.get("pilier_4_action_business"),
            tier=result.get("tier", 3)
        )
        db.add(interaction)
        db.commit()
        db.refresh(interaction)
        
        return {
            "status": "success",
            "processing_time_ms": (time.time() - start_time) * 1000,
            "data": result,
            "advisor_notification": result.get("meta_analysis", {}).get("advisor_feedback", "Note traitée !")
        }
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- UI & DASHBOARD API ---

# --- UI & DASHBOARD API ---

@app.get("/api/search")
async def search_clients(q: str, user: UserProfile = Depends(get_current_user), db: Session = Depends(get_db)):
    """Search historical records by name or tags"""
    q = q.lower() if q else ""
    # Simple SQL search
    query = db.query(Interaction).filter(Interaction.store_id == user.boutique_id)
    all_interactions = query.all()

    # Filter in python for JSON fields (SQLite legacy support)
    results = []
    for r in all_interactions:
        # Check ID or JSON tags
        if q in str(r.id).lower():
            results.append(r)
            continue
            
        # Check Tags (Univers Produit)
        cats = r.pilier_1.get('categories', []) if r.pilier_1 else []
        if any(q in str(c).lower() for c in cats):
           results.append(r)

    # Format for UI
    formatted = []
    for r in results[:20]:
         formatted.append({
             "ID": r.id,
             "Transcription": r.transcription,
             "tier": r.tier,
             "meta_analysis": r.meta_analysis,
             "pilier_4_action_business": r.pilier_4,
             "pilier_1_univers_produit": r.pilier_1
         })
         
    return {"results": formatted, "total": len(results)}

def _get_live_leaderboard_data(db: Session):
    # Aggregation SQL
    interactions = db.query(Interaction).all()
    leaderboard = {}
    
    for r in interactions:
        adv = r.advisor_id
        score = r.meta_analysis.get('quality_score', 0) if r.meta_analysis else 0
        
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
async def get_leaderboard(user: UserProfile = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get advisor ranking (REST)"""
    return _get_live_leaderboard_data(db)

@app.websocket("/ws/leaderboard")
async def leaderboard_websocket(websocket: WebSocket):
    """Live leaderboard updates via WebSocket"""
    await websocket.accept()
    db = SessionLocal()
    try:
        while True:
            data = _get_live_leaderboard_data(db)
            await websocket.send_json(data)
            await asyncio.sleep(5) 
    except:
        pass 
    finally:
        db.close()

@app.get("/api/stats")
async def get_store_stats(user: UserProfile = Depends(get_current_user), db: Session = Depends(get_db)):
    """Aggregate stats for Manager Dashboard via SQL"""
    check_role(user, ["Manager", "Admin"])
    
    interactions = db.query(Interaction).filter(Interaction.store_id == user.boutique_id).all()
    total = len(interactions)
    tier_dist = {1:0, 2:0, 3:0}
    
    if total == 0: 
        return {
            "total_notes": 0, 
            "avg_quality": 0, 
            "tier_distribution": tier_dist,
            "store_id": user.boutique_id
        }
    
    total_quality = 0
    for r in interactions:
        tier = r.tier or 3
        if tier in tier_dist: tier_dist[tier] += 1
        total_quality += r.meta_analysis.get('quality_score', 0) if r.meta_analysis else 0
        
    avg_quality = total_quality / total
        
    return {
        "total_notes": total,
        "avg_quality": round(avg_quality, 1),
        "tier_distribution": tier_dist,
        "store_id": user.boutique_id
    }
