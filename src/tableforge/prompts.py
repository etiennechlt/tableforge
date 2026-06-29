"""Assemblage des prompts d'art + encodage des images de référence (i2i)."""
from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Optional

import yaml
from PIL import Image


def load_prompts(path: Path) -> dict:
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def prompt_for(asset_id: str, cfg: dict) -> str:
    prompts = cfg.get("prompts", {}) or {}
    if asset_id not in prompts:
        raise KeyError(f"prompt inconnu pour l'id « {asset_id} »")
    subject = str(prompts[asset_id]).strip().rstrip(".")
    art_direction = str(cfg.get("art_direction", "")).strip()
    text = f"{subject}. {art_direction}".strip()
    override = (cfg.get("overrides", {}) or {}).get(asset_id, {})
    if override.get("suffix"):
        text += " " + str(override["suffix"]).strip()
    if cfg.get("negative"):
        text += " " + str(cfg["negative"]).strip()
    return text


def encode_image_data_url(path, max_px: int = 1024, quality: int = 85) -> str:
    img = Image.open(path).convert("RGB")
    img.thumbnail((max_px, max_px))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=quality)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def reference_data_urls(
    cfg: dict,
    root: Path,
    asset_id: Optional[str] = None,
    max_refs: int = 3,
    max_px: int = 1024,
) -> list[str]:
    refs = list((cfg.get("style_refs", []) or [])[:max_refs])
    if asset_id:
        override = (cfg.get("overrides", {}) or {}).get(asset_id, {})
        refs += list(override.get("style_refs", []) or [])
    return [encode_image_data_url(Path(root) / ref, max_px=max_px) for ref in refs]
