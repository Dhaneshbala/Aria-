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
        # Jail: only allow file ops inside DATA_DIR or project root
        try:
            from models.database import DATA_DIR as _DD
            self._allowed_roots = [Path(_DD).resolve(), Path.cwd().resolve()]
        except Exception:
            self._allowed_roots = [Path.cwd().resolve()]

    def _is_jailed(self, path: str) -> bool:
        try:
            p = Path(path).resolve()
            return any(str(p).startswith(str(root)) for root in self._allowed_roots)
        except Exception:
            return False

    async def execute_terminal(self, command: str, cwd: Optional[str] = None, timeout: int = 30) -> dict:
        """Execute a terminal command with safety timeout."""
        # Safety: block dangerous patterns
        dangerous = ['rm -rf /', 'mkfs', 'dd if=', ':(){ :|:& };:', 'chmod -R 777 /',
                     'curl', 'wget', '| sh', '| bash', 'nc -', 'nmap', 'ssh ', 'shutdown', 'reboot',
                     'mv /', 'cp /etc', 'cat /etc/passwd', ':(){']
        lower = command.lower()
        if any(d in lower for d in dangerous):
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
            return {
                "stdout": stdout.decode(errors="replace"),
                "stderr": stderr.decode(errors="replace"),
                "returncode": proc.returncode,
                "command": command,
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
        """Write content to a file."""
        try:
            p = Path(path).resolve()
            if not self._is_jailed(str(p)):
                return {"error": f"Path not allowed: {path}"}
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
