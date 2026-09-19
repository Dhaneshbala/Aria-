"""Agent router — tool calling endpoints for autonomous actions."""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional
from services.agent_service import AgentService

router = APIRouter(prefix="/api/agent", tags=["agent"])
agent_svc = AgentService()


class TerminalRequest(BaseModel):
    command: str = Field(..., min_length=1, max_length=5000)
    cwd: Optional[str] = Field(default=None, max_length=500)
    timeout: int = Field(default=30, ge=1, le=300)


class FileRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=1000)
    content: Optional[str] = Field(default=None, max_length=1000000)


class SearchRequest(BaseModel):
    pattern: str = Field(..., min_length=1, max_length=500)
    path: str = Field(default=".", max_length=500)


@router.post("/terminal")
async def execute_terminal(req: TerminalRequest):
    return await agent_svc.execute_terminal(req.command, req.cwd, req.timeout)


@router.post("/read-file")
async def read_file(req: FileRequest):
    return await agent_svc.read_file(req.path)


@router.post("/write-file")
async def write_file(req: FileRequest):
    if not req.content:
        return {"error": "content is required"}
    return await agent_svc.write_file(req.path, req.content)


@router.post("/list-directory")
async def list_directory(req: FileRequest):
    return await agent_svc.list_directory(req.path)


@router.post("/search-files")
async def search_files(req: SearchRequest):
    return await agent_svc.search_files(req.pattern, req.path)
