"""Contrat provider : AssetJob, Protocol plan/execute, résolution du provider d'un kind.

`plan()` est pur et sans clé API ; `execute()` est le seul point réseau. L'adaptateur
legacy enveloppe les objets duck-typés v1 (.build/.generate) — dont les FakeProvider
des tests — pour que `generate_kind` n'ait qu'un seul chemin.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from ..config import KindConfig, ProjectConfig
from ..paths import asset_path

if TYPE_CHECKING:  # pas d'import runtime : targets importe providers.base
    from ..targets import KindSpec

SUPPORTED_ASSETS: dict[str, frozenset[str]] = {
    "seedream": frozenset({"image"}),
    "elevenlabs": frozenset({"music", "sfx", "tts", "dialogue"}),
    "higgsfield": frozenset({"image", "video"}),
    "manual": frozenset({"image", "music", "sfx", "tts", "dialogue", "video"}),
}


@dataclass(frozen=True)
class AssetJob:
    id: str
    dest: Path
    request: dict
    payload: dict = field(default_factory=dict)
    notes: tuple[str, ...] = ()


@runtime_checkable
class Provider(Protocol):
    def plan(self, spec: "KindSpec") -> list[AssetJob]: ...

    def execute(self, job: AssetJob) -> list[Path]: ...


def resolve_provider_name(project: ProjectConfig, kind_cfg: KindConfig) -> str:
    explicit = kind_cfg.generate.with_ if kind_cfg.generate else None
    if explicit is not None:
        if explicit == "manual":
            return "manual"
        if explicit not in project.providers:
            raise ValueError(
                f"kind '{kind_cfg.name}' : provider '{explicit}' inconnu "
                f"(déclarés : {', '.join(project.providers) or 'aucun'})")
        return explicit
    candidates = sorted(name for name, cfg in project.providers.items()
                        if kind_cfg.asset in SUPPORTED_ASSETS[cfg.type])
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise ValueError(
            f"kind '{kind_cfg.name}' : aucun provider déclaré ne sait produire "
            f"l'asset '{kind_cfg.asset}' — ajoute un provider adapté ou "
            "'generate: {with: manual}'")
    raise ValueError(
        f"kind '{kind_cfg.name}' : plusieurs providers possibles pour l'asset "
        f"'{kind_cfg.asset}' ({', '.join(candidates)}) — précise 'generate: {{with: …}}'")


class _LegacyAdapter:
    """Adapte un objet duck-typé v1 (.build/.generate) au contrat plan/execute."""

    def __init__(self, legacy):
        self._legacy = legacy

    def plan(self, spec: "KindSpec") -> list[AssetJob]:
        from .seedream import summarize_request
        jobs = []
        for target in spec.targets:
            size = target.settings.get("size")
            refs = list(target.refs)
            request = summarize_request(self._legacy.build(target.text, size, refs))
            dest = asset_path(spec.root, spec.asset, spec.kind, target.id,
                              spec.output_format)
            jobs.append(AssetJob(id=target.id, dest=dest, request=request,
                                 payload={"prompt": target.text, "size": size,
                                          "refs": refs},
                                 notes=tuple(target.notes)))
        return jobs

    def execute(self, job: AssetJob) -> list[Path]:
        return self._legacy.generate(job.payload["prompt"], job.dest,
                                     size=job.payload.get("size"),
                                     refs=job.payload.get("refs") or None)


def ensure_provider(obj) -> Provider:
    if hasattr(obj, "plan") and hasattr(obj, "execute"):
        return obj
    return _LegacyAdapter(obj)


def provider_for(project: ProjectConfig, kind_cfg: KindConfig) -> Provider:
    name = resolve_provider_name(project, kind_cfg)
    if name == "manual":
        raise NotImplementedError(
            "provider 'manual' : disponible en P1 (forge studio)")
    cfg = project.providers[name]
    if cfg.type == "seedream":
        from .seedream import SeedreamProvider
        return SeedreamProvider.from_provider_config(cfg)
    raise NotImplementedError(
        f"provider de type '{cfg.type}' : pas encore implémenté (phases P1+)")
