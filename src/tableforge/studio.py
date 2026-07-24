"""Fiches studio : texte assemblé + réglages + destination + URL du bon écran web."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .config import KindConfig, ProjectConfig
from .providers.base import provider_for
from .targets import build_kind_spec

STUDIO_URLS: dict[tuple[str, str], str] = {
    ("elevenlabs", "music"): "https://elevenlabs.io/app/music",
    ("elevenlabs", "sfx"): "https://elevenlabs.io/app/sound-effects",
    ("elevenlabs", "tts"): "https://elevenlabs.io/app/speech-synthesis",
    ("elevenlabs", "dialogue"): "https://elevenlabs.io/app/speech-synthesis",
    ("higgsfield", "video"): "https://higgsfield.ai/create/video",
    # NB : URL non vérifiée à date (par symétrie avec /create/video) — à confirmer
    # sur higgsfield.ai si elle s'avère fausse.
    ("higgsfield", "image"): "https://higgsfield.ai/create/image",
}


@dataclass(frozen=True)
class StudioCard:
    kind: str
    id: str
    text: str
    settings: dict
    dest: Path
    url: Optional[str]
    notes: tuple[str, ...]


def _studio_url(project: ProjectConfig, kind_cfg: KindConfig, provider_name: str,
                asset: str) -> Optional[str]:
    if kind_cfg.studio_url:
        return kind_cfg.studio_url
    if provider_name == "manual":
        return None
    provider_type = project.providers[provider_name].type
    return STUDIO_URLS.get((provider_type, asset))


def studio_cards(project: ProjectConfig, kind: str,
                 ids: Optional[list[str]] = None) -> list[StudioCard]:
    spec = build_kind_spec(project, kind, ids)
    kind_cfg = project.kind(kind)
    jobs_by_id = {job.id: job for job in provider_for(project, kind_cfg).plan(spec)}
    url = _studio_url(project, kind_cfg, spec.provider_name, spec.asset)
    return [StudioCard(kind=kind, id=target.id, text=target.text,
                       settings={k: v for k, v in target.settings.items() if v is not None},
                       dest=jobs_by_id[target.id].dest,
                       url=url, notes=target.notes)
            for target in spec.targets]
