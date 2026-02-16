"""
Note Segmentation - Stub module.
"""

from typing import List, Dict, Optional


class NoteSegmentation:
    """Segment notes into logical parts."""
    
    def __init__(self):
        pass
    
    def segment(self, text: str) -> List[Dict]:
        """Segment text into parts."""
        if not text:
            return []
        return [{"text": text, "type": "full", "start": 0, "end": len(text)}]
    
    def extract_sentences(self, text: str) -> List[str]:
        """Extract sentences from text."""
        if not text:
            return []
        import re
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip()]
