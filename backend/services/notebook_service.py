"""Notebook service — Source-grounded AI notebooks (NotebookLM-style).

Manages notebooks with multiple sources, provides source-grounded chat,
and generates study materials from notebook contents.
"""
import json
import hashlib
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("ARIA_DATA_DIR", Path.home() / ".aria_data")) / "notebooks"


class NotebookService:
    """Manage AI notebooks with source grounding."""

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    def list_notebooks(self) -> List[Dict]:
        """List all notebooks."""
        notebooks = []
        for f in DATA_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                notebooks.append({
                    "id": data.get("id"),
                    "name": data.get("name"),
                    "description": data.get("description", ""),
                    "source_count": len(data.get("sources", [])),
                    "created": data.get("created"),
                    "updated": data.get("updated"),
                    "tags": data.get("tags", []),
                    "cover_color": data.get("cover_color", "#7c6af7"),
                })
            except Exception:
                continue
        return sorted(notebooks, key=lambda x: x.get("updated", ""), reverse=True)

    def get_notebook(self, notebook_id: str) -> Optional[Dict]:
        """Get a notebook by ID."""
        path = DATA_DIR / f"{notebook_id}.json"
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                return None
        return None

    def create_notebook(self, name: str, description: str = "", tags: List[str] = None, cover_color: str = None) -> Dict:
        """Create a new notebook."""
        notebook_id = hashlib.md5(f"{name}{datetime.now().isoformat()}".encode()).hexdigest()[:12]
        colors = ["#7c6af7", "#f59e0b", "#10b981", "#ef4444", "#3b82f6", "#ec4899", "#8b5cf6"]
        notebook = {
            "id": notebook_id,
            "name": name,
            "description": description,
            "sources": [],
            "conversations": [],
            "tags": tags or [],
            "cover_color": cover_color or colors[hash(notebook_id) % len(colors)],
            "created": datetime.now().isoformat(),
            "updated": datetime.now().isoformat(),
            "persona": "You are a helpful study assistant. Answer using ONLY the sources in this notebook. Always cite sources with [N] format.",
        }
        path = DATA_DIR / f"{notebook_id}.json"
        path.write_text(json.dumps(notebook, indent=2))
        return notebook

    def update_notebook(self, notebook_id: str, **kwargs) -> Optional[Dict]:
        """Update notebook metadata."""
        notebook = self.get_notebook(notebook_id)
        if not notebook:
            return None
        for key, value in kwargs.items():
            if key != "id":
                notebook[key] = value
        notebook["updated"] = datetime.now().isoformat()
        path = DATA_DIR / f"{notebook_id}.json"
        path.write_text(json.dumps(notebook, indent=2))
        return notebook

    def delete_notebook(self, notebook_id: str) -> bool:
        """Delete a notebook."""
        path = DATA_DIR / f"{notebook_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    def add_source(
        self,
        notebook_id: str,
        source_type: str,
        content: str,
        title: str = "",
        metadata: Dict = None,
    ) -> Optional[Dict]:
        """Add a source to a notebook."""
        notebook = self.get_notebook(notebook_id)
        if not notebook:
            return None

        source_id = hashlib.md5(f"{notebook_id}{content[:200]}".encode()).hexdigest()[:10]
        source = {
            "id": source_id,
            "type": source_type,
            "title": title or f"Source {len(notebook['sources']) + 1}",
            "content": content[:50000],
            "char_count": len(content),
            "word_count": len(content.split()),
            "metadata": metadata or {},
            "tags": self._auto_tag(content, source_type),
            "added": datetime.now().isoformat(),
        }

        notebook["sources"].append(source)
        notebook["updated"] = datetime.now().isoformat()
        path = DATA_DIR / f"{notebook_id}.json"
        path.write_text(json.dumps(notebook, indent=2))
        return source

    def remove_source(self, notebook_id: str, source_id: str) -> bool:
        """Remove a source from a notebook."""
        notebook = self.get_notebook(notebook_id)
        if not notebook:
            return False
        original_count = len(notebook["sources"])
        notebook["sources"] = [s for s in notebook["sources"] if s["id"] != source_id]
        if len(notebook["sources"]) < original_count:
            notebook["updated"] = datetime.now().isoformat()
            path = DATA_DIR / f"{notebook_id}.json"
            path.write_text(json.dumps(notebook, indent=2))
            return True
        return False

    def get_sources_context(self, notebook_id: str, query: str = "", max_chars: int = 8000) -> str:
        """Get concatenated source content for grounding."""
        notebook = self.get_notebook(notebook_id)
        if not notebook:
            return ""
        sources = notebook.get("sources", [])
        if not sources:
            return ""
        if query:
            query_terms = set(query.lower().split())
            scored = []
            for s in sources:
                content_lower = s["content"].lower()
                score = sum(1 for t in query_terms if t in content_lower)
                scored.append((score, s))
            scored.sort(key=lambda x: x[0], reverse=True)
            sources = [s for _, s in scored]
        parts = []
        total = 0
        for i, s in enumerate(sources):
            content = s["content"][:4000]
            if total + len(content) > max_chars:
                break
            parts.append(f"[Source {i+1}: {s['title']}]\n{content}")
            total += len(content)
        return "\n\n".join(parts)

    def build_source_list(self, notebook_id: str) -> List[Dict]:
        """Build a list of sources for citation mapping."""
        notebook = self.get_notebook(notebook_id)
        if not notebook:
            return []
        return [
            {
                "index": i + 1,
                "id": s["id"],
                "type": s["type"],
                "title": s["title"],
                "char_count": s["char_count"],
                "word_count": s.get("word_count", 0),
                "tags": s.get("tags", []),
                "added": s["added"],
            }
            for i, s in enumerate(notebook.get("sources", []))
        ]

    def get_grounding_prompt(self, notebook_id: str, query: str = "") -> str:
        """Build a system prompt that grounds responses in notebook sources."""
        notebook = self.get_notebook(notebook_id)
        if not notebook:
            return ""
        persona = notebook.get("persona", "Answer using the sources below.")
        sources_context = self.get_sources_context(notebook_id, query)
        source_list = self.build_source_list(notebook_id)
        source_refs = "\n".join(
            f"[{s['index']}] {s['title']} ({s['type']})"
            for s in source_list
        )
        return f"""{persona}

━━ NOTEBOOK SOURCES ━━
{sources_context}

━━ SOURCE INDEX ━━
{source_refs}

CITATION RULES:
- Use [N] to cite sources, where N matches the source number above
- Every factual claim must cite at least one source
- If information isn't in the sources, say "This isn't covered in the notebook sources"
- After your answer, list the sources you cited in a **Sources:** section
"""

    def get_all_content(self, notebook_id: str, max_chars: int = 20000) -> str:
        """Get all source content concatenated for study material generation."""
        notebook = self.get_notebook(notebook_id)
        if not notebook:
            return ""
        sources = notebook.get("sources", [])
        if not sources:
            return ""
        parts = []
        total = 0
        for s in sources:
            content = s["content"][:8000]
            if total + len(content) > max_chars:
                break
            parts.append(f"=== {s['title']} ===\n{content}")
            total += len(content)
        return "\n\n".join(parts)

    def _auto_tag(self, content: str, source_type: str) -> List[str]:
        """Auto-tag content based on keywords and type."""
        tags = []
        content_lower = content.lower()
        tag_keywords = {
            "math": ["math", "equation", "formula", "algebra", "geometry", "calculus", "theorem", "proof"],
            "science": ["physics", "chemistry", "biology", "experiment", "hypothesis", "atom", "molecule"],
            "history": ["history", "war", "civilization", "century", "ancient", "medieval", "revolution"],
            "english": ["literature", "poem", "novel", "author", "narrative", "metaphor", "shakespeare"],
            "geography": ["geography", "climate", "continent", "ocean", "country", "population"],
            "technology": ["computer", "software", "programming", "algorithm", "data", "ai", "robot"],
        }
        for tag, keywords in tag_keywords.items():
            if any(kw in content_lower for kw in keywords):
                tags.append(tag)
        type_tags = {"pdf": "document", "youtube": "video", "url": "web", "text": "text", "docx": "document"}
        if source_type in type_tags:
            tags.append(type_tags[source_type])
        return tags[:5]

    def get_file_organizer_data(self, notebook_id: str) -> Dict:
        """Get organized file data for the file organizer view."""
        notebook = self.get_notebook(notebook_id)
        if not notebook:
            return {}
        sources = notebook.get("sources", [])
        by_type = {}
        by_tag = {}
        total_words = 0
        for s in sources:
            stype = s.get("type", "text")
            if stype not in by_type:
                by_type[stype] = []
            by_type[stype].append({
                "id": s["id"],
                "title": s["title"],
                "char_count": s["char_count"],
                "word_count": s.get("word_count", 0),
                "tags": s.get("tags", []),
                "added": s["added"],
            })
            total_words += s.get("word_count", 0)
            for tag in s.get("tags", []):
                if tag not in by_tag:
                    by_tag[tag] = []
                by_tag[tag].append(s["id"])
        return {
            "total_sources": len(sources),
            "total_words": total_words,
            "by_type": by_type,
            "by_tag": by_tag,
            "folders": self._build_folders(notebook),
            "sources": [
                {
                    "id": s["id"],
                    "title": s["title"],
                    "type": s["type"],
                    "char_count": s["char_count"],
                    "word_count": s.get("word_count", 0),
                    "tags": s.get("tags", []),
                    "added": s["added"],
                    "folder": s.get("folder", "Uncategorized"),
                    "content_preview": s["content"][:200] if s.get("content") else "",
                }
                for s in sources
            ],
        }

    def _build_folders(self, notebook: Dict) -> Dict:
        """Build folder structure from source tags and types."""
        folders = {}
        for s in notebook.get("sources", []):
            folder = s.get("folder", "Uncategorized")
            if folder not in folders:
                folders[folder] = {"name": folder, "count": 0, "icon": self._folder_icon(folder)}
            folders[folder]["count"] += 1
        return folders

    def _folder_icon(self, folder_name: str) -> str:
        """Get icon name for a folder based on its name."""
        folder_lower = folder_name.lower()
        if any(kw in folder_lower for kw in ["math", "physics", "science", "chemistry", "biology"]):
            return "atom"
        elif any(kw in folder_lower for kw in ["history", "civilization", "war"]):
            return "scroll"
        elif any(kw in folder_lower for kw in ["literature", "english", "writing", "poem"]):
            return "book-open"
        elif any(kw in folder_lower for kw in ["code", "programming", "software", "tech"]):
            return "code"
        elif any(kw in folder_lower for kw in ["geography", "climate", "environment"]):
            return "globe"
        elif any(kw in folder_lower for kw in ["image", "photo", "video", "media"]):
            return "image"
        elif any(kw in folder_lower for kw in ["document", "report", "paper"]):
            return "file-text"
        else:
            return "folder"

    def _save_notebook(self, notebook: Dict):
        """Atomic save for a notebook."""
        path = DATA_DIR / f"{notebook['id']}.json"
        notebook["updated"] = datetime.now().isoformat()
        path.write_text(json.dumps(notebook, indent=2))

    def rename_source(self, notebook_id: str, source_id: str, new_title: str) -> Optional[Dict]:
        """Rename a source's title."""
        notebook = self.get_notebook(notebook_id)
        if not notebook:
            return None
        for s in notebook.get("sources", []):
            if s["id"] == source_id:
                s["title"] = new_title
                s["modified"] = True
                self._save_notebook(notebook)
                return s
        return None

    def move_source(self, notebook_id: str, source_id: str, folder: str) -> Optional[Dict]:
        """Move a source to a different folder."""
        notebook = self.get_notebook(notebook_id)
        if not notebook:
            return None
        for s in notebook.get("sources", []):
            if s["id"] == source_id:
                s["folder"] = folder
                self._save_notebook(notebook)
                return s
        return None

    def bulk_move_sources(self, notebook_id: str, source_ids: List[str], folder: str) -> int:
        """Move multiple sources to a folder. Returns count moved."""
        notebook = self.get_notebook(notebook_id)
        if not notebook:
            return 0
        count = 0
        for s in notebook.get("sources", []):
            if s["id"] in source_ids:
                s["folder"] = folder
                count += 1
        if count:
            self._save_notebook(notebook)
        return count

    def bulk_delete_sources(self, notebook_id: str, source_ids: List[str]) -> int:
        """Delete multiple sources. Returns count deleted."""
        notebook = self.get_notebook(notebook_id)
        if not notebook:
            return 0
        original_len = len(notebook.get("sources", []))
        notebook["sources"] = [s for s in notebook.get("sources", []) if s["id"] not in source_ids]
        if len(notebook["sources"]) != original_len:
            self._save_notebook(notebook)
        return original_len - len(notebook.get("sources", []))
