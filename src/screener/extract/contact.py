"""Contact extraction: email, GitHub username/URL, and name heuristic."""

import re
from pathlib import Path
from typing import List, Optional, Tuple

EMAIL_REGEX = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

# Valid GitHub username regex per GitHub specifications
GITHUB_USERNAME_REGEX = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")

# GitHub URL regex matching https://github.com/username or github.com/username/repo
GITHUB_URL_REGEX = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9_.-]+)(?:/([A-Za-z0-9_.-]+))?",
    re.IGNORECASE,
)

RESERVED_GITHUB_PATHS = {
    "features",
    "topics",
    "marketplace",
    "orgs",
    "sponsors",
    "about",
    "pricing",
    "login",
    "join",
    "settings",
    "enterprise",
    "collections",
    "trending",
    "explore",
    "notifications",
    "pulls",
    "issues",
    "apps",
    "security",
    "customer-stories",
    "readme",
}

HEADING_WORDS = {
    "resume",
    "curriculum",
    "vitae",
    "cv",
    "profile",
    "summary",
    "experience",
    "education",
    "skills",
    "projects",
    "contact",
    "objective",
    "work",
    "employment",
}


def extract_email(text: str) -> Optional[str]:
    """Extract first valid email address from text."""
    match = EMAIL_REGEX.search(text)
    return match.group(0).strip() if match else None


def clean_github_username(raw: str) -> Optional[str]:
    """Validate and clean GitHub username."""
    cleaned = raw.strip().rstrip("/").lstrip("@")
    if cleaned.lower() in RESERVED_GITHUB_PATHS:
        return None
    if GITHUB_USERNAME_REGEX.match(cleaned):
        return cleaned
    return None


def extract_github(
    text: str,
    hyperlinks: Optional[List[str]] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract (github_url, github_username).
    Prefer hyperlink annotations first, then text regex.
    """
    # 1. Check hyperlinks first
    if hyperlinks:
        for link in hyperlinks:
            match = GITHUB_URL_REGEX.search(link)
            if match:
                raw_user = match.group(1)
                username = clean_github_username(raw_user)
                if username:
                    return f"https://github.com/{username}", username

    # 2. Check text regex
    for match in GITHUB_URL_REGEX.finditer(text):
        raw_user = match.group(1)
        username = clean_github_username(raw_user)
        if username:
            return f"https://github.com/{username}", username

    return None, None


def extract_candidate_name(text: str, filename: str) -> str:
    """
    Name heuristic:
    Inspect first 8 non-empty lines. Look for line with 2-4 alphabetic tokens,
    no '@', no digits, and no standard resume heading words.
    Fallback to prettified filename.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()][:8]

    for line in lines:
        if "@" in line or any(char.isdigit() for char in line):
            continue
        # Split tokens
        tokens = line.split()
        if 2 <= len(tokens) <= 4:
            # Check all alphabetic and not heading words
            if all(t.isalpha() for t in tokens):
                lower_tokens = [t.lower() for t in tokens]
                if not any(t in HEADING_WORDS for t in lower_tokens):
                    return line

    # Fallback to prettified filename
    stem = Path(filename).stem
    cleaned = re.sub(r"[_\-]+", " ", stem)
    cleaned = re.sub(r"(resume|cv|\bdoc\b)", "", cleaned, flags=re.IGNORECASE).strip()
    tokens = [t.capitalize() for t in cleaned.split() if t.isalpha()]
    if tokens:
        return " ".join(tokens)

    return "Unknown Candidate"
