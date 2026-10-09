"""Typed exceptions for deterministic and fail-visible error handling."""

from typing import Optional


class ScreenerError(Exception):
    """Base exception for all screener errors."""
    pass


class ParseError(ScreenerError):
    """Raised when a resume document cannot be parsed into text."""

    def __init__(self, reason: str, message: Optional[str] = None):
        self.reason = reason
        super().__init__(message or f"Parse error: {reason}")


class LLMError(ScreenerError):
    """Raised when an LLM provider call or extraction fails."""

    def __init__(self, message: str, provider: Optional[str] = None):
        self.provider = provider
        super().__init__(message)


class GitHubError(ScreenerError):
    """Raised when GitHub enrichment fails."""

    def __init__(self, status: str, message: Optional[str] = None):
        self.status = status
        super().__init__(message or f"GitHub error: {status}")
