"""Shared API schemas — single source of truth for $100k-grade consistency.

All routers should return errors in the unified envelope:
    {"detail": {"type": "...", "message": "...", "hint": "..."}}

This lets the frontend show one premium toast instead of 18 ad-hoc formats.
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    type: Literal["validation", "not_found", "too_large", "rate_limited", "friendly", "upstream"] = Field(
        default="friendly", description="Machine-readable error class"
    )
    message: str = Field(..., max_length=500, description="Human-readable message")
    hint: str = Field(default="", max_length=500, description="What the user can do next")


class ApiError(BaseModel):
    detail: ErrorDetail


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
    ollama: bool
    disk_free_gb: float
    data_dir: str


class ReadyResponse(BaseModel):
    ready: bool
    checks: dict[str, Any]


def error_envelope(
    message: str,
    *,
    type: str = "friendly",
    hint: str = "",
) -> dict[str, Any]:
    """Build the unified error body without raising (for SSE / manual returns)."""
    # Validate through pydantic so shape can never drift.
    return ApiError(
        detail=ErrorDetail(type=type, message=message[:500], hint=hint[:500])  # type: ignore[arg-type]
    ).model_dump()
