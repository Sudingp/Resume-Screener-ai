"""Deterministic PDF parser using pdfplumber extracting text and hyperlink annotations."""

from pathlib import Path
from typing import List, Set
import pdfplumber
from pdfminer.pdfdocument import PDFPasswordIncorrect, PDFEncryptionError
from pdfminer.pdfparser import PDFSyntaxError
from screener.errors import ParseError
from screener.models import ParsedDocument
from screener.ingest import normalize_text_hash


def parse_pdf(path: Path, max_pages: int = 10) -> ParsedDocument:
    """
    Parse a PDF file, returning extracted text and hyperlink URIs.
    Raises ParseError with specific reasons:
      - 'encrypted_pdf'
      - 'unreadable_pdf'
      - 'no_extractable_text'
      - 'file_too_large'
      - 'parse_error'
    """
    try:
        with pdfplumber.open(path) as pdf:
            page_count = len(pdf.pages)
            if page_count > max_pages:
                raise ParseError(
                    reason="file_too_large",
                    message=f"PDF page count ({page_count}) exceeds limit ({max_pages})",
                )

            extracted_text_chunks: List[str] = []
            hyperlinks_set: Set[str] = set()

            for page_num, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text()
                if page_text:
                    extracted_text_chunks.append(page_text)

                # Extract hyperlinks from annotations
                try:
                    if hasattr(page, "hyperlinks") and page.hyperlinks:
                        for hl in page.hyperlinks:
                            if isinstance(hl, dict) and "uri" in hl and hl["uri"]:
                                hyperlinks_set.add(hl["uri"].strip())
                    elif hasattr(page, "annots") and page.annots:
                        for annot in page.annots:
                            uri = annot.get("uri") or annot.get("A", {}).get("URI")
                            if uri:
                                hyperlinks_set.add(str(uri).strip())
                except Exception:
                    # Non-fatal hyperlink extraction failure
                    pass

            full_text = "\n\n".join(extracted_text_chunks).strip()
            if not full_text:
                raise ParseError(
                    reason="no_extractable_text",
                    message="PDF contained no extractable text (e.g. scanned image or empty document)",
                )

            norm_hash = normalize_text_hash(full_text)

            return ParsedDocument(
                text=full_text,
                hyperlinks=sorted(hyperlinks_set),
                page_count=page_count,
                normalized_text_hash=norm_hash,
            )

    except (PDFPasswordIncorrect, PDFEncryptionError) as e:
        raise ParseError(reason="encrypted_pdf", message=f"PDF is encrypted: {e}") from e
    except (PDFSyntaxError, ValueError) as e:
        raise ParseError(reason="unreadable_pdf", message=f"Corrupt or invalid PDF: {e}") from e
    except ParseError:
        raise
    except Exception as e:
        # Check cause/context for pdfminer wrapped exceptions
        ctx = getattr(e, "__context__", None) or getattr(e, "__cause__", None)
        if ctx and isinstance(ctx, (PDFPasswordIncorrect, PDFEncryptionError)):
            raise ParseError(reason="encrypted_pdf", message=f"PDF is encrypted: {ctx}") from e
        if ctx and isinstance(ctx, (PDFSyntaxError, ValueError)):
            raise ParseError(reason="unreadable_pdf", message=f"Corrupt PDF: {ctx}") from e

        msg = (str(e) + " " + repr(e)).lower()
        if "password" in msg or "encrypt" in msg:
            raise ParseError(reason="encrypted_pdf", message=str(e)) from e
        if "syntax" in msg or "corrupt" in msg or "header" in msg or "startxref" in msg or "eof" in msg:
            raise ParseError(reason="unreadable_pdf", message=str(e)) from e
        raise ParseError(reason="parse_error", message=str(e)) from e
