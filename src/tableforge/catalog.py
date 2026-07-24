"""Catalogues non-image (music, sfx, tts, dialogue, video) : chargement + prompts.

Miroir de `prompts.py` pour les assets audio/vidéo. Un catalogue est un YAML avec
une direction commune, un négatif optionnel (replié dans le prompt — pas de champ
API dédié chez ElevenLabs), des réglages par défaut, et une table `entries:`
indexée par id. Logique pure : rien ici n'appelle d'API.
"""
from __future__ import annotations

from pathlib import Path

import yaml

# Bornes ElevenLabs. Music : 3 s..10 min ; Sound Effects : 0.5 s..30 s.
MUSIC_MIN_MS, MUSIC_MAX_MS = 3000, 600000
SFX_MIN_S, SFX_MAX_S = 0.5, 30.0
DEFAULT_MUSIC_LENGTH_MS = 90000


def load_catalog(path: Path) -> dict:
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def catalog_entries(cfg: dict) -> dict:
    if "entries" not in cfg:
        raise KeyError(
            "catalogue sans table 'entries:' "
            "(schéma : direction, negative?, defaults?, output_format?, entries)")
    return cfg["entries"] or {}


def get_entry(cfg: dict, entry_id: str) -> dict:
    entries = catalog_entries(cfg)
    if entry_id not in entries:
        raise KeyError(f"aucune entrée « {entry_id} » dans le catalogue")
    entry = entries[entry_id]
    return entry if isinstance(entry, dict) else {"prompt": entry}


def build_media_prompt(subject: str, direction: str) -> str:
    return f"{subject.strip().rstrip('.')}. {direction.strip()}".strip()


def prompt_for_entry(entry_id: str, cfg: dict, *, with_negative: bool = True) -> str:
    subject = get_entry(cfg, entry_id).get("prompt", "")
    text = build_media_prompt(subject, cfg.get("direction", ""))
    if with_negative and cfg.get("negative"):
        text += " " + cfg["negative"].strip()
    return text


def clamp_music_length_ms(value: int) -> int:
    return max(MUSIC_MIN_MS, min(MUSIC_MAX_MS, int(value)))


def clamp_sfx_duration_s(value: float) -> float:
    return max(SFX_MIN_S, min(SFX_MAX_S, float(value)))
