"""Provider réservé `manual` : plan des fiches, exécution refusée (→ forge studio)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ..paths import asset_path
from .base import AssetJob

if TYPE_CHECKING:  # pragma: no cover
    from ..targets import KindSpec


@dataclass(frozen=True)
class ManualProvider:
    def plan(self, spec: "KindSpec") -> list[AssetJob]:
        jobs: list[AssetJob] = []
        for target in spec.targets:
            dest = asset_path(spec.root, spec.asset, spec.kind, target.id,
                              spec.output_format)
            jobs.append(AssetJob(
                id=target.id, dest=dest,
                request={"manual": True, "prompt": target.text,
                         "settings": dict(target.settings)},
                payload={"kind": spec.kind},
                notes=target.notes))
        return jobs

    def execute(self, job: AssetJob) -> list[Path]:
        kind = job.payload.get("kind", "?")
        raise RuntimeError(
            f"provider manuel : lance `forge studio {kind}` "
            f"puis dépose le fichier à {job.dest}")
