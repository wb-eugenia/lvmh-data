"""
Shared normalization utilities for LVMH API.
These functions are used across multiple modules to ensure consistency.
"""

from typing import Any, List, Set


TRUTHY_VALUES: Set[str] = {"1", "true", "yes", "y", "oui", "on"}


def normalize_to_string_list(value: Any) -> List[str]:
    """
    Normalize various input types to a list of strings with deduplication.
    Handles: comma-separated strings, lists, tuples, sets.
    """
    if isinstance(value, str):
        source = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        source = list(value)
    else:
        return []
    
    normalized: List[str] = []
    seen: Set[str] = set()
    
    for raw in source:
        if raw is None:
            continue
        text = str(raw).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text)
    
    return normalized


def normalize_to_bool(value: Any) -> bool:
    """Normalize various input types to boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    normalized = str(value or "").strip().lower()
    if not normalized:
        return False
    return normalized in TRUTHY_VALUES


def normalize_to_int(value: Any, default: int = 0, min_val: int = None, max_val: int = None) -> int:
    """Normalize various input types to integer with bounds."""
    try:
        result = int(round(float(value)))
    except (TypeError, ValueError):
        result = default
    
    if min_val is not None and result < min_val:
        result = min_val
    if max_val is not None and result > max_val:
        result = max_val
    
    return result


def normalize_to_float(value: Any, default: float = 0.0, min_val: float = None, max_val: float = None) -> float:
    """Normalize various input types to float with bounds."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = default
    
    if min_val is not None and result < min_val:
        result = min_val
    if max_val is not None and result > max_val:
        result = max_val
    
    return result


def normalize_tier(value: Any) -> int:
    """Normalize tier value (1, 2, or 3)."""
    return normalize_to_int(value, default=1, min_val=1, max_val=3)


def normalize_confidence(value: Any) -> float:
    """Normalize confidence value (0.0 to 1.0)."""
    return normalize_to_float(value, default=0.0, min_val=0.0, max_val=1.0)
