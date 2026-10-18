"""System health & support — friendly diagnostics, logs, Ollama restart.

Gives the UI everything it needs to turn a raw failure into a friendly
recovery screen:
  • /diagnostics  — structured check of every moving part
  • /restart-ollama — attempts to relaunch Ollama if it died
  • /logs, /logs/download — tail + full log export (the "send logs" flow)
"""

import logging
import shutil
import subprocess
import sys
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException

from models.database import DATA_DIR, get_config
from services.ollama_service import OllamaService

router = APIRouter(prefix="/api/system", tags=["system"])
logger = logging.getLogger(__name__)
ollama = OllamaService()

LOG_FILE = DATA_DIR / "aria.log"


# ── Diagnostics ─────────────────────────────────────────────────────────────


@router.get("/diagnostics")
async def diagnostics():
    """Run a full health check and return human-readable results."""
    report: dict = {
        "status": "ok",
        "checks": {},
        "friendly": "Everything looks good.",
    }
    problems: list[str] = []

    # 1. Backend itself
    report["checks"]["backend"] = {"ok": True, "message": "ARIA backend is running"}

    # 2. Ollama reachable?
    try:
        h = await ollama.health()
        ok = bool(h.get("ok"))
        report["checks"]["ollama"] = {
            "ok": ok,
            "message": f"Ollama is {'running' if ok else 'not responding'}",
            "models": h.get("models", []),
        }
        if not ok:
            problems.append("ollama")
    except Exception as e:
        report["checks"]["ollama"] = {"ok": False, "message": f"Ollama error: {e}"}
        problems.append("ollama")

    # 3. Configured models installed? (single main model + embedding)
    cfg = get_config()
    wanted = [
        ("main", cfg.get("model") or cfg.get("reasoning_model")),
        ("embedding", cfg.get("embedding_model")),
    ]
    missing = []
    installed = report["checks"]["ollama"].get("models", [])
    # Ollama reports "nomic-embed-text:latest" but config is "nomic-embed-text"
    # so compare base names (before :) as well.
    installed_bases = {m.split(":")[0] for m in installed}
    installed_set = set(installed) | installed_bases
    for role, model in wanted:
        if (
            model
            and model not in installed_set
            and model.split(":")[0] not in installed_set
        ):
            missing.append(f"{role}: {model}")
    report["checks"]["models"] = {
        "ok": not missing,
        "message": (
            "All configured models installed"
            if not missing
            else f"Missing: {', '.join(missing)}"
        ),
        "missing": missing,
    }
    if missing:
        problems.append("models")

    # 3b. Embedding actually works? (nomic-embed-text loads and returns vector)
    if not missing:
        try:
            emb = await ollama.embed(
                cfg.get("embedding_model", "nomic-embed-text"), "test ok"
            )
            ok_emb = isinstance(emb, list) and len(emb) > 100  # nomic is 768-dim
            report["checks"]["embedding"] = {
                "ok": ok_emb,
                "message": f"Embedding OK ({len(emb)}-dim)"
                if ok_emb
                else "Embedding returned empty — nomic may be missing",
            }
            if not ok_emb:
                problems.append("models")
        except Exception as e:
            report["checks"]["embedding"] = {
                "ok": False,
                "message": f"Embedding error: {e}",
            }
            problems.append("models")

    # 4. Storage writable?
    try:
        probe = DATA_DIR / ".write_test"
        probe.write_text("ok")
        probe.unlink()
        report["checks"]["storage"] = {"ok": True, "message": "Data folder is writable"}
    except Exception as e:
        report["checks"]["storage"] = {
            "ok": False,
            "message": f"Data folder not writable: {e}",
        }
        problems.append("storage")

    # 5. Disk space
    try:
        usage = shutil.disk_usage(str(DATA_DIR))
        free_gb = usage.free / 1024**3
        report["checks"]["disk"] = {
            "ok": free_gb > 2,
            "message": f"{free_gb:.1f} GB free",
            "free_gb": round(free_gb, 1),
        }
        if free_gb <= 2:
            problems.append("disk")
    except Exception:
        report["checks"]["disk"] = {"ok": True, "message": "Disk space unknown"}

    # 6. RAM pressure (the #1 crash cause on 16 GB Macs)
    try:
        import psutil

        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()
        avail_gb = round(vm.available / 1024**3, 1)
        # A 12B model needs ~9 GB resident; flag early so the UI can nudge
        # the user (close tabs) or offer one-click model unload.
        ok_mem = avail_gb > 3.0 and swap.percent < 90
        report["checks"]["memory"] = {
            "ok": ok_mem,
            "message": (
                f"{avail_gb} GB RAM available"
                if ok_mem
                else f"Only {avail_gb} GB RAM free — close heavy apps or unload models"
            ),
            "available_gb": avail_gb,
            "swap_percent": round(swap.percent, 1),
        }
        if not ok_mem:
            problems.append("memory")
    except Exception as e:
        logger.debug("Memory check failed: %s", e)
        report["checks"]["memory"] = {"ok": True, "message": "RAM status unknown"}

    # 7. Telemetry status
    from services.telemetry_service import summary as telemetry_summary

    ts = telemetry_summary()
    report["checks"]["telemetry"] = {
        "ok": True,
        "message": "Telemetry is " + ("enabled" if ts["enabled"] else "off (opt-in)"),
        "enabled": ts["enabled"],
    }

    report["problems"] = problems
    if problems:
        report["status"] = "degraded"
        report["friendly"] = _friendly_message(problems)
    return report


def _friendly_message(problems: list[str]) -> str:
    msgs = {
        "ollama": "The AI engine (Ollama) isn't responding. Press 'Restart Ollama' below — "
        "ARIA will try to start it for you.",
        "models": "Some AI models aren't downloaded yet. Go to Admin → Models and pull the "
        "missing ones (one time, a few GB).",
        "storage": "ARIA can't write to its data folder. Check that the folder isn't read-only "
        "or blocked by your antivirus.",
        "disk": "Your disk is nearly full. Free some space so ARIA can save your chats.",
        "memory": "RAM is nearly full — this is what crashes ARIA. Close Chrome tabs and heavy apps, "
        "or go to Admin → Memory → Unload AI models to free ~8 GB instantly.",
    }
    return " ".join(msgs[p] for p in problems if p in msgs) or "ARIA needs attention."


# ── Restart Ollama ──────────────────────────────────────────────────────────


@router.post("/restart-ollama")
async def restart_ollama():
    """Try to (re)start Ollama. Safe to call repeatedly."""
    from services.telemetry_service import record_event

    try:
        h = await ollama.health()
        if h.get("ok"):
            return {
                "status": "already_running",
                "message": "Ollama is already running.",
            }
    except Exception:
        pass

    launched = False
    for cmd in _start_commands():
        try:
            subprocess.Popen(  # noqa: ASYNC220 — fire-and-forget boot launcher, deliberate
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            launched = True
            break
        except Exception as e:
            logger.warning("Failed to launch %s: %s", cmd, e)

    if not launched:
        raise HTTPException(
            500,
            "Could not start Ollama automatically. "
            "Please open the Ollama app from your Applications folder.",
        )

    # Wait up to 15 s for it to come up
    for _ in range(30):
        await _sleep(0.5)
        try:
            h = await ollama.health()
            if h.get("ok"):
                record_event("ollama_restarted")
                return {"status": "started", "message": "Ollama started successfully."}
        except Exception:
            continue
    return {
        "status": "starting",
        "message": "Ollama is starting in the background — give it a few seconds.",
    }


def _start_commands() -> list[list[str]]:
    if sys.platform == "darwin":
        return [
            ["open", "-a", "Ollama"],
            ["ollama", "serve"],
        ]
    if sys.platform.startswith("win"):
        return [
            ["start", "", "ollama", "serve"],
            ["ollama", "serve"],
        ]
    return [["ollama", "serve"]]


async def _sleep(seconds: float):
    import asyncio

    await asyncio.sleep(seconds)


# ── Logs (send-logs flow) ───────────────────────────────────────────────────


@router.get("/logs")
async def tail_logs(lines: int = 200):
    try:
        lines = max(1, min(int(lines), 2000))
    except Exception:
        lines = 200
    if not LOG_FILE.exists():
        return {"content": "", "lines": 0}
    import collections

    content = LOG_FILE.read_text(errors="replace").splitlines()
    tail = list(collections.deque(content, maxlen=lines))
    return {"content": "\n".join(tail), "lines": len(tail)}


@router.get("/logs/download")
async def download_logs():
    """Bundle diagnostics + recent logs + telemetry into a zip for support."""
    import io
    import json
    import zipfile

    report = await diagnostics()

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("diagnostics.json", json.dumps(report, indent=2, default=str))
        log_text = ""
        if LOG_FILE.exists():
            log_text = LOG_FILE.read_text(errors="replace")[-200_000:]
        zf.writestr("aria.log", log_text)
        zf.writestr("config.json", json.dumps(get_config(), indent=2, default=str))

    buffer.seek(0)
    from fastapi.responses import Response

    stamp = time.strftime("%Y%m%d-%H%M%S")
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="aria-support-{stamp}.zip"'
        },
    )


def _dir_size(path: Path) -> int:
    total = 0
    try:
        for p in path.rglob("*"):
            try:
                if p.is_file() and not p.is_symlink():
                    total += p.stat().st_size
            except OSError:
                pass
    except OSError:
        pass
    return total


@router.get("/storage")
async def storage_info():
    """Disk visibility: uploads, backups, data-dir sizes + counts (helps 86%-full disk)."""
    backend_dir = Path(__file__).resolve().parents[1]
    uploads = backend_dir / "storage" / "uploads"
    backups = backend_dir / "storage" / "backups"
    try:
        disk = shutil.disk_usage(str(DATA_DIR))
        free_gb = round(disk.free / 1024**3, 1)
        total_gb = round(disk.total / 1024**3, 1)
    except OSError:
        free_gb, total_gb = -1, -1
    backup_zips = sorted(backups.glob("aria-*.zip")) if backups.exists() else []
    return {
        "data_dir": str(DATA_DIR),
        "data_dir_bytes": _dir_size(DATA_DIR),
        "uploads_bytes": _dir_size(uploads) if uploads.exists() else 0,
        "backups_bytes": sum(p.stat().st_size for p in backup_zips),
        "backups_count": len(backup_zips),
        "disk_free_gb": free_gb,
        "disk_total_gb": total_gb,
    }


@router.get("/metrics")
async def prometheus_metrics():
    """Prometheus scrape endpoint for the always-on box."""
    from fastapi.responses import Response
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
