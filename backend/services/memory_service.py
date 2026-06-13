"""
Memory service — ChromaDB-backed RAG.
Stores conversation turns and study-profile data.
Retrieves semantically similar memories at query time.
"""
import asyncio
import hashlib
import json
from datetime import datetime
from pathlib import Path

# Dynamic path resolution for macOS
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Explicitly defining the global variables for the JSON file paths
CONVERSATIONS_FILE = DATA_DIR / "conversations.json"
PROFILE_FILE = DATA_DIR / "study_profile.json"


def _load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return default


def _save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2))


class MemoryService:

    def __init__(self):
        self._chroma_available = False
        self._collection = None
        self._init_chroma()

    def _init_chroma(self):
        try:
            import chromadb
            from chromadb.config import Settings
            db_path = str(DATA_DIR / "chromadb")
            client = chromadb.PersistentClient(path=db_path)
            self._collection = client.get_or_create_collection(
                name="aria_memory",
                metadata={"hnsw:space": "cosine"}
            )
            self._chroma_available = True
        except Exception:
            # Fallback to JSON-based memory
            pass

    async def save(self, conversation_id: str, user_msg: str, ai_msg: str):
        """Save a conversation turn."""
        ts = datetime.utcnow().isoformat()
        turn = {
            "conversation_id": conversation_id,
            "user": user_msg,
            "ai": ai_msg,
            "timestamp": ts,
        }
        # JSON store (always)
        convs = _load_json(CONVERSATIONS_FILE, {})
        if conversation_id not in convs:
            convs[conversation_id] = []
        convs[conversation_id].append(turn)
        # Keep only last 100 turns per conversation
        convs[conversation_id] = convs[conversation_id][-100:]
        _save_json(CONVERSATIONS_FILE, convs)

        # ChromaDB (semantic search)
        if self._chroma_available and self._collection:
            try:
                # Security Fix: Strong SHA-256 implementation
                doc_id = hashlib.sha256(f"{conversation_id}{ts}".encode()).hexdigest()
                combined = f"User: {user_msg}\nAI: {ai_msg}"
                self._collection.add(
                    documents=[combined],
                    ids=[doc_id],
                    metadatas=[{"conversation_id": conversation_id, "timestamp": ts}]
                )
            except Exception:
                pass

    async def retrieve(self, conversation_id: str, query: str, k: int = 4) -> list[str]:
        """Retrieve relevant past messages."""
        # Recent turns from JSON (always include)
        convs = _load_json(CONVERSATIONS_FILE, {})
        turns = convs.get(conversation_id, [])
        recent = [f"User: {t['user']}\nAI: {t['ai']}" for t in turns[-6:]]

        # Semantic search from ChromaDB
        semantic = []
        if self._chroma_available and self._collection:
            try:
                results = self._collection.query(
                    query_texts=[query],
                    n_results=min(k, max(1, self._collection.count())),
                    where={"conversation_id": conversation_id}
                )
                semantic = results["documents"][0] if results["documents"] else []
            except Exception:
                pass

        # Merge, deduplicate, limit
        all_memories = list(dict.fromkeys(semantic + recent))
        return all_memories[:k + 4]

    async def get_conversations(self) -> list[dict]:
        convs = _load_json(CONVERSATIONS_FILE, {})
        result = []
        for cid, turns in convs.items():
            if turns:
                first = turns[0]
                result.append({
                    "id": cid,
                    "title": first["user"][:60] + "..." if len(first["user"]) > 60 else first["user"],
                    "timestamp": first["timestamp"],
                    "turn_count": len(turns),
                })
        return sorted(result, key=lambda x: x["timestamp"], reverse=True)

    async def get_conversation(self, conversation_id: str) -> list[dict]:
        convs = _load_json(CONVERSATIONS_FILE, {})
        return convs.get(conversation_id, [])

    async def delete_conversation(self, conversation_id: str):
        convs = _load_json(CONVERSATIONS_FILE, {})
        if conversation_id in convs:
            del convs[conversation_id]
            _save_json(CONVERSATIONS_FILE, convs)

    async def get_profile(self) -> dict:
        return _load_json(PROFILE_FILE, {
            "subjects": {},
            "streak": 0,
            "last_active": None,
            "total_questions": 0,
            "correct_answers": 0,
            "weak_areas": [],
            "strong_areas": [],
        })

    async def update_profile(self, subject: str, correct: bool):
        profile = await self.get_profile()
        if subject not in profile["subjects"]:
            profile["subjects"][subject] = {"correct": 0, "total": 0}
        profile["subjects"][subject]["total"] += 1
        if correct:
            profile["subjects"][subject]["correct"] += 1
        profile["total_questions"] = profile.get("total_questions", 0) + 1
        if correct:
            profile["correct_answers"] = profile.get("correct_answers", 0) + 1
        # Update weak/strong areas
        weak, strong = [], []
        for subj, stats in profile["subjects"].items():
            if stats["total"] >= 3:
                ratio = stats["correct"] / stats["total"]
                if ratio < 0.5:
                    weak.append(subj)
                elif ratio >= 0.8:
                    strong.append(subj)
        profile["weak_areas"] = weak
        profile["strong_areas"] = strong
        profile["last_active"] = datetime.utcnow().isoformat()
        _save_json(PROFILE_FILE, profile)
        return profile
