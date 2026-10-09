"""Pytest configuration and global fixtures."""

import sys
from pathlib import Path

# Add src to sys.path so screener can be imported cleanly
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))
