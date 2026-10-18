"""Agent router — tool calling endpoints for autonomous actions."""

import os

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from services.agent_service import AgentService

router = APIRouter(prefix="/api/agent", tags=["agent"])
agent_svc = AgentService()

MAX_COMMAND_CHARS = 5000
MAX_WRITE_CHARS = 1 * 1024 * 1024  # 1MB


def _is_loopback_host(host: str) -> bool:
    """True for loopback callers (frontend proxy runs on loopback).

    Covers 127.0.0.0/8 + ::1 via is_loopback, plus local aliases the app
    itself uses ("localhost") and Starlette's TestClient ("testclient").
    Empty/unknown host is treated as local (preserves existing UX/tests).
    """
    if not host or host in ("localhost", "testclient"):
        return True
    try:
        import ipaddress

        return ipaddress.ip_address(host).is_loopback
    except Exception:
        return False


def _check_agent_auth(request: Request):
    """Shared-token auth + loopback-only when no token is configured.

    Local-only app has no user accounts. If ARIA_AGENT_TOKEN is set,
    require it via X-Agent-Token header (even from loopback). Otherwise
    allow loopback callers only — reject any known non-loopback host.

    Drive-by protection: also require header X-Agent-Request: 1. Custom
    headers cannot be sent by cross-origin form posts or fetch(mode:'no-cors')
    without a CORS preflight, and ARIA's CORS allow-list is localhost-only —
    so a malicious website can never trigger terminal/file commands.
    """
    if request.headers.get("x-agent-request", "") != "1":
        raise HTTPException(403, "Agent API requires X-Agent-Request: 1 header")
    expected = os.environ.get("ARIA_AGENT_TOKEN", "")
    try:
        host = request.client.host if request.client else ""
    except Exception:
        host = ""
    if expected:
        provided = request.headers.get("X-Agent-Token", "")
        if provided != expected:
            raise HTTPException(403, "Agent API requires valid X-Agent-Token")
        if host and not _is_loopback_host(host):
            raise HTTPException(
                403, f"Agent API is local-only (blocked remote host {host})"
            )
    else:
        if host and not _is_loopback_host(host):
            raise HTTPException(
                403, f"Agent API is local-only (blocked remote host {host})"
            )


class TerminalRequest(BaseModel):
    command: str = Field(min_length=1, max_length=MAX_COMMAND_CHARS)
    cwd: str | None = None
    timeout: int = Field(default=30, ge=1, le=120)


class FileRequest(BaseModel):
    path: str
    content: str | None = None


class SearchRequest(BaseModel):
    pattern: str
    path: str = "."


@router.post("/terminal")
async def execute_terminal(req: TerminalRequest, request: Request):
    _check_agent_auth(request)
    return await agent_svc.execute_terminal(req.command, req.cwd, req.timeout)


@router.post("/read-file")
async def read_file(req: FileRequest, request: Request):
    _check_agent_auth(request)
    return await agent_svc.read_file(req.path)


@router.post("/write-file")
async def write_file(req: FileRequest, request: Request):
    _check_agent_auth(request)
    if not req.content:
        return {"error": "content is required"}
    if len(req.content) > MAX_WRITE_CHARS:
        raise HTTPException(413, "Content too large (max 1MB)")
    return await agent_svc.write_file(req.path, req.content)


@router.post("/list-directory")
async def list_directory(req: FileRequest, request: Request):
    _check_agent_auth(request)
    return await agent_svc.list_directory(req.path)


@router.post("/search-files")
async def search_files(req: SearchRequest, request: Request):
    _check_agent_auth(request)
    return await agent_svc.search_files(req.pattern, req.path)
