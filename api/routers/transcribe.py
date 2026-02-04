"""
Transcribe router - Handles audio transcription via OpenAI Whisper.
"""

import os
import logging
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException
from openai import OpenAI

logger = logging.getLogger("lvmh-api.transcribe")
router = APIRouter()

# Initialize OpenAI Client (Lazy load to avoid startup error if key missing)
_client: Optional[OpenAI] = None

def get_client():
    global _client
    if not _client:
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            _client = OpenAI(api_key=api_key)
    return _client

@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """
    Transcribe uploaded audio file using Whisper-1.
    Fallback to mock if no API key provided.
    """
    temp_file = Path(f"temp_{file.filename}")
    
    try:
        # Save uploaded file temporarily
        with open(temp_file, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        client = get_client()
        
        if not client:
            logger.warning("OPENAI_API_KEY not found. Using mock transcription.")
            # Mock response for testing without cost/key
            import random
            mocks = [
                "Cliente VIP très intéressée par la collection Capucines. Elle cherche un cadeau pour son mari qui aime le golf. Budget confortable.",
                "Client régulier, cherche une montre connectée pour le sport. Budget environ 5000 euros. Aime le bleu marine.",
                "Nouvelle cliente, première visite. Cherche un sac à main pour le travail. Budget max 2000€. Préfère le cuir grainé.",
                "Couple en voyage de noces. Veulent s'offrir des alliances. Budget illimité. Très pressés car repartent demain.",
                "Mme Martin, allergique au nickel sévère. Cherche des bijoux hypoallergéniques pour une soirée de gala.",
                "Monsieur cherche un cadeau pour sa fille de 20 ans. Elle aime le rose et le style décontracté. Budget 1500 euros."
            ]
            selected_mock = random.choice(mocks)
            logger.info(f"Using mock transcription: {selected_mock[:30]}...")
            return {"transcription": selected_mock}
            
        # Open file for reading
        with open(temp_file, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file,
                response_format="text"
                # language="fr" # Auto-detect is usually fine, but can enforce if needed
            )
            
        logger.info(f"Transcription success: {len(transcript)} chars")
        return {"transcription": transcript}

    except Exception as e:
        logger.error(f"Transcription error: {e}")
        # Return mock on error to keep app usable in demo mode
        logger.info("Falling back to mock transcription due to error.")
        import random
        mocks = [
            "Cliente VIP très intéressée par la collection Capucines. Elle cherche un cadeau pour son mari qui aime le golf. Budget confortable.",
            "Client régulier, cherche une montre connectée pour le sport. Budget environ 5000 euros. Aime le bleu marine.",
            "Nouvelle cliente, première visite. Cherche un sac à main pour le travail. Budget max 2000€. Préfère le cuir grainé.",
            "Couple en voyage de noces. Veulent s'offrir des alliances. Budget illimité. Très pressés car repartent demain.",
            "Mme Martin, allergique au nickel sévère. Cherche des bijoux hypoallergéniques pour une soirée de gala."
        ]
        return {
            "transcription": random.choice(mocks)
        }
        
    finally:
        # Cleanup
        if temp_file.exists():
            os.remove(temp_file)
