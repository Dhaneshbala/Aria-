"""Backup & export — one-click full backup of ARIA data.

Zips everything that makes ARIA *yours*:
  • conversations + study profile + analytics + telemetry (~/.aria_data)
  • app config and rules (backend/data)
  • organizer index + history (backend/storage/organizer.db, files_index)

Backups land in backend/storage/backups/ (last 10 kept). Restore merges
the files back and asks for a restart so in-memory caches reload.
Uploaded files (can be many GB) are excluded by default.
"""
import json
import os
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/backup", tags=["backup"])

BACKEND_DIR = Path(__file__).resolve().parents[1]
BACKUP_DIR = BACKEND_DIR / "storage" / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

MAX_BACKUPS = 10
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

    # Retention: keep newest MAX_BACKUPS
    backups = sorted(BACKUP_DIR.glob("aria-backup-*.zip"))
    for old in backups[:-MAX_BACKUPS]:
        try:
            old.unlink()
        except OSError:
            pass

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
