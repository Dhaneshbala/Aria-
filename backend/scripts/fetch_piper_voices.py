"""Day 34: fetch Piper neural TTS voices (reproducible provisioning).

Downloads the ONNX voices in services.voice_service.PIPER_VOICES into
$ARIA_DATA_DIR/piper via curl (curl uses the macOS keychain CA store, which
is why it works where python-ssl tooling fails on managed networks).

Skips files that already exist at a sane size (>1 MB guards against cached
rate-limit pages). Retries with backoff — HuggingFace rate-limits rapid
parallel fetches, so this goes one file at a time with pauses.

Usage:
  python3 backend/scripts/fetch_piper_voices.py [--check-only]
"""

import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
# (repo subdir, stem) — subdir mirrors the piper-voices tree layout
VOICE_FILES = [
    ("en/en_US/lessac/medium", "en_US-lessac-medium"),
    ("hi/hi_IN/pratham/medium", "hi_IN-pratham-medium"),
    ("te/te_IN/maya/medium", "te_IN-maya-medium"),
    ("bn/bn_BD/google/medium", "bn_BD-google-medium"),
    ("ml/ml_IN/meera/medium", "ml_IN-meera-medium"),
    ("mr/mr_IN/google/medium", "mr_IN-google-medium"),
    ("ur/ur_PK/aegis_female/medium", "ur_PK-aegis_female-medium"),
]

MIN_BYTES = 1024 * 1024  # anything smaller is an error page, not a model


def piper_dir() -> Path:
    d = Path(os.environ.get("ARIA_DATA_DIR", Path.home() / ".aria_data")) / "piper"
    d.mkdir(parents=True, exist_ok=True)
    return d


def fetch(subdir: str, stem: str, outdir: Path) -> bool:
    ok = True
    for ext in (".onnx", ".onnx.json"):
        dest = outdir / f"{stem}{ext}"
        if dest.exists() and dest.stat().st_size > (
            MIN_BYTES if ext == ".onnx" else 100
        ):
            print(f"  skip {dest.name} (present, {dest.stat().st_size // 1024} KB)")
            continue
        url = f"{HF_BASE}/{subdir}/{stem}{ext}"
        print(f"  get  {stem}{ext} ...", flush=True)
        r = subprocess.run(
            [
                "curl",
                "-sL",
                "--retry",
                "5",
                "--retry-delay",
                "15",
                "--retry-all-errors",
                "--max-time",
                "900",
                "-o",
                str(dest),
                url,
            ],
            capture_output=True,
        )
        size = dest.stat().st_size if dest.exists() else 0
        floor = MIN_BYTES if ext == ".onnx" else 100
        if r.returncode != 0 or size < floor:
            print(f"  FAIL {stem}{ext} ({size} bytes) — retry later")
            ok = False
        else:
            print(f"  ok   {dest.name} ({size // 1024} KB)")
        time.sleep(5)  # stay under HF rate limits
    return ok


def main() -> int:
    from services.voice_service import PIPER_VOICES

    outdir = piper_dir()
    check_only = "--check-only" in sys.argv
    stems = set(PIPER_VOICES.values())
    missing_map = [v for v in VOICE_FILES if v[1] not in stems]
    if missing_map:
        print(f"WARNING: script knows voices missing from PIPER_VOICES: {missing_map}")
    print(f"target dir: {outdir}")
    all_ok = True
    for subdir, stem in VOICE_FILES:
        if check_only:
            have = all(
                (outdir / f"{stem}{e}").exists() for e in (".onnx", ".onnx.json")
            )
            print(f"  {'ok  ' if have else 'MISS'} {stem}")
            all_ok = all_ok and have
        elif not fetch(subdir, stem, outdir):
            all_ok = False
    print("ALL PRESENT" if all_ok else "INCOMPLETE — rerun later")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
