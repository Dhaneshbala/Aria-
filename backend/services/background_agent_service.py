"""
Background Agent Service — Runs tasks while the user is away.
Supports:
  • Task queue (batch processing)
  • Folder automation (watch for new files)
  • Auto-research agent
  • Continuous coding agent
"""
import asyncio
import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

DATA_DIR = Path.home() / ".aria_data"
TASKS_FILE = DATA_DIR / "background_tasks.json"


def _load_tasks():
    if TASKS_FILE.exists():
        try:
            return json.loads(TASKS_FILE.read_text())
        except Exception:
            pass
    return []


def _save_tasks(tasks):
    TASKS_FILE.write_text(json.dumps(tasks, indent=2))


class BackgroundAgentService:

    def __init__(self):
        self._tasks: list[dict] = _load_tasks()
        self._running: dict[str, asyncio.Task] = {}
        self._watchers: dict[str, bool] = {}
        self._callback: Callable | None = None

    def set_callback(self, callback: Callable):
        """Set callback to send task results to chat."""
        self._callback = callback

    # ── Task Queue ────────────────────────────────────────────────────────────

    async def add_task(self, task_type: str, payload: dict) -> dict:
        """Add a background task to the queue."""
        task = {
            "id": f"task_{int(time.time()*1000)}",
            "type": task_type,
            "payload": payload,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "result": None,
        }
        self._tasks.append(task)
        _save_tasks(self._tasks)
        return task

    async def run_batch(self, task_type: str, items: list[dict], handler: Callable) -> dict:
        """Run a batch of items through a handler function."""
        results = []
        for i, item in enumerate(items):
            try:
                result = await handler(item)
                results.append({"item": item, "result": result, "success": True})
            except Exception as e:
                results.append({"item": item, "error": str(e), "success": False})

        return {
            "total": len(items),
            "completed": sum(1 for r in results if r["success"]),
            "failed": sum(1 for r in results if not r["success"]),
            "results": results,
        }

    async def summarise_folder(self, folder_path: str) -> dict:
        """Summarise all PDFs/documents in a folder."""
        from services.document_service import DocumentService
        from services.study_service import StudyService

        doc_svc = DocumentService()
        study_svc = StudyService()

        path = Path(folder_path)
        if not path.exists():
            return {"error": f"Folder not found: {folder_path}"}

        summaries = []
        supported = {".pdf", ".docx", ".doc", ".pptx", ".txt", ".md", ".py", ".js"}

        for file in sorted(path.iterdir()):
            if file.suffix.lower() in supported and file.is_file():
                try:
                    content = file.read_bytes()
                    text = await doc_svc.extract_text(content, file.name)
                    if text and len(text) > 50:
                        summary = await study_svc.generate_summary(text[:4000])
                        summaries.append({
                            "file": file.name,
                            "summary": summary,
                            "size": file.stat().st_size,
                        })
                except Exception as e:
                    summaries.append({"file": file.name, "error": str(e)})

        return {
            "folder": folder_path,
            "files_processed": len(summaries),
            "summaries": summaries,
        }

    # ── Folder Automation ─────────────────────────────────────────────────────

    def watch_folder(self, folder_path: str, handler: Callable | None = None):
        """Start watching a folder for new files."""
        path = Path(folder_path)
        if not path.exists():
            logger.warning("Folder not found: %s", folder_path)
            return

        self._watchers[folder_path] = True
        thread = threading.Thread(
            target=self._watch_loop,
            args=(folder_path, handler),
            daemon=True,
        )
        thread.start()
        logger.info("Watching folder: %s", folder_path)

    def stop_watching(self, folder_path: str):
        self._watchers.pop(folder_path, None)

    def _watch_loop(self, folder_path: str, handler: Callable | None):
        """Simple polling-based folder watcher."""
        path = Path(folder_path)
        seen_files = set(f.name for f in path.iterdir() if f.is_file())

        while self._watchers.get(folder_path):
            try:
                current_files = set(f.name for f in path.iterdir() if f.is_file())
                new_files = current_files - seen_files

                for fname in new_files:
                    fpath = path / fname
                    logger.info("New file detected: %s", fpath)
                    if handler:
                        try:
                            handler(str(fpath))
                        except Exception as e:
                            logger.error("Handler error for %s: %s", fpath, e)

                seen_files = current_files
                time.sleep(5)  # Poll every 5 seconds
            except Exception as e:
                logger.error("Watch loop error: %s", e)
                time.sleep(10)

    # ── Auto Research Agent ───────────────────────────────────────────────────

    async def auto_research(self, topic: str, depth: int = 3) -> dict:
        """Continuously research a topic, building knowledge incrementally."""
        from services.research_service import ResearchService

        research_svc = ResearchService()
        findings = []

        queries = [
            topic,
            f"{topic} overview",
            f"{topic} explained",
            f"{topic} examples",
            f"{topic} common mistakes",
        ]

        for i in range(min(depth, len(queries))):
            try:
                results = await research_svc.search(queries[i])
                if results:
                    findings.append({
                        "query": queries[i],
                        "results": results[:3],
                    })
            except Exception as e:
                logger.warning("Research query failed: %s", e)

        return {
            "topic": topic,
            "queries_run": len(findings),
            "findings": findings,
        }

    # ── Task Management ───────────────────────────────────────────────────────

    def get_tasks(self, status: str | None = None) -> list[dict]:
        if status:
            return [t for t in self._tasks if t["status"] == status]
        return self._tasks

    def update_task(self, task_id: str, status: str, result=None) -> bool:
        for task in self._tasks:
            if task["id"] == task_id:
                task["status"] = status
                if result is not None:
                    task["result"] = result
                _save_tasks(self._tasks)
                return True
        return False

    def clear_completed(self) -> int:
        before = len(self._tasks)
        self._tasks = [t for t in self._tasks if t["status"] != "completed"]
        _save_tasks(self._tasks)
        return before - len(self._tasks)
