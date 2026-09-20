"""System health & support — friendly diagnostics, logs, Ollama restart.

Gives the UI everything it needs to turn a raw failure into a friendly
recovery screen:
  • /diagnostics  — structured check of every moving part
  • /restart-ollama — attempts to relaunch Ollama if it died
  • /logs, /logs/download — tail + full log export (the "send logs" flow)
"""
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

from models.database import DATA_DIR, get_config
from services.ollama_service import OllamaService

router = APIRouter(prefix="/api/system", tags=["system"])
logger = logging.getLogger(__name__)
ollama = OllamaService()

LOG_FILE = DATA_DIR / "aria.log"


def _redacted_config() -> dict:
    """Support-zip config with secrets stripped. The zip leaves the machine
    (emailed to support), so any *key/*token/*secret/*password value is
    replaced — the shape stays for debugging, the secret doesn't."""
    try:
        cfg = dict(get_config())
    except Exception:
        return {"error": "config unreadable"}
    sensitive = ("key", "token", "secret", "password", "passwd", "auth", "credential")
    return {
        k: ("<redacted>" if any(s in k.lower() for s in sensitive) and v else v)
        for k, v in cfg.items()
    }


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
    report["checks"]["backend"] = {"ok": True, "message": "Study Buddy backend is running"}

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
    # Ollama reports "mxbai-embed-large:latest" but config is "mxbai-embed-large"
    # so compare base names (before :) as well.
    installed_bases = {m.split(":")[0] for m in installed}
    installed_set = set(installed) | installed_bases
    for role, model in wanted:
        if model and model not in installed_set and model.split(":")[0] not in installed_set:
            missing.append(f"{role}: {model}")
    report["checks"]["models"] = {
        "ok": not missing,
        "message": ("All configured models installed" if not missing
                    else f"Missing: {', '.join(missing)}"),
        "missing": missing,
    }
    if missing:
        problems.append("models")

    # 3b. Embedding actually works? (mxbai-embed-large loads and returns vector)
    if not missing:
        try:
            emb = await ollama.embed(cfg.get("embedding_model", "mxbai-embed-large"), "test ok")
            ok_emb = isinstance(emb, list) and len(emb) > 100  # mxbai is 1024-dim
            report["checks"]["embedding"] = {
                "ok": ok_emb,
                "message": f"Embedding OK ({len(emb)}-dim)" if ok_emb else "Embedding returned empty — mxbai-embed-large may be missing",
            }
            if not ok_emb:
                problems.append("models")
        except Exception as e:
            report["checks"]["embedding"] = {"ok": False, "message": f"Embedding error: {e}"}
            problems.append("models")

    # 4. Storage writable?
    try:
        probe = DATA_DIR / ".write_test"
        probe.write_text("ok")
        probe.unlink()
        report["checks"]["storage"] = {"ok": True, "message": "Data folder is writable"}
    except Exception as e:
        report["checks"]["storage"] = {"ok": False, "message": f"Data folder not writable: {e}"}
        problems.append("storage")

    # 5. Disk space
    try:
        usage = shutil.disk_usage(str(DATA_DIR))
        free_gb = usage.free / 1024 ** 3
        report["checks"]["disk"] = {
            "ok": free_gb > 2,
            "message": f"{free_gb:.1f} GB free",
            "free_gb": round(free_gb, 1),
        }
        if free_gb <= 2:
            problems.append("disk")
    except Exception:
        report["checks"]["disk"] = {"ok": True, "message": "Disk space unknown"}

    # 6. Telemetry status
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
                  "Study Buddy will try to start it for you.",
        "models": "Some AI models aren't downloaded yet. Go to Admin → Models and pull the "
                  "missing ones (one time, a few GB).",
        "storage": "Study Buddy can't write to its data folder. Check that the folder isn't read-only "
                   "or blocked by your antivirus.",
        "disk": "Your disk is nearly full. Free some space so Study Buddy can save your chats.",
    }
    return " ".join(msgs[p] for p in problems if p in msgs) or "Study Buddy needs attention."


# ── Restart Ollama ──────────────────────────────────────────────────────────

@router.post("/restart-ollama")
async def restart_ollama():
    """Try to (re)start Ollama. Safe to call repeatedly."""
    from services.telemetry_service import record_event

    try:
        h = await ollama.health()
        if h.get("ok"):
            return {"status": "already_running", "message": "Ollama is already running."}
    except Exception:
        pass

    launched = False
    for cmd in _start_commands():
        try:
            subprocess.Popen(
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
        raise HTTPException(500, "Could not start Ollama automatically. "
                                 "Please open the Ollama app from your Applications folder.")

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
    return {"status": "starting", "message": "Ollama is starting in the background — give it a few seconds."}


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
    lines = max(1, min(5000, lines))
    if not LOG_FILE.exists():
        return {"content": "", "lines": 0}
    content = LOG_FILE.read_text(errors="replace").splitlines()
    tail = content[-lines:]
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
        zf.writestr("config.json", json.dumps(_redacted_config(), indent=2, default=str))

    buffer.seek(0)
    from fastapi.responses import Response
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="aria-support-{stamp}.zip"'},
    )
