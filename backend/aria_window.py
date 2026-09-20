"""Study Buddy native window — a real Mac app, no Terminal.

Double-click Study Buddy.app → this runs: it starts the single-server FastAPI
(API + built UI on 127.0.0.1) in a background thread, waits for /api/health,
then opens a native WKWebView window. Closing the window stops the server.

First-run and model problems are shown INSIDE the window — you never need
a terminal. Headless check (no window popup): ARIA_WINDOW_TEST=1.
"""
import os
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

PORT = int(os.environ.get("ARIA_PORT", "8000"))
BASE = f"http://127.0.0.1:{PORT}"
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
REQUIRED_MODELS = ("gemma4:e4b-mlx", "mxbai-embed-large")

# Finder-launched apps have no console: mirror every phase to a log file so a
# stuck/error window is diagnosable without a terminal.
try:
    from models.database import DATA_DIR as _DD
    APP_LOG = Path(_DD) / "aria-app.log"
except Exception:
    APP_LOG = Path.home() / ".aria_data" / "aria-app.log"


def log(msg: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} [app] {msg}"
    try:
        APP_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(APP_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

# GUI-launched apps (double-click) get a minimal PATH without /usr/local/bin
# or /opt/homebrew/bin — where ollama/npm live. Extend it for child processes.
_EXTRA_BIN_DIRS = ("/opt/homebrew/bin", "/usr/local/bin", "/opt/local/bin")


def find_bin(name: str) -> str | None:
    """Locate a binary beyond the GUI PATH (shutil.which + known Mac dirs)."""
    import shutil
    found = shutil.which(name)
    if found:
        return found
    for d in _EXTRA_BIN_DIRS:
        cand = Path(d) / name
        try:
            if cand.is_file() and os.access(cand, os.X_OK):
                return str(cand)
        except Exception:
            continue
    return None


def check_ollama() -> tuple[bool, str]:
    """Is Ollama installed and serving? Pure stdlib, no window needed."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=5) as r:
            if r.status == 200:
                return True, "Ollama running"
    except Exception:
        pass
    # Try to start a local Ollama (installed but not running).
    ollama_bin = find_bin("ollama")
    if ollama_bin is None:
        return False, "missing"
    try:
        subprocess.Popen([ollama_bin, "serve"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(12):
            time.sleep(1)
            try:
                with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=5) as r:
                    if r.status == 200:
                        return True, "Ollama started"
            except Exception:
                continue
    except FileNotFoundError:
        return False, "missing"
    except Exception:
        pass
    return False, "unreachable"


def check_models() -> list[str]:
    """Models required before the window opens. Queried over HTTP (/api/tags),
    not the `ollama` CLI — GUI-launched apps don't inherit the shell PATH, so
    the CLI may be invisible even with models installed. Never auto-pulls
    gigabytes — the user confirms via ./start-app.sh on first run."""
    import json
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=10) as r:
            data = json.load(r)
    except Exception:
        return list(REQUIRED_MODELS)
    installed = [str(m.get("name", "")).lower() for m in data.get("models", [])]

    def _present(required: str) -> bool:
        req = required.lower()
        req_base, _, req_tag = req.partition(":")
        for name in installed:
            if name == req:
                return True
            base, _, tag = name.partition(":")
            # Same model, registry-added :latest suffix (e.g. mxbai-embed-large).
            if base == req_base and tag in ("latest", req_tag):
                return True
        return False

    return [m for m in REQUIRED_MODELS if not _present(m)]


def ensure_frontend() -> tuple[bool, str]:
    """Production UI must be built (dist/). Builds it if npm exists."""
    if (ROOT / "frontend" / "dist" / "index.html").exists():
        return True, "built"
    npm_bin = find_bin("npm")
    if npm_bin is None:
        return False, "Node.js not installed — install it, then reopen Study Buddy."
    try:
        subprocess.run([npm_bin, "run", "build"], cwd=str(ROOT / "frontend"),
                       capture_output=True, timeout=600)
    except FileNotFoundError:
        return False, "Node.js not installed — install it, then reopen Study Buddy."
    except Exception as e:
        return False, f"UI build failed: {e}"
    if (ROOT / "frontend" / "dist" / "index.html").exists():
        return True, "built now"
    return False, "UI build failed — run `npm run build` in frontend/ once."


def server_already_running(port: int = PORT, timeout: float = 3) -> bool:
    """Single-instance reuse: if Study Buddy is already serving (e.g. ./start.sh or a
    previous app launch), point the new window at it instead of binding twice."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health",
                                    timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def serves_ui(port: int = PORT, timeout: float = 5) -> bool:
    """Does this port serve the Study Buddy web UI (HTML at /)? A stale server from
    before single-server mode answers /api/health but 404s the UI — the
    window must not point at it."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/",
                                    timeout=timeout) as r:
            return (r.status == 200
                    and "text/html" in r.headers.get("Content-Type", ""))
    except Exception:
        return False


def first_free_port(start: int, tries: int = 10) -> int | None:
    import socket
    for p in range(start, start + tries):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    return None


def select_target() -> tuple[int, bool]:
    """Pick (port, start_own). Reuse a server only if it serves the UI;
    a stale API-only server keeps its port — we take the next free one."""
    if server_already_running(PORT) and serves_ui(PORT):
        return PORT, False
    if not server_already_running(PORT):
        return PORT, True
    nxt = first_free_port(PORT + 1)
    if nxt is not None:
        return nxt, True
    return PORT, False


def server_log_file() -> Path:
    return APP_LOG.parent / "aria-server.log"


def build_server_cmd(port: int) -> list[str]:
    """Sidecar argv: same venv interpreter, backend cwd (set at spawn).

    `arch -arm64` is deliberate, not paranoia: the framework Python is a
    universal2 binary and the venv's compiled wheels are arm64-only. If this
    app ever runs translated (Rosetta "Open using …" checkbox), children
    inherit x86_64 and die with an arch ImportError (proven 2026-09-20).
    The prefix forces native; on an already-native parent it's a no-op."""
    return ["arch", "-arm64", sys.executable, "-m", "uvicorn", "main:app",
            "--host", "127.0.0.1", "--port", str(port),
            "--log-level", "warning"]


def start_sidecar(port: int = PORT):
    """Run the server as a child PROCESS (not a thread).

    Why: a thread server died silently after ~10 healthy minutes with zero
    traceback and no crash report — in-process uvicorn shares the Cocoa
    runloop's fate. A sidecar isolates crashes, leaves stderr on disk, and
    can be restarted. Returns the Popen handle.
    """
    env = dict(os.environ, ARIA_SERVE_FRONTEND="1")
    logf = open(server_log_file(), "a", encoding="utf-8")
    log(f"sidecar starting on {port} (log: {server_log_file()})")
    return subprocess.Popen(build_server_cmd(port), cwd=str(BACKEND_DIR),
                            env=env, stdout=logf, stderr=subprocess.STDOUT)


def stop_sidecar(proc) -> None:
    try:
        proc.terminate()
        proc.wait(timeout=8)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    log(f"sidecar stopped (rc={proc.poll()})")


def watch_sidecar(proc, window) -> None:
    """Daemon watchdog: if the server exits while the window lives, say so
    IN the window (with log paths) instead of leaving a dead page."""
    import time as _t
    while True:
        _t.sleep(5)
        if proc.poll() is not None:
            log(f"sidecar exited rc={proc.poll()} — notifying window")
            try:
                window.load_html(error_html(
                    "Server stopped",
                    "Study Buddy's server exited unexpectedly.<br>"
                    f"Details: <code>{server_log_file()}</code><br>"
                    f"and <code>{APP_LOG}</code><br><br>"
                    "Reopen the app to restart it."))
            except Exception:
                pass
            return


def wait_for_health(port: int = PORT, timeout: float = 60) -> bool:
    # Cold start measured ~14 s on a quiet M4; a busy machine (stale server +
    # Ollama + browser) needs headroom — 20 s was too tight (error page bug).
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health",
                                        timeout=3) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def error_html(title: str, body: str) -> str:
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Study Buddy — {title}</title>
<style>body{{background:#131314;color:#e8e8e8;font-family:-apple-system,Helvetica,sans-serif;
display:flex;align-items:center;justify-content:center;height:100vh;margin:0}}
.card{{max-width:520px;padding:32px;border:1px solid #2a2a40;border-radius:16px;background:#1a1a2e}}
h1{{color:#7c6af7;font-size:22px}}code{{background:#0f0f0f;padding:2px 8px;border-radius:6px}}</style>
</head><body><div class="card"><h1>Study Buddy — {title}</h1><p>{body}</p></div></body></html>"""


def show_window(url: str = BASE, html: str | None = None,
                on_close=None) -> None:
    import webview
    kwargs = dict(title="Study Buddy — AI Study Assistant", width=1300, height=880,
                  min_size=(940, 640), background_color="#131314")
    if html is not None:
        window = webview.create_window(html=html, **kwargs)
    else:
        window = webview.create_window(url=url, **kwargs)
    if on_close is not None:
        window.events.closed += on_close
    webview.start()
    return window


def main() -> int:
    log("launch")
    ok, msg = check_ollama()
    log(f"ollama ok={ok} ({msg})")
    if not ok:
        show_window(html=error_html(
            "Ollama needed",
            "Study Buddy's AI engine isn't installed yet.<br><br>"
            "1. Install it from <b>https://ollama.com</b> (one time).<br>"
            f"2. Reopen Study Buddy. <span style='color:#888'>({msg})</span>"))
        return 1
    missing = check_models()
    log(f"models missing={missing}")
    if missing:
        show_window(html=error_html(
            "First-run download",
            "Study Buddy needs its AI models (about 9 GB, one time).<br><br>"
            "Open Terminal once and run:<br>"
            f"<code>cd {ROOT} && ./start-app.sh</code><br><br>"
            f"Missing: <b>{', '.join(missing)}</b>"))
        return 1
    ok, msg = ensure_frontend()
    log(f"frontend ok={ok} ({msg})")
    if not ok:
        show_window(html=error_html("UI not built", msg))
        return 1
    if os.environ.get("ARIA_WINDOW_TEST") == "1":
        port, start_own = select_target()
        proc = start_sidecar(port) if start_own else None
        ok = wait_for_health(port)
        if proc is not None:
            stop_sidecar(proc)
        print(f"window-test: port={port} own={start_own}",
              "healthy" if ok else "UNHEALTHY")
        return 0 if ok else 1
    port, start_own = select_target()
    url = f"http://127.0.0.1:{port}"
    log(f"target port={port} own={start_own}")
    if not start_own:
        if serves_ui(port):
            # Single instance: reuse the running server (./start.sh or another
            # window). Closing this window leaves the foreign server alone.
            log("reusing running server")
            show_window(url=url)
            return 0
        show_window(html=error_html(
            "Ports busy",
            "Every port near 8000 is taken by something that isn't Study Buddy. "
            "Quit the other app and reopen Study Buddy."))
        return 1
    t0 = time.time()
    proc = start_sidecar(port)
    if not wait_for_health(port):
        rc = proc.poll()
        log(f"sidecar on {port} silent after {time.time()-t0:.0f}s "
            f"(rc={rc}) — see {server_log_file()} and {APP_LOG}")
        show_window(html=error_html(
            "Backend didn't start",
            "The Study Buddy server didn't answer in 60 s"
            + (f" (exited, code {rc})" if rc is not None else "") + ".<br>"
            f"Details: <code>{server_log_file()}</code>"))
        stop_sidecar(proc)
        return 1
    log(f"server healthy on {port} after {time.time()-t0:.1f}s")

    import webview as _wv

    holder: dict = {}

    def _on_close() -> None:
        stop_sidecar(proc)

    def _watch() -> None:
        watch_sidecar(proc, holder["window"])

    window = _wv.create_window(
        title="Study Buddy — AI Study Assistant", url=url,
        width=1300, height=880, min_size=(940, 640),
        background_color="#131314")
    window.events.closed += _on_close
    holder["window"] = window
    threading.Thread(target=_watch, daemon=True, name="aria-watchdog").start()
    _wv.start()
    # Window closed: make extra sure the sidecar is gone.
    stop_sidecar(proc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
