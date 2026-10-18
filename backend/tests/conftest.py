"""Pytest configuration — isolates test data from real user data.

Points ARIA_DATA_DIR at a temp dir BEFORE any service module is imported,
so tests never touch the real index. Imports of services.* happen lazily
inside fixtures/tests.
"""

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="aria_test_"))
# Point all data (conversations, config, telemetry, logs, chroma) at the
# temp dir so tests never read or write the real ~/.aria_data.
os.environ["ARIA_DATA_DIR"] = str(_TMP / "aria_data")
# Disable ChromaDB's telemetry background threads — they can keep the
# interpreter alive after the session, hanging teardown intermittently.
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

import pytest


@pytest.fixture(autouse=True)
def clean_db():
    """No-op placeholder (File Organizer removed, no tables to wipe)."""
    yield None


@pytest.fixture
def tmp_files(tmp_path):
    """Create a handful of sample files and return their paths."""
    files = {}
    for name, content in [
        (
            "algebra_hw.txt",
            "Solve for x: 2x + 5 = 13. Show working.\nHomework due Friday.",
        ),
        (
            "cells_notes.txt",
            "Plant cells have chloroplasts and a cell wall.\nAnimal cells do not.",
        ),
        (
            "python_code.py",
            "def fib(n):\n    return n if n < 2 else fib(n-1) + fib(n-2)\nprint(fib(10))",
        ),
        ("invoice.pdf", ""),
        ("essay_english.docx", ""),
    ]:
        p = tmp_path / name
        p.write_text(content)
        files[name] = str(p)
    return files
