"""Ré-exports de compat v1 (`from tableforge.providers import SeedreamProvider`…).

Shim de compat : à supprimer quand examples/ et le starter n'utilisent plus le
format v1 — revoir 2026-10.
"""
from .seedream import (DEFAULT_SEQUENTIAL, SeedreamProvider, _save_image,
                       build_request, summarize_request)

__all__ = ["DEFAULT_SEQUENTIAL", "SeedreamProvider", "_save_image",
           "build_request", "summarize_request"]
