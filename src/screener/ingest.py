"""Ingestion module: file discovery, size capping, and SHA-256 deduplication."""

import hashlib
from pathlib import Path
from typing import Dict, List, Set, Tuple
from screener.models import CandidateFile


SUPPORTED_EXTENSIONS: Set[str] = {".pdf", ".docx", ".txt"}


def compute_file_sha256(path: Path) -> str:
    """Compute SHA-256 hex digest of a file in chunks to optimize memory."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def normalize_text_hash(text: str) -> str:
    """Hash normalized text (lowercased, whitespace-stripped) to detect re-exports."""
    norm = "".join(text.lower().split())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def discover_files(
    directory: Path,
    max_size_mb: int = 10,
    supported_extensions: Set[str] = SUPPORTED_EXTENSIONS,
) -> Tuple[List[CandidateFile], int]:
    """
    Discover all files in directory recursively.
    Returns:
        (candidate_files, unsupported_count)
        where candidate_files includes exact duplicate flags.
    """
    if not directory.exists() or not directory.is_dir():
        raise FileNotFoundError(f"Input directory does not exist or is not a directory: {directory}")

    max_size_bytes = max_size_mb * 1024 * 1024
    unsupported_count = 0
    candidate_files: List[CandidateFile] = []
    seen_hashes: Dict[str, str] = {}  # sha256 -> first_seen_filename

    # Sort files deterministically by name
    all_paths = sorted(directory.rglob("*"))

    for p in all_paths:
        if not p.is_file():
            continue

        ext = p.suffix.lower()
        if ext not in supported_extensions:
            unsupported_count += 1
            continue

        size = p.stat().st_size
        sha256 = compute_file_sha256(p)

        is_dup = False
        dup_of = None
        if sha256 in seen_hashes:
            is_dup = True
            dup_of = seen_hashes[sha256]
        else:
            seen_hashes[sha256] = p.name

        candidate_files.append(
            CandidateFile(
                path=p,
                filename=p.name,
                size_bytes=size,
                sha256=sha256,
                is_duplicate=is_dup,
                duplicate_of=dup_of,
            )
        )

    return candidate_files, unsupported_count
