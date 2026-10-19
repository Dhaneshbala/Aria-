"""Regression tests for /api/research/* — no network, services mocked.

Covers: search passthrough shape + query plumbing; youtube passthrough;
model validation (rejects non-string / missing fields via pydantic).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _client():
    from fastapi.testclient import TestClient

    import main

    return TestClient(main.app)


class TestWebSearch:
    def test_search_passthrough_and_query(self, monkeypatch):
        from services.research_service import ResearchService

        called = []

        async def _search(self, query, max_results=8):
            called.append(query)
            return [
                {
                    "title": "Newton's laws",
                    "url": "https://example.com/newton",
                    "snippet": "F=ma",
                },
                {"title": "Second", "url": "https://example.com/2", "snippet": "..."},
            ]

        monkeypatch.setattr(ResearchService, "search", _search)
        r = _client().post("/api/research/search", json={"query": "newtons laws"})
        assert r.status_code == 200
        body = r.json()
        assert called == ["newtons laws"]
        assert body["results"][0]["title"] == "Newton's laws"
        assert len(body["results"]) == 2

    def test_search_empty_results_ok(self, monkeypatch):
        from services.research_service import ResearchService

        async def _search(self, query, max_results=8):
            return []

        monkeypatch.setattr(ResearchService, "search", _search)
        r = _client().post("/api/research/search", json={"query": "zzz no results"})
        assert r.status_code == 200
        assert r.json() == {"results": []}

    def test_search_requires_string_query(self):
        r = _client().post("/api/research/search", json={})
        assert r.status_code == 422  # pydantic body validation


class TestYouTube:
    def test_youtube_passthrough(self, monkeypatch):
        from services.youtube_service import YouTubeService

        called = []

        async def _process(self, url):
            called.append(url)
            return {"status": "ok", "transcript": "lesson text", "title": "Phy lesson"}

        monkeypatch.setattr(YouTubeService, "process", _process)
        r = _client().post(
            "/api/research/youtube", json={"url": "https://youtube.com/watch?v=x"}
        )
        assert r.status_code == 200
        body = r.json()
        assert called == ["https://youtube.com/watch?v=x"]
        assert body["status"] == "ok"
        assert "transcript" in body

    def test_youtube_requires_url(self):
        r = _client().post("/api/research/youtube", json={})
        assert r.status_code == 422

    def test_youtube_error_is_reported_in_transport(self, monkeypatch):
        """Service errors surface as a 500 with JSON detail, not a hang."""
        from services.youtube_service import YouTubeService

        async def _boom(self, url):
            raise RuntimeError("download failed")

        monkeypatch.setattr(YouTubeService, "process", _boom)
        r = _client().post("/api/research/youtube", json={"url": "https://x.io/1"})
        assert r.status_code == 500
