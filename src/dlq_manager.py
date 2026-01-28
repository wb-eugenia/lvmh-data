"""
Dead Letter Queue (DLQ) Manager.
Handles notes that failed processing after all retries to ensure ZERO data loss.
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class DeadLetterQueue:
    """
    Manages failed notes.
    Persists failures to disk for manual review and replay.
    """
    
    def __init__(self, output_dir: str = "outputs/dlq"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.failed_notes: List[Dict] = []
        self._load_existing()
    
    def _load_existing(self):
        """Load existing failures from current session if any."""
        # In a real DB system we would query, here we just keep in memory for the session
        pass
    
    def add(
        self, 
        note_id: str, 
        note_text: str, 
        error: str,
        tier_attempted: str,
        retry_count: int = 0,
        metadata: Optional[Dict] = None
    ):
        """Add a failed note to the DLQ."""
        failure_record = {
            'note_id': note_id,
            'note_text': note_text,
            'error': str(error),
            'tier_attempted': tier_attempted,
            'retry_count': retry_count,
            'timestamp': datetime.now().isoformat(),
            'requires_manual_review': True,
            'metadata': json.dumps(metadata) if metadata else "{}"
        }
        
        self.failed_notes.append(failure_record)
        
        # Immediate persist to avoid loss on crash
        self._persist_single(failure_record)
        
        logger.error(f"💀 Note {note_id} moved to DLQ: {error}")
    
    def _persist_single(self, record: Dict):
        """Append single record to daily DLQ file."""
        date_str = datetime.now().strftime("%Y%m%d")
        filepath = self.output_dir / f"dlq_{date_str}.jsonl"
        
        try:
            with open(filepath, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.critical(f"Failed to write to DLQ file: {e}")
    
    def export_csv(self) -> str:
        """Export current session failures to CSV for manual review."""
        if not self.failed_notes:
            return ""
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = self.output_dir / f"dlq_export_{timestamp}.csv"
        
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ['note_id', 'timestamp', 'tier_attempted', 'retry_count', 'error', 'note_text', 'metadata']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for note in self.failed_notes:
                    # Filter keys to match fieldnames
                    row = {k: note.get(k) for k in fieldnames}
                    writer.writerow(row)
            
            return str(filepath)
        except Exception as e:
            logger.error(f"Failed to export DLQ to CSV: {e}")
            return ""
    
    def size(self) -> int:
        """Get number of failed notes in current session."""
        return len(self.failed_notes)
    
    def clear(self):
        """Clear memory DLQ (does not delete files)."""
        self.failed_notes.clear()
