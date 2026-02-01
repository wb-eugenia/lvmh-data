import os
import io
from groq import Groq

# Ensure GROQ_API_KEY is set in environment or .env
# In production, this should always be loaded safely.
try:
    client = Groq(api_key=os.environ.get("GROQ_API_KEY", "gsk_...")) 
except:
    client = None

def transcribe_audio(audio_file) -> str:
    """
    Transcribe audio blob using Groq Whisper-large-v3.
    """
    if not client:
        # Fallback for dev without key
        return "Simulation: Le client cherche un sac rouge."
        
    try:
        # Create a file-like object with a name, as Groq client often expects it
        audio_file.name = "audio.wav" 
        
        translation = client.audio.transcriptions.create(
            file=(audio_file.name, audio_file.read()),
            model="whisper-large-v3",
            response_format="json",
            temperature=0.0
        )
        return translation.text
    except Exception as e:
        print(f"Whisper Error: {e}")
        return f"Erreur transcription: {str(e)}"
