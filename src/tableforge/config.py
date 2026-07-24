"""Modèles de configuration (forge.yaml) validés par pydantic + chargeur.

Deux formats acceptés :
  v1 : bloc `provider:` anonyme (Seedream implicite) — normalisé en providers["default"].
  v2 : map `providers:` nommée (type: explicite exigé) + kinds multimodaux (asset:).
"""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, Optional, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field

AssetType = Literal["image", "music", "sfx", "tts", "dialogue", "video"]


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


class GenerateConfig(BaseModel):
    """Bloc `generate:` d'un kind. Les clés hors `with` (voice, text, model…) sont
    libres ici ; elles sont validées strictement par le modèle d'options du provider."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    with_: Optional[str] = Field(default=None, alias="with")

    def extras(self) -> dict:
        return dict(self.__pydantic_extra__ or {})


class KindConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    name: str
    asset: AssetType = "image"
    template: Optional[Path] = None
    render_size: Optional[RenderSize] = None
    data: Optional[Path] = None
    prompts: Optional[Path] = None
    capture_selector: str = ".forge-asset"
    scale: int = Field(default=1, gt=0)
    art_size: Optional[str] = None
    sheet: Optional[SheetConfig] = None
    from_: Optional[str] = Field(default=None, alias="from")
    generate: Optional[GenerateConfig] = None
    studio_url: Optional[str] = None


class SeedreamProviderConfig(BaseModel):
    # `type` a un défaut pour rester constructible sans lui (tests v1, normalisation
    # legacy) ; la map `providers:` exige un type explicite via _normalize_providers.
    type: Literal["seedream"] = "seedream"
    base_url: str
    api_key_env: str
    model: str
    default_size: str = "4704x3520"
    watermark: bool = False
    output_format: str = "png"


class ElevenLabsProviderConfig(BaseModel):
    type: Literal["elevenlabs"]
    api_key_env: str = "ELEVENLABS_API_KEY"
    base_url: str = "https://api.elevenlabs.io"
    output_format: str = "mp3_44100_128"
    sfx_model: str = "eleven_text_to_sound_v2"
    tts_model: str = "eleven_multilingual_v2"
    dialogue_model: str = "eleven_v3"


class HiggsfieldProviderConfig(BaseModel):
    type: Literal["higgsfield"]
    api_key_env: str = "HIGGSFIELD_API_KEY"
    api_secret_env: str = "HIGGSFIELD_API_SECRET"
    base_url: str = "https://platform.higgsfield.ai"
    default_image_model: str = "higgsfield-ai/soul/standard"
    poll_interval_s: float = 5.0
    poll_timeout_s: float = 600.0


AnyProviderConfig = Annotated[
    Union[SeedreamProviderConfig, ElevenLabsProviderConfig, HiggsfieldProviderConfig],
    Field(discriminator="type"),
]

ProviderConfig = SeedreamProviderConfig  # alias rétro-compat v1 (tests, starter)


class Defaults(BaseModel):
    max_refs: int = 3
    ref_max_px: int = 1024


class ProjectConfig(BaseModel):
    project: str
    root: Path
    providers: dict[str, AnyProviderConfig]
    voices: dict[str, str] = Field(default_factory=dict)
    kinds: dict[str, KindConfig]
    defaults: Defaults = Field(default_factory=Defaults)

    @property
    def provider(self) -> AnyProviderConfig:
        # DÉPRÉCIÉ (compat v1) : à supprimer quand starter et tests n'utilisent
        # plus le bloc `provider:` anonyme — revoir 2026-10.
        if "default" not in self.providers:
            raise KeyError(
                "pas de provider 'default' (format v1) — utilise cfg.providers['<nom>']")
        return self.providers["default"]

    def kind(self, name: str) -> KindConfig:
        if name not in self.kinds:
            raise KeyError(f"kind inconnu : '{name}' (connus : {', '.join(self.kinds)})")
        return self.kinds[name]


_PATH_FIELDS = ("data", "prompts", "template")
_PROVIDER_TYPES = ("seedream", "elevenlabs", "higgsfield")


def _normalize_providers(raw: dict) -> dict[str, dict]:
    has_legacy = raw.get("provider") is not None
    has_named = raw.get("providers") is not None
    if has_legacy and has_named:
        raise ValueError(
            "forge.yaml : utilise soit 'provider:' (ancien format) soit 'providers:', "
            "pas les deux")
    if has_legacy:
        return {"default": {**raw["provider"], "type": "seedream"}}
    providers = dict(raw.get("providers") or {})
    if not providers:
        raise ValueError(
            "forge.yaml : déclare au moins un provider ('provider:' ou 'providers:')")
    for name in ("manual", "default"):
        if name in providers:
            raise ValueError(
                f"provider '{name}' : nom réservé — choisis un autre nom "
                "(ex. 'ark', 'eleven', 'higgs')")
    for name, block in providers.items():
        if not isinstance(block, dict) or "type" not in block:
            raise ValueError(
                f"provider '{name}' : champ 'type' requis "
                f"({' | '.join(_PROVIDER_TYPES)})")
        if block["type"] == "manual":
            raise ValueError(
                f"provider '{name}' : type 'manual' réservé — utilise "
                "'generate: {with: manual}' sur le kind, sans déclarer de provider")
        if block["type"] not in _PROVIDER_TYPES:
            raise ValueError(
                f"provider '{name}' : type '{block['type']}' inconnu "
                f"({' | '.join(_PROVIDER_TYPES)})")
    return providers


def load_project(path: Path) -> ProjectConfig:
    path = Path(path)
    forge_file = path / "forge.yaml" if path.is_dir() else path
    root = forge_file.parent
    with open(forge_file, encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    providers_raw = _normalize_providers(raw)
    is_legacy = raw.get("provider") is not None

    kinds_raw = raw.get("kinds", {}) or {}
    kinds: dict[str, KindConfig] = {}
    for name, spec in kinds_raw.items():
        spec = dict(spec)
        for field in _PATH_FIELDS:
            if spec.get(field) is not None:
                spec[field] = (root / spec[field]).resolve()
        kind = KindConfig(name=name, **spec)
        if is_legacy and kind.asset == "image" and kind.prompts is not None \
                and kind.generate is None:
            kind = kind.model_copy(update={"generate": GenerateConfig(with_="default")})
        kinds[name] = kind

    return ProjectConfig(
        project=raw["project"],
        root=root.resolve(),
        providers=providers_raw,
        voices=raw.get("voices") or {},
        defaults=Defaults(**(raw.get("defaults") or {})),
        kinds=kinds,
    )
