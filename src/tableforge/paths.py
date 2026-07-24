"""Conventions de chemins de sortie (out/art|render|sheet/<kind>/)."""
from __future__ import annotations

from pathlib import Path
from typing import Optional


def art_dir(root: Path, kind: str) -> Path:
    return root / "out" / "art" / kind


def render_dir(root: Path, kind: str) -> Path:
    return root / "out" / "render" / kind


def art_path(root: Path, kind: str, asset_id: str) -> Path:
    return art_dir(root, kind) / f"{asset_id}.png"


def find_art(root: Path, kind: str, asset_id: str) -> Optional[Path]:
    """Art d'un id, quelle que soit l'extension (.png prioritaire, sinon premier match)."""
    exact = art_path(root, kind, asset_id)
    if exact.exists():
        return exact
    candidates = sorted(art_dir(root, kind).glob(f"{asset_id}.*"))
    return candidates[0] if candidates else None


def render_path(root: Path, kind: str, asset_id: str) -> Path:
    return render_dir(root, kind) / f"{asset_id}.png"


def sheet_path(root: Path, kind: str) -> Path:
    return root / "out" / "sheet" / f"{kind}.pdf"


MODALITY_BY_ASSET = {
    "image": "art",
    "music": "audio",
    "sfx": "audio",
    "tts": "audio",
    "dialogue": "audio",
    "video": "video",
}

_AUDIO_EXT_BY_PREFIX = {"mp3": ".mp3", "opus": ".ogg", "pcm": ".wav",
                        "ulaw": ".wav", "alaw": ".wav"}


def extension_for(asset: str, output_format: Optional[str] = None) -> str:
    if asset == "image":
        return f".{output_format or 'png'}"
    if asset == "video":
        return ".mp4"
    prefix = (output_format or "mp3").split("_", 1)[0]
    return _AUDIO_EXT_BY_PREFIX.get(prefix, ".mp3")


def asset_dir(root: Path, asset: str, kind: str) -> Path:
    return root / "out" / MODALITY_BY_ASSET[asset] / kind


def asset_path(root: Path, asset: str, kind: str, asset_id: str,
               output_format: Optional[str] = None) -> Path:
    return asset_dir(root, asset, kind) / f"{asset_id}{extension_for(asset, output_format)}"
