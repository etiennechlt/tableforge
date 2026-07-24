"""Résolution des cibles d'un kind (pur, sans clé API ni réseau).

`build_kind_spec` transforme la config + les fichiers data/prompts en un `KindSpec`
immuable que les providers consomment (`plan`). Assets image/music/sfx implémentés
ici ; tts/dialogue arrivent en P2, video en P3.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .catalog import (DEFAULT_MUSIC_LENGTH_MS, MUSIC_MAX_MS, MUSIC_MIN_MS,
                      SFX_MAX_S, SFX_MIN_S, catalog_entries, clamp_music_length_ms,
                      clamp_sfx_duration_s, get_entry, load_catalog, prompt_for_entry)
from .config import KindConfig, ProjectConfig
from .prompts import load_prompts, prompt_for, reference_data_urls
from .providers.base import resolve_provider_name


@dataclass(frozen=True)
class DialogueLine:
    voice_id: str
    text: str


@dataclass(frozen=True)
class Target:
    id: str
    text: str
    voice_id: Optional[str] = None
    lines: tuple[DialogueLine, ...] = ()
    source_image: Optional[Path] = None
    settings: dict = field(default_factory=dict)
    refs: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class KindSpec:
    kind: str
    asset: str
    provider_name: str
    options: dict
    targets: tuple[Target, ...]
    root: Path
    output_format: Optional[str] = None


def build_kind_spec(project: ProjectConfig, kind: str,
                    ids: Optional[list[str]] = None) -> KindSpec:
    kind_cfg = project.kind(kind)
    provider_name = resolve_provider_name(project, kind_cfg)
    provider_cfg = project.providers.get(provider_name)  # None si 'manual'
    options = kind_cfg.generate.extras() if kind_cfg.generate else {}
    if kind_cfg.asset in ("music", "sfx"):
        return _audio_spec(project, kind_cfg, ids)
    if kind_cfg.asset == "image":
        targets = _image_targets(project, kind_cfg, provider_cfg, ids)
        output_format = getattr(provider_cfg, "output_format", None)
    else:
        raise NotImplementedError(
            f"asset '{kind_cfg.asset}' : pas encore implémenté "
            "(tts/dialogue : P2 ; video : P3)")
    return KindSpec(kind=kind_cfg.name, asset=kind_cfg.asset,
                    provider_name=provider_name, options=options,
                    targets=tuple(targets), root=project.root,
                    output_format=output_format)


def _image_targets(project: ProjectConfig, kind_cfg: KindConfig,
                   provider_cfg, ids: Optional[list[str]]) -> list[Target]:
    if kind_cfg.prompts is None:
        raise ValueError(f"le kind '{kind_cfg.name}' n'a pas de fichier prompts")
    cfg = load_prompts(kind_cfg.prompts)
    size = kind_cfg.art_size or getattr(provider_cfg, "default_size", None)
    target_ids = ids or list((cfg.get("prompts", {}) or {}).keys())
    targets = []
    for asset_id in target_ids:
        prompt = prompt_for(asset_id, cfg)
        refs = reference_data_urls(cfg, project.root, asset_id,
                                   project.defaults.max_refs,
                                   project.defaults.ref_max_px)
        targets.append(Target(id=asset_id, text=prompt, refs=tuple(refs),
                              settings={"size": size}))
    return targets


def _first_set(*values):
    for value in values:
        if value is not None:
            return value
    return None


def _load_kind_catalog(kind_cfg: KindConfig) -> dict:
    if kind_cfg.prompts is None:
        raise ValueError(
            f"le kind '{kind_cfg.name}' ({kind_cfg.asset}) n'a pas de fichier prompts (catalogue)")
    return load_catalog(kind_cfg.prompts)


def _catalog_ids(catalog_cfg: dict, ids: Optional[list[str]]) -> list[str]:
    if ids is not None:
        for entry_id in ids:
            get_entry(catalog_cfg, entry_id)   # KeyError français si inconnu
        return list(ids)
    return list(catalog_entries(catalog_cfg).keys())


def _music_targets(catalog_cfg: dict, options: dict,
                   ids: Optional[list[str]]) -> tuple[Target, ...]:
    defaults = catalog_cfg.get("defaults") or {}
    targets: list[Target] = []
    for entry_id in _catalog_ids(catalog_cfg, ids):
        entry = get_entry(catalog_cfg, entry_id)
        requested = _first_set(entry.get("length_ms"), defaults.get("length_ms"),
                               options.get("length_ms"), DEFAULT_MUSIC_LENGTH_MS)
        clamped = clamp_music_length_ms(requested)
        notes: tuple[str, ...] = ()
        if clamped != int(requested):
            notes = (f"length_ms {requested} hors bornes "
                     f"({MUSIC_MIN_MS}–{MUSIC_MAX_MS} ms) → {clamped}",)
        targets.append(Target(id=entry_id, text=prompt_for_entry(entry_id, catalog_cfg),
                              settings={"length_ms": clamped}, notes=notes))
    return tuple(targets)


def _sfx_targets(catalog_cfg: dict, options: dict,
                 ids: Optional[list[str]]) -> tuple[Target, ...]:
    defaults = catalog_cfg.get("defaults") or {}
    targets: list[Target] = []
    for entry_id in _catalog_ids(catalog_cfg, ids):
        entry = get_entry(catalog_cfg, entry_id)
        duration = _first_set(entry.get("duration_s"), defaults.get("duration_s"),
                              options.get("duration_s"))
        loop = bool(_first_set(entry.get("loop"), defaults.get("loop"),
                               options.get("loop"), False))
        settings: dict = {"loop": loop}
        notes: tuple[str, ...] = ()
        if duration is not None:
            clamped = clamp_sfx_duration_s(duration)
            if clamped != float(duration):
                notes = (f"duration_s {duration} hors bornes "
                         f"({SFX_MIN_S}–{SFX_MAX_S} s) → {clamped}",)
            settings["duration_s"] = clamped
        targets.append(Target(id=entry_id, text=prompt_for_entry(entry_id, catalog_cfg),
                              settings=settings, notes=notes))
    return tuple(targets)


def _audio_spec(project: ProjectConfig, kind_cfg: KindConfig,
                ids: Optional[list[str]]) -> KindSpec:
    catalog_cfg = _load_kind_catalog(kind_cfg)
    options = kind_cfg.generate.extras() if kind_cfg.generate else {}
    if kind_cfg.asset == "music":
        targets = _music_targets(catalog_cfg, options, ids)
    else:
        targets = _sfx_targets(catalog_cfg, options, ids)
    return KindSpec(kind=kind_cfg.name, asset=kind_cfg.asset,
                    provider_name=resolve_provider_name(project, kind_cfg),
                    options=options, targets=targets,
                    output_format=catalog_cfg.get("output_format"),
                    root=project.root)
