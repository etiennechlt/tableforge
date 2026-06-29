"""Conventions de chemins de sortie (out/art|render|sheet/<kind>/)."""
from __future__ import annotations

from pathlib import Path


def art_dir(root: Path, kind: str) -> Path:
    return root / "out" / "art" / kind


def render_dir(root: Path, kind: str) -> Path:
    return root / "out" / "render" / kind


def art_path(root: Path, kind: str, asset_id: str) -> Path:
    return art_dir(root, kind) / f"{asset_id}.png"


def render_path(root: Path, kind: str, asset_id: str) -> Path:
    return render_dir(root, kind) / f"{asset_id}.png"


def sheet_path(root: Path, kind: str) -> Path:
    return root / "out" / "sheet" / f"{kind}.pdf"
