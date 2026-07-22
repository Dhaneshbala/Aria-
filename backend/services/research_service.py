"""Web search service — plain requests + Bing HTML scraping, zero external packages."""
import asyncio
import re
import html as html_mod
from typing import List, Dict
from urllib.parse import quote_plus

import requests

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Accept-Language": "en-US,en;q=0.9",
}


class ResearchService:

    async def search(self, query: str, max_results: int = 8) -> List[Dict]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._search_bing, query, max_results)

    def _search_bing(self, query: str, max_results: int) -> List[Dict]:
        try:
            url = f"https://www.bing.com/search?q={quote_plus(query)}&count={max_results + 3}"
            resp = requests.get(url, headers=_HEADERS, timeout=10)
            resp.raise_for_status()

            results = []
            for m in re.finditer(r'<h2[^>]*>(.*?)</h2>', resp.text, re.DOTALL):
                title = html_mod.unescape(re.sub(r'<[^>]+>', '', m.group(1))).strip()
                if len(title) < 8:
                    continue
                after = resp.text[m.end():m.end()+600]
                snippet = ""
                p_match = re.search(r'<p[^>]*>(.*?)</p>', after, re.DOTALL)
                if p_match:
                    snippet = html_mod.unescape(re.sub(r'<[^>]+>', '', p_match.group(1))).strip()
                results.append({"title": title, "snippet": snippet[:300], "url": ""})
                if len(results) >= max_results:
                    break

            return results
        except Exception as e:
            return [{"title": "Search unavailable", "snippet": str(e), "url": ""}]

    async def search_news(self, query: str) -> List[Dict]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._search_bing_news, query)

    def _search_bing_news(self, query: str) -> List[Dict]:
        try:
            url = f"https://www.bing.com/news/search?q={quote_plus(query)}&count=5"
            resp = requests.get(url, headers=_HEADERS, timeout=10)
            resp.raise_for_status()

            results = []
            for m in re.finditer(r'<h2[^>]*>(.*?)</h2>', resp.text, re.DOTALL):
                title = html_mod.unescape(re.sub(r'<[^>]+>', '', m.group(1))).strip()
                if len(title) < 8:
                    continue
                after = resp.text[m.end():m.end()+400]
                snippet = ""
                p_match = re.search(r'<p[^>]*>(.*?)</p>', after, re.DOTALL)
                if p_match:
                    snippet = html_mod.unescape(re.sub(r'<[^>]+>', '', p_match.group(1))).strip()
                results.append({
                    "title": title, "snippet": snippet[:200],
                    "url": "", "date": "", "source": "",
                })
                if len(results) >= 5:
                    break
            return results
        except Exception:
            return []
