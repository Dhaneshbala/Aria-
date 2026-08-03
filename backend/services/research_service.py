"""Web search service — multi-engine fallback, zero external packages.

Engine chain (first success wins):
  1. Google HTML scrape      — richest results when accessible
  2. Wikipedia search + API  — reliable, well-structured, works through proxies
  3. DuckDuckGo Instant Answer — quick snippets for common facts

On corporate/school networks (Zscaler etc.) Google often serves a bot-gated
page; Wikipedia's API is the dependable fallback that keeps the
cross-check + citation pipeline alive.
"""
import asyncio
import re
import html as html_mod
import json
from typing import List, Dict
from urllib.parse import quote_plus

import requests
import urllib3
urllib3.disable_warnings()

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_VERIFY = False  # tolerant of MITM school proxies; plain-HTML scraping only


class ResearchService:

    async def search(self, query: str, max_results: int = 8) -> List[Dict]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._search_all, query, max_results)

    def _search_all(self, query: str, max_results: int) -> List[Dict]:
        """Try each engine in order; merge gaps until max_results filled."""
        engines = [
            self._search_google,
            self._search_wikipedia,
            self._search_ddg_instant,
        ]
        merged: List[Dict] = []
        seen_urls = set()
        for engine in engines:
            if len(merged) >= max_results:
                break
            try:
                results = engine(query, max_results - len(merged))
            except Exception:
                results = []
            for r in results:
                url = r.get("url", "")
                if url and url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)
                merged.append(r)
                if len(merged) >= max_results:
                    break
        return merged[:max_results]

    # ── Engine 1: Google HTML ──────────────────────────────────────────────

    def _search_google(self, query: str, max_results: int) -> List[Dict]:
        url = f"https://www.google.com/search?q={quote_plus(query)}&num={max_results + 3}&udm=14"
        resp = requests.get(url, headers=_HEADERS, timeout=10, verify=_VERIFY)
        resp.raise_for_status()

        results = []
        for m in re.finditer(r'<h3[^>]*>(.*?)</h3>', resp.text, re.DOTALL):
            title = html_mod.unescape(re.sub(r'<[^>]+>', '', m.group(1))).strip()
            if len(title) < 8:
                continue
            after = resp.text[m.end():m.end() + 800]
            snippet = ""
            span_match = re.search(r'<span[^>]*>(.*?)</span>', after, re.DOTALL)
            if span_match:
                snippet = html_mod.unescape(re.sub(r'<[^>]+>', '', span_match.group(1))).strip()
            if not snippet or len(snippet) < 20:
                div_match = re.search(r'<div[^>]*>(.*?)</div>', after, re.DOTALL)
                if div_match:
                    raw = html_mod.unescape(re.sub(r'<[^>]+>', '', div_match.group(1))).strip()
                    if len(raw) > len(snippet):
                        snippet = raw
            link = ""
            a_match = re.search(r'<a[^>]+href="(/url\?q=([^&"]+))', resp.text[max(0, m.start() - 500):m.end()])
            if a_match:
                link = html_mod.unescape(a_match.group(2))
            results.append({"title": title, "snippet": snippet[:300], "url": link})
            if len(results) >= max_results:
                break
        return results

    # ── Engine 2: Wikipedia search + lede extract ──────────────────────────

    def _search_wikipedia(self, query: str, max_results: int) -> List[Dict]:
        base = "https://en.wikipedia.org/w/api.php"
        headers = {"User-Agent": "ARIA-StudyAssistant/1.0 (educational; contact: local)"}

        # 2a. Search for matching titles
        params = {
            "action": "query", "list": "search", "srsearch": query,
            "format": "json", "srlimit": str(max_results),
        }
        resp = requests.get(base, params=params, headers=headers, timeout=10, verify=_VERIFY)
        resp.raise_for_status()
        hits = resp.json().get("query", {}).get("search", [])
        if not hits:
            return []

        # 2b. Fetch the intro extract for the top hit (most informative)
        results = []
        for hit in hits:
            results.append({
                "title": hit.get("title", ""),
                "snippet": re.sub(r"<[^>]+>", "", hit.get("snippet", ""))[:300],
                "url": f"https://en.wikipedia.org/wiki/{quote_plus(hit.get('title', '').replace(' ', '_'))}",
            })

        top_title = hits[0].get("title", "")
        if top_title:
            try:
                ex_params = {
                    "action": "query", "prop": "extracts", "exintro": 1,
                    "explaintext": 1, "redirects": 1,
                    "titles": top_title, "format": "json",
                }
                er = requests.get(base, params=ex_params, headers=headers, timeout=10, verify=_VERIFY)
                er.raise_for_status()
                pages = er.json().get("query", {}).get("pages", {})
                for page in pages.values():
                    extract = (page.get("extract") or "").strip()
                    if extract:
                        results[0]["snippet"] = extract[:400]
                        break
            except Exception:
                pass
        return results

    # ── Engine 3: DuckDuckGo Instant Answer ────────────────────────────────

    def _search_ddg_instant(self, query: str, max_results: int) -> List[Dict]:
        url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_html=1&skip_disambig=1"
        resp = requests.get(url, headers={"User-Agent": "ARIA/1.0"}, timeout=10, verify=_VERIFY)
        if resp.status_code != 200:
            return []
        try:
            data = json.loads(resp.text)
        except Exception:
            return []
        results = []
        if data.get("AbstractText"):
            results.append({
                "title": data.get("Heading") or "Answer",
                "snippet": data["AbstractText"][:400],
                "url": data.get("AbstractURL", ""),
            })
        for topic in (data.get("RelatedTopics") or [])[:max_results]:
            if "Topics" in topic:  # nested category
                for sub in topic["Topics"][:2]:
                    if sub.get("Text"):
                        results.append({
                            "title": sub.get("Text", "").split(" - ")[0][:80],
                            "snippet": sub.get("Text", "")[:300],
                            "url": sub.get("FirstURL", ""),
                        })
            elif topic.get("Text"):
                results.append({
                    "title": topic["Text"].split(" - ")[0][:80],
                    "snippet": topic["Text"][:300],
                    "url": topic.get("FirstURL", ""),
                })
            if len(results) >= max_results:
                break
        return results

    # ── News (Google News) ──────────────────────────────────────────────────

    async def search_news(self, query: str) -> List[Dict]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._search_google_news, query)

    def _search_google_news(self, query: str) -> List[Dict]:
        try:
            url = f"https://www.google.com/search?q={quote_plus(query)}&tbm=nws&num=5"
            resp = requests.get(url, headers=_HEADERS, timeout=10, verify=_VERIFY)
            resp.raise_for_status()

            results = []
            for m in re.finditer(r'<h3[^>]*>(.*?)</h3>', resp.text, re.DOTALL):
                title = html_mod.unescape(re.sub(r'<[^>]+>', '', m.group(1))).strip()
                if len(title) < 8:
                    continue
                after = resp.text[m.end():m.end() + 600]
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
