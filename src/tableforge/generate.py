"""Orchestration de la génération (toutes modalités) via le contrat plan/execute."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .config import ProjectConfig
from .providers.base import ensure_provider, provider_for
from .targets import build_kind_spec


@dataclass(frozen=True)
class GenerateResult:
    id: str
    dest: Optional[Path]
    request: dict


def generate_kind(project: ProjectConfig, kind: str, ids: Optional[list[str]] = None,
                  dry_run: bool = False, force: bool = False,
                  provider=None) -> list[GenerateResult]:
    spec = build_kind_spec(project, kind, ids)
    if provider is not None:
        provider = ensure_provider(provider)
    else:
        provider = provider_for(project, project.kind(kind))

    results: list[GenerateResult] = []
    for job in provider.plan(spec):
        if dry_run:
            results.append(GenerateResult(job.id, None, job.request))
            continue
        if job.dest.exists() and not force:
            results.append(GenerateResult(job.id, job.dest, {"skipped": "exists"}))
            continue
        provider.execute(job)
        results.append(GenerateResult(job.id, job.dest, job.request))
    return results
