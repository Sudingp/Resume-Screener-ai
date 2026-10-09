"""Pytest configuration and global fixtures."""

import sys
from pathlib import Path

# Add src to sys.path so screener can be imported cleanly
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Automatically ensure synthetic test fixtures exist on clean checkouts
fixtures_dir = Path(__file__).resolve().parent / "fixtures" / "resumes"
if not fixtures_dir.is_dir() or len(list(fixtures_dir.glob("*.pdf"))) < 5:
    try:
        from tests.fixtures.make_fixtures import make_fixtures
        make_fixtures()
    except Exception:
        pass
