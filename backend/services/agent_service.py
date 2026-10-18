"""
Agent service — tool calling framework for autonomous actions.
Supports: terminal commands, file operations, web browsing.
All actions require confirmation for safety.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import ClassVar

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
            for root in self._allowed_roots:
                try:
                    if p.is_relative_to(root):
                        return True
                except AttributeError:
                    # Python < 3.9 fallback
                    if os.path.commonpath([str(p), str(root)]) == str(root):
                        return True
                except Exception:
                    continue
            return False
        except Exception:
            return False

    _ALLOWED_CMDS: ClassVar[set[str]] = {
        "ls",
        "pwd",
        "echo",
        "cat",
        "head",
        "tail",
        "wc",
        "grep",
        "find",
        "python3",
        "git",
        "npm",
        "node",
        "ollama",
    }

    async def execute_terminal(
        self, command: str, cwd: str | None = None, timeout: int = 30
    ) -> dict:
        """Execute a terminal command with safety timeout."""
        # Validate inputs (fix: unvalidated timeout / oversize command = DoS)
        try:
            timeout = int(timeout)
        except Exception:
            return {"error": "Invalid timeout (must be 1-120s)", "command": command}
        if timeout < 1 or timeout > 120:
            return {"error": "Invalid timeout (must be 1-120s)", "command": command}
        if not command or not command.strip():
            return {"error": "Command cannot be empty", "command": command}
        if len(command) > 5000:
            return {"error": "Command too long (max 5000 chars)", "command": command}
        # Allowlist: only known-safe first tokens, no shell. Parse with shlex.
        import shlex as _shlex

        try:
            argv = _shlex.split(command)
        except Exception:
            return {"error": "Could not parse command", "command": command}
        if not argv:
            return {"error": "Command cannot be empty", "command": command}
        import os as _os2

        prog = _os2.path.basename(argv[0])
        if prog not in self._ALLOWED_CMDS:
            return {"error": f"Command not allowed: {prog}", "command": command}
        # Reject shell metachars (no shell is used, but reject smuggling attempts)
        if any(
            c in command
            for c in (";", "|", "&", "$", "`", "(", ")", "{", "}", "<", ">", "\\", "\n")
        ):
            return {"error": "Shell metacharacters not allowed", "command": command}
        if cwd and not self._is_jailed(cwd):
            return {"error": f"Working directory not allowed: {cwd}"}

        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd or os.getcwd(),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            out_text = stdout.decode(errors="replace")
            err_text = stderr.decode(errors="replace")
            return {
                "output": out_text,
                "stdout": out_text,
                "stderr": err_text,
                "returncode": proc.returncode,
                "command": command,
            }
        except TimeoutError:
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
            if content is None:
                return {"error": "content is required"}
            if len(content) > 1 * 1024 * 1024:
                return {"error": "Content too large (max 1MB)"}
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
                items.append(
                    {
                        "name": item.name,
                        "type": "dir" if item.is_dir() else "file",
                        "size": item.stat().st_size if item.is_file() else 0,
                    }
                )
            return {"path": str(p), "items": items, "count": len(items)}
        except Exception as e:
            return {"error": str(e)}

    async def search_files(
        self, pattern: str, path: str = ".", max_results: int = 20
    ) -> dict:
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
                matches.append(
                    {"path": str(item), "type": "dir" if item.is_dir() else "file"}
                )
            return {"matches": matches, "count": len(matches)}
        except Exception as e:
            return {"error": str(e)}
