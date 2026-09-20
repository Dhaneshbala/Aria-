"""Native window shell + settings robustness (hermetic, no window popup)."""
import importlib.util
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "aria_window", str(Path(__file__).parent.parent / "aria_window.py"))
aria_window = importlib.util.module_from_spec(_spec)
sys.modules["aria_window"] = aria_window
_spec.loader.exec_module(aria_window)


def test_error_html_mentions_title():
    html = aria_window.error_html("Ollama needed", "install it")
    assert "Ollama needed" in html and "install it" in html


def test_ensure_frontend_true_when_built():
    ok, _ = aria_window.ensure_frontend()
    assert ok is True  # frontend/dist exists in repo


def _fake_tags(names):
    import io
    import json
    body = io.BytesIO(json.dumps({"models": [{"name": n} for n in names]}).encode())
    class _Resp:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def read(self, *a):
            return body.read()
        status = 200
    return _Resp()


def test_check_models_all_present(monkeypatch):
    # Real-world shape: mxbai carries a registry :latest suffix.
    monkeypatch.setattr(
        aria_window.urllib.request, "urlopen",
        lambda *a, **k: _fake_tags(["gemma4:e4b-mlx", "mxbai-embed-large:latest"]))
    assert aria_window.check_models() == []


def test_check_models_reports_missing(monkeypatch):
    monkeypatch.setattr(
        aria_window.urllib.request, "urlopen",
        lambda *a, **k: _fake_tags(["some-other-model"]))
    missing = aria_window.check_models()
    assert set(missing) == set(aria_window.REQUIRED_MODELS)


def test_check_models_server_down(monkeypatch):
    def _boom(*a, **k):
        raise ConnectionError("down")
    monkeypatch.setattr(aria_window.urllib.request, "urlopen", _boom)
    assert set(aria_window.check_models()) == set(aria_window.REQUIRED_MODELS)


def test_find_bin_sees_usrlocal(monkeypatch):
    # ollama lives in /usr/local/bin here — invisible to a GUI-only PATH,
    # which is exactly what double-clicked apps get.
    monkeypatch.setenv("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")
    assert aria_window.find_bin("ollama") == "/usr/local/bin/ollama"


def _serve(handler, port=0):
    import threading
    from http.server import HTTPServer
    srv = HTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


class _FullARIA(BaseHTTPRequestHandler):
    """Healthy current server: JSON health + HTML UI (like single-server mode)."""
    def do_GET(self):
        import json
        if self.path == "/api/health":
            body = json.dumps({"status": "ok"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
        elif self.path == "/":
            body = b"<html>ARIA</html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
        else:
            body = b'{"detail":"Not found"}'
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class _StaleAPIOnly(BaseHTTPRequestHandler):
    """Pre-single-server backend: health ok, UI 404s (the user's :8000 bug)."""
    def do_GET(self):
        import json
        if self.path == "/api/health":
            body = json.dumps({"status": "ok"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
        else:
            body = b'{"detail":"Not Found"}'
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def test_reuse_detects_full_server():
    srv = _serve(_FullARIA)
    port = srv.server_address[1]
    try:
        assert aria_window.server_already_running(port=port, timeout=2) is True
        assert aria_window.serves_ui(port=port, timeout=2) is True
    finally:
        srv.shutdown()


def test_stale_server_health_ok_ui_missing():
    srv = _serve(_StaleAPIOnly)
    port = srv.server_address[1]
    try:
        assert aria_window.server_already_running(port=port, timeout=2) is True
        assert aria_window.serves_ui(port=port, timeout=2) is False
    finally:
        srv.shutdown()


def test_server_reuse_false_on_empty_port():
    assert aria_window.server_already_running(port=8999, timeout=1) is False
    assert aria_window.serves_ui(port=8999, timeout=1) is False


def test_first_free_port_bindable():
    port = aria_window.first_free_port(8990, tries=5)
    assert port is not None
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", port))  # truly free


def test_select_target_reuses_full_server(monkeypatch):
    srv = _serve(_FullARIA)
    port = srv.server_address[1]
    monkeypatch.setattr(aria_window, "PORT", port)
    try:
        assert aria_window.select_target() == (port, False)
    finally:
        srv.shutdown()


def test_select_target_skips_stale_server(monkeypatch):
    srv = _serve(_StaleAPIOnly)
    port = srv.server_address[1]
    monkeypatch.setattr(aria_window, "PORT", port)
    try:
        got_port, start_own = aria_window.select_target()
        assert start_own is True and got_port != port
    finally:
        srv.shutdown()


def test_settings_ignores_extra_env(monkeypatch):
    """Regression: repo-root .env has keys outside AriaSettings (ARIA_MAIN_MODEL,
    REASONING_MODEL, ...). get_settings() must not crash on them."""
    monkeypatch.setenv("ARIA_MAIN_MODEL", "gemma4:e4b-mlx")
    monkeypatch.setenv("REASONING_MODEL", "x")
    monkeypatch.setenv("STUDENT_NAME", "Test")
    from config.settings import get_settings
    get_settings.cache_clear()
    try:
        s = get_settings()
        assert s.backend_port == 8000
    finally:
        get_settings.cache_clear()


class _FakeProc:
    def __init__(self, rc=1):
        self._rc = rc
        self.terminated = False
        self.killed = False

    def poll(self):
        return self._rc

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return self._rc

    def kill(self):
        self.killed = True


def test_build_server_cmd_localhost():
    import sys
    cmd = aria_window.build_server_cmd(8001)
    assert cmd[:5] == ["arch", "-arm64", sys.executable, "-m", "uvicorn"]
    assert "--port" in cmd and "8001" in cmd
    assert "127.0.0.1" in cmd
    assert "0.0.0.0" not in cmd  # never expose (agent can run shell)


def test_launcher_forces_native_arch():
    src = (aria_window.ROOT / "build-app.sh").read_text()
    assert "arch -arm64" in src
    assert "LSRequiresNativeExecution" in src


def test_stop_sidecar_terminates():
    proc = _FakeProc()
    aria_window.stop_sidecar(proc)
    assert proc.terminated is True


def test_watchdog_notifies_window_on_exit(monkeypatch):
    import time as _t
    _real_sleep = _t.sleep
    monkeypatch.setattr(aria_window.time, "sleep", lambda s: _real_sleep(0.01))
    seen = {}

    class _Win:
        def load_html(self, html):
            seen["html"] = html

    aria_window.watch_sidecar(_FakeProc(rc=3), _Win())
    assert "Server stopped" in seen["html"]
    assert "aria-server.log" in seen["html"]
