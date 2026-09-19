"""Typed configuration for ARIA backend.

Provides Pydantic-validated settings loaded from environment variables
and the persistent config file. Replaces scattered magic numbers and
ad-hoc os.environ.get() calls throughout the codebase.
"""

from .settings import AriaSettings, get_settings

__all__ = ["AriaSettings", "get_settings"]
