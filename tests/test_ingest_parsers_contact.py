"""Tests for ingestion, parsing, and contact extraction."""

import pytest
from pathlib import Path
from screener.ingest import discover_files, compute_file_sha256
from screener.parsers import parse_document
from screener.errors import ParseError
from screener.extract.contact import (
    extract_email,
    extract_github,
    extract_candidate_name,
    clean_github_username,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "resumes"


def test_discover_files_and_deduplication():
    candidates, unsupported = discover_files(FIXTURES_DIR)
    assert len(candidates) > 0
    # There should be an exact duplicate file
    duplicates = [c for c in candidates if c.is_duplicate]
    assert len(duplicates) >= 1
    assert duplicates[0].duplicate_of in ("python_ai_strong.pdf", "duplicate_python_ai_strong.pdf")


def test_parse_valid_pdf():
    doc = parse_document(FIXTURES_DIR / "python_ai_strong.pdf")
    assert "Asha Rao" in doc.text
    assert "LangGraph" in doc.text
    assert doc.page_count >= 1
    assert len(doc.normalized_text_hash) == 64


def test_parse_corrupt_pdf():
    with pytest.raises(ParseError) as exc_info:
        parse_document(FIXTURES_DIR / "corrupt.pdf")
    assert exc_info.value.reason in ("unreadable_pdf", "parse_error")


def test_parse_empty_pdf():
    with pytest.raises(ParseError) as exc_info:
        parse_document(FIXTURES_DIR / "empty.pdf")
    assert exc_info.value.reason == "no_extractable_text"


def test_parse_encrypted_pdf():
    with pytest.raises(ParseError) as exc_info:
        parse_document(FIXTURES_DIR / "encrypted.pdf")
    assert exc_info.value.reason in ("encrypted_pdf", "unreadable_pdf")


def test_parse_fake_pdf():
    with pytest.raises(ParseError) as exc_info:
        parse_document(FIXTURES_DIR / "fake_pdf.pdf")
    assert exc_info.value.reason in ("unreadable_pdf", "parse_error")


def test_contact_email_extraction():
    text = "Contact me at asha.rao@example.com or support@company.org"
    email = extract_email(text)
    assert email == "asha.rao@example.com"


def test_contact_github_extraction():
    text = "My profile is https://github.com/asharao and project at github.com/asharao/repo"
    url, username = extract_github(text)
    assert url == "https://github.com/asharao"
    assert username == "asharao"


def test_github_reserved_paths_ignored():
    assert clean_github_username("features") is None
    assert clean_github_username("trending") is None
    assert clean_github_username("marketplace") is None
    assert clean_github_username("johndoe") == "johndoe"


def test_name_heuristic():
    text = "James Miller\njames@example.com\nSkills: Java, React"
    name = extract_candidate_name(text, "james_miller_cv.pdf")
    assert name == "James Miller"

    # Fallback to filename when text has no clear name line
    text_no_name = "Experience Summary\njames@example.com\n12345678"
    name2 = extract_candidate_name(text_no_name, "david_chen_resume.pdf")
    assert "David Chen" in name2
