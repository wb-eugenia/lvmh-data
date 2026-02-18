"""
Transcribe router - audio transcription + TTS endpoints.
Whisper Edge (WASM) is used on frontend for local processing.
"""

import os
import logging
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Query, Body
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response

logger = logging.getLogger("lvmh-api.transcribe")
router = APIRouter()


def get_mock_transcription():
    """Return mock transcription for demo/testing."""
    return {
        "transcription": (
            "Cliente VIP tres interessee par la collection Capucines. "
            "Elle cherche un cadeau pour son mari qui aime le golf. "
            "Budget confortable."
        ),
        "provider": "mock",
    }


def has_stt_provider() -> bool:
    return bool(os.getenv("GROQ_API_KEY") or os.getenv("MISTRAL_API_KEY"))


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: Optional[str] = None,
    provider: Optional[str] = Query(default="groq", description="groq | mistral"),
):
    """
    Transcribe uploaded audio file.

    - Primary default: Groq Whisper
    - Fallback: Voxtral (Mistral)
    - Last fallback: mock payload
    """
    from src.transcriber import transcribe, TranscriptionResult

    temp_file = Path(f"temp_{file.filename}")

    try:
        with open(temp_file, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        if not has_stt_provider():
            logger.warning("No STT provider key found (GROQ_API_KEY/MISTRAL_API_KEY). Using mock transcription.")
            return get_mock_transcription()

        try:
            result: TranscriptionResult = await transcribe(
                temp_file,
                language=language,
                enable_timestamps=True,
                provider=str(provider or "groq").strip().lower(),
            )
            logger.info("Transcription success: %s, %s chars", result.provider, len(result.text))
            response = {
                "transcription": result.text,
                "provider": result.provider,
                "language": result.language,
            }
            if result.timestamps:
                response["timestamps"] = result.timestamps
            return response
        except Exception as e:
            logger.error("Transcription error: %s", e)
            return get_mock_transcription()
    except Exception as e:
        logger.error("File handling error: %s", e)
        return get_mock_transcription()
    finally:
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
    provider: Optional[str] = Query(default="groq", description="groq | mistral"),
):
    """
    Transcribe audio with timestamp control.
    """
    from src.transcriber import transcribe, TranscriptionResult

    temp_file = Path(f"temp_{file.filename}")

    try:
        with open(temp_file, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        if not has_stt_provider():
            return get_mock_transcription()

        ts_enabled = bool(timestamp_granularities and timestamp_granularities != "none")
        result: TranscriptionResult = await transcribe(
            temp_file,
            language=language,
            enable_timestamps=ts_enabled,
            provider=str(provider or "groq").strip().lower(),
        )

        return {
            "transcription": result.text,
            "provider": result.provider,
            "language": result.language,
            "timestamps": result.timestamps or [],
        }
    except Exception as e:
        logger.error("Transcription error: %s", e)
        return get_mock_transcription()
    finally:
        if temp_file.exists():
            try:
                temp_file.unlink()
            except Exception:
                pass


@router.post("/transcribe/speak")
async def synthesize_speech(payload: dict = Body(...)):
    """
    Text-to-speech endpoint for Advisor view.
    Uses Groq OpenAI-compatible TTS API and returns audio bytes.
    """
    text = str((payload or {}).get("text") or "").strip()
    voice = str((payload or {}).get("voice") or "Arista-PlayAI").strip()
    model = (payload or {}).get("model")
    response_format = str((payload or {}).get("format") or "mp3").strip().lower()

    if not text:
        return Response(status_code=400, content=b"Missing 'text' payload")
    if response_format not in {"mp3", "wav"}:
        response_format = "mp3"

    try:
        from src.transcriber import synthesize_with_groq

        audio_bytes = await run_in_threadpool(
            synthesize_with_groq,
            text,
            voice,
            model,
            response_format,
        )
        media_type = "audio/mpeg" if response_format == "mp3" else "audio/wav"
        return Response(
            content=audio_bytes,
            media_type=media_type,
            headers={"X-TTS-Provider": "groq"},
        )
    except Exception as e:
        logger.error("TTS synthesis error: %s", e)
        return Response(status_code=502, content=f"TTS failed: {e}".encode("utf-8"))
