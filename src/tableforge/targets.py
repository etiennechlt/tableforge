"""Résolution des cibles d'un kind (pur, sans clé API ni réseau).

`build_kind_spec` transforme la config + les fichiers data/prompts en un `KindSpec`
immuable que les providers consomment (`plan`). Les six assets (image, music, sfx,
tts, dialogue, video) sont désormais tous implémentés ici.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import jinja2

from .catalog import (DEFAULT_MUSIC_LENGTH_MS, MUSIC_MAX_MS, MUSIC_MIN_MS,
                      SFX_MAX_S, SFX_MIN_S, catalog_entries, clamp_music_length_ms,
                      clamp_sfx_duration_s, get_entry, load_catalog, prompt_for_entry)
from .config import KindConfig, ProjectConfig
from .data import load_rows
from .paths import asset_dir, asset_path
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
    if kind_cfg.asset in ("music", "sfx"):
        targets, output_format = _audio_spec(kind_cfg, options, ids)
    elif kind_cfg.asset == "image":
        targets = _image_targets(project, kind_cfg, provider_cfg, ids)
        output_format = getattr(provider_cfg, "output_format", None)
    elif kind_cfg.asset == "tts":
        targets = _tts_targets(project, kind_cfg, options, ids)
        output_format = _catalog_output_format(kind_cfg)
    elif kind_cfg.asset == "dialogue":
        targets = _dialogue_targets(project, kind_cfg, options, ids)
        output_format = _catalog_output_format(kind_cfg)
    else:  # kind_cfg.asset == "video" — dernier littéral d'AssetType (config.py)
        targets = _video_targets(project, kind_cfg, ids)
        output_format = None
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


def _first_set(*values):
    for value in values:
        if value is not None:
            return value
    return None


def _load_kind_catalog(kind_cfg: KindConfig) -> dict:
    if kind_cfg.prompts is None:
        raise ValueError(
            f"le kind '{kind_cfg.name}' ({kind_cfg.asset}) n'a pas de fichier prompts (catalogue)")
    return load_catalog(kind_cfg.prompts)


def _catalog_ids(catalog_cfg: dict, ids: Optional[list[str]]) -> list[str]:
    if ids is not None:
        for entry_id in ids:
            get_entry(catalog_cfg, entry_id)   # KeyError français si inconnu
        return list(ids)
    return list(catalog_entries(catalog_cfg).keys())


def _music_targets(catalog_cfg: dict, options: dict,
                   ids: Optional[list[str]]) -> tuple[Target, ...]:
    defaults = catalog_cfg.get("defaults") or {}
    targets: list[Target] = []
    for entry_id in _catalog_ids(catalog_cfg, ids):
        entry = get_entry(catalog_cfg, entry_id)
        requested = _first_set(entry.get("length_ms"), defaults.get("length_ms"),
                               options.get("length_ms"), DEFAULT_MUSIC_LENGTH_MS)
        clamped = clamp_music_length_ms(requested)
        notes: tuple[str, ...] = ()
        if clamped != int(requested):
            notes = (f"length_ms {requested} hors bornes "
                     f"({MUSIC_MIN_MS}–{MUSIC_MAX_MS} ms) → {clamped}",)
        targets.append(Target(id=entry_id, text=prompt_for_entry(entry_id, catalog_cfg),
                              settings={"length_ms": clamped}, notes=notes))
    return tuple(targets)


def _sfx_targets(catalog_cfg: dict, options: dict,
                 ids: Optional[list[str]]) -> tuple[Target, ...]:
    defaults = catalog_cfg.get("defaults") or {}
    targets: list[Target] = []
    for entry_id in _catalog_ids(catalog_cfg, ids):
        entry = get_entry(catalog_cfg, entry_id)
        duration = _first_set(entry.get("duration_s"), defaults.get("duration_s"),
                              options.get("duration_s"))
        loop = bool(_first_set(entry.get("loop"), defaults.get("loop"),
                               options.get("loop"), False))
        settings: dict = {"loop": loop}
        notes: tuple[str, ...] = ()
        if duration is not None:
            clamped = clamp_sfx_duration_s(duration)
            if clamped != float(duration):
                notes = (f"duration_s {duration} hors bornes "
                         f"({SFX_MIN_S}–{SFX_MAX_S} s) → {clamped}",)
            settings["duration_s"] = clamped
        targets.append(Target(id=entry_id, text=prompt_for_entry(entry_id, catalog_cfg),
                              settings=settings, notes=notes))
    return tuple(targets)


def _audio_spec(kind_cfg: KindConfig, options: dict,
                ids: Optional[list[str]]) -> tuple[tuple[Target, ...], Optional[str]]:
    catalog_cfg = _load_kind_catalog(kind_cfg)
    if kind_cfg.asset == "music":
        targets = _music_targets(catalog_cfg, options, ids)
    else:
        targets = _sfx_targets(catalog_cfg, options, ids)
    return targets, catalog_cfg.get("output_format")


# --- P2 : cibles vocales (tts) ---------------------------------------------

def _resolve_voice(name: str, voices: dict[str, str], *, kind: str) -> str:
    """Résout un nom humain de la map voices: en voice_id ElevenLabs."""
    if name in voices:
        return voices[name]
    declared = ", ".join(sorted(voices)) if voices else "aucune"
    raise KeyError(
        f"kind '{kind}' : voix inconnue « {name} » (voix déclarées : {declared})")


def _catalog_output_format(kind_cfg: KindConfig) -> Optional[str]:
    if kind_cfg.prompts is None:
        return None
    return load_catalog(kind_cfg.prompts).get("output_format")


def _tts_targets_from_catalog(project: ProjectConfig, kind_cfg: KindConfig,
                              options: dict, ids: Optional[list[str]]) -> tuple[Target, ...]:
    cfg = _load_kind_catalog(kind_cfg)
    target_ids = _catalog_ids(cfg, ids)
    default_voice = options.get("voice")
    targets: list[Target] = []
    for entry_id in target_ids:
        entry = get_entry(cfg, entry_id)
        text = entry.get("text") or entry.get("prompt")
        if not text:
            raise ValueError(
                f"kind '{kind_cfg.name}', entrée '{entry_id}' : champ 'text' "
                "(ou 'prompt', ou entrée chaîne) requis")
        voice_name = entry.get("voice") or default_voice
        if not voice_name:
            raise ValueError(
                f"kind '{kind_cfg.name}', entrée '{entry_id}' : aucune voix — déclare "
                "generate.voice ou un champ voice dans l'entrée")
        voice_id = _resolve_voice(str(voice_name), project.voices, kind=kind_cfg.name)
        targets.append(Target(id=entry_id, text=str(text).strip(), voice_id=voice_id))
    return tuple(targets)


def _tts_targets_from_rows(project: ProjectConfig, kind_cfg: KindConfig,
                           options: dict, ids: Optional[list[str]]) -> tuple[Target, ...]:
    if kind_cfg.data is None:
        raise ValueError(
            f"le kind tts '{kind_cfg.name}' utilise generate.text mais n'a pas de data")
    rows = load_rows(kind_cfg.data)
    if ids is not None:
        wanted = set(ids)
        missing = wanted - {row.id for row in rows}
        if missing:
            raise KeyError(
                f"kind '{kind_cfg.name}' : id(s) inconnu(s) : {', '.join(sorted(missing))}")
        rows = [row for row in rows if row.id in wanted]
    try:
        template = jinja2.Template(str(options["text"]), undefined=jinja2.StrictUndefined)
    except jinja2.TemplateSyntaxError as exc:
        raise ValueError(
            f"kind '{kind_cfg.name}' : gabarit generate.text invalide — {exc.message}") from exc
    voice_field = options.get("voice_field")
    default_voice = options.get("voice")
    targets: list[Target] = []
    for row in rows:
        try:
            text = template.render(**row.data).strip()
        except jinja2.exceptions.UndefinedError as exc:
            raise ValueError(
                f"kind '{kind_cfg.name}', id '{row.id}' : champ manquant dans le gabarit "
                f"generate.text — {exc.message}") from exc
        voice_name = (row.get(voice_field) if voice_field else None) or default_voice
        if not voice_name:
            raise ValueError(
                f"kind '{kind_cfg.name}', id '{row.id}' : aucune voix — déclare "
                "generate.voice ou generate.voice_field")
        voice_id = _resolve_voice(str(voice_name), project.voices, kind=kind_cfg.name)
        targets.append(Target(id=row.id, text=text, voice_id=voice_id))
    return tuple(targets)


# --- P2 : cibles dialogue multi-voix ----------------------------------------

def _dialogue_targets(project: ProjectConfig, kind_cfg: KindConfig,
                      options: dict, ids: Optional[list[str]]) -> tuple[Target, ...]:
    if kind_cfg.prompts is None:
        raise ValueError(f"le kind dialogue '{kind_cfg.name}' n'a pas de fichier prompts")
    cfg = load_catalog(kind_cfg.prompts)
    target_ids = _catalog_ids(cfg, ids)
    targets: list[Target] = []
    for entry_id in target_ids:
        entry = get_entry(cfg, entry_id)
        raw_lines = entry.get("lines")
        if not isinstance(raw_lines, list) or not raw_lines:
            raise ValueError(
                f"kind '{kind_cfg.name}', entrée '{entry_id}' : liste 'lines' requise "
                "(éléments {voice, text})")
        lines: list[DialogueLine] = []
        display: list[str] = []
        for index, raw in enumerate(raw_lines, start=1):
            voice_name = raw.get("voice") if isinstance(raw, dict) else None
            text = raw.get("text") if isinstance(raw, dict) else None
            if not voice_name or not text:
                raise ValueError(
                    f"kind '{kind_cfg.name}', entrée '{entry_id}', ligne {index} : "
                    "'voice' et 'text' sont requis")
            voice_id = _resolve_voice(str(voice_name), project.voices, kind=kind_cfg.name)
            lines.append(DialogueLine(voice_id=voice_id, text=str(text)))
            display.append(f"{voice_name}: {text}")
        targets.append(Target(id=entry_id, text="\n".join(display), lines=tuple(lines)))
    return tuple(targets)


def _tts_targets(project: ProjectConfig, kind_cfg: KindConfig,
                 options: dict, ids: Optional[list[str]]) -> tuple[Target, ...]:
    if options.get("text") is not None:
        return _tts_targets_from_rows(project, kind_cfg, options, ids)
    if kind_cfg.prompts is not None:
        return _tts_targets_from_catalog(project, kind_cfg, options, ids)
    raise ValueError(
        f"le kind tts '{kind_cfg.name}' : déclare generate.text + data, "
        "ou un fichier prompts (catalogue)")


# --- P3a : cibles vidéo — i2v (depuis un kind image via `from:`) et t2v (catalogue) --

def _filter_ids(kind_name: str, target_ids: list[str],
                ids: Optional[list[str]]) -> list[str]:
    """Filtre une liste de cibles déjà résolues (union art/catalogue pour i2v,
    ids du catalogue pour t2v) par une liste d'ids explicite, en conservant l'ordre
    canonique de `target_ids` (pas celui de `ids`). `ids=None` = pas de filtre ;
    `ids=[]` = filtre explicite « zéro cible » — même sémantique que `_catalog_ids`
    (utilisée par music/sfx/tts/dialogue) pour rester cohérent entre tous les assets."""
    if ids is None:
        return target_ids
    unknown = sorted(set(ids) - set(target_ids))
    if unknown:
        raise KeyError(
            f"id(s) inconnu(s) pour le kind '{kind_name}' : {', '.join(unknown)} "
            f"(connus : {', '.join(target_ids)})")
    wanted = set(ids)
    return [target_id for target_id in target_ids if target_id in wanted]


def _video_settings(cfg: dict, entry: dict) -> dict:
    """Précédence entrée > `defaults:` du catalogue pour `duration_s` (le niveau
    kind, lui, est géré par `options` côté provider — Task 4)."""
    defaults = cfg.get("defaults") or {}
    duration = _first_set(entry.get("duration_s"), defaults.get("duration_s"))
    return {"duration_s": duration} if duration is not None else {}


def _t2v_targets(kind_cfg: KindConfig, ids: Optional[list[str]]) -> tuple[Target, ...]:
    if kind_cfg.prompts is None:
        raise ValueError(
            f"le kind '{kind_cfg.name}' (video t2v) requiert un fichier prompts "
            "(catalogue d'entrées) — ou un `from:` pour animer un kind image (i2v)")
    cfg = load_catalog(kind_cfg.prompts)
    target_ids = _filter_ids(kind_cfg.name, list(catalog_entries(cfg)), ids)
    return tuple(
        Target(id=entry_id, text=prompt_for_entry(entry_id, cfg),
              settings=_video_settings(cfg, get_entry(cfg, entry_id)))
        for entry_id in target_ids)


def _source_image_ids(source_kind: KindConfig) -> list[str]:
    """Ids déclarés du kind image source (prompts ou data) — sert à valider qu'une
    entrée du catalogue de mouvement désigne bien une carte connue, même si son art
    n'a pas encore été généré (l'art manquant est une note, pas une erreur ici)."""
    if source_kind.prompts is not None:
        return list((load_prompts(source_kind.prompts).get("prompts") or {}).keys())
    if source_kind.data is not None:
        return [row.id for row in load_rows(source_kind.data)]
    return []


def _i2v_targets(project: ProjectConfig, kind_cfg: KindConfig,
                 ids: Optional[list[str]]) -> tuple[Target, ...]:
    source_name = kind_cfg.from_
    source_kind = project.kind(source_name)
    if source_kind.asset != "image":
        raise ValueError(
            f"le kind '{kind_cfg.name}' anime '{source_name}' qui n'est pas un kind "
            f"image (asset : {source_kind.asset})")
    art_ids = sorted(p.stem for p in
                     asset_dir(project.root, "image", source_name).glob("*.png"))
    catalog_cfg: dict = {}
    entry_ids: list[str] = []
    if kind_cfg.prompts is not None:
        catalog_cfg = load_catalog(kind_cfg.prompts)
        entry_ids = list(catalog_entries(catalog_cfg))
        allowed = set(_source_image_ids(source_kind)) | set(art_ids)
        unknown = sorted(set(entry_ids) - allowed)
        if unknown:
            source_file = source_kind.prompts or source_kind.data
            raise ValueError(
                f"catalogue de mouvement {kind_cfg.prompts} : entrées sans carte "
                f"source ({', '.join(unknown)}) — ids attendus dans {source_file}")
    target_ids = _filter_ids(kind_cfg.name, sorted(set(art_ids) | set(entry_ids)), ids)
    known_entries = set(entry_ids)
    targets: list[Target] = []
    for target_id in target_ids:
        source_image = asset_path(project.root, "image", source_name, target_id)
        notes: list[str] = []
        if not source_image.exists():
            notes.append(f"art source manquant : {source_image} — lance d'abord "
                        f"`forge generate {source_name}`")
        if target_id in known_entries:
            text = prompt_for_entry(target_id, catalog_cfg)
            settings = _video_settings(catalog_cfg, get_entry(catalog_cfg, target_id))
        else:
            # Ni entrée catalogue ni `direction:` (contrairement à prompt_for_entry,
            # ce texte-ci n'est pas glué à un séparateur) : "" est possible et
            # partirait silencieusement vers le provider sans cette note.
            text = str(catalog_cfg.get("direction", "")).strip()
            settings = _video_settings(catalog_cfg, {})
            if not text:
                notes.append(
                    "prompt vide (aucune entrée catalogue, aucune `direction:`) — "
                    "renseigne l'une des deux")
        targets.append(Target(id=target_id, text=text, source_image=source_image,
                              settings=settings, notes=tuple(notes)))
    return tuple(targets)


def _video_targets(project: ProjectConfig, kind_cfg: KindConfig,
                   ids: Optional[list[str]]) -> tuple[Target, ...]:
    if kind_cfg.from_ is not None:
        return _i2v_targets(project, kind_cfg, ids)
    return _t2v_targets(kind_cfg, ids)
