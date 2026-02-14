"""
Input validation for pipeline notes.
"""

import logging
from typing import Optional, Tuple

logger = logging.getLogger("lvmh-api.validator")


class ValidationError(Exception):
    """Raised when note validation fails."""
    def __init__(self, message: str, field: str):
        super().__init__(message)
        self.field = field


class NoteValidator:
    """
    Validates incoming notes before processing.
    """
    
    MIN_TEXT_LENGTH = 10
    MAX_TEXT_LENGTH = 50000
    
    FORBIDDEN_PATTERNS = [
        "<script",
        "javascript:",
        "onerror=",
        "onclick=",
    ]
    
    @classmethod
    def validate(cls, note: dict) -> Tuple[bool, Optional[str]]:
        """
        Validate a note before processing.
        Returns (is_valid, error_message).
        """
        # Check required fields
        if not note:
            return False, "Note is empty"
        
        # Validate Transcription field
        text = note.get('Transcription') or note.get('text') or ''
        
        if not text:
            return False, "Transcription field is required"
        
        if not isinstance(text, str):
            return False, "Transcription must be a string"
        
        # Check length
        if len(text.strip()) < cls.MIN_TEXT_LENGTH:
            return False, f"Transcription too short (min {cls.MIN_TEXT_LENGTH} characters)"
        
        if len(text) > cls.MAX_TEXT_LENGTH:
            return False, f"Transcription too long (max {cls.MAX_TEXT_LENGTH} characters)"
        
        # Check for XSS patterns
        text_lower = text.lower()
        for pattern in cls.FORBIDDEN_PATTERNS:
            if pattern in text_lower:
                return False, f"Forbidden pattern detected: {pattern}"
        
        # Validate Language if provided
        language = note.get('Language')
        if language is not None:
            valid_languages = {'FR', 'EN', 'IT', 'ES', 'DE', 'AUTO'}
            if language.upper() not in valid_languages:
                return False, f"Invalid language: {language}. Must be one of {valid_languages}"
        
        return True, None
    
    @classmethod
    def sanitize(cls, note: dict) -> dict:
        """
        Sanitize note fields.
        """
        sanitized = note.copy()
        
        # Strip whitespace from text
        if 'Transcription' in sanitized:
            sanitized['Transcription'] = sanitized['Transcription'].strip()
        elif 'text' in sanitized:
            sanitized['text'] = sanitized['text'].strip()
        
        # Normalize language
        if 'Language' in sanitized and sanitized['Language']:
            sanitized['Language'] = sanitized['Language'].upper()
        
        return sanitized
    
    @classmethod
    def validate_batch(cls, notes: list[dict]) -> Tuple[list[dict], list[dict]]:
        """
        Validate a batch of notes.
        Returns (valid_notes, invalid_notes).
        """
        valid = []
        invalid = []
        
        for i, note in enumerate(notes):
            is_valid, error = cls.validate(note)
            if is_valid:
                valid.append(cls.sanitize(note))
            else:
                logger.warning(f"Note {i} validation failed: {error}")
                invalid.append({
                    "index": i,
                    "note": note,
                    "error": error
                })
        
        return valid, invalid


def validate_note(note: dict) -> dict:
    """
    FastAPI dependency for note validation.
    Raises HTTPException if validation fails.
    """
    is_valid, error = NoteValidator.validate(note)
    if not is_valid:
        raise ValidationError(error, "Transcription")
    return NoteValidator.sanitize(note)
