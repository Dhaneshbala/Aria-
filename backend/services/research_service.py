"""Web search service using DuckDuckGo."""
import asyncio
from typing import List, Dict


class ResearchService:

    async def search(self, query: str, max_results: int = 8) -> List[Dict]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._search_sync, query, max_results)

    def _search_sync(self, query: str, max_results: int) -> List[Dict]:
        try:
            from duckduckgo_search import DDGS
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append({
                        "title": r.get("title", ""),
                        "snippet": r.get("body", ""),
                        "url": r.get("href", ""),
                    })
            return results
        except Exception as e:
            return [{"title": "Search unavailable", "snippet": str(e), "url": ""}]

    async def search_news(self, query: str) -> List[Dict]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._news_sync, query)

    def _news_sync(self, query: str) -> List[Dict]:
        try:
            from duckduckgo_search import DDGS
            results = []
            with DDGS() as ddgs:
                for r in ddgs.news(query, max_results=5):
                    results.append({
                        "title": r.get("title", ""),
                        "snippet": r.get("body", ""),
                        "url": r.get("url", ""),
                        "date": r.get("date", ""),
                        "source": r.get("source", ""),
                    })
            return results
        except Exception:
            return []
