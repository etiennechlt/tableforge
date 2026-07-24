"""Contrat provider : AssetJob, Protocol plan/execute, résolution du provider d'un kind.

`plan()` est pur et sans clé API ; `execute()` est le seul point réseau. L'adaptateur
legacy enveloppe les objets duck-typés v1 (.build/.generate) — dont les FakeProvider
des tests — pour que `generate_kind` n'ait qu'un seul chemin.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

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
    """Nom du provider d'un kind : `with:` explicite, `manual` réservé, sinon
    auto-résolution si exactement un provider déclaré sait produire l'asset."""
    asset = kind_cfg.asset
    with_ = kind_cfg.generate.with_ if kind_cfg.generate else None
    if with_ == "manual":
        return "manual"
    if with_ is not None:
        if with_ not in project.providers:
            declared = ", ".join(project.providers) or "aucun"
            raise ValueError(
                f"kind '{kind_cfg.name}' : provider '{with_}' inconnu (déclarés : {declared})")
        provider_type = project.providers[with_].type
        if asset not in SUPPORTED_ASSETS[provider_type]:
            raise ValueError(
                f"kind '{kind_cfg.name}' : le provider '{with_}' (type {provider_type}) "
                f"ne sait pas générer l'asset '{asset}'")
        return with_
    candidates = [name for name, cfg in project.providers.items()
                  if asset in SUPPORTED_ASSETS[cfg.type]]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise ValueError(
            f"kind '{kind_cfg.name}' : aucun provider déclaré ne sait générer "
            f"l'asset '{asset}' — déclare-en un dans providers: ou utilise "
            "generate: {with: manual}")
    raise ValueError(
        f"kind '{kind_cfg.name}' : plusieurs providers savent générer '{asset}' "
        f"({', '.join(candidates)}) — précise generate: {{with: …}}")


class MusicOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    length_ms: Optional[int] = None


class SfxOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    duration_s: Optional[float] = None
    loop: Optional[bool] = None


_OPTION_MODELS: dict[tuple[str, str], type[BaseModel]] = {
    ("elevenlabs", "music"): MusicOptions,
    ("elevenlabs", "sfx"): SfxOptions,
}


def options_model(provider_type: str, asset: str) -> Optional[type[BaseModel]]:
    return _OPTION_MODELS.get((provider_type, asset))


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
