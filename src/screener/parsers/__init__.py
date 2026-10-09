"""Parsers package for extracting text and hyperlinks from resumes."""

from pathlib import Path
from screener.models import ParsedDocument
from screener.errors import ParseError
from screener.parsers.pdf import parse_pdf
from screener.parsers.txt import parse_txt


def parse_document(
    path: Path,
    max_pages: int = 10,
    max_size_mb: int = 10,
) -> ParsedDocument:
    """Parse document based on extension."""
    ext = path.suffix.lower()
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > max_size_mb:
        raise ParseError(reason="file_too_large", message=f"File exceeds {max_size_mb} MB limit")

    if ext == ".pdf":
        return parse_pdf(path, max_pages=max_pages)
    elif ext == ".txt":
        return parse_txt(path)
    elif ext == ".docx":
        # If python-docx is available or fallback
        try:
            from screener.parsers.docx import parse_docx
            return parse_docx(path)
        except ImportError:
            raise ParseError(reason="parse_error", message="DOCX parser dependency not installed")
    else:
        raise ParseError(reason="parse_error", message=f"Unsupported format: {ext}")
