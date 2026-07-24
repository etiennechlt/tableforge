# Multimodal P0 — Refactor à comportement constant : Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactorer tableforge vers l'architecture multi-provider (package `providers/`, contrat plan/execute, providers nommés, `build_kind_spec`, chemins multi-assets) avec ZÉRO changement de comportement observable — verrouillé par un test de byte-équivalence des requêtes dry-run.

**Architecture:** On fige d'abord le comportement actuel (test de caractérisation avec dicts attendus collés en constantes), puis on étend `config.py` (union discriminée de providers + normalisation legacy), on déplace `providers.py` en package (`git mv` → `providers/seedream.py` + ré-exports), on introduit `providers/base.py` (AssetJob, Protocol plan/execute, résolution de provider, adaptateur legacy) et `targets.py` (`build_kind_spec`, image uniquement), puis on réécrit `generate.py` pour passer par plan/execute. La clé API n'est plus lue qu'à l'exécution (`_require_key`), jamais pendant plan/dry-run.

**Tech Stack:** Python ≥ 3.10, pydantic v2, PyYAML, typer, Pillow, httpx, python-dotenv, pytest (+pytest-cov). Pas de nouveau chemin réseau en P0 → respx pas encore nécessaire.

## Global Constraints

- **Interpréteur : toujours `.venv/bin/python`** (jamais python/pip système). Bootstrap si besoin : `uv venv .venv && uv pip install --python .venv/bin/python -e ".[dev]" && .venv/bin/playwright install chromium`.
- **TDD** : test rouge → implémentation minimale → vert → commit. Exceptions assumées : Task 1 (test de caractérisation, vert par construction) et les tâches de pur refactor (4, 8) où le filet est la suite existante + le verrou de byte-équivalence.
- **Compat figée par les tests existants** (lus, non modifiables) : `SeedreamProvider.from_config` continue de résoudre la clé immédiatement et de lever `RuntimeError` si absente (`test_from_config_requires_key`/`_reads_key`) — le chemin keyless est un NOUVEAU constructeur `from_provider_config`. `ProviderConfig(base_url=…, api_key_env=…, model=…)` doit rester constructible sans `type:` (`test_providers._cfg`) — donc `type` a un défaut sur le modèle, et l'obligation de `type:` explicite dans la map `providers:` est vérifiée par le CHARGEUR (`_normalize_providers`), pas par pydantic.
- **Suite verte à CHAQUE commit** : `.venv/bin/python -m pytest -q` doit passer avant chaque `git commit`.
- **VERROU 1 — byte-équivalence** : les dicts `request` des dry-run v1 (fixture inline + `examples/couronnes`) sont STRICTEMENT identiques avant/après (Task 1 fige les constantes, calculées sur le commit `199f667`).
- **VERROU 2 — aucun fichier de tests existant n'est modifié** : `test_cli.py`, `test_config.py`, `test_data.py`, `test_example_couronnes.py`, `test_generate.py`, `test_package.py`, `test_paths.py`, `test_prompts.py`, `test_providers.py`, `test_render.py`, `test_scaffold.py`, `test_sheet.py`, `test_smoke_render.py` restent intacts. Les nouveaux tests vont dans `tests/test_byte_equivalence.py`, `tests/test_config_providers.py`, `tests/test_paths_assets.py`, `tests/test_providers_base.py`, `tests/test_targets.py`, `tests/test_cli_guards.py`.
- **Couverture ≥ 80 %** sur la logique pure (objectif : rester ≈ 96 %). `render.py`, `cli.py`, `__main__.py` exclus (pyproject). Le chemin SDK OpenAI de Seedream reste `pragma: no cover`.
- Modules ≤ ~400 lignes ; dataclasses `frozen=True` ; données immuables ; messages d'erreur en **français** ; secrets jamais imprimés (noms de variables d'env uniquement).
- Commits conventionnels en français (`feat:`, `fix:`, `refactor:`, `test:`, `chore:`) — pas de ligne d'attribution (désactivée globalement).
- Plan en français, code et noms de tests en anglais, structure AAA, style des tests existants.
- **AUCUNE feature** : P0 ne livre aucun provider audio/vidéo. `build_kind_spec` lève `NotImplementedError` (français) pour tout asset ≠ image ; `provider_for` lève `NotImplementedError` pour les types elevenlabs/higgsfield/manual.

## Structure des fichiers (P0)

| Fichier | Rôle |
|---|---|
| `src/tableforge/config.py` (modifié) | AssetType, GenerateConfig, union discriminée de providers, voices, normalisation legacy, propriété `provider` dépréciée |
| `src/tableforge/paths.py` (modifié) | `MODALITY_BY_ASSET`, `extension_for`, `asset_dir`, `asset_path` (helpers actuels conservés) |
| `src/tableforge/providers/__init__.py` (créé) | Ré-exports compat : `SeedreamProvider`, `build_request`, `summarize_request`, `_save_image`, `DEFAULT_SEQUENTIAL` |
| `src/tableforge/providers/seedream.py` (git mv de `providers.py`) | Provider existant + split clé (`_require_key`) + `plan`/`execute` |
| `src/tableforge/providers/base.py` (créé) | `AssetJob`, `Provider` (Protocol), `SUPPORTED_ASSETS`, `resolve_provider_name`, `provider_for`, `ensure_provider`, `_LegacyAdapter` |
| `src/tableforge/targets.py` (créé) | `DialogueLine`, `Target`, `KindSpec`, `build_kind_spec` (image uniquement en P0) |
| `src/tableforge/generate.py` (réécrit) | Orchestrateur via plan/execute, `GenerateResult` inchangé |
| `src/tableforge/cli.py` (modifié) | Garde template None dans `_render_kind` et `list` |

Sens des imports (aucun cycle à l'exécution) : `seedream → base → config` ; `targets → providers.base` ; `base` importe `seedream`/`paths` **paresseusement** (dans les corps de fonctions).

---

### Task 1: Verrou de byte-équivalence des requêtes dry-run

Test de **caractérisation** : il doit passer VERT sur le code actuel (commit `199f667`), AVANT tout refactor. Les constantes ci-dessous ont été calculées en exécutant l'implémentation actuelle — ne jamais les régénérer depuis le code refactoré. Si ce test échoue à sa première exécution (étape 2), STOP : soit le dépôt a bougé depuis `199f667`, soit une constante a été mal copiée — recalcule-la depuis le code AVANT refactor et corrige.

**Files:**
- Test: `tests/test_byte_equivalence.py` (créé)

**Interfaces:**
- Consumes: `tableforge.config.load_project`, `tableforge.generate.generate_kind` (API publique actuelle, inchangée par le refactor)
- Produces: le harnais de non-régression que toutes les tâches suivantes doivent garder vert

- [ ] **Step 1: Vérifier que la suite actuelle est verte**

Run: `.venv/bin/python -m pytest -q`
Expected: suite verte (0 failed). Sinon STOP — corriger l'environnement avant de continuer.

- [ ] **Step 2: Écrire le test de caractérisation**

Créer `tests/test_byte_equivalence.py` :

```python
"""Verrou P0 : les requêtes dry-run v1 restent strictement identiques après refactor.

Constantes calculées avec l'implémentation d'AVANT le refactor (commit 199f667).
Ne JAMAIS les régénérer depuis le code refactoré.
"""
import hashlib
import json
from pathlib import Path

from PIL import Image

from tableforge.config import load_project
from tableforge.generate import generate_kind

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "couronnes"

FORGE_V1 = """
project: demo
provider:
  base_url: https://ark.x/api/v3
  api_key_env: ARK_API_KEY
  model: seedream-5-0-260128
  default_size: "64x64"
defaults: {max_refs: 2, ref_max_px: 32}
kinds:
  cards:
    prompts: prompts/cards.yaml
    template: templates/card
    render_size: {width: 10, height: 10}
    art_size: "32x32"
"""

PROMPTS_V1 = """
art_direction: "Dark fantasy."
negative: "Avoid: text."
style_refs: [reference/a.png, reference/b.png, reference/c.png]
prompts:
  lame: "A footman."
  emissaire: "A hooded envoy"
overrides:
  lame: {suffix: "Corrupted.", style_refs: [reference/x.png]}
"""

EXPECTED_LAME = {
    "model": "seedream-5-0-260128",
    "prompt": "A footman. Dark fantasy. Corrupted. Avoid: text.",
    "size": "32x32",
    "response_format": "url",
    "extra_body": {
        "watermark": False,
        "sequential_image_generation": "auto",
        "output_format": "png",
        "image": "[3 référence(s), data-URLs omises]",
    },
}

EXPECTED_EMISSAIRE = {
    "model": "seedream-5-0-260128",
    "prompt": "A hooded envoy. Dark fantasy. Avoid: text.",
    "size": "32x32",
    "response_format": "url",
    "extra_body": {
        "watermark": False,
        "sequential_image_generation": "auto",
        "output_format": "png",
        "image": "[2 référence(s), data-URLs omises]",
    },
}

COURONNES_COUNT = 18
COURONNES_IDS = [
    "plaidoyer", "lame", "emissaire", "marchandage", "glanage", "patrouille",
    "anneau-du-sceau", "edit-royal", "recruteur", "caravane-marchande",
    "chevalier-errant", "maitre-de-guilde", "pretresse", "banneret",
    "pacte-d-ether", "legion-damnee", "couronne-maudite", "cendres-vivantes",
]
COURONNES_DIGEST = "4914073c56812daf2f2300366ca1d55d1a63aedd76dac4144d207079f0e84d17"

EXPECTED_COURONNE_MAUDITE = {
    "model": "seedream-5-0-260128",
    "prompt": (
        "A blackened, thorn-wrought crown levitating above an empty throne, wreathed in cold "
        "violet ether flames, ash spiralling up into darkness, hairline cracks leaking pale "
        "light. Cursed majesty, the heart of corruption. Dark medieval fantasy trading-card "
        "illustration, painterly digital gouache with the weathered texture of an aged "
        "illuminated manuscript. A single centered subject, medium shot, strong cinematic "
        "chiaroscuro: one warm candle-gold key light against deep cold shadow. Muted grim "
        "palette — ash grey, weathered stone, oxblood red, candle gold; desaturated, somber. "
        "Visible hand-painted brushwork, fine detail, subtle parchment grain, slightly hazy "
        "atmospheric background that only suggests the setting. Cohesive concept-art look. "
        "No text, no letters, no card frame, no border, no UI — illustration only, full-bleed. "
        "Corrupted variant: introduce a sickly ether glow of violet and teal as the only "
        "saturated color, drifting grey ash and orange embers, hairline cracks leaking faint "
        "pale light, an oppressive cursed atmosphere — darker and colder than the base style. "
        "Avoid: any text, letters, captions, watermark, logo, signature; card frame, border "
        "or UI; modern objects, photographic realism, bright cheerful colors; multiple "
        "disconnected subjects, cluttered composition; deformed hands or anatomy."
    ),
    "size": "4704x3520",
    "response_format": "url",
    "extra_body": {
        "watermark": False,
        "sequential_image_generation": "auto",
        "output_format": "png",
        "image": "[3 référence(s), data-URLs omises]",
    },
}


def _project(tmp_path: Path):
    # Arrange : projet v1 complet (bloc provider: anonyme, refs de style réelles)
    (tmp_path / "forge.yaml").write_text(FORGE_V1, encoding="utf-8")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "cards.yaml").write_text(PROMPTS_V1, encoding="utf-8")
    for name in ("a", "b", "c", "x"):
        ref = tmp_path / "reference" / f"{name}.png"
        ref.parent.mkdir(exist_ok=True)
        Image.new("RGB", (8, 8), "gray").save(ref)
    return load_project(tmp_path)


def test_inline_v1_dry_run_requests_are_frozen(tmp_path):
    # Act
    results = generate_kind(_project(tmp_path), "cards", dry_run=True)
    # Assert
    assert [r.id for r in results] == ["lame", "emissaire"]
    assert all(r.dest is None for r in results)
    by_id = {r.id: r.request for r in results}
    assert by_id["lame"] == EXPECTED_LAME
    assert by_id["emissaire"] == EXPECTED_EMISSAIRE


def test_couronnes_dry_run_requests_are_frozen():
    # Act
    results = generate_kind(load_project(EXAMPLE), "cards", dry_run=True)
    # Assert
    assert len(results) == COURONNES_COUNT
    assert [r.id for r in results] == COURONNES_IDS
    by_id = {r.id: r.request for r in results}
    assert by_id["couronne-maudite"] == EXPECTED_COURONNE_MAUDITE
    payload = [{"id": r.id, "request": r.request} for r in results]
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    assert digest == COURONNES_DIGEST
```

- [ ] **Step 3: Vérifier qu'il passe sur le code ACTUEL (pré-refactor)**

Run: `.venv/bin/python -m pytest tests/test_byte_equivalence.py -v`
Expected: `2 passed` (test de caractérisation : vert par construction).

- [ ] **Step 4: Commit**

```bash
git add tests/test_byte_equivalence.py
git commit -m "test: verrou de byte-équivalence des requêtes dry-run (P0)"
```

---

### Task 2: paths.py — chemins multi-assets

**Files:**
- Modify: `src/tableforge/paths.py`
- Test: `tests/test_paths_assets.py` (créé)

**Interfaces:**
- Consumes: rien (module feuille)
- Produces: `MODALITY_BY_ASSET: dict[str, str]`, `extension_for(asset: str, output_format: Optional[str] = None) -> str`, `asset_dir(root: Path, asset: str, kind: str) -> Path`, `asset_path(root: Path, asset: str, kind: str, asset_id: str, output_format: Optional[str] = None) -> Path`. Helpers actuels (`art_dir`, `render_dir`, `art_path`, `render_path`, `sheet_path`) inchangés.

- [ ] **Step 1: Écrire les tests (rouge)**

Créer `tests/test_paths_assets.py` :

```python
from pathlib import Path

from tableforge.paths import art_path, asset_dir, asset_path, extension_for

ROOT = Path("/proj")


def test_extension_for_image_defaults_to_png():
    assert extension_for("image", None) == ".png"
    assert extension_for("image", "webp") == ".webp"


def test_extension_for_audio_follows_output_format_prefix():
    assert extension_for("music", "mp3_44100_128") == ".mp3"
    assert extension_for("sfx", "opus_48000_128") == ".ogg"
    assert extension_for("tts", "pcm_44100") == ".wav"
    assert extension_for("dialogue", "ulaw_8000") == ".wav"
    assert extension_for("music", None) == ".mp3"


def test_extension_for_video_is_mp4():
    assert extension_for("video", None) == ".mp4"


def test_asset_dir_maps_modalities():
    assert asset_dir(ROOT, "image", "cards") == ROOT / "out" / "art" / "cards"
    assert asset_dir(ROOT, "music", "musiques") == ROOT / "out" / "audio" / "musiques"
    assert asset_dir(ROOT, "sfx", "nappes") == ROOT / "out" / "audio" / "nappes"
    assert asset_dir(ROOT, "video", "teaser") == ROOT / "out" / "video" / "teaser"


def test_asset_path_image_matches_art_path():
    assert asset_path(ROOT, "image", "cards", "lame", "png") == art_path(ROOT, "cards", "lame")


def test_asset_path_audio_uses_format_extension():
    expected = ROOT / "out" / "audio" / "nappes" / "cite.mp3"
    assert asset_path(ROOT, "sfx", "nappes", "cite", "mp3_44100_128") == expected
```

- [ ] **Step 2: Vérifier le rouge**

Run: `.venv/bin/python -m pytest tests/test_paths_assets.py -v`
Expected: FAIL — `ImportError: cannot import name 'asset_dir'` (et consorts).

- [ ] **Step 3: Implémenter**

Ajouter à la fin de `src/tableforge/paths.py` (imports : ajouter `from typing import Optional` en tête) :

```python
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
```

- [ ] **Step 4: Vérifier le vert**

Run: `.venv/bin/python -m pytest tests/test_paths_assets.py tests/test_paths.py -v`
Expected: tout PASS (les helpers existants n'ont pas bougé).

- [ ] **Step 5: Commit**

```bash
git add src/tableforge/paths.py tests/test_paths_assets.py
git commit -m "feat: chemins multi-assets (asset_path, extension_for) sans toucher aux helpers v1"
```

---

### Task 3: config.py — providers nommés, kinds multimodaux, normalisation legacy

**Files:**
- Modify: `src/tableforge/config.py`
- Test: `tests/test_config_providers.py` (créé)

**Interfaces:**
- Consumes: rien de nouveau
- Produces (contrat figé, consommé par toutes les phases) :
  - `AssetType = Literal["image", "music", "sfx", "tts", "dialogue", "video"]`
  - `GenerateConfig` (`with_` alias `with`, extras libres + méthode `extras() -> dict`)
  - `SeedreamProviderConfig` (= alias `ProviderConfig`, `type` défaut `"seedream"`), `ElevenLabsProviderConfig`, `HiggsfieldProviderConfig`, `ManualProviderConfig`, `AnyProviderConfig` (union discriminée par `type`)
  - `KindConfig` : + `asset`, `from_` (alias `from`), `generate`, `studio_url` ; `template`/`render_size` deviennent `Optional`
  - `ProjectConfig` : `providers: dict[str, AnyProviderConfig]`, `voices: dict[str, str]`, propriété `provider` dépréciée → `providers["default"]`
  - `load_project` : erreur si `provider:` ET `providers:` ; legacy → `providers={"default": …}` + injection `generate: {with: default}` sur les kinds image avec `prompts:` ; `type:` explicite exigé dans la map `providers:` (par le chargeur)

- [ ] **Step 1: Écrire les tests (rouge)**

Créer `tests/test_config_providers.py` :

```python
from pathlib import Path

import pytest

from tableforge.config import GenerateConfig, load_project

LEGACY = """
project: demo
provider:
  base_url: https://ark.x/api/v3
  api_key_env: ARK_API_KEY
  model: seedream-5-0-260128
kinds:
  cards:
    prompts: prompts/cards.yaml
    template: templates/card
    render_size: {width: 10, height: 10}
  board:
    data: data/board.yaml
    template: templates/board
    render_size: {width: 10, height: 10}
"""

NAMED = """
project: demo
providers:
  ark:
    type: seedream
    base_url: https://ark.x/api/v3
    api_key_env: ARK_API_KEY
    model: seedream-5-0-260128
  eleven:
    type: elevenlabs
voices:
  narrateur: JBFqnCBsd6RMkjVDRZzb
kinds:
  cards:
    prompts: prompts/cards.yaml
    generate: {with: ark}
  narration:
    asset: tts
    data: data/cards.yaml
    generate: {with: eleven, voice: narrateur, text: "{{ name }}"}
  affiche:
    prompts: prompts/affiche.yaml
    generate: {with: manual}
    studio_url: https://example.test/app
"""


def _write(tmp_path: Path, text: str) -> Path:
    (tmp_path / "forge.yaml").write_text(text, encoding="utf-8")
    return tmp_path


def test_legacy_provider_is_normalized_to_default(tmp_path):
    cfg = load_project(_write(tmp_path, LEGACY))
    assert set(cfg.providers) == {"default"}
    assert cfg.providers["default"].type == "seedream"
    assert cfg.provider.model == "seedream-5-0-260128"  # propriété dépréciée


def test_legacy_image_kind_with_prompts_gets_default_generate(tmp_path):
    cfg = load_project(_write(tmp_path, LEGACY))
    assert cfg.kind("cards").generate.with_ == "default"
    assert cfg.kind("board").generate is None  # pas de prompts -> pas d'injection


def test_both_provider_forms_rejected(tmp_path):
    both = LEGACY + "\nproviders:\n  ark:\n    type: seedream\n    base_url: x\n    api_key_env: K\n    model: m\n"
    with pytest.raises(ValueError, match="pas les deux"):
        load_project(_write(tmp_path, both))


def test_named_providers_parse_with_defaults(tmp_path):
    cfg = load_project(_write(tmp_path, NAMED))
    assert cfg.providers["eleven"].base_url == "https://api.elevenlabs.io"
    assert cfg.providers["eleven"].output_format == "mp3_44100_128"
    assert cfg.providers["eleven"].api_key_env == "ELEVENLABS_API_KEY"
    assert cfg.voices == {"narrateur": "JBFqnCBsd6RMkjVDRZzb"}


def test_named_provider_requires_explicit_type(tmp_path):
    text = NAMED.replace("    type: elevenlabs\n", "")
    with pytest.raises(ValueError, match="type"):
        load_project(_write(tmp_path, text))


def test_kind_multimodal_fields(tmp_path):
    cfg = load_project(_write(tmp_path, NAMED))
    narration = cfg.kind("narration")
    assert narration.asset == "tts"
    assert narration.template is None and narration.render_size is None
    assert narration.generate.with_ == "eleven"
    assert narration.generate.extras() == {"voice": "narrateur", "text": "{{ name }}"}
    affiche = cfg.kind("affiche")
    assert affiche.asset == "image"
    assert affiche.studio_url == "https://example.test/app"


def test_from_alias_parses(tmp_path):
    text = NAMED + "  anim:\n    asset: video\n    from: cards\n    prompts: prompts/anim.yaml\n    generate: {with: manual}\n"
    cfg = load_project(_write(tmp_path, text))
    assert cfg.kind("anim").from_ == "cards"


def test_project_without_any_provider_rejected(tmp_path):
    with pytest.raises(ValueError, match="provider"):
        load_project(_write(tmp_path, "project: demo\nkinds: {}\n"))


def test_deprecated_provider_property_without_default_raises(tmp_path):
    cfg = load_project(_write(tmp_path, NAMED))
    with pytest.raises(KeyError, match="default"):
        cfg.provider


def test_generate_config_alias_and_extras():
    gc = GenerateConfig(**{"with": "ark", "voice": "narrateur"})
    assert gc.with_ == "ark"
    assert gc.extras() == {"voice": "narrateur"}
```

- [ ] **Step 2: Vérifier le rouge**

Run: `.venv/bin/python -m pytest tests/test_config_providers.py -v`
Expected: FAIL — `ImportError: cannot import name 'GenerateConfig'`.

- [ ] **Step 3: Implémenter — remplacer intégralement `src/tableforge/config.py` par :**

```python
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


class ManualProviderConfig(BaseModel):
    type: Literal["manual"] = "manual"


AnyProviderConfig = Annotated[
    Union[SeedreamProviderConfig, ElevenLabsProviderConfig,
          HiggsfieldProviderConfig, ManualProviderConfig],
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
_PROVIDER_TYPES = ("seedream", "elevenlabs", "higgsfield", "manual")


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
    for name, block in providers.items():
        if not isinstance(block, dict) or "type" not in block:
            raise ValueError(
                f"provider '{name}' : champ 'type' requis "
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
```

- [ ] **Step 4: Vérifier le vert + la non-régression**

Run: `.venv/bin/python -m pytest tests/test_config_providers.py tests/test_config.py tests/test_byte_equivalence.py -v` puis `.venv/bin/python -m pytest -q`
Expected: tout PASS (la propriété dépréciée `provider` et la normalisation legacy gardent `test_config.py` et le reste de la suite verts).

- [ ] **Step 5: Commit**

```bash
git add src/tableforge/config.py tests/test_config_providers.py
git commit -m "feat: providers nommés + kinds multimodaux dans forge.yaml (compat v1 totale)"
```

---

### Task 4: Package providers/ (git mv, pur refactor)

**Files:**
- Move: `src/tableforge/providers.py` → `src/tableforge/providers/seedream.py`
- Create: `src/tableforge/providers/__init__.py`

**Interfaces:**
- Produces: les imports `from tableforge.providers import SeedreamProvider, build_request, summarize_request, _save_image, DEFAULT_SEQUENTIAL` continuent de fonctionner à l'identique (ré-exports).

- [ ] **Step 1: Déplacer le module**

```bash
mkdir src/tableforge/providers
git mv src/tableforge/providers.py src/tableforge/providers/seedream.py
```

- [ ] **Step 2: Corriger l'import relatif dans `seedream.py`**

Dans `src/tableforge/providers/seedream.py`, remplacer :

```python
from .config import ProviderConfig
```

par :

```python
from ..config import ProviderConfig
```

- [ ] **Step 3: Créer `src/tableforge/providers/__init__.py`**

```python
"""Package providers — ré-exports de compatibilité v1 (à revoir 2026-10)."""
from .seedream import (DEFAULT_SEQUENTIAL, SeedreamProvider, _save_image,
                       build_request, summarize_request)

__all__ = ["DEFAULT_SEQUENTIAL", "SeedreamProvider", "_save_image",
           "build_request", "summarize_request"]
```

- [ ] **Step 4: Vérifier la suite**

Run: `.venv/bin/python -m pytest -q`
Expected: suite verte inchangée (`test_providers.py`, `test_generate.py` importent via le package).

- [ ] **Step 5: Commit**

```bash
git add -A src/tableforge/providers
git commit -m "refactor: providers.py devient le package providers/ (ré-exports compat)"
```

---

### Task 5: providers/base.py — AssetJob, Protocol, résolution, adaptateur legacy

**Files:**
- Create: `src/tableforge/providers/base.py`
- Test: `tests/test_providers_base.py` (créé)

**Interfaces:**
- Consumes: `tableforge.config` (`ProjectConfig`, `KindConfig`), `tableforge.paths.asset_path`, `seedream.summarize_request` (lazy)
- Produces (contrat P1+) : `AssetJob(id, dest, request, payload, notes)`, `Provider` (Protocol `plan`/`execute`), `SUPPORTED_ASSETS`, `resolve_provider_name(project, kind_cfg) -> str`, `ensure_provider(obj) -> Provider`, `_LegacyAdapter`. (`provider_for` arrive en Task 6, une fois le constructeur keyless de Seedream disponible.)

- [ ] **Step 1: Écrire les tests (rouge)**

Créer `tests/test_providers_base.py` :

```python
from pathlib import Path
from types import SimpleNamespace

import pytest

from tableforge.config import load_project
from tableforge.providers.base import (AssetJob, ensure_provider,
                                       resolve_provider_name)

FORGE = """
project: demo
providers:
  ark:
    type: seedream
    base_url: https://ark.x/api/v3
    api_key_env: ARK_API_KEY
    model: seedream-5-0-260128
  eleven:
    type: elevenlabs
kinds:
  cards:
    prompts: prompts/cards.yaml
    generate: {with: ark}
  libre:
    prompts: prompts/libre.yaml
  nappes:
    asset: sfx
    prompts: prompts/nappes.yaml
  affiche:
    prompts: prompts/affiche.yaml
    generate: {with: manual}
"""


def _project(tmp_path: Path):
    (tmp_path / "forge.yaml").write_text(FORGE, encoding="utf-8")
    return load_project(tmp_path)


def test_explicit_with_wins(tmp_path):
    project = _project(tmp_path)
    assert resolve_provider_name(project, project.kind("cards")) == "ark"


def test_manual_is_reserved(tmp_path):
    project = _project(tmp_path)
    assert resolve_provider_name(project, project.kind("affiche")) == "manual"


def test_unknown_with_lists_declared(tmp_path):
    project = _project(tmp_path)
    kind = project.kind("cards").model_copy(deep=True)
    kind.generate.with_ = "typo"
    with pytest.raises(ValueError, match="ark, eleven"):
        resolve_provider_name(project, kind)


def test_auto_resolution_single_candidate(tmp_path):
    project = _project(tmp_path)
    # asset image : seul 'ark' (seedream) sait faire -> auto-résolution
    assert resolve_provider_name(project, project.kind("libre")) == "ark"
    # asset sfx : seul 'eleven' (elevenlabs) sait faire
    assert resolve_provider_name(project, project.kind("nappes")) == "eleven"


def test_auto_resolution_ambiguous_lists_candidates(tmp_path):
    text = FORGE.replace("  eleven:\n    type: elevenlabs\n",
                         "  ark2:\n    type: seedream\n    base_url: https://b.x\n"
                         "    api_key_env: K2\n    model: m2\n")
    (tmp_path / "forge.yaml").write_text(text, encoding="utf-8")
    project = load_project(tmp_path)
    with pytest.raises(ValueError, match="ark, ark2"):
        resolve_provider_name(project, project.kind("libre"))


def test_auto_resolution_no_candidate(tmp_path):
    project = _project(tmp_path)
    kind = project.kind("libre").model_copy(update={"asset": "video"})
    with pytest.raises(ValueError, match="aucun provider"):
        resolve_provider_name(project, kind)


def test_ensure_provider_passthrough_and_wrap(tmp_path):
    class Modern:
        def plan(self, spec):
            return []

        def execute(self, job):
            return []

    modern = Modern()
    assert ensure_provider(modern) is modern

    class Legacy:
        def build(self, prompt, size=None, refs=None):
            return {"prompt": prompt, "size": size}

        def generate(self, prompt, dest, size=None, refs=None):
            return [dest]

    adapter = ensure_provider(Legacy())
    spec = SimpleNamespace(kind="cards", asset="image", root=Path("/proj"),
                           output_format="png",
                           targets=(SimpleNamespace(id="lame", text="A footman.",
                                                    refs=("data:x",),
                                                    settings={"size": "32x32"},
                                                    notes=()),))
    jobs = adapter.plan(spec)
    assert [j.id for j in jobs] == ["lame"]
    assert jobs[0].dest == Path("/proj/out/art/cards/lame.png")
    assert jobs[0].payload == {"prompt": "A footman.", "size": "32x32",
                               "refs": ["data:x"]}
    assert adapter.execute(jobs[0]) == [jobs[0].dest]


def test_asset_job_is_frozen():
    job = AssetJob(id="x", dest=Path("/tmp/x.png"), request={})
    with pytest.raises(Exception):
        job.id = "y"
```

- [ ] **Step 2: Vérifier le rouge**

Run: `.venv/bin/python -m pytest tests/test_providers_base.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tableforge.providers.base'`.

- [ ] **Step 3: Implémenter — créer `src/tableforge/providers/base.py` :**

```python
"""Contrat provider : AssetJob, Protocol plan/execute, résolution du provider d'un kind.

`plan()` est pur et sans clé API ; `execute()` est le seul point réseau. L'adaptateur
legacy enveloppe les objets duck-typés v1 (.build/.generate) — dont les FakeProvider
des tests — pour que `generate_kind` n'ait qu'un seul chemin.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from ..config import KindConfig, ProjectConfig
from ..paths import asset_path

if TYPE_CHECKING:  # pas d'import runtime : targets importe providers.base
    from ..targets import KindSpec

SUPPORTED_ASSETS: dict[str, frozenset[str]] = {
    "seedream": frozenset({"image"}),
    "elevenlabs": frozenset({"music", "sfx", "tts", "dialogue"}),
    "higgsfield": frozenset({"image", "video"}),
    "manual": frozenset({"image", "music", "sfx", "tts", "dialogue", "video"}),
}


@dataclass(frozen=True)
class AssetJob:
    id: str
    dest: Path
    request: dict
    payload: dict = field(default_factory=dict)
    notes: tuple[str, ...] = ()


@runtime_checkable
class Provider(Protocol):
    def plan(self, spec: "KindSpec") -> list[AssetJob]: ...

    def execute(self, job: AssetJob) -> list[Path]: ...


def resolve_provider_name(project: ProjectConfig, kind_cfg: KindConfig) -> str:
    explicit = kind_cfg.generate.with_ if kind_cfg.generate else None
    if explicit is not None:
        if explicit == "manual":
            return "manual"
        if explicit not in project.providers:
            raise ValueError(
                f"kind '{kind_cfg.name}' : provider '{explicit}' inconnu "
                f"(déclarés : {', '.join(project.providers) or 'aucun'})")
        return explicit
    candidates = sorted(name for name, cfg in project.providers.items()
                        if kind_cfg.asset in SUPPORTED_ASSETS[cfg.type])
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise ValueError(
            f"kind '{kind_cfg.name}' : aucun provider déclaré ne sait produire "
            f"l'asset '{kind_cfg.asset}' — ajoute un provider adapté ou "
            "'generate: {with: manual}'")
    raise ValueError(
        f"kind '{kind_cfg.name}' : plusieurs providers possibles pour l'asset "
        f"'{kind_cfg.asset}' ({', '.join(candidates)}) — précise 'generate: {{with: …}}'")


class _LegacyAdapter:
    """Adapte un objet duck-typé v1 (.build/.generate) au contrat plan/execute."""

    def __init__(self, legacy):
        self._legacy = legacy

    def plan(self, spec: "KindSpec") -> list[AssetJob]:
        from .seedream import summarize_request
        jobs = []
        for target in spec.targets:
            size = target.settings.get("size")
            refs = list(target.refs)
            request = summarize_request(self._legacy.build(target.text, size, refs))
            dest = asset_path(spec.root, spec.asset, spec.kind, target.id,
                              spec.output_format)
            jobs.append(AssetJob(id=target.id, dest=dest, request=request,
                                 payload={"prompt": target.text, "size": size,
                                          "refs": refs},
                                 notes=tuple(target.notes)))
        return jobs

    def execute(self, job: AssetJob) -> list[Path]:
        return self._legacy.generate(job.payload["prompt"], job.dest,
                                     size=job.payload.get("size"),
                                     refs=job.payload.get("refs") or None)


def ensure_provider(obj) -> Provider:
    if hasattr(obj, "plan") and hasattr(obj, "execute"):
        return obj
    return _LegacyAdapter(obj)
```

- [ ] **Step 4: Vérifier le vert**

Run: `.venv/bin/python -m pytest tests/test_providers_base.py -v` puis `.venv/bin/python -m pytest -q`
Expected: tout PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tableforge/providers/base.py tests/test_providers_base.py
git commit -m "feat: contrat provider plan/execute (AssetJob, résolution, adaptateur legacy)"
```

---

### Task 6: Seedream — constructeur keyless, clé à l'exécution, plan/execute, provider_for

**Files:**
- Modify: `src/tableforge/providers/seedream.py`
- Modify: `src/tableforge/providers/base.py` (ajout de `provider_for`)
- Test: `tests/test_providers_base.py` (étendu)

**Interfaces:**
- Consumes: `SeedreamProviderConfig`, `base.AssetJob`, `paths.asset_path`
- Produces: `SeedreamProvider.from_provider_config(cfg) -> SeedreamProvider` (keyless), `SeedreamProvider._require_key() -> str`, `SeedreamProvider.plan(spec) -> list[AssetJob]`, `SeedreamProvider.execute(job) -> list[Path]`, `base.provider_for(project, kind_cfg) -> Provider`. **Compat intacte** : `from_config` résout toujours la clé immédiatement (tests existants), `.build`/`.generate` inchangés.

- [ ] **Step 1: Écrire les tests (rouge) — ajouter à `tests/test_providers_base.py` :**

```python
def test_from_provider_config_is_keyless(tmp_path, monkeypatch):
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    from tableforge.providers.seedream import SeedreamProvider
    project = _project(tmp_path)
    provider = SeedreamProvider.from_provider_config(project.providers["ark"])
    assert provider.api_key is None
    assert provider.api_key_env == "ARK_API_KEY"
    assert provider.model == "seedream-5-0-260128"


def test_require_key_reads_env_at_execute_time(tmp_path, monkeypatch):
    from tableforge.providers.seedream import SeedreamProvider
    project = _project(tmp_path)
    provider = SeedreamProvider.from_provider_config(project.providers["ark"])
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ARK_API_KEY"):
        provider._require_key()
    monkeypatch.setenv("ARK_API_KEY", "secret")
    assert provider._require_key() == "secret"


def test_seedream_plan_matches_build_summary(tmp_path, monkeypatch):
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    from tableforge.providers.seedream import (SeedreamProvider,
                                               summarize_request)
    project = _project(tmp_path)
    provider = SeedreamProvider.from_provider_config(project.providers["ark"])
    spec = SimpleNamespace(kind="cards", asset="image", root=Path("/proj"),
                           output_format="png",
                           targets=(SimpleNamespace(id="lame", text="A footman. Dark.",
                                                    refs=("data:x",),
                                                    settings={"size": "32x32"},
                                                    notes=()),))
    jobs = provider.plan(spec)
    assert jobs[0].dest == Path("/proj/out/art/cards/lame.png")
    assert jobs[0].request == summarize_request(
        provider.build("A footman. Dark.", size="32x32", refs=["data:x"]))
    assert jobs[0].payload == {"prompt": "A footman. Dark.", "size": "32x32",
                               "refs": ["data:x"]}


def test_provider_for_builds_keyless_seedream(tmp_path, monkeypatch):
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    from tableforge.providers.base import provider_for
    project = _project(tmp_path)
    provider = provider_for(project, project.kind("cards"))
    assert provider.api_key is None and provider.api_key_env == "ARK_API_KEY"


def test_provider_for_other_types_not_implemented_in_p0(tmp_path):
    from tableforge.providers.base import provider_for
    project = _project(tmp_path)
    with pytest.raises(NotImplementedError):
        provider_for(project, project.kind("nappes"))       # elevenlabs -> P1
    with pytest.raises(NotImplementedError):
        provider_for(project, project.kind("affiche"))      # manual -> P1
```

- [ ] **Step 2: Vérifier le rouge**

Run: `.venv/bin/python -m pytest tests/test_providers_base.py -v`
Expected: FAIL — `from_provider_config` inexistant (AttributeError) sur les nouveaux tests, anciens tests verts.

- [ ] **Step 3: Implémenter dans `src/tableforge/providers/seedream.py`**

Imports en tête : ajouter `from .base import AssetJob` et `from ..paths import asset_path` ; ajouter `TYPE_CHECKING`/`KindSpec` si annoté. Remplacer la dataclass par :

```python
@dataclass(frozen=True)
class SeedreamProvider:
    api_key: Optional[str]
    base_url: str
    model: str
    default_size: str
    watermark: bool
    output_format: str
    api_key_env: Optional[str] = None

    @classmethod
    def from_config(cls, cfg: ProviderConfig) -> "SeedreamProvider":
        # v1 (compat tests) : résout la clé IMMÉDIATEMENT et échoue si absente.
        load_dotenv()
        key = os.environ.get(cfg.api_key_env)
        if not key:
            raise RuntimeError(
                f"{cfg.api_key_env} manquant : copie .env.example vers .env et renseigne ta clé.")
        return cls(api_key=key, base_url=cfg.base_url, model=cfg.model,
                   default_size=cfg.default_size, watermark=cfg.watermark,
                   output_format=cfg.output_format, api_key_env=cfg.api_key_env)

    @classmethod
    def from_provider_config(cls, cfg: ProviderConfig) -> "SeedreamProvider":
        # v2 : keyless — la clé n'est lue qu'à execute() (_require_key).
        return cls(api_key=None, base_url=cfg.base_url, model=cfg.model,
                   default_size=cfg.default_size, watermark=cfg.watermark,
                   output_format=cfg.output_format, api_key_env=cfg.api_key_env)

    def _require_key(self) -> str:
        if self.api_key:
            return self.api_key
        load_dotenv()
        key = os.environ.get(self.api_key_env or "")
        if not key:
            raise RuntimeError(
                f"{self.api_key_env} manquant : copie .env.example vers .env et renseigne ta clé.")
        return key

    def build(self, prompt: str, size: Optional[str] = None,
              refs: Optional[list[str]] = None) -> dict:
        req = build_request(model=self.model, size=size or self.default_size,
                            refs=refs or [], watermark=self.watermark,
                            output_format=self.output_format)
        req["prompt"] = prompt
        return req

    def plan(self, spec) -> list[AssetJob]:
        jobs = []
        for target in spec.targets:
            size = target.settings.get("size") or self.default_size
            refs = list(target.refs)
            request = summarize_request(self.build(target.text, size=size, refs=refs))
            dest = asset_path(spec.root, spec.asset, spec.kind, target.id,
                              self.output_format)
            jobs.append(AssetJob(id=target.id, dest=dest, request=request,
                                 payload={"prompt": target.text, "size": size,
                                          "refs": refs},
                                 notes=tuple(target.notes)))
        return jobs

    def execute(self, job: AssetJob) -> list[Path]:  # pragma: no cover — réseau
        return self.generate(job.payload["prompt"], job.dest,
                             size=job.payload.get("size"),
                             refs=job.payload.get("refs") or None)

    def _client(self):  # pragma: no cover
        from openai import OpenAI
        return OpenAI(api_key=self._require_key(), base_url=self.base_url,
                      max_retries=3, timeout=180.0)

    def generate(self, prompt: str, dest: Path, size: Optional[str] = None,
                 refs: Optional[list[str]] = None) -> list[Path]:  # pragma: no cover
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        response = self._client().images.generate(**self.build(prompt, size, refs))
        saved = [_save_image(response.data[0], dest)]
        for index, item in enumerate(response.data[1:], start=2):
            saved.append(_save_image(item, dest.with_name(f"{dest.stem}-{index}.png")))
        return saved
```

Attention au cycle d'import : `seedream` importe `base` (AssetJob) au niveau module, `base` n'importe `seedream` que paresseusement (déjà le cas en Task 5) — pas de cycle.

Puis ajouter à `src/tableforge/providers/base.py` :

```python
def provider_for(project: ProjectConfig, kind_cfg: KindConfig) -> Provider:
    name = resolve_provider_name(project, kind_cfg)
    if name == "manual":
        raise NotImplementedError(
            "provider 'manual' : disponible en P1 (forge studio)")
    cfg = project.providers[name]
    if cfg.type == "seedream":
        from .seedream import SeedreamProvider
        return SeedreamProvider.from_provider_config(cfg)
    raise NotImplementedError(
        f"provider de type '{cfg.type}' : pas encore implémenté (phases P1+)")
```

- [ ] **Step 4: Vérifier le vert + compat**

Run: `.venv/bin/python -m pytest tests/test_providers_base.py tests/test_providers.py -v` puis `.venv/bin/python -m pytest -q`
Expected: tout PASS — en particulier `test_from_config_requires_key` et `test_from_config_reads_key` (comportement v1 intact).

- [ ] **Step 5: Commit**

```bash
git add src/tableforge/providers/seedream.py src/tableforge/providers/base.py tests/test_providers_base.py
git commit -m "feat: Seedream plan/execute + clé résolue à l'exécution (provider_for keyless)"
```

---

### Task 7: targets.py — build_kind_spec (asset image)

**Files:**
- Create: `src/tableforge/targets.py`
- Test: `tests/test_targets.py` (créé)

**Interfaces:**
- Consumes: `config.ProjectConfig`, `prompts.load_prompts/prompt_for/reference_data_urls`, `providers.base.resolve_provider_name`
- Produces (contrat P1+ — noms et champs EXACTS, P1 utilise `spec.root`) :
  - `DialogueLine(voice_id, text)`, `Target(id, text, voice_id, lines, source_image, settings, refs, notes)`
  - `KindSpec(kind, asset, provider_name, options, targets, root, output_format)`
  - `build_kind_spec(project, kind, ids=None) -> KindSpec` — image OK ; tout autre asset → `NotImplementedError`

- [ ] **Step 1: Écrire les tests (rouge)**

Créer `tests/test_targets.py` :

```python
from pathlib import Path

import pytest

from tableforge.config import load_project
from tableforge.targets import build_kind_spec

FORGE = """
project: demo
providers:
  ark:
    type: seedream
    base_url: https://ark.x/api/v3
    api_key_env: ARK_API_KEY
    model: seedream-5-0-260128
    default_size: "64x64"
  eleven:
    type: elevenlabs
kinds:
  cards:
    prompts: prompts/cards.yaml
    art_size: "32x32"
    generate: {with: ark}
  sans-prompts:
    template: templates/card
    render_size: {width: 10, height: 10}
    generate: {with: ark}
  nappes:
    asset: sfx
    prompts: prompts/nappes.yaml
"""

PROMPTS = """
art_direction: "Dark fantasy."
negative: "Avoid: text."
prompts:
  lame: "A footman."
  emissaire: "A hooded envoy."
"""


def _project(tmp_path: Path):
    (tmp_path / "forge.yaml").write_text(FORGE, encoding="utf-8")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "cards.yaml").write_text(PROMPTS, encoding="utf-8")
    return load_project(tmp_path)


def test_image_spec_resolves_targets_and_settings(tmp_path):
    project = _project(tmp_path)
    spec = build_kind_spec(project, "cards")
    assert (spec.kind, spec.asset, spec.provider_name) == ("cards", "image", "ark")
    assert spec.root == project.root
    assert spec.output_format == "png"
    assert [t.id for t in spec.targets] == ["lame", "emissaire"]
    lame = spec.targets[0]
    assert lame.text == "A footman. Dark fantasy. Avoid: text."
    assert lame.settings == {"size": "32x32"}   # art_size prime sur default_size
    assert lame.refs == ()                       # pas de style_refs déclarées


def test_image_spec_falls_back_to_provider_default_size(tmp_path):
    project = _project(tmp_path)
    kind = project.kind("cards").model_copy(update={"art_size": None})
    project = project.model_copy(update={"kinds": {**project.kinds, "cards": kind}})
    spec = build_kind_spec(project, "cards")
    assert spec.targets[0].settings == {"size": "64x64"}


def test_ids_filter_preserves_order(tmp_path):
    spec = build_kind_spec(_project(tmp_path), "cards", ids=["emissaire"])
    assert [t.id for t in spec.targets] == ["emissaire"]


def test_image_kind_without_prompts_raises(tmp_path):
    with pytest.raises(ValueError, match="prompts"):
        build_kind_spec(_project(tmp_path), "sans-prompts")


def test_non_image_asset_not_implemented_in_p0(tmp_path):
    with pytest.raises(NotImplementedError, match="sfx"):
        build_kind_spec(_project(tmp_path), "nappes")


def test_options_come_from_generate_extras(tmp_path):
    from tableforge.config import GenerateConfig
    project = _project(tmp_path)
    kind = project.kind("cards").model_copy(
        update={"generate": GenerateConfig(**{"with": "ark", "style": "sombre"})})
    project = project.model_copy(update={"kinds": {**project.kinds, "cards": kind}})
    spec = build_kind_spec(project, "cards")
    assert spec.options == {"style": "sombre"}
```

Note : l'extra (`style`) doit être posé À LA CONSTRUCTION de `GenerateConfig` (validation → `__pydantic_extra__`) ; `model_copy(update=…)` ne passe pas par la validation et ne remplirait pas `extras()`.

- [ ] **Step 2: Vérifier le rouge**

Run: `.venv/bin/python -m pytest tests/test_targets.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tableforge.targets'`.

- [ ] **Step 3: Implémenter — créer `src/tableforge/targets.py` :**

```python
"""Résolution des cibles d'un kind (pur, sans clé API ni réseau).

`build_kind_spec` transforme la config + les fichiers data/prompts en un `KindSpec`
immuable que les providers consomment (`plan`). P0 : asset image uniquement ;
les branches music/sfx/tts/dialogue/video arrivent en P1/P2/P3.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .config import KindConfig, ProjectConfig
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
    if kind_cfg.asset == "image":
        targets = _image_targets(project, kind_cfg, provider_cfg, ids)
        output_format = getattr(provider_cfg, "output_format", None)
    else:
        raise NotImplementedError(
            f"asset '{kind_cfg.asset}' : pas encore implémenté (phases P1+)")
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
```

- [ ] **Step 4: Vérifier le vert**

Run: `.venv/bin/python -m pytest tests/test_targets.py -v` puis `.venv/bin/python -m pytest -q`
Expected: tout PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tableforge/targets.py tests/test_targets.py
git commit -m "feat: build_kind_spec — cibles image résolues sans clé (KindSpec/Target)"
```

---

### Task 8: generate.py via plan/execute (refactor, verrou byte-équivalence)

**Files:**
- Modify: `src/tableforge/generate.py` (réécriture complète)

**Interfaces:**
- Consumes: `targets.build_kind_spec`, `providers.base.ensure_provider/provider_for`
- Produces: `GenerateResult(id, dest, request)` et `generate_kind(project, kind, ids=None, dry_run=False, force=False, provider=None)` — signatures et comportement observable STRICTEMENT inchangés.

- [ ] **Step 1: Remplacer intégralement `src/tableforge/generate.py` par :**

```python
"""Orchestration de la génération (toutes modalités) via le contrat plan/execute."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .config import ProjectConfig
from .providers.base import ensure_provider, provider_for
from .targets import build_kind_spec


@dataclass(frozen=True)
class GenerateResult:
    id: str
    dest: Optional[Path]
    request: dict


def generate_kind(project: ProjectConfig, kind: str, ids: Optional[list[str]] = None,
                  dry_run: bool = False, force: bool = False,
                  provider=None) -> list[GenerateResult]:
    spec = build_kind_spec(project, kind, ids)
    if provider is not None:
        provider = ensure_provider(provider)
    else:
        provider = provider_for(project, project.kind(kind))

    results: list[GenerateResult] = []
    for job in provider.plan(spec):
        if dry_run:
            results.append(GenerateResult(job.id, None, job.request))
            continue
        if job.dest.exists() and not force:
            results.append(GenerateResult(job.id, job.dest, {"skipped": "exists"}))
            continue
        provider.execute(job)
        results.append(GenerateResult(job.id, job.dest, job.request))
    return results
```

**Déviation acceptée et documentée (revue Task 8)** : en v1, un appel non-dry-run
sans clé API levait `RuntimeError` AVANT la boucle, même si toutes les destinations
existaient déjà (tout aurait été skippé). Avec plan/execute, la clé n'est lue qu'au
premier `execute()` réel : un run entièrement skippé réussit désormais **sans clé**.
C'est intentionnel — le flux studio (déposer les fichiers à la main puis relancer)
et la relance de `forge all` sans `.env` en dépendent. Seul signal perdu : le message
informatif « (génération ignorée : …) » de `forge all` quand tout existe déjà.

Points de comportement conservés (c'est le filet, pas une intention) :
- dry-run sans clé : `provider_for` construit un Seedream keyless, `plan()` ne lit jamais l'env ;
- `ValueError` « n'a pas de fichier prompts » levée par `build_kind_spec` AVANT toute résolution réseau ;
- provider injecté duck-typé (FakeProvider des tests) → enveloppé par `ensure_provider`, `.generate` jamais appelé sur un art existant sans `--force` ;
- requête d'un id exécuté = `job.request` = `summarize_request(build(...))` (identique à v1).

- [ ] **Step 2: Vérifier les verrous**

Run: `.venv/bin/python -m pytest tests/test_byte_equivalence.py tests/test_generate.py tests/test_example_couronnes.py -v` puis `.venv/bin/python -m pytest -q`
Expected: tout PASS — notamment les 2 tests de byte-équivalence (requêtes identiques au commit `199f667`).

- [ ] **Step 3: Commit**

```bash
git add src/tableforge/generate.py
git commit -m "refactor: generate_kind passe par plan/execute (dry-run via provider, un seul chemin)"
```

---

### Task 9: Gardes CLI pour kinds sans template

**Files:**
- Modify: `src/tableforge/cli.py` (fonctions `_render_kind` et `list_kinds` uniquement)
- Test: `tests/test_cli_guards.py` (créé)

**Interfaces:**
- Consumes: `KindConfig.template/render_size` désormais `Optional`
- Produces: `forge render/board` refusent proprement un kind sans template ; `forge list` tolère les kinds sans template. (Les refus par modalité, « le kind est audio (tts)… », arrivent en P1 — ici garde générique seulement.)

- [ ] **Step 1: Écrire les tests (rouge)**

Créer `tests/test_cli_guards.py` :

```python
from typer.testing import CliRunner

from tableforge.cli import app

runner = CliRunner()

FORGE = """
project: demo
providers:
  ark:
    type: seedream
    base_url: https://ark.x/api/v3
    api_key_env: ARK_API_KEY
    model: seedream-5-0-260128
kinds:
  libre:
    prompts: prompts/libre.yaml
    generate: {with: ark}
"""


def _project(tmp_path):
    (tmp_path / "forge.yaml").write_text(FORGE, encoding="utf-8")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "libre.yaml").write_text(
        "art_direction: 'X.'\nprompts:\n  a: 'A.'\n", encoding="utf-8")
    return tmp_path


def test_render_refuses_template_less_kind(tmp_path):
    res = runner.invoke(app, ["render", "libre", "--project", str(_project(tmp_path))])
    assert res.exit_code != 0
    assert "template" in res.output


def test_list_tolerates_template_less_kind(tmp_path):
    res = runner.invoke(app, ["list", "--project", str(_project(tmp_path))])
    assert res.exit_code == 0
    assert "libre" in res.output


def test_dry_run_works_on_template_less_kind(tmp_path):
    res = runner.invoke(app, ["generate", "libre", "--project",
                              str(_project(tmp_path)), "--dry-run"])
    assert res.exit_code == 0
    assert "a" in res.output
```

- [ ] **Step 2: Vérifier le rouge**

Run: `.venv/bin/python -m pytest tests/test_cli_guards.py -v`
Expected: FAIL — `AttributeError: 'NoneType' object has no attribute 'exists'` (list) et/ou crash render.

- [ ] **Step 3: Implémenter dans `src/tableforge/cli.py`**

Dans `list_kinds`, remplacer la ligne `flags.append("template" if kind.template.exists() else "template?")` par :

```python
        if kind.template:
            flags.append("template" if kind.template.exists() else "template?")
```

Dans `_render_kind`, juste après `kind_cfg = cfg.kind(kind)`, ajouter :

```python
    if kind_cfg.template is None or kind_cfg.render_size is None:
        raise typer.BadParameter(
            f"le kind '{kind}' n'a pas de template — rien à rendre")
```

- [ ] **Step 4: Vérifier le vert**

Run: `.venv/bin/python -m pytest tests/test_cli_guards.py tests/test_cli.py -v` puis `.venv/bin/python -m pytest -q`
Expected: tout PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tableforge/cli.py tests/test_cli_guards.py
git commit -m "fix: gardes CLI pour les kinds sans template (list/render)"
```

---

### Task 10: Vérification finale P0

**Files:** aucun (vérification pure).

- [ ] **Step 1: Suite complète + couverture**

Run: `.venv/bin/python -m pytest -q --cov=tableforge --cov-report=term`
Expected: tout PASS, couverture totale ≥ 80 % (attendu ≈ 95 %+ : `base.py`, `targets.py`, `config.py` sont couverts par les nouveaux tests ; seuls `execute`/`generate`/`_client` de Seedream restent `pragma: no cover`).

- [ ] **Step 2: Vérifier qu'aucun test existant n'a bougé**

Run: `git diff --stat 199f667 -- tests/`
Expected: uniquement des fichiers AJOUTÉS (`test_byte_equivalence.py`, `test_config_providers.py`, `test_paths_assets.py`, `test_providers_base.py`, `test_targets.py`, `test_cli_guards.py`) — zéro ligne modifiée dans les fichiers existants.

- [ ] **Step 3: Fumée CLI sur l'exemple v1 intact**

Run: `.venv/bin/python -m tableforge list -p examples/couronnes && .venv/bin/python -m tableforge generate cards -p examples/couronnes --dry-run | head -3`
Expected: `list` affiche cards/board comme avant ; dry-run liste les 18 ids sans demander de clé.

- [ ] **Step 4: Commit de clôture (si retouches) puis tag de phase**

```bash
git commit -am "chore: clôture P0 — refactor multi-provider à comportement constant" || true
```

---

## Clôture P0

À ce stade : l'architecture multi-provider est en place (providers nommés, plan/execute, cibles, chemins multi-assets), le comportement v1 est prouvé identique (byte-équivalence + suite intacte), et AUCUNE feature nouvelle n'est exposée. P1 (`2026-07-24-multimodal-p1-audio.md`) peut démarrer : ses deux « points d'adaptation » sont résolus par construction (`KindSpec.root` existe, `resolve_provider_name(project, kind_cfg)` est dans `providers/base.py` avec la sémantique attendue).
