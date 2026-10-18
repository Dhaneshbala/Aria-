"""KB persistence regression tests — rebuild_index must work after upload.

Before the fix, /api/kb/upload ingested a tempfile the router deleted right
after ingest; the stored file_path pointed at a dead temp file, so
rebuild_index silently skipped every document forever ("rebuilt: 0").
"""

import asyncio
import os
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.knowledge_base_service import (
    KB_FILES_DIR,
    KnowledgeBaseService,
    _file_hash,
)


def _run(coro):
    return asyncio.run(coro)


def _fake_embed(monkeypatch):
    """Deterministic offline embed_batch (no Ollama, no network)."""
    from services.ollama_service import OllamaService

    async def _stub(self, model, chunks):
        return [[((len(c) % 7) + 1) / 64] * 8 for c in chunks]

    monkeypatch.setattr(OllamaService, "embed_batch", _stub)


def _sample_text() -> str:
    # Unique per call so hashes never collide between tests (dedup guard).
    salt = uuid.uuid4().hex
    words = []
    for i in range(300):
        words.append(f"photosynthesis{i} {salt} oxygen carbon glucose")
    return " ".join(words)


@pytest.fixture
def svc():
    return KnowledgeBaseService()


class TestIngestPersistence:
    def test_ingest_persists_original_inside_kb_files_dir(
        self, tmp_path, monkeypatch, svc
    ):
        _fake_embed(monkeypatch)
        src = tmp_path / f"study_notes_{uuid.uuid4().hex[:8]}.txt"
        src.write_text(_sample_text())

        res = _run(svc.ingest_file(str(src), collection="general"))
        assert res["status"] == "ok", res

        h = _file_hash(str(src))
        doc = svc._documents[h]
        stored = Path(doc["file_path"])
        # Filename is preserved as the human-facing title; the on-disk copy
        # is keyed by content hash inside KB_FILES_DIR/<hash>.<suffix>.
        assert stored != src
        assert stored.name == f"{h}.txt"
        assert stored.parent == KB_FILES_DIR
        assert stored.exists()
        src.unlink()
        # The persisted copy survives the caller deleting its temp file.
        assert stored.exists()

    def test_rebuild_no_eternal_skip(self, tmp_path, monkeypatch, svc):
        """The headline bug: upload → delete temp → rebuild used to skip."""
        _fake_embed(monkeypatch)
        src = tmp_path / f"rebuild_me_{uuid.uuid4().hex[:8]}.txt"
        src.write_text(_sample_text())

        res = _run(svc.ingest_file(str(src), collection="general"))
        assert res["status"] == "ok"
        # Simulate the router's finally-block: the upload tempfile is gone.
        h = _file_hash(str(src))
        doc_hash_before = svc._documents[h]["title"]
        stored = svc._documents[h]["file_path"]
        src.unlink()

        results = _run(svc.rebuild_index())
        title = svc._documents[h]["title"]
        # Our doc must have been rebuilt (not skipped, not failed).
        rebuilt_titles = [
            d.get("title")
            for d in svc._documents.values()
            if d.get("file_path") == stored
        ]
        assert title in rebuilt_titles
        assert title == doc_hash_before
        assert results["rebuilt"] >= 1
        assert results["failed"] == 0

    def test_rebuild_preserves_original_title(self, tmp_path, monkeypatch, svc):
        _fake_embed(monkeypatch)
        src = tmp_path / f"by_hash_{uuid.uuid4().hex[:8]}.txt"
        src.write_text(_sample_text())
        res = _run(svc.ingest_file(str(src), collection="general"))
        assert res["status"] == "ok"
        h = _file_hash(str(src))
        original_title = svc._documents[h]["title"]

        _run(svc.rebuild_index())
        assert svc._documents[h]["title"] == original_title

    def test_delete_removes_persisted_copy(self, tmp_path, monkeypatch, svc):
        _fake_embed(monkeypatch)
        src = tmp_path / f"deletable_{uuid.uuid4().hex[:8]}.txt"
        src.write_text(_sample_text())
        res = _run(svc.ingest_file(str(src), collection="general"))
        assert res["status"] == "ok"

        h = _file_hash(str(src))
        stored = Path(svc._documents[h]["file_path"])
        assert stored.exists()
        assert svc.delete_document(h) is True
        assert not stored.exists()
        assert h not in svc._documents

    def test_delete_keeps_outside_paths(self, tmp_path, monkeypatch, svc):
        """Never delete files that live outside KB files dir (defensive)."""
        outside = tmp_path / "keep_me.txt"
        outside.write_text("not ours to delete")
        h = f"manual_{uuid.uuid4().hex[:8]}"
        svc._documents[h] = {
            "title": "outside doc",
            "file_hash": h,
            "collection": "general",
            "file_path": str(outside),
        }
        svc.delete_document(h, delete_file=True)
        assert outside.exists()
        assert h not in svc._documents


class TestRebuildLegacySafety:
    def test_rebuild_skips_dead_paths_without_destroying_doc(self, monkeypatch, svc):
        """Legacy docs whose source is long gone keep their chunks."""
        _fake_embed(monkeypatch)
        ghost = f"ghost_{uuid.uuid4().hex[:8]}"
        svc._documents[ghost] = {
            "title": ghost,
            "file_hash": ghost,
            "collection": "general",
            "chunks_stored": 3,
            "file_path": "/nonexistent/path/ghost.txt",
        }
        try:
            results = _run(svc.rebuild_index())
            assert ghost in svc._documents  # not destroyed
            assert results["skipped"] >= 1
        finally:
            svc._documents.pop(ghost, None)
            svc._save_meta()
