"""GitHub URL and username parsing and validation."""

from typing import List, Optional, Tuple
from screener.extract.contact import (
    extract_github,
    clean_github_username,
    GITHUB_USERNAME_REGEX,
    RESERVED_GITHUB_PATHS,
)


def parse_github_identity(
    text: str,
    hyperlinks: Optional[List[str]] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract and validate (url, username).
    Returns (None, None) if no valid profile or if username is invalid/reserved.
    """
    return extract_github(text, hyperlinks)
