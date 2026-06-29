"""Scaffold d'un nouveau projet à partir du starter bundlé."""
from __future__ import annotations

import shutil
from importlib import resources
from pathlib import Path

PLACEHOLDER = "__PROJECT_NAME__"
_TEXT_SUFFIXES = (".yaml", ".yml", ".md", ".css", ".j2", ".txt", "")


def starter_dir() -> Path:
    return Path(resources.files("tableforge")) / "templates" / "starter"


def init_project(name: str, dest: Path) -> Path:
    target = Path(dest) / name
    if target.exists() and any(target.iterdir()):
        raise FileExistsError(f"{target} existe déjà et n'est pas vide")
    shutil.copytree(starter_dir(), target, dirs_exist_ok=True)
    for path in target.rglob("*"):
        if not path.is_file() or path.suffix not in _TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if PLACEHOLDER in text:
            path.write_text(text.replace(PLACEHOLDER, name), encoding="utf-8")
    return target
