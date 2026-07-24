"""Package providers — ré-exports de compatibilité v1 (à revoir 2026-10)."""
from .seedream import (DEFAULT_SEQUENTIAL, SeedreamProvider, _save_image,
                       build_request, summarize_request)

__all__ = ["DEFAULT_SEQUENTIAL", "SeedreamProvider", "_save_image",
           "build_request", "summarize_request"]
