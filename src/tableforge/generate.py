"""Orchestration de la génération d'art (un kind, ses ids)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .config import ProjectConfig
from .paths import art_path
from .prompts import load_prompts, prompt_for, reference_data_urls
from .providers import SeedreamProvider, build_request, summarize_request


@dataclass(frozen=True)
class GenerateResult:
    id: str
    dest: Optional[Path]
    request: dict


def generate_kind(project: ProjectConfig, kind: str, ids: Optional[list[str]] = None,
                  dry_run: bool = False, force: bool = False,
                  provider: Optional[SeedreamProvider] = None) -> list[GenerateResult]:
    kind_cfg = project.kind(kind)
    if kind_cfg.prompts is None:
        raise ValueError(f"le kind '{kind}' n'a pas de fichier prompts")
    cfg = load_prompts(kind_cfg.prompts)
    size = kind_cfg.art_size or project.provider.default_size
    target_ids = ids or list((cfg.get("prompts", {}) or {}).keys())

    if not dry_run and provider is None:
        provider = SeedreamProvider.from_config(project.provider)

    results: list[GenerateResult] = []
    for asset_id in target_ids:
        prompt = prompt_for(asset_id, cfg)
        refs = reference_data_urls(cfg, project.root, asset_id,
                                   project.defaults.max_refs, project.defaults.ref_max_px)
        dest = art_path(project.root, kind, asset_id)
        if dry_run:
            req = build_request(model=project.provider.model, size=size, refs=refs,
                                watermark=project.provider.watermark,
                                output_format=project.provider.output_format)
            req["prompt"] = prompt
            results.append(GenerateResult(asset_id, None, summarize_request(req)))
            continue
        if dest.exists() and not force:
            results.append(GenerateResult(asset_id, dest, {"skipped": "exists"}))
            continue
        provider.generate(prompt, dest, size=size, refs=refs)
        results.append(GenerateResult(asset_id, dest,
                                      summarize_request(provider.build(prompt, size, refs))))
    return results
