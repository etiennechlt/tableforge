"""Contrat provider : AssetJob, Protocol plan/execute, résolution du provider d'un kind.

`plan()` est pur et sans clé API ; `execute()` est le seul point réseau. L'adaptateur
legacy enveloppe les objets duck-typés v1 (.build/.generate) — dont les FakeProvider
des tests — pour que `generate_kind` n'ait qu'un seul chemin.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, ValidationError

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
    candidates = sorted(name for name, cfg in project.providers.items()
                        if asset in SUPPORTED_ASSETS[cfg.type])
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


class ElevenLabsTtsOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    voice: Optional[str] = None
    voice_field: Optional[str] = None
    text: Optional[str] = None
    model: Optional[str] = None
    language: Optional[str] = None
    seed: Optional[int] = None


class ElevenLabsDialogueOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: Optional[str] = None


_OPTION_MODELS: dict[tuple[str, str], type[BaseModel]] = {
    ("elevenlabs", "music"): MusicOptions,
    ("elevenlabs", "sfx"): SfxOptions,
    ("elevenlabs", "tts"): ElevenLabsTtsOptions,
    ("elevenlabs", "dialogue"): ElevenLabsDialogueOptions,
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


def _seedream_provider(cfg) -> Provider:
    from .seedream import SeedreamProvider
    return SeedreamProvider.from_provider_config(cfg)


def _elevenlabs_provider(cfg) -> Provider:
    from .elevenlabs import ElevenLabsProvider
    return ElevenLabsProvider.from_config(cfg)


# Registre {type de provider: factory}. Ajouter un provider = une entrée ici,
# pas une branche if/elif de plus — chaque factory importe localement pour
# éviter tout cycle d'import au chargement du package (providers/__init__.py
# reste léger, sans import eager d'elevenlabs/manual/seedream).
_PROVIDER_FACTORIES: dict[str, Callable[..., Provider]] = {
    "seedream": _seedream_provider,
    "elevenlabs": _elevenlabs_provider,
}


def provider_for(project: ProjectConfig, kind_cfg: KindConfig) -> Provider:
    """Instancie le provider d'un kind via `_PROVIDER_FACTORIES` (registre par
    type). `manual` reste un cas à part : c'est un nom réservé, jamais une
    entrée de `project.providers` (cf. `_normalize_providers`), donc il n'a
    pas de `cfg.type` sur lequel indexer le registre."""
    name = resolve_provider_name(project, kind_cfg)
    if name == "manual":
        from .manual import ManualProvider
        return ManualProvider()
    cfg = project.providers[name]
    factory = _PROVIDER_FACTORIES.get(cfg.type)
    if factory is None:
        raise ValueError(
            f"provider '{name}' : type '{cfg.type}' pas encore pris en charge "
            "pour la génération (higgsfield arrive en P3)")
    return factory(cfg)


def validate_project(project: ProjectConfig) -> list[str]:
    """Linter de forge.yaml : liste de problèmes en français (vide si tout est bon)."""
    issues: list[str] = []
    for name, kind_cfg in project.kinds.items():
        issues.extend(_kind_issues(project, name, kind_cfg))
    issues.extend(_voice_resolution_issues(project))
    # _kind_issues et _voice_resolution_issues rejouent toutes deux
    # resolve_provider_name (directement / via build_kind_spec) : un kind
    # tts/dialogue avec un provider invalide produit le même message deux
    # fois. dict.fromkeys préserve l'ordre et déduplique sans coupler les
    # deux passes.
    return list(dict.fromkeys(issues))


def _voice_resolution_issues(project: ProjectConfig) -> list[str]:
    """Détecte les voix inconnues où qu'elles soient déclarées (generate.voice,
    entrée de catalogue, row via voice_field...) en rejouant build_kind_spec
    pour chaque kind tts/dialogue — profite ainsi de toute la logique de
    résolution des Tasks 2-4. Import local : targets importe providers.base
    au chargement du module, un import en tête de fichier créerait un cycle."""
    from ..targets import build_kind_spec

    issues: list[str] = []
    for name, kind_cfg in project.kinds.items():
        if kind_cfg.asset not in ("tts", "dialogue"):
            continue
        try:
            build_kind_spec(project, name)
        except (KeyError, ValueError, FileNotFoundError) as exc:
            # Les messages de targets.py incluent déjà "kind '<name>' : ..." —
            # même convention que le except ValueError plus haut : pas de
            # double préfixe.
            message = exc.args[0] if exc.args else str(exc)
            issues.append(message)
    return issues


def _kind_issues(project: ProjectConfig, name: str, kind_cfg: KindConfig) -> list[str]:
    issues: list[str] = []
    if kind_cfg.sheet is not None and kind_cfg.asset != "image":
        issues.append(f"kind '{name}' : bloc 'sheet' sur un asset {kind_cfg.asset} "
                      "(réservé aux kinds image)")
    if kind_cfg.from_ is not None:
        source = project.kinds.get(kind_cfg.from_)
        if source is None:
            issues.append(f"kind '{name}' : from: '{kind_cfg.from_}' ne désigne "
                          "aucun kind déclaré")
        elif source.asset != "image":
            issues.append(f"kind '{name}' : from: '{kind_cfg.from_}' doit être un kind "
                          f"image (trouvé : {source.asset})")
    if kind_cfg.generate is None:
        return issues
    try:
        provider_name = resolve_provider_name(project, kind_cfg)
    except ValueError as exc:
        issues.append(str(exc))
        return issues
    provider_type = ("manual" if provider_name == "manual"
                     else project.providers[provider_name].type)
    extras = kind_cfg.generate.extras()
    voice = extras.get("voice")
    if isinstance(voice, str) and voice not in project.voices:
        declared = ", ".join(project.voices) or "aucune"
        issues.append(f"kind '{name}' : voix '{voice}' inconnue (déclarées : {declared})")
    model = options_model(provider_type, kind_cfg.asset)
    if model is not None:
        try:
            model(**extras)
        except ValidationError:
            accepted = ", ".join(model.model_fields) or "aucune"
            issues.append(f"kind '{name}' : options generate: invalides pour "
                          f"{provider_type}/{kind_cfg.asset} (clés acceptées : {accepted})")
    return issues
