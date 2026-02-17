"""
Test script for Voxtral transcription.
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()


async def test_voxtral():
    """Test Voxtral transcription with a sample audio file."""
    from src.transcriber import transcribe, TranscriptionResult
    
    # Check API key
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        print("[X] MISTRAL_API_KEY not set")
        print("    Set it in .env or export MISTRAL_API_KEY=your_key")
        return False
    
    print(f"[OK] MISTRAL_API_KEY found: {api_key[:10]}...")
    
    # Look for test audio files
    test_dir = Path("data/test_audio")
    audio_files = []
    
    if test_dir.exists():
        audio_files = list(test_dir.glob("*.mp3")) + list(test_dir.glob("*.wav")) + list(test_dir.glob("*.m4a"))
    
    if not audio_files:
        print("[!] No test audio files found in data/test_audio")
        
        # Create a simple test to verify the API is reachable
        from src.transcriber import get_mistral_client
        client = get_mistral_client()
        
        if client:
            print("[OK] Mistral client initialized successfully")
            print("[OK] Voxtral client ready for transcription")
            return True
        else:
            print("[X] Could not initialize Mistral client")
            return False
    
    # Test with actual audio file
    audio_file = audio_files[0]
    print(f"[*] Testing with: {audio_file.name}")
    
    try:
        result: TranscriptionResult = await transcribe(
            audio_file,
            language="fr",  # Test with French
            enable_timestamps=True,
        )
        
        print(f"[*] Transcription successful!")
        print(f"   Provider: {result.provider}")
        print(f"   Language: {result.language}")
        print(f"   Text length: {len(result.text)} chars")
        print(f"   Text preview: {result.text[:100]}...")
        
        if result.timestamps:
            print(f"   Timestamps: {len(result.timestamps)} words/segments")
            if result.timestamps:
                first_ts = result.timestamps[0]
                print(f"   First timestamp: {first_ts}")
        
        return True
        
    except Exception as e:
        print(f"[X] Transcription failed: {e}")
        return False


async def main():
    print("=" * 50)
    print("LVMH Voxtral Transcription Test")
    print("=" * 50)
    
    print("\n[1] Testing Voxtral...")
    voxtral_ok = await test_voxtral()
    
    print("\n" + "=" * 50)
    print("Summary:")
    print(f"  Voxtral: {'[OK]' if voxtral_ok else '[X]'}")
    print("=" * 50)
    
    if voxtral_ok:
        print("\n[OK] Transcription is ready to use!")
    else:
        print("\n[!] Check your API keys and try again")


if __name__ == "__main__":
    asyncio.run(main())
