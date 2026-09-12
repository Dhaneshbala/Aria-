"""Pytest configuration for organizer tests.

Sets ARIA_ORGANIZER_DB to a temp path BEFORE any service module is imported,
so tests never touch the real index. Imports of services.* happen lazily
inside fixtures/tests.
"""
import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="aria_orgtest_"))
os.environ["ARIA_ORGANIZER_DB"] = str(_TMP / "organizer_test.db")
os.environ["ARIA_ORGANIZER_TESTING"] = "1"
# Point all data (conversations, config, telemetry, logs, chroma) at the
# temp dir so tests never read or write the real ~/.aria_data.
os.environ["ARIA_DATA_DIR"] = str(_TMP / "aria_data")

import pytest


@pytest.fixture(autouse=True)
def clean_db():
    """Wipe all tables before each test, return the Database instance.

    NOTE: File Organizer was removed — if services.organizer_db is gone,
    this fixture is a no-op so the remaining tests still run.
    """
    try:
        from services.organizer_db import get_db
    except ImportError:
        yield None
        return

    db = get_db()
    for table in ("files", "history", "rules", "profiles", "saved_searches",
                  "folders", "events", "settings", "feedback", "proposals"):
        db.query(f"DELETE FROM {table}")
    yield db


@pytest.fixture
def tmp_files(tmp_path):
    """Create a handful of sample files and return their paths."""
    files = {}
    for name, content in [
        ("algebra_hw.txt", "Solve for x: 2x + 5 = 13. Show working.\nHomework due Friday."),
        ("cells_notes.txt", "Plant cells have chloroplasts and a cell wall.\nAnimal cells do not."),
        ("python_code.py", "def fib(n):\n    return n if n < 2 else fib(n-1) + fib(n-2)\nprint(fib(10))"),
        ("invoice.pdf", ""),
        ("essay_english.docx", ""),
    ]:
        p = tmp_path / name
        p.write_text(content)
        files[name] = str(p)
    return files
