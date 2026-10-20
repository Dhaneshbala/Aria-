"""Notebook service — Source-grounded AI notebooks (NotebookLM-style).

Manages notebooks with multiple sources, provides source-grounded chat,
and generates study materials from notebook contents.
"""

import hashlib
import json
import logging
import os
import re
import threading
from datetime import datetime
from pathlib import Path

from services.untrusted import UNTRUSTED_RULES, wrap_untrusted

logger = logging.getLogger(__name__)

DATA_DIR = (
    Path(os.environ.get("ARIA_DATA_DIR", Path.home() / ".aria_data")) / "notebooks"
)


class NotebookService:
    """Manage AI notebooks with source grounding."""

    # Guards read-modify-write races on the same notebook file (chat,
    # add_source and UI updates can overlap) and sanitises every
    # client-supplied notebook id used in a filename.
    _LOCK = threading.RLock()
    _ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

    def __init__(self):
        self._base_dir().mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _base_dir() -> Path:
        """This account's notebooks directory (stage 2).

        Local mode → the historic ``DATA_DIR/notebooks`` (unchanged);
        accounts mode → ``DATA_DIR/users/<username>/notebooks``.
        """
        from services.scoping import store_dir

        return store_dir("notebooks")

    def _safe_path(self, notebook_id: str) -> Path | None:
        """Notebook ids are used in filenames — never allow traversal or odd ids."""
        if not self._ID_RE.match(notebook_id or ""):
            return None
        return self._base_dir() / f"{notebook_id}.json"

    def list_notebooks(self) -> list[dict]:
        """List all notebooks."""
        notebooks = []
        for f in self._base_dir().glob("*.json"):
            try:
                data = json.loads(f.read_text())
                notebooks.append(
                    {
                        "id": data.get("id"),
                        "name": data.get("name"),
                        "description": data.get("description", ""),
                        "source_count": len(data.get("sources", [])),
                        "created": data.get("created"),
                        "updated": data.get("updated"),
                        "tags": data.get("tags", []),
                        "cover_color": data.get("cover_color", "#7c6af7"),
                    }
                )
            except Exception:
                continue
        return sorted(notebooks, key=lambda x: x.get("updated", ""), reverse=True)

    def get_notebook(self, notebook_id: str) -> dict | None:
        """Get a notebook by ID."""
        path = self._safe_path(notebook_id)
        if not path:
            return None
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                return None
        return None

    def create_notebook(
        self,
        name: str,
        description: str = "",
        tags: list[str] | None = None,
        cover_color: str | None = None,
    ) -> dict:
        """Create a new notebook."""
        notebook_id = hashlib.md5(
            f"{name}{datetime.now().isoformat()}".encode(), usedforsecurity=False
        ).hexdigest()[:12]
        colors = [
            "#7c6af7",
            "#f59e0b",
            "#10b981",
            "#ef4444",
            "#3b82f6",
            "#ec4899",
            "#8b5cf6",
        ]
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
        path = self._base_dir() / f"{notebook_id}.json"
        with self._LOCK:
            path.write_text(json.dumps(notebook, indent=2))
        return notebook

    def update_notebook(self, notebook_id: str, **kwargs) -> dict | None:
        """Update notebook metadata."""
        path = self._safe_path(notebook_id)
        if not path:
            return None
        with self._LOCK:
            notebook = self.get_notebook(notebook_id)
            if not notebook:
                return None
            for key, value in kwargs.items():
                if key != "id":
                    notebook[key] = value
            notebook["updated"] = datetime.now().isoformat()
            path.write_text(json.dumps(notebook, indent=2))
        return notebook

    def delete_notebook(self, notebook_id: str) -> bool:
        """Delete a notebook."""
        path = self._safe_path(notebook_id)
        if not path:
            return False
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
        metadata: dict | None = None,
    ) -> dict | None:
        """Add a source to a notebook."""
        path = self._safe_path(notebook_id)
        if not path:
            return None
        with self._LOCK:
            notebook = self.get_notebook(notebook_id)
            if not notebook:
                return None

            source_id = hashlib.md5(
                f"{notebook_id}{content[:200]}".encode(), usedforsecurity=False
            ).hexdigest()[:10]
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
            path.write_text(json.dumps(notebook, indent=2))
        return source

    def remove_source(self, notebook_id: str, source_id: str) -> bool:
        """Remove a source from a notebook."""
        path = self._safe_path(notebook_id)
        if not path:
            return False
        with self._LOCK:
            notebook = self.get_notebook(notebook_id)
            if not notebook:
                return False
            original_count = len(notebook["sources"])
            notebook["sources"] = [
                s for s in notebook["sources"] if s["id"] != source_id
            ]
            if len(notebook["sources"]) < original_count:
                notebook["updated"] = datetime.now().isoformat()
                path.write_text(json.dumps(notebook, indent=2))
                return True
        return False

    def get_sources_context(
        self, notebook_id: str, query: str = "", max_chars: int = 8000
    ) -> str:
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
            parts.append(f"[Source {i + 1}: {s['title']}]\n{content}")
            total += len(content)
        return "\n\n".join(parts)

    def build_source_list(self, notebook_id: str) -> list[dict]:
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
            f"[{s['index']}] {s['title']} ({s['type']})" for s in source_list
        )
        return f"""{persona}

━━ NOTEBOOK SOURCES ━━
{wrap_untrusted("notebook-source", sources_context, limit=20000)}

━━ SOURCE INDEX ━━
{source_refs}

CITATION RULES:
- Use [N] to cite sources, where N matches the source number above
- Every factual claim must cite at least one source
- If information isn't in the sources, say "This isn't covered in the notebook sources"
- After your answer, list the sources you cited in a **Sources:** section

{UNTRUSTED_RULES}
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
            parts.append(
                f"=== {s['title']} ===\n{wrap_untrusted('notebook-source', content)}"
            )
            total += len(content)
        return "\n\n".join(parts)

    def _auto_tag(self, content: str, source_type: str) -> list[str]:
        """Auto-tag content based on keywords and type."""
        tags = []
        content_lower = content.lower()
        tag_keywords = {
            "math": [
                "math",
                "equation",
                "formula",
                "algebra",
                "geometry",
                "calculus",
                "theorem",
                "proof",
            ],
            "science": [
                "physics",
                "chemistry",
                "biology",
                "experiment",
                "hypothesis",
                "atom",
                "molecule",
            ],
            "history": [
                "history",
                "war",
                "civilization",
                "century",
                "ancient",
                "medieval",
                "revolution",
            ],
            "english": [
                "literature",
                "poem",
                "novel",
                "author",
                "narrative",
                "metaphor",
                "shakespeare",
            ],
            "geography": [
                "geography",
                "climate",
                "continent",
                "ocean",
                "country",
                "population",
            ],
            "technology": [
                "computer",
                "software",
                "programming",
                "algorithm",
                "data",
                "ai",
                "robot",
            ],
        }
        for tag, keywords in tag_keywords.items():
            if any(kw in content_lower for kw in keywords):
                tags.append(tag)
        type_tags = {
            "pdf": "document",
            "youtube": "video",
            "url": "web",
            "text": "text",
            "docx": "document",
        }
        if source_type in type_tags:
            tags.append(type_tags[source_type])
        return tags[:5]

    def get_file_organizer_data(self, notebook_id: str) -> dict:
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
            by_type[stype].append(
                {
                    "id": s["id"],
                    "title": s["title"],
                    "char_count": s["char_count"],
                    "word_count": s.get("word_count", 0),
                    "tags": s.get("tags", []),
                    "added": s["added"],
                }
            )
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

    def _build_folders(self, notebook: dict) -> dict:
        """Build folder structure from source tags and types."""
        folders = {}
        for s in notebook.get("sources", []):
            folder = s.get("folder", "Uncategorized")
            if folder not in folders:
                folders[folder] = {
                    "name": folder,
                    "count": 0,
                    "icon": self._folder_icon(folder),
                }
            folders[folder]["count"] += 1
        return folders

    def _folder_icon(self, folder_name: str) -> str:
        """Get icon name for a folder based on its name."""
        folder_lower = folder_name.lower()
        if any(
            kw in folder_lower
            for kw in ["math", "physics", "science", "chemistry", "biology"]
        ):
            return "atom"
        elif any(kw in folder_lower for kw in ["history", "civilization", "war"]):
            return "scroll"
        elif any(
            kw in folder_lower for kw in ["literature", "english", "writing", "poem"]
        ):
            return "book-open"
        elif any(
            kw in folder_lower for kw in ["code", "programming", "software", "tech"]
        ):
            return "code"
        elif any(kw in folder_lower for kw in ["geography", "climate", "environment"]):
            return "globe"
        elif any(kw in folder_lower for kw in ["image", "photo", "video", "media"]):
            return "image"
        elif any(kw in folder_lower for kw in ["document", "report", "paper"]):
            return "file-text"
        else:
            return "folder"

    def _save_notebook(self, notebook: dict):
        """Atomic save for a notebook."""
        path = self._base_dir() / f"{notebook['id']}.json"
        notebook["updated"] = datetime.now().isoformat()
        path.write_text(json.dumps(notebook, indent=2))

    def rename_source(
        self, notebook_id: str, source_id: str, new_title: str
    ) -> dict | None:
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

    def move_source(self, notebook_id: str, source_id: str, folder: str) -> dict | None:
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

    def bulk_move_sources(
        self, notebook_id: str, source_ids: list[str], folder: str
    ) -> int:
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

    def bulk_delete_sources(self, notebook_id: str, source_ids: list[str]) -> int:
        """Delete multiple sources. Returns count deleted."""
        notebook = self.get_notebook(notebook_id)
        if not notebook:
            return 0
        original_len = len(notebook.get("sources", []))
        notebook["sources"] = [
            s for s in notebook.get("sources", []) if s["id"] not in source_ids
        ]
        if len(notebook["sources"]) != original_len:
            self._save_notebook(notebook)
        return original_len - len(notebook.get("sources", []))
