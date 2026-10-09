"""Plain text parser."""

from pathlib import Path
from screener.errors import ParseError
from screener.models import ParsedDocument
from screener.ingest import normalize_text_hash


def parse_txt(path: Path) -> ParsedDocument:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            text = path.read_text(encoding="latin-1")
        except Exception as e:
            raise ParseError(reason="unreadable_pdf", message=f"Cannot decode text file: {e}") from e
    except Exception as e:
        raise ParseError(reason="parse_error", message=str(e)) from e

    cleaned = text.strip()
    if not cleaned:
        raise ParseError(reason="no_extractable_text", message="Text file is empty")

    return ParsedDocument(
        text=cleaned,
        hyperlinks=[],
        page_count=1,
        normalized_text_hash=normalize_text_hash(cleaned),
    )
