"""
LLM Guard Service for LVMH Pipeline

Provides PII masking, toxicity detection, and prompt injection protection.
"""

import logging
import re
from typing import Tuple, Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

try:
    from llm_guard import input_scanners
    from llm_guard.util import get_logger
    LLM_GUARD_AVAILABLE = True
except ImportError:
    LLM_GUARD_AVAILABLE = False
    logger.warning("llm-guard not available, security scanning disabled")


@dataclass
class SecurityResult:
    """Result of security scanning."""
    is_safe: bool
    sanitized_text: str
    risk_score: float
    detected_issues: List[str]
    scanner_results: Dict[str, Any]


class LLMGuardService:
    """
    Security service using llm-guard for PII masking and protection.
    
    Features:
    - PII anonymization (emails, phones, names)
    - Toxicity detection
    - Prompt injection protection
    - Secrets detection
    """
    
    # Default PII patterns for fallback
    DEFAULT_PATTERNS = {
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'phone': r'\b(?:\+33|0)[1-9](?:[\s.-]?\d{2}){4}\b',
        'credit_card': r'\b(?:\d{4}[\s-]?){3}\d{4}\b',
        'ssn': r'\b\d{2}\s?\d{2}\s?\d{2}\s?\d{3}\b',
    }
    
    def __init__(self, use_llm_guard: bool = True):
        self.use_llm_guard = use_llm_guard and LLM_GUARD_AVAILABLE
        self._scanner = None
        
        if self.use_llm_guard:
            try:
                self._init_llm_guard_scanners()
            except Exception as e:
                logger.warning(f"Failed to initialize llm-guard scanners: {e}")
                self.use_llm_guard = False
    
    def _init_llm_guard_scanners(self):
        """Initialize llm-guard scanners."""
        try:
            # Try without arguments first (newer API)
            self._scanner = input_scanners.Anonymize()
            logger.info("LLM Guard scanners initialized successfully")
        except Exception as e:
            logger.warning(f"Could not initialize Anonymize scanner: {e}")
            self._scanner = None
    
    def scan(self, text: str) -> SecurityResult:
        """
        Scan and sanitize text.
        
        Args:
            text: Input text to scan
            
        Returns:
            SecurityResult with sanitized text and detected issues
        """
        if not self.use_llm_guard or self._scanner is None:
            return self._fallback_scan(text)
        
        try:
            result = self._scanner.scan(text)
            sanitized = result.get("text", text)
            issues = []
            
            # Check for detected entities
            if result.get("entities"):
                for entity_type, entities in result["entities"].items():
                    if entities:
                        issues.append(f"{entity_type}: {len(entities)} detected")
            
            # Calculate risk score (0-1)
            risk_score = 1.0 if issues else 0.0
            
            return SecurityResult(
                is_safe=True,
                sanitized_text=sanitized,
                risk_score=risk_score,
                detected_issues=issues,
                scanner_results=result
            )
            
        except Exception as e:
            logger.error(f"LLM Guard scan failed: {e}")
            return self._fallback_scan(text)
    
    def _fallback_scan(self, text: str) -> SecurityResult:
        """
        Fallback scanning using regex patterns.
        Used when llm-guard is not available.
        """
        sanitized = text
        issues = []
        
        # Mask emails
        sanitized, email_count = self._replace_pattern(
            sanitized, self.DEFAULT_PATTERNS['email'], "[EMAIL]"
        )
        if email_count > 0:
            issues.append(f"email: {email_count} detected")
        
        # Mask phone numbers
        sanitized, phone_count = self._replace_pattern(
            sanitized, self.DEFAULT_PATTERNS['phone'], "[PHONE]"
        )
        if phone_count > 0:
            issues.append(f"phone: {phone_count} detected")
        
        # Mask credit cards
        sanitized, cc_count = self._replace_pattern(
            sanitized, self.DEFAULT_PATTERNS['credit_card'], "[CREDIT_CARD]"
        )
        if cc_count > 0:
            issues.append(f"credit_card: {cc_count} detected")
        
        risk_score = 1.0 if issues else 0.0
        
        return SecurityResult(
            is_safe=True,
            sanitized_text=sanitized,
            risk_score=risk_score,
            detected_issues=issues,
            scanner_results={"method": "regex_fallback"}
        )
    
    def _replace_pattern(self, text: str, pattern: str, replacement: str) -> Tuple[str, int]:
        """Replace pattern and return count of replacements."""
        matches = re.findall(pattern, text)
        sanitized = re.sub(pattern, replacement, text)
        return sanitized, len(matches)
    
    def check_prompt_injection(self, text: str) -> bool:
        """
        Check for prompt injection attempts.
        
        Args:
            text: Input text to check
            
        Returns:
            True if prompt injection detected
        """
        if not self.use_llm_guard:
            return self._fallback_prompt_injection_check(text)
        
        try:
            from llm_guard.input_scanners import PromptInjection
            scanner = PromptInjection()
            result = scanner.scan(text)
            return not result.get("is_safe", True)
        except Exception as e:
            logger.warning(f"Prompt injection check failed: {e}")
            return self._fallback_prompt_injection_check(text)
    
    def _fallback_prompt_injection_check(self, text: str) -> bool:
        """Fallback prompt injection check using common patterns."""
        injection_patterns = [
            r"ignore\s+(previous|above|all)\s+(instructions?|rules?|prompts?)",
            r"system\s*:\s*",
            r"you\s+are\s+(now|free|allowed)\s+to",
            r"forget\s+(everything|all|your)\s+(instructions?|rules?)",
            r"new\s+instructions?:",
            r"\\n\\n(system|assistant|user):",
        ]
        
        text_lower = text.lower()
        for pattern in injection_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True
        
        return False
    
    def check_toxicity(self, text: str) -> Tuple[bool, float]:
        """
        Check for toxic content.
        
        Args:
            text: Input text to check
            
        Returns:
            Tuple of (is_safe, toxicity_score)
        """
        if not self.use_llm_guard:
            return True, 0.0
        
        try:
            from llm_guard.input_scanners import Toxicity
            scanner = Toxicity()
            result = scanner.scan(text)
            return result.get("is_safe", True), result.get("toxicity_score", 0.0)
        except Exception as e:
            logger.warning(f"Toxicity check failed: {e}")
            return True, 0.0
    
    def check_secrets(self, text: str) -> Tuple[bool, List[str]]:
        """
        Check for secrets/API keys in text.
        
        Args:
            text: Input text to check
            
        Returns:
            Tuple of (is_safe, list of detected secrets)
        """
        if not self.use_llm_guard:
            return self._fallback_secrets_check(text)
        
        try:
            from llm_guard.input_scanners import Secrets
            scanner = Secrets()
            result = scanner.scan(text)
            is_safe = result.get("is_safe", True)
            detected = result.get("secrets", [])
            return is_safe, detected
        except Exception as e:
            logger.warning(f"Secrets check failed: {e}")
            return self._fallback_secrets_check(text)
    
    def _fallback_secrets_check(self, text: str) -> Tuple[bool, List[str]]:
        """Fallback secrets check using patterns."""
        secrets = []
        
        # Check for API key patterns
        api_key_patterns = {
            'OPENAI_API_KEY': r'OPENAI_API_KEY[=:\s]+[a-zA-Z0-9-_]+',
            'MISTRAL_API_KEY': r'MISTRAL_API_KEY[=:\s]+[a-zA-Z0-9-_]+',
            'GROQ_API_KEY': r'GROQ_API_KEY[=:\s]+[a-zA-Z0-9-_]+',
        }
        
        for name, pattern in api_key_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                secrets.append(name)
        
        return len(secrets) == 0, secrets


# Singleton instance
_service: Optional[LLMGuardService] = None


def get_llm_guard_service() -> LLMGuardService:
    """Get singleton instance of LLMGuardService."""
    global _service
    if _service is None:
        _service = LLMGuardService()
    return _service


def secure_input(text: str) -> Tuple[str, SecurityResult]:
    """
    Convenience function to secure input text.
    
    Args:
        text: Input text to secure
        
    Returns:
        Tuple of (sanitized_text, security_result)
    """
    service = get_llm_guard_service()
    result = service.scan(text)
    return result.sanitized_text, result
