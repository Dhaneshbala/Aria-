"""Web search service — plain requests + Google HTML scraping, zero external packages."""
import asyncio
import re
import html as html_mod
from typing import List, Dict
from urllib.parse import quote_plus

import requests

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class ResearchService:

    async def search(self, query: str, max_results: int = 8) -> List[Dict]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._search_google, query, max_results)

    def _search_google(self, query: str, max_results: int) -> List[Dict]:
        try:
            url = f"https://www.google.com/search?q={quote_plus(query)}&num={max_results + 3}"
            resp = requests.get(url, headers=_HEADERS, timeout=10)
            resp.raise_for_status()

            results = []
            # Google uses <h3> for result titles
            for m in re.finditer(r'<h3[^>]*>(.*?)</h3>', resp.text, re.DOTALL):
                title = html_mod.unescape(re.sub(r'<[^>]+>', '', m.group(1))).strip()
                if len(title) < 8:
                    continue
                after = resp.text[m.end():m.end()+800]
                snippet = ""
                # Google wraps snippets in <span> inside <div class="...">
                span_match = re.search(r'<span[^>]*>(.*?)</span>', after, re.DOTALL)
                if span_match:
                    snippet = html_mod.unescape(re.sub(r'<[^>]+>', '', span_match.group(1))).strip()
                # Fallback: try <div> with longer text
                if not snippet or len(snippet) < 20:
                    div_match = re.search(r'<div[^>]*>(.*?)</div>', after, re.DOTALL)
                    if div_match:
                        raw = html_mod.unescape(re.sub(r'<[^>]+>', '', div_match.group(1))).strip()
                        if len(raw) > len(snippet):
                            snippet = raw
                # Extract URL from nearest <a href>
                link = ""
                a_match = re.search(r'<a[^>]+href="(/url\?q=([^&"]+))', resp.text[max(0, m.start()-500):m.end()])
                if a_match:
                    link = html_mod.unescape(a_match.group(2))
                results.append({"title": title, "snippet": snippet[:300], "url": link})
                if len(results) >= max_results:
                    break

            return results
        except Exception as e:
            return [{"title": "Search unavailable", "snippet": str(e), "url": ""}]

    async def search_news(self, query: str) -> List[Dict]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._search_google_news, query)

    def _search_google_news(self, query: str) -> List[Dict]:
        try:
            url = f"https://www.google.com/search?q={quote_plus(query)}&tbm=nws&num=5"
            resp = requests.get(url, headers=_HEADERS, timeout=10)
            resp.raise_for_status()

            results = []
            for m in re.finditer(r'<h3[^>]*>(.*?)</h3>', resp.text, re.DOTALL):
                title = html_mod.unescape(re.sub(r'<[^>]+>', '', m.group(1))).strip()
                if len(title) < 8:
                    continue
                after = resp.text[m.end():m.end()+600]
                snippet = ""
                span_match = re.search(r'<span[^>]*>(.*?)</span>', after, re.DOTALL)
                if span_match:
                    snippet = html_mod.unescape(re.sub(r'<[^>]+>', '', span_match.group(1))).strip()
                results.append({
                    "title": title, "snippet": snippet[:200],
                    "url": "", "date": "", "source": "",
                })
                if len(results) >= 5:
                    break
            return results
        except Exception:
            return []
