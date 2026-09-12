"""Citation service — Programmatic citation parsing and source grounding.

Extracts structured citations from LLM output, validates them against
available sources, and provides citation metadata for frontend display.
"""
import re
import json
import logging
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class Citation:
    """Represents a single citation reference."""
    def __init__(self, index: int, text: str, source_type: str, source_url: str = "",
                 source_title: str = "", snippet: str = "", page: int = None):
        self.index = index
        self.text = text
        self.source_type = source_type  # web, kb, document, youtube, memory
        self.source_url = source_url
        self.source_title = source_title
        self.snippet = snippet
        self.page = page

    def to_dict(self):
        d = {
            "index": self.index,
            "text": self.text,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "source_title": self.source_title,
            "snippet": self.snippet,
        }
        if self.page is not None:
            d["page"] = self.page
        return d


class CitationService:
    """Parse and manage citations in LLM responses."""

    # Pattern for [N] style citations
    CITATION_PATTERN = re.compile(r'\[(\d+)\]')
    # Pattern for page citations like "page 3" or "p. 3"
    PAGE_PATTERN = re.compile(r'(?:page|p\.?)\s*(\d+)', re.I)

    def __init__(self):
        self.sources: List[Dict] = []
        self.citations: List[Citation] = []

    def register_sources(
        self,
        web_results: List[Dict] = None,
        kb_results: List[Dict] = None,
        doc_content: str = None,
        youtube_results: Dict = None,
        memory_context: str = None,
        cross_check: List[Dict] = None,
    ):
        """Register all available sources for citation mapping."""
        self.sources = []
        self.citations = []
        idx = 1

        # Web search results
        if web_results:
            for r in web_results[:8]:
                self.sources.append({
                    "index": idx,
                    "type": "web",
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("snippet", "")[:300],
                })
                idx += 1

        # Cross-check results (if different from web results)
        if cross_check:
            existing_urls = {s.get("url") for s in self.sources if s.get("url")}
            for r in cross_check[:4]:
                url = r.get("url", "")
                if url and url not in existing_urls:
                    self.sources.append({
                        "index": idx,
                        "type": "web",
                        "title": r.get("title", ""),
                        "url": url,
                        "snippet": r.get("snippet", "")[:300],
                        "role": "cross-check",
                    })
                    existing_urls.add(url)
                    idx += 1

        # Knowledge base results
        if kb_results:
            for r in kb_results[:5]:
                self.sources.append({
                    "index": idx,
                    "type": "kb",
                    "title": r.get("metadata", {}).get("source", "Knowledge Base"),
                    "collection": r.get("collection", ""),
                    "snippet": r.get("text", "")[:200],
                    "score": r.get("score", 0),
                })
                idx += 1

        # Document content
        if doc_content:
            pages = self._extract_pages(doc_content)
            for page_num, page_text in pages[:10]:
                self.sources.append({
                    "index": idx,
                    "type": "document",
                    "title": f"Document (page {page_num})",
                    "page": page_num,
                    "snippet": page_text[:200],
                })
                idx += 1

        # YouTube
        if youtube_results and not youtube_results.get("error"):
            self.sources.append({
                "index": idx,
                "type": "youtube",
                "title": youtube_results.get("title", "YouTube Video"),
                "url": f"https://youtube.com/watch?v={youtube_results.get('video_id', '')}",
                "snippet": youtube_results.get("transcript", "")[:200],
            })
            idx += 1

    def parse_citations(self, text: str) -> Tuple[str, List[Citation]]:
        """Parse [N] citations from LLM output and return cleaned text + citation objects."""
        citations = []
        seen_indices = set()

        for match in self.CITATION_PATTERN.finditer(text):
            idx = int(match.group(1))
            if idx in seen_indices:
                continue
            seen_indices.add(idx)

            # Find matching source
            source = next((s for s in self.sources if s["index"] == idx), None)
            if source:
                citation = Citation(
                    index=idx,
                    text=match.group(0),
                    source_type=source.get("type", "unknown"),
                    source_url=source.get("url", ""),
                    source_title=source.get("title", ""),
                    snippet=source.get("snippet", ""),
                    page=source.get("page"),
                )
                citations.append(citation)

        self.citations = citations
        return text, citations

    def extract_inline_citations(self, text: str) -> List[Dict]:
        """Extract citations with their surrounding context for highlighting."""
        results = []
        for match in self.CITATION_PATTERN.finditer(text):
            idx = int(match.group(1))
            start = max(0, match.start() - 100)
            end = min(len(text), match.end() + 100)
            context = text[start:end]

            source = next((s for s in self.sources if s["index"] == idx), None)
            if source:
                results.append({
                    "index": idx,
                    "context": context,
                    "source_type": source.get("type", "unknown"),
                    "source_title": source.get("title", ""),
                    "source_url": source.get("url", ""),
                })
        return results

    def get_source_list(self) -> List[Dict]:
        """Get all registered sources as a list for frontend display."""
        return [
            {
                "index": s["index"],
                "type": s.get("type", "unknown"),
                "title": s.get("title", ""),
                "url": s.get("url", ""),
                "snippet": s.get("snippet", "")[:200],
                "page": s.get("page"),
                "score": s.get("score"),
            }
            for s in self.sources
        ]

    def build_citation_footer(self) -> str:
        """Build a formatted sources section for the response."""
        if not self.sources:
            return ""

        lines = ["\n\n---\n**Sources:**\n"]
        for s in self.sources:
            idx = s["index"]
            title = s.get("title", "Unknown")
            url = s.get("url", "")
            stype = s.get("type", "")

            if stype == "web" and url:
                lines.append(f"[{idx}] [{title}]({url})")
            elif stype == "kb":
                lines.append(f"[{idx}] {title} (Knowledge Base)")
            elif stype == "document":
                page = s.get("page", "?")
                lines.append(f"[{idx}] Document — page {page}")
            elif stype == "youtube":
                lines.append(f"[{idx}] {title} (YouTube)")
            else:
                lines.append(f"[{idx}] {title}")

        return "\n".join(lines)

    def _extract_pages(self, doc_text: str) -> List[Tuple[int, str]]:
        """Extract page-numbered sections from document text."""
        pages = []
        # Try to split by page markers
        page_splits = re.split(r'(?:---\s*Page\s+(\d+)\s*---|Page\s+(\d+))', doc_text)

        if len(page_splits) > 1:
            current_page = 1
            for i, part in enumerate(page_splits):
                if part and part.isdigit():
                    current_page = int(part)
                elif part and part.strip():
                    pages.append((current_page, part.strip()[:500]))
        else:
            # No page markers — split into chunks
            chunk_size = 2000
            for i in range(0, len(doc_text), chunk_size):
                page_num = (i // chunk_size) + 1
                pages.append((page_num, doc_text[i:i + chunk_size]))

        return pages


def enhance_system_prompt_with_citations(base_prompt: str, sources: List[Dict]) -> str:
    """Add citation instructions to the system prompt based on available sources."""
    if not sources:
        return base_prompt

    source_lines = []
    for s in sources[:8]:
        idx = s["index"]
        stype = s.get("type", "")
        title = s.get("title", "")
        url = s.get("url", "")

        if stype == "web" and url:
            source_lines.append(f"[{idx}] {title} — {url}")
        elif stype == "kb":
            source_lines.append(f"[{idx}] {title} (from Knowledge Base)")
        elif stype == "document":
            page = s.get("page", "?")
            source_lines.append(f"[{idx}] Document, page {page}")
        elif stype == "youtube":
            source_lines.append(f"[{idx}] YouTube: {title}")

    if not source_lines:
        return base_prompt

    citation_block = (
        "\n━━ CITATION SOURCES ━━\n"
        "The following sources are available for citation. "
        "When referencing information from these sources, use the format [N] "
        "where N is the source number.\n\n"
        + "\n".join(source_lines)
        + "\n\n"
        "After your answer, include a **Sources:** section listing only "
        "the sources you actually cited, with their numbers and titles.\n"
    )

    return base_prompt + citation_block
