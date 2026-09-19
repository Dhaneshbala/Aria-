"""Day 52: tests for the voice helper scripts (fetch + bench).

Scripts live outside the package, so they're loaded by file path. All tests
are hermetic: temp dirs, closed ports, no downloads, no models.
"""

import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_fetch_map_matches_service():
    fetch = _load("fetch_piper_voices")
    from services.voice_service import PIPER_VOICES

    assert {stem for _, stem in fetch.VOICE_FILES} == set(PIPER_VOICES.values())


def test_fetch_check_only_all_missing(monkeypatch, tmp_path, capsys):
    fetch = _load("fetch_piper_voices")
    monkeypatch.setenv("ARIA_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["fetch_piper_voices.py", "--check-only"])
    assert fetch.main() == 1
    assert "MISS" in capsys.readouterr().out


def test_fetch_check_only_all_present(monkeypatch, tmp_path, capsys):
    fetch = _load("fetch_piper_voices")
    monkeypatch.setenv("ARIA_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["fetch_piper_voices.py", "--check-only"])
    piper = tmp_path / "piper"
    piper.mkdir()
    for _, stem in fetch.VOICE_FILES:
        (piper / f"{stem}.onnx").write_bytes(b"x")
        (piper / f"{stem}.onnx.json").write_bytes(b"x")
    assert fetch.main() == 0
    assert "ALL PRESENT" in capsys.readouterr().out


def test_bench_live_skips_dead_server(capsys):
    bench = _load("bench_voice")
    # Port 9 (discard) is never listening → fast refusal, graceful skip.
    assert bench.bench_live_turn("http://127.0.0.1:9") is None
    assert "skipped" in capsys.readouterr().out
