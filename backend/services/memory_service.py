"""
Memory service — ChromaDB-backed RAG with intelligence features.
Stores conversation turns, study-profile data, and knowledge graph.
Retrieves semantically similar memories at query time.
Includes cross-conversation search, timeline, compression, and cleanup.
"""
import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("ARIA_DATA_DIR", Path.home() / ".aria_data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

CONVERSATIONS_FILE = DATA_DIR / "conversations.json"
PROFILE_FILE = DATA_DIR / "study_profile.json"
COMPRESSED_FILE = DATA_DIR / "compressed_memory.json"
TITLES_FILE = DATA_DIR / "titles.json"


import threading
import tempfile

_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_LOCK = threading.Lock()

def _lock_for(path: Path) -> threading.RLock:
    key = str(path)
    with _LOCKS_LOCK:
        if key not in _LOCKS:
            _LOCKS[key] = threading.RLock()
        return _LOCKS[key]

def _load_json(path: Path, default):
    lock = _lock_for(path)
    with lock:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return default


def _save_json(path: Path, data):
    lock = _lock_for(path)
    with lock:
        text = json.dumps(data, indent=2, ensure_ascii=False)
        fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.tmp.")
        try:
            with open(fd, "w", encoding="utf-8") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            Path(tmp_path).replace(path)
        finally:
            p = Path(tmp_path)
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass


def _rerank_local(query: str, docs: list[str], top_k: int | None = None) -> list[str]:
    """Local reranker — cross-encoder quantized if available, else nomic similarity fallback.
    Runs on CPU, no API, no RAM spike. Used for Phase 3 free polish."""
    if not docs:
        return docs
    # Try sentence-transformers cross-encoder (quantized, CPU)
    try:
        from sentence_transformers import CrossEncoder
        # Use tiny quantized cross-encoder if available, else skip
        model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", device="cpu")
        scores = model.predict([(query, d) for d in docs])
        ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
        out = [d for d, _ in ranked]
        return out[:top_k] if top_k else out
    except Exception:
        pass
    # Fallback: simple keyword overlap + nomic cosine via difflib (free, no model)
    try:
        q_words = set(query.lower().split())
        def score(d):
            d_words = set(d.lower().split())
            return len(q_words & d_words) / max(1, len(q_words))
        ranked = sorted(docs, key=score, reverse=True)
        return ranked[:top_k] if top_k else ranked
    except Exception:
        return docs


def _load_titles() -> dict:
    return _load_json(TITLES_FILE, {})


def _save_titles(titles: dict):
    _save_json(TITLES_FILE, titles)


def _heuristic_title(turns: list[dict]) -> str:
    if not turns:
        return "New chat"
    users = [t.get("user", "").strip() for t in turns if t.get("user", "").strip()]
    if not users:
        return "New chat"
    if len(users) == 1:
        txt = users[0]
        return txt[:55] + ("…" if len(txt) > 55 else "")
    # Progression: combine first topic + last focus
    first, last = users[0], users[-1]
    # If last is very short follow-up, combine
    if len(last) < 24 and len(users) >= 2:
        # Use first topic truncated + last
        combined = f"{first[:30].strip()} → {last.strip()}"
        return combined[:60]
    # If conversation drifted (few overlapping words), show evolution arrow
    first_words = set(first.lower().split()[:8])
    last_words = set(last.lower().split()[:8])
    overlap = len(first_words & last_words)
    if overlap == 0 and len(users) >= 3:
        # Show progression: last title captures current, hint origin
        short_first = " ".join(first.split()[:3])
        return f"{last[:45].strip()} · {short_first}…"[:60]
    return last[:55] + ("…" if len(last) > 55 else "")


async def _llm_title_for_turns(turns: list[dict], model: str | None = None) -> str | None:
    """Try LLM for a 3-6 word title, fallback to heuristic."""
    try:
        if not turns:
            return None
        users = [t.get("user", "").strip() for t in turns if t.get("user", "").strip()]
        if not users:
            return None
        # Don't call LLM for first turn — heuristic is faster and sufficient
        if len(users) <= 2:
            return _heuristic_title(turns)
        # Build prompt from recent progression
        snippet = "\n".join(f"- {u[:120]}" for u in users[-5:])
        prompt = f"Conversation progression (oldest to newest):\n{snippet}\n\nGenerate a concise 3-6 word chat title capturing the overall journey/progression. No quotes, no period, title case. Title:"
        system = "You generate short chat titles. Output ONLY the title, 3-6 words, no punctuation, no quotes."
        from services.ollama_service import OllamaService
        from models.database import MODELS as _MODELS
        m = model or _MODELS.get("main", "gemma4:e4b-mlx")
        svc = OllamaService()
        # 4s timeout — title is not worth blocking chat
        import asyncio as _asyncio
        try:
            raw = await _asyncio.wait_for(
                svc.complete(m, prompt, system, max_tokens=16, think=False, context_window=2048),
                timeout=4,
            )
        except _asyncio.TimeoutError:
            return _heuristic_title(turns)
        raw = (raw or "").strip().strip('"').strip("'").strip()
        # Take first line, strip bullet
        raw = raw.split("\n")[0].lstrip("- •").strip()
        # Remove trailing period
        raw = raw.rstrip(".")
        if not raw or len(raw) < 3:
            return _heuristic_title(turns)
        if len(raw) > 60:
            raw = raw[:60]
        # Cap words
        words = raw.split()
        if len(words) > 6:
            raw = " ".join(words[:6])
        # Title case if all lower
        if raw.islower():
            raw = raw.title()
        return raw
    except Exception:
        return _heuristic_title(turns)


class _NomicEmbeddingFunction:
    """Embedding function that calls nomic-embed-text via Ollama.
    Keeps memory vectors consistent with KB vectors (both use nomic).
    Respects OLLAMA_URL env and MODELS config, handles both /api/embed
    and legacy /api/embeddings, and avoids poisoning DB with zero vectors."""

    def __call__(self, input: list[str]) -> list[list[float]]:
        import httpx
        # Resolve OLLAMA_URL and embedding model from central config
        try:
            from models.database import OLLAMA_URL as _OLLAMA_URL, MODELS as _MODELS
            ollama_url = _OLLAMA_URL
            embed_model = _MODELS.get("embedding", "nomic-embed-text")
        except Exception:
            ollama_url = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/").split("/api")[0]
            embed_model = os.environ.get("ARIA_EMBED_MODEL", "nomic-embed-text")

        # Normalize model variants — Ollama may have :latest suffix
        candidates = [embed_model]
        if embed_model and not embed_model.endswith(":latest"):
            candidates.append(f"{embed_model}:latest")
        elif embed_model and embed_model.endswith(":latest"):
            candidates.append(embed_model.replace(":latest", ""))

        # Try modern /api/embed with batch input — 60s for cold start
        for mdl in candidates:
            try:
                r = httpx.post(
                    f"{ollama_url}/api/embed",
                    json={"model": mdl, "input": input},
                    timeout=60,
                )
                r.raise_for_status()
                data = r.json()
                if "embeddings" in data and isinstance(data["embeddings"], list):
                    embs = data["embeddings"]
                    if len(embs) == len(input):
                        return embs
                if "embedding" in data:
                    return [data["embedding"] for _ in input]
            except Exception as e:
                logger.debug("Memory embed via /api/embed failed for %s: %s", mdl, e)
                continue

        # Legacy fallback: /api/embeddings per text — 60s
        for mdl in candidates:
            try:
                embeddings: list[list[float]] = []
                with httpx.Client(timeout=60, base_url=ollama_url) as client:
                    for text in input:
                        r = client.post("/api/embeddings", json={"model": mdl, "prompt": text})
                        r.raise_for_status()
                        emb = r.json().get("embedding")
                        if emb:
                            embeddings.append(emb)
                        else:
                            embeddings.append([0.0] * 768)
                if len(embeddings) == len(input):
                    return embeddings
            except Exception as e:
                logger.debug("Memory embedding failed for %s via embeddings: %s", mdl, e)
                continue

        logger.warning("Memory embedding failed for all candidates %s — returning zero vectors", candidates)
        return [[0.0] * 768 for _ in input]


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
            # Use nomic-embed-text via Ollama for consistent embeddings with KB
            embedding_fn = _NomicEmbeddingFunction()
            self._collection = client.get_or_create_collection(
                name="aria_memory",
                metadata={"hnsw:space": "cosine"},
                embedding_function=embedding_fn,
            )
            # Global collection for cross-conversation search
            self._global_collection = client.get_or_create_collection(
                name="aria_global_memory",
                metadata={"hnsw:space": "cosine"},
                embedding_function=embedding_fn,
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

        # Adaptive title — fast heuristic immediately, LLM refines in background
        try:
            titles = _load_titles()
            heuristic = _heuristic_title(convs[conversation_id])
            # Only update if changed or new
            if titles.get(conversation_id) != heuristic:
                titles[conversation_id] = heuristic
                _save_titles(titles)
            # Schedule LLM refinement for longer conversations (every 2 turns after 2)
            n = len(convs[conversation_id])
            if n >= 3 and n % 2 == 1:
                import asyncio as _asyncio
                try:
                    loop = _asyncio.get_running_loop()
                    loop.create_task(self._background_llm_title(conversation_id))
                except RuntimeError:
                    pass
        except Exception:
            pass

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

    async def _background_llm_title(self, conversation_id: str):
        try:
            convs = _load_json(CONVERSATIONS_FILE, {})
            turns = convs.get(conversation_id, [])
            if not turns:
                return
            new_title = await _llm_title_for_turns(turns)
            if new_title:
                titles = _load_titles()
                if titles.get(conversation_id) != new_title:
                    titles[conversation_id] = new_title
                    _save_titles(titles)
        except Exception:
            pass

    async def get_title(self, conversation_id: str) -> str | None:
        titles = _load_titles()
        if conversation_id in titles:
            return titles[conversation_id]
        convs = _load_json(CONVERSATIONS_FILE, {})
        turns = convs.get(conversation_id, [])
        if turns:
            return _heuristic_title(turns)
        return None

    async def set_title(self, conversation_id: str, title: str) -> str:
        titles = _load_titles()
        clean = title.strip()[:60]
        if not clean:
            raise ValueError("Title cannot be empty")
        titles[conversation_id] = clean
        _save_titles(titles)
        return clean

    async def regenerate_title(self, conversation_id: str, use_llm: bool = True) -> str | None:
        convs = _load_json(CONVERSATIONS_FILE, {})
        turns = convs.get(conversation_id, [])
        if not turns:
            return None
        if use_llm:
            new_title = await _llm_title_for_turns(turns)
        else:
            new_title = _heuristic_title(turns)
        if new_title:
            titles = _load_titles()
            titles[conversation_id] = new_title
            _save_titles(titles)
        return new_title

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
            except Exception as e:
                logger.warning("ChromaDB conversation search failed: %s", e)

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

        # Merge, deduplicate, rerank, limit — Phase 3 local reranker (free)
        all_memories = list(dict.fromkeys(semantic + recent + global_context))
        try:
            all_memories = _rerank_local(query, all_memories, top_k=k+6)
        except Exception:
            pass
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
        titles = _load_titles()
        result = []
        for cid, turns in convs.items():
            if turns:
                first = turns[0]
                last = turns[-1]
                # Adaptive title: persisted LLM/heuristic or fallback
                title = titles.get(cid)
                if not title:
                    title = _heuristic_title(turns)
                    # persist fallback for next time
                    try:
                        titles[cid] = title
                    except Exception:
                        pass
                result.append({
                    "id": cid,
                    "title": title,
                    "timestamp": first["timestamp"],
                    "last_timestamp": last["timestamp"],
                    "turn_count": len(turns),
                })
        # Save any newly generated heuristic titles
        try:
            _save_titles(titles)
        except Exception:
            pass
        return sorted(result, key=lambda x: x["last_timestamp"], reverse=True)

    async def search_conversations(self, query: str) -> list[dict]:
        """Search across all conversation content."""
        convs = _load_json(CONVERSATIONS_FILE, {})
        titles = _load_titles()
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
                title = titles.get(cid) or _heuristic_title(turns)
                results.append({
                    "id": cid,
                    "title": title,
                    "timestamp": turns[0]["timestamp"],
                    "last_timestamp": turns[-1]["timestamp"],
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
        # Also remove title
        try:
            titles = _load_titles()
            if conversation_id in titles:
                del titles[conversation_id]
                _save_titles(titles)
        except Exception:
            pass

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
        titles = _load_titles()
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
                title = titles.get(cid) or _heuristic_title(date_turns)
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
