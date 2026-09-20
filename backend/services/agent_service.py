"""
Agent service — tool calling framework for autonomous actions.
Supports: terminal commands, file operations, web browsing.
All actions require confirmation for safety.
"""
import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class AgentService:

    def __init__(self):
        self._pending_confirmations = {}
        # Jail: only allow file ops inside DATA_DIR or the Study Buddy project root.
        # (Not cwd: Finder-launched apps start with cwd=/, which would jail
        # nothing. Repo root is the stable equivalent of "the project".)
        _repo_root = Path(__file__).resolve().parents[1]
        try:
            from models.database import DATA_DIR as _DD
            self._allowed_roots = [Path(_DD).resolve(), _repo_root.resolve()]
            # Writes are DATA_DIR-only — never backend code. A mistaken or
            # injected write to backend/*.py would survive restarts.
            self._writable_roots = [Path(_DD).resolve()]
        except Exception:
            self._allowed_roots = [_repo_root.resolve()]
            self._writable_roots = [_repo_root.resolve()]

    def _is_jailed(self, path: str) -> bool:
        try:
            p = Path(path).resolve()
            return any(p == root or p.is_relative_to(root) for root in self._allowed_roots)
        except Exception:
            return False

    def _is_writable(self, path: str) -> bool:
        """Writes are DATA_DIR-only. Reads/list/search may use the wider jail
        (DATA_DIR + project root), but writes must never touch backend code —
        a compromised/mistaken write to backend/*.py survives restarts."""
        try:
            p = Path(path).resolve()
            return any(p == root or p.is_relative_to(root) for root in self._writable_roots)
        except Exception:
            return False

    # Denylist: substring match on lowered command. Deliberately broad —
    # denylists can't be complete, so this is a tripwire, not a sandbox.
    # Local-only bind (127.0.0.1) is the real boundary; see main.py.
    BLOCKED_SUBSTRINGS = (
        # destructive filesystem (any rm -rf, not just /)
        'rm -rf', 'rm -r', 'rmdir', 'mkfs', 'dd if=', 'dd of=',
        'chmod -r 777', 'chmod -R 777', ':(){', 'fork bomb',
        'mv /', 'cp /etc', '/etc/passwd', '/etc/shadow',
        # interpreters that trivially bypass string matching
        'python -c', 'python3 -c', 'python -m', 'python3 -m',
        'bash -c', 'sh -c', 'zsh -c', 'perl ', 'perl -', 'ruby ',
        'ruby -', 'node -e', 'php -r', 'os.system', 'import subprocess',
        'subprocess.', 'subprocess(',
        # network exfil / remote execution
        'curl', 'wget', '| sh', '| bash', '| zsh', 'nc -', 'nc.', 'ncat',
        'socat', 'nmap', 'ssh ', 'scp ', 'ftp ', 'telnet',
        'shutdown', 'reboot', 'halt', 'poweroff',
        '.ssh', 'authorized_keys',
    )

    # Cap captured output so `cat hugefile` can't OOM the backend.
    MAX_OUTPUT_CHARS = 100_000

    async def execute_terminal(self, command: str, cwd: Optional[str] = None, timeout: int = 30) -> dict:
        """Execute a terminal command with safety timeout."""
        lower = command.lower()
        if any(d in lower for d in self.BLOCKED_SUBSTRINGS):
            return {"error": "Command blocked for safety", "command": command}
        if cwd and not self._is_jailed(cwd):
            return {"error": f"Working directory not allowed: {cwd}"}

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd or os.getcwd(),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            out = stdout.decode(errors="replace")
            err = stderr.decode(errors="replace")
            truncated = False
            if len(out) > self.MAX_OUTPUT_CHARS:
                out = out[:self.MAX_OUTPUT_CHARS] + "\n…[truncated: output exceeded 100k chars]"
                truncated = True
            if len(err) > self.MAX_OUTPUT_CHARS:
                err = err[:self.MAX_OUTPUT_CHARS] + "\n…[truncated]"
                truncated = True
            return {
                "stdout": out,
                "stderr": err,
                "returncode": proc.returncode,
                "command": command,
                "truncated": truncated,
            }
        except asyncio.TimeoutError:
            proc.kill()
            return {"error": f"Command timed out after {timeout}s", "command": command}
        except Exception as e:
            return {"error": str(e), "command": command}

    async def read_file(self, path: str, max_chars: int = 50000) -> dict:
        """Read a file's contents."""
        try:
            p = Path(path).resolve()
            if not self._is_jailed(str(p)):
                return {"error": f"Path not allowed: {path}"}
            if not p.exists():
                return {"error": f"File not found: {path}"}
            if p.stat().st_size > max_chars * 4:
                return {"error": "File too large to read in full"}
            content = p.read_text(errors="replace")[:max_chars]
            return {"content": content, "path": str(p), "size": p.stat().st_size}
        except Exception as e:
            return {"error": str(e)}

    async def write_file(self, path: str, content: str) -> dict:
        """Write content to a file (DATA_DIR only — never backend code)."""
        try:
            p = Path(path).resolve()
            if not self._is_writable(str(p)):
                return {"error": f"Path not allowed for writes (DATA_DIR only): {path}"}
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return {"path": str(p), "size": len(content), "success": True}
        except Exception as e:
            return {"error": str(e)}

    async def list_directory(self, path: str = ".", max_items: int = 50) -> dict:
        """List directory contents."""
        try:
            p = Path(path).resolve()
            if not self._is_jailed(str(p)):
                return {"error": f"Path not allowed: {path}"}
            if not p.is_dir():
                return {"error": f"Not a directory: {path}"}
            items = []
            for i, item in enumerate(sorted(p.iterdir())):
                if i >= max_items:
                    break
                items.append({
                    "name": item.name,
                    "type": "dir" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else 0,
                })
            return {"path": str(p), "items": items, "count": len(items)}
        except Exception as e:
            return {"error": str(e)}

    async def search_files(self, pattern: str, path: str = ".", max_results: int = 20) -> dict:
        """Search for files matching a pattern."""
        try:
            p = Path(path).resolve()
            if not self._is_jailed(str(p)):
                return {"error": f"Path not allowed: {path}"}
            # Block glob patterns that could escape jail
            if ".." in pattern or pattern.startswith("/"):
                return {"error": "Pattern not allowed"}
            matches = []
            for item in p.rglob(pattern):
                if not self._is_jailed(str(item)):
                    continue
                if len(matches) >= max_results:
                    break
                matches.append({"path": str(item), "type": "dir" if item.is_dir() else "file"})
            return {"matches": matches, "count": len(matches)}
        except Exception as e:
            return {"error": str(e)}
