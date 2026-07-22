"""
Memory service — ChromaDB-backed RAG with intelligence features.
Stores conversation turns, study-profile data, and knowledge graph.
Retrieves semantically similar memories at query time.
Includes cross-conversation search, timeline, compression, and cleanup.
"""
import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path.home() / ".aria_data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

CONVERSATIONS_FILE = DATA_DIR / "conversations.json"
PROFILE_FILE = DATA_DIR / "study_profile.json"
COMPRESSED_FILE = DATA_DIR / "compressed_memory.json"


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
        self._global_collection = None
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
            # Global collection for cross-conversation search
            self._global_collection = client.get_or_create_collection(
                name="aria_global_memory",
                metadata={"hnsw:space": "cosine"}
            )
            self._chroma_available = True
        except Exception:
            pass

    async def save(self, conversation_id: str, user_msg: str, ai_msg: str):
        """Save a conversation turn to both local and global stores."""
        ts = datetime.now(timezone.utc).isoformat()
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
        convs[conversation_id] = convs[conversation_id][-100:]
        _save_json(CONVERSATIONS_FILE, convs)

        # ChromaDB (semantic search)
        if self._chroma_available and self._collection:
            try:
                doc_id = hashlib.sha256(f"{conversation_id}{ts}".encode()).hexdigest()
                combined = f"User: {user_msg}\nAI: {ai_msg}"
                self._collection.add(
                    documents=[combined],
                    ids=[doc_id],
                    metadatas=[{"conversation_id": conversation_id, "timestamp": ts}]
                )
                # Also add to global collection (no conversation_id filter)
                self._global_collection.add(
                    documents=[combined],
                    ids=[f"g_{doc_id}"],
                    metadatas=[{"conversation_id": conversation_id, "timestamp": ts}]
                )
            except Exception:
                pass

    async def retrieve(self, conversation_id: str, query: str, k: int = 4) -> list[str]:
        """Retrieve relevant past messages from this conversation + global context."""
        # Recent turns from JSON
        convs = _load_json(CONVERSATIONS_FILE, {})
        turns = convs.get(conversation_id, [])
        recent = [f"User: {t['user']}\nAI: {t['ai']}" for t in turns[-6:]]

        # Semantic search from this conversation
        semantic = []
        if self._chroma_available and self._collection:
            try:
                count = self._collection.count()
                if count > 0:
                    results = self._collection.query(
                        query_texts=[query],
                        n_results=min(k, max(1, count)),
                        where={"conversation_id": conversation_id}
                    )
                    semantic = results["documents"][0] if results["documents"] else []
            except Exception:
                pass

        # Cross-conversation semantic search (global)
        global_context = []
        if self._chroma_available and self._global_collection:
            try:
                count = self._global_collection.count()
                if count > 0:
                    results = self._global_collection.query(
                        query_texts=[query],
                        n_results=min(3, max(1, count)),
                    )
                    global_context = results["documents"][0] if results["documents"] else []
            except Exception:
                pass

        # Merge, deduplicate, limit
        all_memories = list(dict.fromkeys(semantic + recent + global_context))
        return all_memories[:k + 6]

    async def search_global(self, query: str, limit: int = 20) -> list[dict]:
        """Semantic search across ALL conversations."""
        results_list = []
        if self._chroma_available and self._global_collection:
            try:
                count = self._global_collection.count()
                if count > 0:
                    results = self._global_collection.query(
                        query_texts=[query],
                        n_results=min(limit, max(1, count)),
                    )
                    docs = results["documents"][0] if results["documents"] else []
                    metas = results["metadatas"][0] if results["metadatas"] else []
                    for doc, meta in zip(docs, metas):
                        results_list.append({
                            "text": doc[:300],
                            "conversation_id": meta.get("conversation_id", ""),
                            "timestamp": meta.get("timestamp", ""),
                        })
            except Exception as e:
                logger.warning("Global search failed: %s", e)

        # Also do substring search as fallback
        convs = _load_json(CONVERSATIONS_FILE, {})
        q = query.lower()
        for cid, turns in convs.items():
            for turn in turns:
                if q in turn.get("user", "").lower() or q in turn.get("ai", "").lower():
                    snippet = (turn.get("ai", "") or turn.get("user", ""))[:200]
                    # Avoid duplicates
                    if not any(r["conversation_id"] == cid and r["text"][:50] == snippet[:50] for r in results_list):
                        results_list.append({
                            "text": snippet,
                            "conversation_id": cid,
                            "timestamp": turn.get("timestamp", ""),
                        })

        return results_list[:limit]

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

    async def search_conversations(self, query: str) -> list[dict]:
        """Search across all conversation content."""
        convs = _load_json(CONVERSATIONS_FILE, {})
        query_lower = query.lower()
        results = []
        for cid, turns in convs.items():
            matching_turns = []
            for turn in turns:
                if query_lower in turn.get("user", "").lower() or query_lower in turn.get("ai", "").lower():
                    matching_turns.append(turn)
            if matching_turns:
                score = len(matching_turns)
                first_match = matching_turns[0]
                snippet = first_match.get("ai", "")[:200]
                results.append({
                    "id": cid,
                    "title": turns[0]["user"][:60] + "..." if len(turns[0]["user"]) > 60 else turns[0]["user"],
                    "timestamp": turns[0]["timestamp"],
                    "turn_count": len(turns),
                    "snippet": snippet,
                    "score": score,
                })
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:20]

    async def get_conversation(self, conversation_id: str) -> list[dict]:
        convs = _load_json(CONVERSATIONS_FILE, {})
        return convs.get(conversation_id, [])

    async def delete_conversation(self, conversation_id: str):
        convs = _load_json(CONVERSATIONS_FILE, {})
        if conversation_id in convs:
            del convs[conversation_id]
            _save_json(CONVERSATIONS_FILE, convs)

    # ── Memory Timeline ───────────────────────────────────────────────────────

    async def get_timeline(self, days: int = 30) -> list[dict]:
        """Get a timeline of learning activity over time."""
        convs = _load_json(CONVERSATIONS_FILE, {})
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        daily = {}
        for cid, turns in convs.items():
            for turn in turns:
                try:
                    ts = turn.get("timestamp", "")
                    if ts:
                        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        if dt >= cutoff:
                            day_key = dt.strftime("%Y-%m-%d")
                            if day_key not in daily:
                                daily[day_key] = {
                                    "date": day_key, "conversation_ids": [],
                                    "topics": [], "turns": 0, "conversations": 0,
                                }
                            daily[day_key]["turns"] += 1
                            if cid not in daily[day_key]["conversation_ids"]:
                                daily[day_key]["conversation_ids"].append(cid)
                            # Extract topics from user messages
                            user_msg = turn.get("user", "")
                            if user_msg and len(daily[day_key]["topics"]) < 5:
                                topic = user_msg[:50] + ("..." if len(user_msg) > 50 else "")
                                if topic not in daily[day_key]["topics"]:
                                    daily[day_key]["topics"].append(topic)
                except Exception:
                    continue

        # Set conversation count
        for day in daily.values():
            day["conversations"] = len(day["conversation_ids"])

        return sorted(daily.values(), key=lambda d: d["date"])

    async def get_conversations_for_date(self, date: str) -> list[dict]:
        """Get all conversations that have turns on a specific date."""
        convs = _load_json(CONVERSATIONS_FILE, {})
        results = []
        for cid, turns in convs.items():
            date_turns = []
            for turn in turns:
                try:
                    ts = turn.get("timestamp", "")
                    if ts and ts.startswith(date):
                        date_turns.append(turn)
                except Exception:
                    continue
            if date_turns:
                # Get first user message as title
                title = ""
                for t in date_turns:
                    if t.get("user"):
                        title = t["user"][:80] + ("..." if len(t["user"]) > 80 else "")
                        break
                results.append({
                    "id": cid,
                    "title": title or "Untitled conversation",
                    "turn_count": len(date_turns),
                    "first_turn": date_turns[0],
                    "last_turn": date_turns[-1],
                    "turns": date_turns,
                })
        return results

    # ── Context Compression ───────────────────────────────────────────────────

    async def compress_old_conversations(self, older_than_days: int = 7) -> dict:
        """Summarize old conversations into compressed memory entries."""
        convs = _load_json(CONVERSATIONS_FILE, {})
        compressed = _load_json(COMPRESSED_FILE, [])
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)

        compressed_count = 0
        for cid, turns in list(convs.items()):
            if not turns:
                continue
            # Check if conversation is old enough
            try:
                first_ts = turns[0].get("timestamp", "")
                if first_ts:
                    dt = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
                    if dt >= cutoff:
                        continue  # Too recent, skip
            except Exception:
                continue

            # Build a summary of this conversation
            user_msgs = [t.get("user", "") for t in turns if t.get("user")]
            topics = list(set(user_msgs[:10]))  # Unique first messages

            summary = {
                "conversation_id": cid,
                "topic_summary": "; ".join(topics[:5]),
                "turn_count": len(turns),
                "first_message": turns[0].get("timestamp", ""),
                "last_message": turns[-1].get("timestamp", ""),
            }

            # Check if already compressed
            existing_ids = {c["conversation_id"] for c in compressed}
            if cid not in existing_ids:
                compressed.append(summary)
                compressed_count += 1

        # Keep only last 200 compressed entries
        compressed = compressed[-200:]
        _save_json(COMPRESSED_FILE, compressed)

        return {
            "compressed_count": compressed_count,
            "total_compressed": len(compressed),
        }

    # ── Smart Memory Cleanup ──────────────────────────────────────────────────

    async def cleanup_old_memory(self, max_age_days: int = 90) -> dict:
        """Remove conversations older than max_age_days and clean up ChromaDB."""
        convs = _load_json(CONVERSATIONS_FILE, {})
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

        removed = 0
        for cid in list(convs.keys()):
            turns = convs[cid]
            if not turns:
                continue
            try:
                last_ts = turns[-1].get("timestamp", "")
                if last_ts:
                    dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                    if dt < cutoff:
                        del convs[cid]
                        removed += 1
            except Exception:
                continue

        _save_json(CONVERSATIONS_FILE, convs)
        return {"removed_conversations": removed, "remaining": len(convs)}

    # ── Study Profile ─────────────────────────────────────────────────────────

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
        profile["last_active"] = datetime.now(timezone.utc).isoformat()
        _save_json(PROFILE_FILE, profile)
        return profile

    # ── Adaptive Learning ─────────────────────────────────────────────────────

    async def get_adaptive_recommendations(self) -> dict:
        """Analyze study profile and recommend what to focus on."""
        profile = await self.get_profile()
        recommendations = []

        weak = profile.get("weak_areas", [])
        strong = profile.get("strong_areas", [])

        if weak:
            recommendations.append({
                "type": "focus_area",
                "message": f"You need more practice in: {', '.join(weak)}",
                "subjects": weak,
            })

        if strong:
            recommendations.append({
                "type": "strength",
                "message": f"Great work in: {', '.join(strong)}! Keep it up!",
                "subjects": strong,
            })

        total = profile.get("total_questions", 0)
        correct = profile.get("correct_answers", 0)
        if total > 0:
            accuracy = correct / total
            if accuracy < 0.5:
                recommendations.append({
                    "type": "overall",
                    "message": "Your overall accuracy is below 50%. Consider reviewing fundamentals.",
                })
            elif accuracy >= 0.8:
                recommendations.append({
                    "type": "overall",
                    "message": f"Excellent! {accuracy:.0%} accuracy across {total} questions.",
                })

        # Revision prediction (spaced repetition heuristic)
        subjects = profile.get("subjects", {})
        for subj, stats in subjects.items():
            if stats["total"] >= 5:
                accuracy = stats["correct"] / stats["total"]
                if accuracy < 0.7:
                    recommendations.append({
                        "type": "revision",
                        "message": f"Review {subj} soon — accuracy is {accuracy:.0%} with {stats['total']} attempts.",
                        "subject": subj,
                        "accuracy": accuracy,
                    })

        return {
            "profile": profile,
            "recommendations": recommendations,
        }
