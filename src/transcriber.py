"""
Unified Transcription Module - Voxtral Primary with Groq Fallback.
"""

import os
import logging
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger("lvmh-api.transcriber")


@dataclass
class TranscriptionResult:
    text: str
    provider: str
    language: Optional[str] = None
    duration: Optional[float] = None
    timestamps: Optional[List[Dict[str, Any]]] = None


def get_mistral_client():
    """Get Mistral client with API key."""
    from mistralai import Mistral
    
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        logger.warning("MISTRAL_API_KEY not found")
        return None
    
    return Mistral(api_key=api_key)


def get_groq_client():
    """Get Groq client for fallback."""
    from groq import AsyncGroq
    
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.warning("GROQ_API_KEY not found")
        return None
    
    return AsyncGroq(api_key=api_key)


async def transcribe_with_voxtral(
    audio_path: Path,
    language: Optional[str] = None,
    timestamp_granularities: Optional[List[str]] = None,
) -> TranscriptionResult:
    """
    Transcribe audio using Voxtral Mini (Mistral).
    
    Args:
        audio_path: Path to audio file
        language: Optional language code (fr, it, de, en, etc.)
        timestamp_granularities: ["word"] or ["segment"] for timestamps
    
    Returns:
        TranscriptionResult with text and metadata
    """
    client = get_mistral_client()
    
    if not client:
        raise Exception("Mistral client not available")
    
    if timestamp_granularities is None:
        timestamp_granularities = ["word"]  # Default to word-level timestamps
    
    logger.info(f"Transcribing with Voxtral: {audio_path.name}, language={language}")
    
    try:
        with open(audio_path, "rb") as audio_file:
            response = client.audio.transcriptions.complete(
                model="voxtral-mini-latest",
                file={
                    "content": audio_file.read(),
                    "file_name": audio_path.name,
                },
                language=language,
                timestamp_granularities=timestamp_granularities,
            )
        
        # Extract text and metadata
        text = response.text if hasattr(response, 'text') else str(response)
        
        # Extract timestamps if available
        timestamps = None
        if hasattr(response, 'words') and response.words:
            timestamps = [
                {
                    "word": w.word,
                    "start": w.start,
                    "end": w.end,
                }
                for w in response.words
            ]
        elif hasattr(response, 'segments') and response.segments:
            timestamps = [
                {
                    "text": s.text,
                    "start": s.start,
                    "end": s.end,
                }
                for s in response.segments
            ]
        
        # Detect language if not provided
        detected_language = language
        if not detected_language and hasattr(response, 'language'):
            detected_language = response.language
        
        logger.info(f"Voxtral transcription success: {len(text)} chars")
        
        return TranscriptionResult(
            text=text,
            provider="voxtral",
            language=detected_language,
            timestamps=timestamps,
        )
        
    except Exception as e:
        logger.error(f"Voxtral transcription error: {e}")
        raise


async def transcribe_with_groq(
    audio_path: Path,
    language: Optional[str] = None,
) -> TranscriptionResult:
    """
    Transcribe audio using Groq Whisper (fallback).
    
    Args:
        audio_path: Path to audio file
        language: Optional language code
    
    Returns:
        TranscriptionResult with text and metadata
    """
    client = get_groq_client()
    
    if not client:
        raise Exception("Groq client not available")
    
    logger.info(f"Transcribing with Groq: {audio_path.name}")
    
    try:
        with open(audio_path, "rb") as audio_file:
            response = await client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=audio_file,
                language=language,
                response_format="verbose_json",
            )
        
        text = response.text if hasattr(response, 'text') else str(response)
        
        # Extract timestamps from Groq response
        timestamps = None
        if hasattr(response, 'words') and response.words:
            timestamps = [
                {
                    "word": w.word,
                    "start": w.start,
                    "end": w.end,
                }
                for w in response.words
            ]
        
        logger.info(f"Groq transcription success: {len(text)} chars")
        
        return TranscriptionResult(
            text=text,
            provider="groq",
            language=language or "auto",
            timestamps=timestamps,
        )
        
    except Exception as e:
        logger.error(f"Groq transcription error: {e}")
        raise


async def transcribe(
    audio_path: Path,
    language: Optional[str] = None,
    enable_timestamps: bool = True,
) -> TranscriptionResult:
    """
    Main transcription function - Voxtral primary with Groq fallback.
    
    Priority:
    1. Voxtral (Mistral) - Primary, EU data sovereignty
    2. Groq - Fallback, faster but US data
    
    Args:
        audio_path: Path to audio file
        language: Optional language code
        enable_timestamps: Include word-level timestamps
    
    Returns:
        TranscriptionResult
    """
    # First try Voxtral (Mistral)
    try:
        timestamps = ["word"] if enable_timestamps else None
        return await transcribe_with_voxtral(
            audio_path,
            language=language,
            timestamp_granularities=timestamps,
        )
    except Exception as e:
        logger.warning(f"Voxtral failed: {e}, trying Groq fallback...")
    
    # Fallback to Groq
    try:
        return await transcribe_with_groq(audio_path, language=language)
    except Exception as e:
        logger.warning(f"Groq fallback failed: {e}")
    
    # If both fail, raise
    raise Exception("All transcription providers failed")


async def transcribe_from_file(
    file_content: bytes,
    filename: str,
    language: Optional[str] = None,
) -> TranscriptionResult:
    """
    Transcribe audio from file content (bytes).
    
    Args:
        file_content: Audio file as bytes
        filename: Original filename for format detection
        language: Optional language code
    
    Returns:
        TranscriptionResult
    """
    import tempfile
    
    # Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=filename) as tmp:
        tmp.write(file_content)
        tmp_path = Path(tmp.name)
    
    try:
        return await transcribe(tmp_path, language=language)
    finally:
        # Cleanup
        if tmp_path.exists():
            tmp_path.unlink()
