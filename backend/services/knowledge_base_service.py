"""
Knowledge Base Service — ARIA's RAG-powered knowledge system.
─────────────────────────────────────────────────────────────
Stores documents in ChromaDB with nomic-embed-text embeddings.
Supports: PDF, DOCX, PPTX, XLSX, TXT, MD, HTML, CSV, JSON, images (OCR).
Collections: education_au, general, coding, research, math, science, history, geography, literature, productivity, user_docs.
"""
import os
import json
import hashlib
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)

DATA_DIR = Path.home() / ".aria_data"
KB_DIR = DATA_DIR / "knowledge_base"
KB_DIR.mkdir(parents=True, exist_ok=True)

EMBEDDING_MODEL = "nomic-embed-text"
CHUNK_SIZE = 600       # tokens (approx 4 chars per token)
CHUNK_OVERLAP = 100    # tokens

COLLECTIONS = {
    "education_au":  "Australian education — NSW syllabus, ACARA, textbooks",
    "general":       "General knowledge — Wikipedia, encyclopedias",
    "coding":        "Programming — official docs, MDN, frameworks",
    "research":      "Academic — arXiv, PubMed, open-access papers",
    "math":          "Mathematics — formulas, proofs, competition problems",
    "science":       "Science — physics, chemistry, biology",
    "history":       "History — events, timelines, civilisations",
    "geography":     "Geography — maps, climate, countries",
    "literature":    "Literature — books, analysis, literary devices",
    "productivity":  "Productivity — study techniques, time management",
    "user_docs":     "User-uploaded documents — personal study materials",
}


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks by character count (approx token count)."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size * 4  # ~4 chars per token
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start += (chunk_size - overlap) * 4
    return chunks


def _file_hash(filepath: str) -> str:
    """SHA-256 hash of file contents for deduplication."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    return h.hexdigest()[:16]


def _detect_collection(filepath: str, text: str) -> str:
    """Auto-detect which collection a document belongs to based on content heuristics."""
    lower = text[:2000].lower()
    name = Path(filepath).name.lower()

    # Education (Australian)
    au_keywords = ["australia", "nsw", "nesa", "acara", "syllabus", "stage 4", "stage 5",
                   "year 7", "year 8", "year 9", "year 10", "hsc", "australian curriculum"]
    if any(k in lower for k in au_keywords) or "australia" in name:
        return "education_au"

    # Coding
    code_keywords = ["def ", "function ", "class ", "import ", "const ", "let ",
                     "python", "javascript", "react", "docker", "git", "api",
                     "def ", "return ", "async ", "await ", "console.log"]
    code_exts = [".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".cpp", ".rs", ".go", ".html", ".css"]
    if any(k in lower for k in code_keywords) or any(name.endswith(e) for e in code_exts):
        return "coding"

    # Research
    research_keywords = ["abstract", "methodology", "conclusion", "doi:", "arxiv",
                         "references", "citation", "peer-reviewed", "hypothesis"]
    if sum(1 for k in research_keywords if k in lower) >= 2:
        return "research"

    # Math
    math_keywords = ["equation", "theorem", "proof", "formula", "integral", "derivative",
                     "matrix", "vector", "algebra", "geometry", "calculus", "probability"]
    if sum(1 for k in math_keywords if k in lower) >= 2:
        return "math"

    # Science
    science_keywords = ["experiment", "hypothesis", "molecule", "cell", "atom",
                        "physics", "chemistry", "biology", "organism", "reaction"]
    if sum(1 for k in science_keywords if k in lower) >= 2:
        return "science"

    # History
    history_keywords = ["war", "revolution", "century", "empire", "civilisation",
                        "dynasty", "treaty", "colonial", "ancient", "medieval"]
    if sum(1 for k in history_keywords if k in lower) >= 2:
        return "history"

    # Geography
    geo_keywords = ["continent", "climate", "latitude", "longitude", "river",
                    "mountain", "ocean", "country", "population", "ecosystem"]
    if sum(1 for k in geo_keywords if k in lower) >= 2:
        return "geography"

    # Literature
    lit_keywords = ["novel", "poem", "author", "narrative", "metaphor",
                    "character", "theme", "symbolism", "literary", "prose"]
    if sum(1 for k in lit_keywords if k in lower) >= 2:
        return "literature"

    return "general"


class KnowledgeBaseService:
    """Core knowledge base with ChromaDB vector storage and Ollama embeddings."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._client = chromadb.PersistentClient(
            path=str(KB_DIR / "chroma"),
            settings=Settings(anonymized_telemetry=False),
        )
        self._collections: dict[str, chromadb.Collection] = {}
        self._meta_path = KB_DIR / "documents.json"
        self._documents: dict[str, dict] = self._load_meta()
        self._init_collections()

    def _init_collections(self):
        for name in COLLECTIONS:
            try:
                self._collections[name] = self._client.get_or_create_collection(
                    name=f"kb_{name}",
                    metadata={"hnsw:space": "cosine"},
                )
            except Exception as e:
                logger.warning("Failed to create collection %s: %s", name, e)

    def _load_meta(self) -> dict:
        if self._meta_path.exists():
            try:
                return json.loads(self._meta_path.read_text())
            except Exception:
                pass
        return {}

    def _save_meta(self):
        self._meta_path.write_text(json.dumps(self._documents, indent=2, default=str))

    def get_collection(self, name: str) -> chromadb.Collection:
        if name not in self._collections:
            self._collections[name] = self._client.get_or_create_collection(
                name=f"kb_{name}",
                metadata={"hnsw:space": "cosine"},
            )
        return self._collections[name]

    async def ingest_file(
        self,
        filepath: str,
        collection: str | None = None,
        metadata: dict | None = None,
        embedding_model: str = EMBEDDING_MODEL,
    ) -> dict:
        """Ingest a file into the knowledge base. Returns ingestion stats."""
        from services.document_service import DocumentService
        from services.ollama_service import OllamaService

        doc_svc = DocumentService()
        ollama = OllamaService()

        filename = Path(filepath).name
        file_hash = _file_hash(filepath)

        # Dedup check
        if file_hash in self._documents:
            existing = self._documents[file_hash]
            return {"status": "duplicate", "document": existing["title"], "chunks": 0}

        # Extract text
        try:
            pages = doc_svc.extract_pages(filepath)
            full_text = "\n\n".join(p.get("text", "") for p in pages)
        except Exception as e:
            return {"status": "error", "error": f"Text extraction failed: {e}"}

        if not full_text.strip():
            return {"status": "error", "error": "No readable text found in document"}

        # Auto-detect collection
        if not collection:
            collection = _detect_collection(filepath, full_text)

        # Chunk text
        chunks = _chunk_text(full_text)
        if not chunks:
            return {"status": "error", "error": "Document too short to chunk"}

        # Generate embeddings
        yield_msg = f"Embedding {len(chunks)} chunks..."
        embeddings = await ollama.embed_batch(embedding_model, chunks)

        # Filter out failed embeddings
        valid = [(i, emb) for i, emb in enumerate(embeddings) if emb]
        if not valid:
            return {"status": "error", "error": "Embedding generation failed — is nomic-embed-text installed?"}

        # Store in ChromaDB
        col = self.get_collection(collection)
        ids = [f"{file_hash}_{i}" for i, _ in valid]
        docs = [chunks[i] for i, _ in valid]
        embs = [e for _, e in valid]
        metas = [
            {
                "source": filename,
                "file_hash": file_hash,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "collection": collection,
                "ingested_at": datetime.now().isoformat(),
                **(metadata or {}),
            }
            for i, _ in valid
        ]

        try:
            col.add(ids=ids, documents=docs, embeddings=embs, metadatas=metas)
        except Exception as e:
            return {"status": "error", "error": f"ChromaDB insert failed: {e}"}

        # Save document metadata
        doc_info = {
            "title": filename,
            "file_hash": file_hash,
            "collection": collection,
            "chunks_stored": len(valid),
            "total_chunks": len(chunks),
            "file_size": os.path.getsize(filepath),
            "ingested_at": datetime.now().isoformat(),
            "file_path": filepath,
            **(metadata or {}),
        }
        self._documents[file_hash] = doc_info
        self._save_meta()

        return {
            "status": "ok",
            "document": filename,
            "collection": collection,
            "chunks_stored": len(valid),
            "total_chunks": len(chunks),
        }

    async def search(
        self,
        query: str,
        collections: list[str] | None = None,
        n_results: int = 5,
        embedding_model: str = EMBEDDING_MODEL,
    ) -> list[dict]:
        """Semantic search across knowledge base collections."""
        from services.ollama_service import OllamaService

        ollama = OllamaService()
        query_emb = await ollama.embed(embedding_model, query)
        if not query_emb:
            return []

        if not collections:
            collections = list(COLLECTIONS.keys())

        all_results = []
        for col_name in collections:
            col = self.get_collection(col_name)
            try:
                count = col.count()
                if count == 0:
                    continue
                results = col.query(
                    query_embeddings=[query_emb],
                    n_results=min(n_results, count),
                    include=["documents", "metadatas", "distances"],
                )
                if results and results["documents"]:
                    for doc, meta, dist in zip(
                        results["documents"][0],
                        results["metadatas"][0],
                        results["distances"][0],
                    ):
                        all_results.append({
                            "text": doc,
                            "metadata": meta,
                            "distance": dist,
                            "score": 1 - dist,  # cosine distance -> similarity
                            "collection": col_name,
                        })
            except Exception as e:
                logger.warning("Search failed on collection %s: %s", col_name, e)

        # Sort by score descending
        all_results.sort(key=lambda x: x["score"], reverse=True)
        return all_results[:n_results]

    def list_documents(self, collection: str | None = None) -> list[dict]:
        """List all ingested documents, optionally filtered by collection."""
        docs = list(self._documents.values())
        if collection:
            docs = [d for d in docs if d.get("collection") == collection]
        return sorted(docs, key=lambda d: d.get("ingested_at", ""), reverse=True)

    def delete_document(self, file_hash: str) -> bool:
        """Delete a document and its chunks from the knowledge base."""
        if file_hash not in self._documents:
            return False

        doc = self._documents[file_hash]
        col_name = doc.get("collection", "general")
        col = self.get_collection(col_name)

        try:
            # Find and delete all chunks for this document
            results = col.get(where={"file_hash": file_hash})
            if results and results["ids"]:
                col.delete(ids=results["ids"])
        except Exception as e:
            logger.warning("Failed to delete chunks for %s: %s", file_hash, e)

        del self._documents[file_hash]
        self._save_meta()
        return True

    def get_stats(self) -> dict:
        """Get knowledge base statistics."""
        stats = {
            "total_documents": len(self._documents),
            "collections": {},
        }
        for name, desc in COLLECTIONS.items():
            col = self.get_collection(name)
            count = col.count()
            doc_count = sum(1 for d in self._documents.values() if d.get("collection") == name)
            stats["collections"][name] = {
                "description": desc,
                "chunks": count,
                "documents": doc_count,
            }
        stats["total_chunks"] = sum(c["chunks"] for c in stats["collections"].values())
        return stats

    async def rebuild_index(self, embedding_model: str = EMBEDDING_MODEL) -> dict:
        """Rebuild all embeddings from stored documents (e.g. after model change)."""
        docs = self.list_documents()
        results = {"rebuilt": 0, "failed": 0, "skipped": 0}
        for doc in docs:
            filepath = doc.get("file_path")
            if not filepath or not os.path.exists(filepath):
                results["skipped"] += 1
                continue
            self.delete_document(doc["file_hash"])
            try:
                await self.ingest_file(filepath, doc.get("collection"), embedding_model=embedding_model)
                results["rebuilt"] += 1
            except Exception:
                results["failed"] += 1
        return results
