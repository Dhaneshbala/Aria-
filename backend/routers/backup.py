"""Backup & export — one-click full backup of ARIA data.

Zips everything that makes ARIA *yours*:
  • conversations + study profile + analytics + telemetry (~/.aria_data)
  • app config and rules (backend/data)
  • organizer index + history (backend/storage/organizer.db, files_index)

Backups land in backend/storage/backups/ with rotation:
  • Keep last 7 daily backups
  • Keep last 4 weekly backups (oldest weekly of each week)
Restore merges the files back and asks for a restart so in-memory caches reload.
Uploaded files (can be many GB) are excluded by default.
"""
import json
import os
import shutil
import tempfile
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/backup", tags=["backup"])

BACKEND_DIR = Path(__file__).resolve().parents[1]
BACKUP_DIR = BACKEND_DIR / "storage" / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

MAX_DAILY_BACKUPS = 7
MAX_WEEKLY_BACKUPS = 4
MAX_BACKUPS = MAX_DAILY_BACKUPS + MAX_WEEKLY_BACKUPS
MAX_RESTORE_SIZE = 500 * 1024 * 1024  # 500 MB

# Files that always belong in a backup
ARIA_DATA_FILES = [
    "conversations.json", "study_profile.json", "compressed_memory.json",
    "analytics.json", "telemetry.jsonl", "aria.log",
]
APP_DATA_FILES = [
    "config.json", "example_rules.json", "conversations.json",
]
STORAGE_FILES = [
    "organizer.db", "organizer.db-wal", "organizer.db-shm",
    "files_index.json", "settings.json",
]


def _aria_data_dir() -> Path:
    env = os.environ.get("ARIA_DATA_DIR")
    if env:
        return Path(env)
    return Path.home() / ".aria_data"


def _safe_add(zf: zipfile.ZipFile, src: Path, arcname: str) -> bool:
    """Add a file/dir to the zip, skipping missing entries."""
    if not src.exists():
        return False
    if src.is_dir():
        for child in sorted(src.rglob("*")):
            if child.is_file():
                zf.write(child, f"{arcname}/{child.relative_to(src)}")
    else:
        zf.write(src, arcname)
    return True


@router.post("/create")
async def create_backup(include_uploads: bool = False):
    """Create a full backup zip and return its filename + size."""
    from services.telemetry_service import record_event

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = BACKUP_DIR / f"aria-backup-{ts}.zip"
    aria_dir = _aria_data_dir()
    counts = {"files": 0, "bytes": 0}

    def _count(zf):
        counts["files"] = len(zf.infolist())

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        # Manifest first
        manifest = {
            "app": "aria",
            "version": "2.1.0",
            "created_at": datetime.now().isoformat(),
            "include_uploads": bool(include_uploads),
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

        # ARIA data dir (conversations, chromadb, profile, analytics...)
        for name in ARIA_DATA_FILES:
            _safe_add(zf, aria_dir / name, f"aria_data/{name}")
        _safe_add(zf, aria_dir / "chromadb", "aria_data/chromadb")

        # App data
        data_dir = BACKEND_DIR / "data"
        for name in APP_DATA_FILES:
            _safe_add(zf, data_dir / name, f"data/{name}")

        # Organizer index
        storage_dir = BACKEND_DIR / "storage"
        for name in STORAGE_FILES:
            _safe_add(zf, storage_dir / name, f"storage/{name}")

        # Optional: uploaded files
        if include_uploads:
            uploads = storage_dir / "uploads"
            if uploads.exists():
                _safe_add(zf, uploads, "uploads")

        _count(zf)

    size_mb = round(out.stat().st_size / 1024 / 1024, 2)
    record_event("backup_created", size_mb=size_mb, include_uploads=bool(include_uploads))

    # Retention: keep 7 daily + 4 weekly backups
    _rotate_backups()

    return {
        "status": "ok",
        "filename": out.name,
        "size_mb": size_mb,
        "files": counts["files"],
        "path": str(out),
    }


@router.get("/list")
async def list_backups():
    backups = []
    for p in sorted(BACKUP_DIR.glob("aria-backup-*.zip")):
        backups.append({
            "filename": p.name,
            "size_mb": round(p.stat().st_size / 1024 / 1024, 2),
            "created_at": datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
        })
    return {"backups": list(reversed(backups)), "count": len(backups)}


@router.get("/download/{filename}")
async def download_backup(filename: str):
    if not filename or ".." in filename or "/" in filename:
        raise HTTPException(400, "Invalid filename")
    p = BACKUP_DIR / filename
    if not p.exists():
        raise HTTPException(404, "Backup not found")
    return FileResponse(
        p,
        media_type="application/zip",
        filename=filename,
    )


@router.delete("/{filename}")
async def delete_backup(filename: str):
    if not filename or ".." in filename or "/" in filename:
        raise HTTPException(400, "Invalid filename")
    p = BACKUP_DIR / filename
    if not p.exists():
        raise HTTPException(404, "Backup not found")
    p.unlink()
    return {"deleted": True, "filename": filename}


def _snapshot_pre_restore() -> str | None:
    """Best-effort safety net: zip current live data before a restore
    overwrites it. Returns the snapshot filename, or None if it failed
    (restore still proceeds — a failed snapshot must never block recovery)."""
    import logging
    log = logging.getLogger(__name__)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = BACKUP_DIR / f"aria-pre-restore-{ts}.zip"
    aria_dir = _aria_data_dir()
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", json.dumps({
                "app": "aria", "version": "2.1.0",
                "created_at": datetime.now().isoformat(),
                "pre_restore_snapshot": True,
            }, indent=2))
            for name in ARIA_DATA_FILES:
                _safe_add(zf, aria_dir / name, f"aria_data/{name}")
            data_dir = BACKEND_DIR / "data"
            for name in APP_DATA_FILES:
                _safe_add(zf, data_dir / name, f"data/{name}")
            storage_dir = BACKEND_DIR / "storage"
            for name in STORAGE_FILES:
                _safe_add(zf, storage_dir / name, f"storage/{name}")
        return out.name
    except Exception as e:
        log.warning("Pre-restore snapshot failed (proceeding anyway): %s", e)
        try:
            if out.exists():
                out.unlink()
        except OSError:
            pass
        return None


@router.post("/restore")
async def restore_backup(file: UploadFile = File(...)):
    """Restore a backup zip. Only known data files are merged back;
    in-memory caches (ChromaDB, organizer DB) reload after a restart."""
    from services.telemetry_service import record_event

    content = await file.read()
    if len(content) > MAX_RESTORE_SIZE:
        raise HTTPException(413, f"Backup too large (max {MAX_RESTORE_SIZE // (1024*1024)} MB)")
    if len(content) == 0:
        raise HTTPException(400, "Empty file")

    # Safety net first: snapshot live data so a bad restore is undoable.
    pre_restore = _snapshot_pre_restore()

    staging = Path(tempfile.mkdtemp(prefix="aria_restore_"))
    restored: list[str] = []
    try:
        with zipfile.ZipFile(io_bytes(content)) as zf:
            names = zf.namelist()
            if "manifest.json" not in names:
                raise HTTPException(400, "Not an ARIA backup (no manifest.json)")
            # Zip-slip-safe extraction
            for name in names:
                target = (staging / name).resolve()
                if not target.is_relative_to(staging.resolve()):
                    raise HTTPException(400, f"Unsafe path in backup: {name}")
                if name.endswith("/"):
                    continue
                zf.extract(name, staging)

            for name in names:
                if name.endswith("/") or not (staging / name).is_file():
                    continue
                if name.startswith("aria_data/"):
                    dest = _aria_data_dir() / name[len("aria_data/"):]
                elif name.startswith("data/"):
                    dest = BACKEND_DIR / "data" / name[len("data/"):]
                elif name.startswith("storage/") and not name.startswith("storage/uploads"):
                    dest = BACKEND_DIR / "storage" / name[len("storage/"):]
                else:
                    continue  # uploads and anything unknown are skipped
                if not _is_safe_dest(dest):
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(staging / name, dest)
                restored.append(name)

        record_event("backup_restored", files=len(restored))
        return {
            "status": "ok",
            "restored": len(restored),
            "note": "Restart ARIA so ChromaDB and the organizer index reload.",
            "files": restored,
            "pre_restore_backup": pre_restore,
            "pre_restore_note": (
                f"Your previous data was snapshotted to {pre_restore} — restore it if this was a mistake."
                if pre_restore else
                "Warning: pre-restore snapshot failed (disk full?) — no undo snapshot exists."
            ),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Restore failed: {e}")
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def io_bytes(data: bytes):
    import io
    return io.BytesIO(data)


def _is_safe_dest(dest: Path) -> bool:
    """Only restore into ARIA's own data/storage dirs."""
    allowed = (BACKEND_DIR / "data", BACKEND_DIR / "storage", _aria_data_dir())
    return any(dest.is_relative_to(a) for a in allowed)


def _rotate_backups():
    """Keep 7 daily + 4 weekly backups.  Newest of each period is kept."""
    backups = sorted(BACKUP_DIR.glob("aria-backup-*.zip"), key=lambda p: p.stat().st_mtime)
    if len(backups) <= MAX_BACKUPS:
        return

    now = datetime.now()
    daily_cutoff = now - timedelta(days=MAX_DAILY_BACKUPS)
    weekly_cutoff = now - timedelta(weeks=MAX_WEEKLY_BACKUPS)

    daily = []
    weekly = []
    older = []

    for b in backups:
        mtime = datetime.fromtimestamp(b.stat().st_mtime)
        if mtime >= daily_cutoff:
            daily.append(b)
        elif mtime >= weekly_cutoff:
            weekly.append(b)
        else:
            older.append(b)

    # Keep newest per week bucket for weekly backups
    weekly_by_week: dict[int, Path] = {}
    for b in weekly:
        week_key = datetime.fromtimestamp(b.stat().st_mtime).isocalendar()[1]
        weekly_by_week[week_key] = b  # last one wins (newest)
    weekly_kept = list(weekly_by_week.values())

    # Delete everything else
    keep = set(daily[-MAX_DAILY_BACKUPS:]) | set(weekly_kept[-MAX_WEEKLY_BACKUPS:])
    for b in older + weekly:
        if b not in keep:
            try:
                b.unlink()
            except OSError:
                pass
