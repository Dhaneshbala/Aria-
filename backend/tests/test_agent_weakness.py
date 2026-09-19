"""P0 weakness fixes: agent shell bypasses + write jail + output cap (hermetic)."""
import pytest
from services.agent_service import AgentService


@pytest.fixture
def svc():
    return AgentService()


async def test_python_c_blocked(svc):
    r = await svc.execute_terminal("python3 -c 'import os; print(1)'")
    assert r.get("error") == "Command blocked for safety"


async def test_bash_c_blocked(svc):
    r = await svc.execute_terminal("bash -c 'echo hi'")
    assert "error" in r


async def test_rm_rf_home_blocked(svc):
    r = await svc.execute_terminal("rm -rf ~")
    assert "error" in r


async def test_rm_rf_dot_blocked(svc):
    r = await svc.execute_terminal("rm -rf .")
    assert "error" in r


async def test_subprocess_import_blocked(svc):
    r = await svc.execute_terminal("grep -r 'import subprocess' .", timeout=10)
    assert "error" in r  # tripwire is broad by design


async def test_safe_command_passes(svc):
    r = await svc.execute_terminal("echo hello", timeout=10)
    assert r.get("stdout", "").strip() == "hello"


async def test_output_capped(svc):
    r = await svc.execute_terminal("seq 1 200000", timeout=15)
    assert len(r.get("stdout", "")) <= 100_050
    assert r.get("truncated") is True


async def test_write_outside_data_dir_blocked(svc, tmp_path):
    outside = str(tmp_path / "evil.txt")
    r = await svc.write_file(outside, "x")
    assert "DATA_DIR only" in r.get("error", "")


async def test_write_backend_code_blocked(svc):
    import pathlib
    backend_file = str(pathlib.Path("services/agent_service.py").resolve())
    r = await svc.write_file(backend_file, "pwned")
    assert "DATA_DIR only" in r.get("error", "")


async def test_write_inside_data_dir_ok(svc, tmp_path):
    from pathlib import Path
    svc._writable_roots = [Path(tmp_path)]
    target = str(tmp_path / "note.txt")
    r = await svc.write_file(target, "hello")
    assert r.get("success") is True
