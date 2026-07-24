"""Résolution des cibles d'un kind (pur, sans clé API ni réseau).

`build_kind_spec` transforme la config + les fichiers data/prompts en un `KindSpec`
immuable que les providers consomment (`plan`). P0 : asset image uniquement ;
les branches music/sfx/tts/dialogue/video arrivent en P1/P2/P3.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

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
    if kind_cfg.asset == "image":
        targets = _image_targets(project, kind_cfg, provider_cfg, ids)
        output_format = getattr(provider_cfg, "output_format", None)
    else:
        raise NotImplementedError(
            f"asset '{kind_cfg.asset}' : pas encore implémenté (phases P1+)")
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
