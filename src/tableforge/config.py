"""Modèles de configuration (forge.yaml) validés par pydantic + chargeur."""
from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field


class RenderSize(BaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class SheetConfig(BaseModel):
    page: Literal["A4", "Letter"] = "A4"
    cols: int = Field(gt=0)
    rows: int = Field(gt=0)
    card_w_mm: float = Field(gt=0)
    card_h_mm: float = Field(gt=0)
    gap_mm: float = 4.0
    bleed_mm: float = 0.0
    cut_marks: bool = True


class KindConfig(BaseModel):
    name: str
    template: Path
    render_size: RenderSize
    data: Optional[Path] = None
    prompts: Optional[Path] = None
    capture_selector: str = ".forge-asset"
    scale: int = Field(default=1, gt=0)
    art_size: Optional[str] = None
    sheet: Optional[SheetConfig] = None


class ProviderConfig(BaseModel):
    base_url: str
    api_key_env: str
    model: str
    default_size: str = "4704x3520"
    watermark: bool = False
    output_format: str = "png"


class Defaults(BaseModel):
    max_refs: int = 3
    ref_max_px: int = 1024


class ProjectConfig(BaseModel):
    project: str
    root: Path
    provider: ProviderConfig
    kinds: dict[str, KindConfig]
    defaults: Defaults = Field(default_factory=Defaults)

    def kind(self, name: str) -> KindConfig:
        if name not in self.kinds:
            raise KeyError(f"kind inconnu : '{name}' (connus : {', '.join(self.kinds)})")
        return self.kinds[name]


_PATH_FIELDS = ("data", "prompts", "template")


def load_project(path: Path) -> ProjectConfig:
    path = Path(path)
    forge_file = path / "forge.yaml" if path.is_dir() else path
    root = forge_file.parent
    with open(forge_file, encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    kinds_raw = raw.get("kinds", {}) or {}
    kinds: dict[str, KindConfig] = {}
    for name, spec in kinds_raw.items():
        spec = dict(spec)
        for field in _PATH_FIELDS:
            if spec.get(field) is not None:
                spec[field] = (root / spec[field]).resolve()
        kinds[name] = KindConfig(name=name, **spec)

    return ProjectConfig(
        project=raw["project"],
        root=root.resolve(),
        provider=ProviderConfig(**raw["provider"]),
        defaults=Defaults(**(raw.get("defaults") or {})),
        kinds=kinds,
    )
