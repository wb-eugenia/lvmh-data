"""
Transcribe router - Handles audio transcription via Voxtral (primary) with Groq fallback.
"""

import os
import logging
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException

logger = logging.getLogger("lvmh-api.transcribe")
router = APIRouter()


def get_mock_transcription():
    """Return mock transcription for demo/testing."""
    return {
        "transcription": "Cliente VIP très intéressée par la collection Capucines. Elle cherche un cadeau pour son mari qui aime le golf. Budget confortable.",
        "provider": "mock",
    }


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: Optional[str] = None,
):
    """
    Transcribe uploaded audio file using Voxtral (Mistral) with Groq fallback.
    
    - Primary: Voxtral Mini (Mistral) - EU data sovereignty
    - Fallback: Groq Whisper - faster but US data
    - Final fallback: Mock for demo mode
    
    Args:
        file: Audio file (mp3, wav, m4a, etc.)
        language: Optional language code (fr, it, de, en, etc.)
    
    Returns:
        Transcription text with provider info and timestamps
    """
    from src.transcriber import transcribe, TranscriptionResult
    
    temp_file = Path(f"temp_{file.filename}")
    
    try:
        # Save uploaded file temporarily
        with open(temp_file, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Check if API keys are available
        mistral_key = os.getenv("MISTRAL_API_KEY")
        groq_key = os.getenv("GROQ_API_KEY")
        
        if not mistral_key and not groq_key:
            logger.warning("No API keys found. Using mock transcription.")
            return get_mock_transcription()
        
        # Attempt transcription
        try:
            result: TranscriptionResult = await transcribe(
                temp_file,
                language=language,
                enable_timestamps=True,
            )
            
            logger.info(f"Transcription success: {result.provider}, {len(result.text)} chars")
            
            response = {
                "transcription": result.text,
                "provider": result.provider,
                "language": result.language,
            }
            
            # Include timestamps if available
            if result.timestamps:
                response["timestamps"] = result.timestamps
            
            return response
            
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return get_mock_transcription()
        
    except Exception as e:
        logger.error(f"File handling error: {e}")
        return get_mock_transcription()
        
    finally:
        # Cleanup
        if temp_file.exists():
            try:
                temp_file.unlink()
            except Exception:
                pass


@router.post("/transcribe/with-timestamps")
async def transcribe_audio_with_timestamps(
    file: UploadFile = File(...),
    language: Optional[str] = None,
    timestamp_granularities: Optional[str] = "word",
):
    """
    Transcribe audio with explicit timestamp control.
    
    Args:
        file: Audio file
        language: Optional language code
        timestamp_granularities: "word" | "segment" | "none"
    
    Returns:
        Full transcription with timestamps
    """
    from src.transcriber import transcribe_with_voxtral, TranscriptionResult
    
    temp_file = Path(f"temp_{file.filename}")
    
    try:
        with open(temp_file, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        mistral_key = os.getenv("MISTRAL_API_KEY")
        if not mistral_key:
            return get_mock_transcription()
        
        # Parse timestamp granularities
        ts_granularities = None
        if timestamp_granularities and timestamp_granularities != "none":
            ts_granularities = [timestamp_granularities]
        
        result: TranscriptionResult = await transcribe_with_voxtral(
            temp_file,
            language=language,
            timestamp_granularities=ts_granularities,
        )
        
        return {
            "transcription": result.text,
            "provider": result.provider,
            "language": result.language,
            "timestamps": result.timestamps or [],
        }
        
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return get_mock_transcription()
        
    finally:
        if temp_file.exists():
            try:
                temp_file.unlink()
            except Exception:
                pass
