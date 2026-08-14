"""Pytest configuration: ensure project root is on sys.path."""

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def write_temp_text_file(content: str, suffix: str = ".csv", encoding: str = "utf-8-sig") -> str:
    """Write content to a closed temp file (safe for reopen on Windows)."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    with open(path, "w", encoding=encoding, newline="") as handle:
        handle.write(content)
    return path
