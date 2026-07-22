"""
Knowledge Graph — Automatically connects people, files, projects, ideas, dates, and notes
extracted from conversations. Builds a queryable graph of everything Aria has learned.
"""
import json
import logging
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path.home() / ".aria_data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
KG_FILE = DATA_DIR / "knowledge_graph.json"


def _load():
    if KG_FILE.exists():
        try:
            return json.loads(KG_FILE.read_text())
        except Exception:
            pass
    return {"nodes": {}, "edges": [], "last_updated": None}


def _save(data):
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    KG_FILE.write_text(json.dumps(data, indent=2))


class KnowledgeGraphService:

    def __init__(self):
        self._data = _load()

    # ── Entity extraction ─────────────────────────────────────────────────────

    async def extract_and_store(self, conversation_id: str, user_msg: str, ai_msg: str):
        """Extract entities from a conversation turn and add to the graph."""
        entities = self._extract_entities(user_msg + " " + ai_msg)
        if not entities:
            return

        ts = datetime.now(timezone.utc).isoformat()
        for etype, value in entities:
            node_id = self._make_id(etype, value)
            if node_id not in self._data["nodes"]:
                self._data["nodes"][node_id] = {
                    "id": node_id,
                    "type": etype,
                    "value": value,
                    "first_seen": ts,
                    "last_seen": ts,
                    "mentions": 1,
                    "conversations": [conversation_id],
                }
            else:
                node = self._data["nodes"][node_id]
                node["last_seen"] = ts
                node["mentions"] += 1
                if conversation_id not in node["conversations"]:
                    node["conversations"].append(conversation_id)
                    # Keep only last 20 conversation refs
                    node["conversations"] = node["conversations"][-20:]

        # Create edges between entities in the same conversation
        node_ids = [self._make_id(t, v) for t, v in entities]
        for i, a in enumerate(node_ids):
            for b in node_ids[i + 1:]:
                edge = {"source": a, "target": b, "conversation_id": conversation_id, "timestamp": ts}
                # Deduplicate edges (same source-target pair)
                exists = any(
                    e["source"] == a and e["target"] == b
                    for e in self._data["edges"]
                )
                if not exists:
                    self._data["edges"].append(edge)

        # Keep edges list manageable
        if len(self._data["edges"]) > 5000:
            self._data["edges"] = self._data["edges"][-3000:]

        _save(self._data)

    def _extract_entities(self, text: str) -> list[tuple[str, str]]:
        """Extract entities from text using pattern matching."""
        entities = []
        seen = set()

        # People (capitalized names near contextual words)
        name_patterns = [
            r"\b([A-Z][a-z]+ [A-Z][a-z]+)\b",
            r"\b(Mr|Mrs|Ms|Dr|Prof)\.?\s+([A-Z][a-z]+)\b",
        ]
        for pat in name_patterns:
            for m in re.finditer(pat, text):
                name = m.group(0).strip()
                if len(name) > 3 and name not in seen:
                    # Filter common false positives
                    lower = name.lower()
                    if lower not in {
                        "the the", "is a", "this is", "you are", "it is",
                        "we are", "they are", "can you", "how does", "what is",
                        "i am", "do you", "let me", "tell me", "give me",
                    }:
                        entities.append(("person", name))
                        seen.add(name)

        # Files and documents
        file_patterns = [
            r"\b[\w\-./]+\.(pdf|docx?|xlsx?|pptx?|csv|txt|py|js|jsx|ts|tsx|html|css|json|md|zip)\b",
        ]
        for pat in file_patterns:
            for m in re.finditer(pat, text, re.I):
                fname = m.group(0).strip()
                if fname not in seen:
                    entities.append(("file", fname))
                    seen.add(fname)

        # Dates and time periods
        date_patterns = [
            r"\b(\d{4})\b",  # Years like 2024, 1945
            r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?,?\s*\d{4}\b",
            r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
            r"\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s*\d{4})\b",
            r"\b(AD|BC|BCE|CE)\s*\d+\b",
        ]
        for pat in date_patterns:
            for m in re.finditer(pat, text, re.I):
                date_str = m.group(0).strip()
                if date_str not in seen:
                    entities.append(("date", date_str))
                    seen.add(date_str)

        # Topics / concepts (detect from quoted or emphasized terms)
        concept_patterns = [
            r'"([^"]{3,50})"',
            r"'([^']{3,50})'",
            r"\*\*([^*]{3,50})\*\*",
        ]
        for pat in concept_patterns:
            for m in re.finditer(pat, text):
                concept = m.group(1).strip()
                if len(concept) > 3 and concept not in seen and not concept.startswith("http"):
                    entities.append(("concept", concept))
                    seen.add(concept)

        # Projects (detect from common project patterns)
        project_patterns = [
            r"\b([\w\-]+(?:\s+[\w\-]+){0,3})\s+(?:project|app|website|game|system|tool|dashboard)\b",
            r"\b(?:project|app|website|game|system|tool|dashboard)\s+([\w\-]+(?:\s+[\w\-]+){0,3})\b",
        ]
        for pat in project_patterns:
            for m in re.finditer(pat, text, re.I):
                proj = m.group(1).strip()
                if len(proj) > 2 and proj not in seen:
                    entities.append(("project", proj))
                    seen.add(proj)

        # Notes / topics discussed
        topic_patterns = [
            r"\b(about|regarding|concerning|on the topic of|subject of)\s+([^.,;!?]{3,60})",
        ]
        for pat in topic_patterns:
            for m in re.finditer(pat, text, re.I):
                topic = m.group(2).strip().rstrip(".")
                if len(topic) > 3 and topic not in seen:
                    entities.append(("topic", topic))
                    seen.add(topic)

        return entities

    def _make_id(self, etype: str, value: str) -> str:
        return f"{etype}:{value.lower().strip()}"

    # ── Query methods ─────────────────────────────────────────────────────────

    def get_all(self) -> dict:
        return self._data

    def get_nodes_by_type(self, node_type: str) -> list[dict]:
        return [
            n for n in self._data["nodes"].values()
            if n["type"] == node_type
        ]

    def get_connections(self, node_id: str) -> list[dict]:
        """Get all nodes connected to a given node."""
        connected_ids = set()
        for edge in self._data["edges"]:
            if edge["source"] == node_id:
                connected_ids.add(edge["target"])
            elif edge["target"] == node_id:
                connected_ids.add(edge["source"])
        return [
            self._data["nodes"][nid]
            for nid in connected_ids
            if nid in self._data["nodes"]
        ]

    def search(self, query: str) -> list[dict]:
        """Search nodes by value."""
        q = query.lower()
        return [
            n for n in self._data["nodes"].values()
            if q in n["value"].lower()
        ]

    def get_stats(self) -> dict:
        """Summary statistics of the knowledge graph."""
        nodes = self._data["nodes"]
        by_type = defaultdict(int)
        for n in nodes.values():
            by_type[n["type"]] += 1
        return {
            "total_nodes": len(nodes),
            "total_edges": len(self._data["edges"]),
            "by_type": dict(by_type),
            "last_updated": self._data.get("last_updated"),
        }

    def get_timeline(self) -> list[dict]:
        """Get nodes sorted by first_seen date for timeline view."""
        nodes = sorted(
            self._data["nodes"].values(),
            key=lambda n: n.get("first_seen", ""),
        )
        return nodes

    def get_graph_data(self, max_nodes: int = 200) -> dict:
        """Return graph data optimized for frontend visualization."""
        # Prioritize nodes by mention count
        nodes = sorted(
            self._data["nodes"].values(),
            key=lambda n: n.get("mentions", 0),
            reverse=True,
        )[:max_nodes]
        node_ids = {n["id"] for n in nodes}

        edges = [
            e for e in self._data["edges"]
            if e["source"] in node_ids and e["target"] in node_ids
        ]

        return {"nodes": nodes, "edges": edges}

    async def clear(self):
        self._data = {"nodes": {}, "edges": [], "last_updated": None}
        _save(self._data)
