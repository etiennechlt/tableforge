# tableforge multimodal — Phase P1 (audio ElevenLabs) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Généraliser l'audio éprouvé de couronnes-cendres dans tableforge : catalogues non-image (`catalog.py`), cibles music/sfx dans `build_kind_spec`, provider ElevenLabs (music + sfx/soundscapes avec loop), hints HTTP français (`errors.py`), provider réservé `manual`, mode studio (`studio.py` + `forge studio`), linter `validate_project` câblé dans `forge list`, refus pédagogiques de render/board/sheet sur les kinds non-image, starter enrichi et `examples/couronnes` migré au format `providers:` avec les vrais catalogues audio (7 musiques, 6 nappes, 15 SFX).

**Architecture:** P0 est mergée : le contrat plan/execute est en place (`providers/base.py` : `AssetJob`, `Provider`, `ensure_provider`, `_LegacyAdapter` ; `providers/seedream.py` ; `targets.build_kind_spec` fonctionne pour `asset: image` et lève `NotImplementedError` pour les autres assets ; `paths.asset_path` ; `config.py` étendu avec providers nommés + normalisation legacy). P1 ajoute la branche audio : `catalog.py` (pur) → `targets` (cibles music/sfx avec settings et notes de clamp) → `providers/elevenlabs.py` (builders purs `{"path","json","params"}` + `execute` httpx) → `providers/manual.py` → registre (`SUPPORTED_ASSETS`, `options_model`, `provider_for`, `validate_project`) → `studio.py` → CLI. `generate_kind` (réécrit en P0, générique) n'est pas modifié : il fonctionne pour l'audio dès que `build_kind_spec` et les providers existent.

**Tech Stack:** Python ≥3.10, pydantic v2, PyYAML, httpx, python-dotenv, typer, pytest, **respx** (nouveau, dev) pour mocker httpx. Venv via uv.

## Global Constraints

- **Toujours `.venv/bin/python`** — jamais `python`/`pip` système. `.venv/bin/python -m pytest -q` doit être vert à la fin de chaque tâche.
- **TDD strict** : test rouge → implémentation minimale → vert → commit. Chaque tâche est un incrément testable indépendamment.
- **Contrat d'interfaces figé** (spec `docs/superpowers/specs/2026-07-24-multimodal-providers-design.md`) : signatures exactes, ne pas renégocier.
- **Doctrine réseau** : tout chemin httpx ElevenLabs est couvert par **respx** (header `xi-api-key`, corps JSON, query params, octets écrits sur disque assertés). Le chemin SDK OpenAI de Seedream reste `pragma: no cover`.
- Couverture ≥ 80 % sur la logique pure (`render.py`, `cli.py`, `__main__.py` exclus par la config coverage existante).
- Dataclasses `frozen=True`, données immuables, modules ≤ ~400 lignes, messages d'erreur **en français**, secrets jamais imprimés (noms de variables d'env uniquement). Code et noms de tests **en anglais**, structure AAA.
- Commits conventionnels en français (`feat:`, `fix:`, `test:`, `chore:`) — pas de ligne d'attribution (désactivée globalement).
- **Deux points d'adaptation P0** (le contrat figé ne précise pas ces détails ; P0 a dû les trancher pour l'asset image) :
  1. Ce plan suppose que `KindSpec` porte un champ `root: Path` (racine du projet — indispensable pour que `plan()` calcule `dest` via `asset_path`). Si P0 a nommé ce champ autrement, utiliser ce nom-là partout où ce plan écrit `spec.root` / `root=project.root`.
  2. Ce plan définit `resolve_provider_name(project, kind_cfg)` dans `providers/base.py`. Si P0 a déjà une fonction équivalente (résolution du nom de provider pour l'image : `with:` explicite, réservation de `manual`, auto-résolution via `SUPPORTED_ASSETS`), remplacer son corps par celui de la Task 5 (le comportement de la Task 5 est le contrat) et n'en garder qu'une.
- **Aucun module de `providers/` n'importe `targets` à l'exécution** (cycle d'import : `targets` → `providers.base`). Tous les fichiers ont `from __future__ import annotations` ; les types `KindSpec`/`Target` en annotation ne nécessitent aucun import runtime. Si P0 a introduit un import runtime de `targets` dans `providers/*`, le déplacer sous `if TYPE_CHECKING:`.
- Si un test écrit « rouge » passe du premier coup (P0 a déjà livré ce comportement, cas possible en Task 3), garder le test comme non-régression, sauter l'étape d'implémentation, et committer le test seul.

---

## Task 1: Dépendance de dev respx

**Files:**
- Modify: `/home/etienne/Documents/tableforge/pyproject.toml`

**Interfaces:**
- Produces: `import respx` fonctionne dans le venv.

- [ ] **Step 1: Ajouter respx aux dev-deps**

Dans `pyproject.toml`, remplacer :
```toml
[project.optional-dependencies]
dev = ["pytest", "pytest-cov"]
```
par :
```toml
[project.optional-dependencies]
dev = ["pytest", "pytest-cov", "respx"]
```

- [ ] **Step 2: Installer et vérifier**

```bash
cd /home/etienne/Documents/tableforge
uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/python -c "import respx; print(respx.__version__)"
```
Attendu : un numéro de version s'affiche (ex. `0.22.0`), pas d'erreur.

- [ ] **Step 3: Suite verte + commit**

```bash
.venv/bin/python -m pytest -q
```
Attendu : tous les tests passent.

```bash
git add pyproject.toml && git commit -m "chore: respx en dépendance de dev (mocks httpx)"
```

---

## Task 2: catalog.py — catalogues non-image

Port épuré de `couronnes-cendres/src/couronnes/media.py` : clé **`entries:` uniquement** (plus de `tracks`/`soundscapes`/`sfx`/`models`/`items`), pas de `intent_to_sfx`, pas de chargeurs à chemin par défaut.

**Files:**
- Create: `/home/etienne/Documents/tableforge/src/tableforge/catalog.py`
- Test: `/home/etienne/Documents/tableforge/tests/test_catalog.py`

**Interfaces:**
- Produces:
  - `MUSIC_MIN_MS: int = 3000`, `MUSIC_MAX_MS: int = 600000`, `SFX_MIN_S: float = 0.5`, `SFX_MAX_S: float = 30.0`, `DEFAULT_MUSIC_LENGTH_MS: int = 90000`
  - `load_catalog(path: Path) -> dict`
  - `catalog_entries(cfg: dict) -> dict` (clé `entries` uniquement, `KeyError` français sinon)
  - `get_entry(cfg: dict, entry_id: str) -> dict` (entrée `str` → `{"prompt": str}`)
  - `build_media_prompt(subject: str, direction: str) -> str`
  - `prompt_for_entry(entry_id: str, cfg: dict, *, with_negative: bool = True) -> str`
  - `clamp_music_length_ms(value: int) -> int`, `clamp_sfx_duration_s(value: float) -> float`

- [ ] **Step 1: Écrire le test rouge**

`tests/test_catalog.py` :
```python
from pathlib import Path

import pytest

from tableforge.catalog import (
    MUSIC_MAX_MS,
    MUSIC_MIN_MS,
    SFX_MAX_S,
    SFX_MIN_S,
    build_media_prompt,
    catalog_entries,
    clamp_music_length_ms,
    clamp_sfx_duration_s,
    get_entry,
    load_catalog,
    prompt_for_entry,
)

CATALOG = {
    "direction": "Epic orchestral score.",
    "negative": "No vocals.",
    "defaults": {"length_ms": 60000},
    "entries": {
        "menu": {"prompt": "Main theme", "length_ms": 90000},
        "raw": "Just a bare prompt",
    },
}


def test_load_catalog_reads_yaml(tmp_path: Path):
    path = tmp_path / "music.yaml"
    path.write_text("direction: Epic.\nentries:\n  menu: {prompt: Theme}\n", encoding="utf-8")
    cfg = load_catalog(path)
    assert cfg["direction"] == "Epic."
    assert cfg["entries"]["menu"]["prompt"] == "Theme"


def test_catalog_entries_requires_entries_key():
    with pytest.raises(KeyError, match="entries"):
        catalog_entries({"tracks": {}})
    assert catalog_entries(CATALOG)["menu"]["length_ms"] == 90000


def test_get_entry_wraps_bare_string():
    assert get_entry(CATALOG, "raw") == {"prompt": "Just a bare prompt"}


def test_get_entry_unknown_id_raises_french():
    with pytest.raises(KeyError, match="aucune entrée"):
        get_entry(CATALOG, "nope")


def test_build_media_prompt_joins_subject_and_direction():
    assert build_media_prompt("A theme.", "Epic score.") == "A theme. Epic score."
    assert build_media_prompt("A theme", "") == "A theme."


def test_prompt_for_entry_folds_negative():
    text = prompt_for_entry("menu", CATALOG)
    assert text == "Main theme. Epic orchestral score. No vocals."


def test_prompt_for_entry_without_negative():
    text = prompt_for_entry("menu", CATALOG, with_negative=False)
    assert text == "Main theme. Epic orchestral score."


def test_clamp_music_length_bounds():
    assert clamp_music_length_ms(1000) == MUSIC_MIN_MS
    assert clamp_music_length_ms(700000) == MUSIC_MAX_MS
    assert clamp_music_length_ms(90000) == 90000


def test_clamp_sfx_duration_bounds():
    assert clamp_sfx_duration_s(0.1) == SFX_MIN_S
    assert clamp_sfx_duration_s(60) == SFX_MAX_S
    assert clamp_sfx_duration_s(2.5) == 2.5
```

- [ ] **Step 2: Vérifier l'échec**

```bash
.venv/bin/python -m pytest tests/test_catalog.py -v
```
Attendu : échec de collecte, `ModuleNotFoundError: No module named 'tableforge.catalog'`.

- [ ] **Step 3: Implémentation**

`src/tableforge/catalog.py` :
```python
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
```

- [ ] **Step 4: Vert + commit**

```bash
.venv/bin/python -m pytest tests/test_catalog.py -v
```
Attendu : `9 passed`.

```bash
.venv/bin/python -m pytest -q
git add src/tableforge/catalog.py tests/test_catalog.py
git commit -m "feat: catalog.py — catalogues non-image (entries, prompts, clamps)"
```

---

## Task 3: Extensions audio de paths.py

P0 a livré `MODALITY_BY_ASSET`, `extension_for`, `asset_dir`, `asset_path` pour l'image. Cette tâche garantit le mapping audio (`mp3_*` → `.mp3`, `opus_*` → `.ogg`, `pcm_*`/`ulaw_*`/`alaw_*` → `.wav`, défaut `.mp3`) et `out/audio/<kind>`.

**Files:**
- Modify: `/home/etienne/Documents/tableforge/src/tableforge/paths.py` (seulement si le test est rouge)
- Test: `/home/etienne/Documents/tableforge/tests/test_paths_audio.py`

**Interfaces:**
- Consumes: `MODALITY_BY_ASSET`, `asset_dir(root, asset, kind)`, `asset_path(root, asset, kind, asset_id, output_format=None)` (P0).
- Produces: `extension_for(asset: str, output_format: Optional[str]) -> str` couvrant les formats audio.

- [ ] **Step 1: Écrire le test**

`tests/test_paths_audio.py` :
```python
from pathlib import Path

from tableforge import paths


def test_extension_for_audio_formats():
    assert paths.extension_for("music", "mp3_44100_128") == ".mp3"
    assert paths.extension_for("sfx", None) == ".mp3"
    assert paths.extension_for("tts", "opus_48000_64") == ".ogg"
    assert paths.extension_for("dialogue", "pcm_16000") == ".wav"
    assert paths.extension_for("music", "ulaw_8000") == ".wav"
    assert paths.extension_for("music", "alaw_8000") == ".wav"


def test_extension_for_image_and_video():
    assert paths.extension_for("image", None) == ".png"
    assert paths.extension_for("image", "jpeg") == ".jpeg"
    assert paths.extension_for("video", None) == ".mp4"


def test_asset_path_audio():
    root = Path("/proj")
    assert paths.asset_dir(root, "music", "musiques") == root / "out" / "audio" / "musiques"
    assert (paths.asset_path(root, "sfx", "nappes", "fleau", "mp3_44100_128")
            == root / "out" / "audio" / "nappes" / "fleau.mp3")
```

- [ ] **Step 2: Lancer**

```bash
.venv/bin/python -m pytest tests/test_paths_audio.py -v
```
Deux issues possibles :
- **Rouge** (P0 n'a couvert que l'image) → Step 3.
- **Vert** (`3 passed`, P0 avait déjà tout) → sauter Step 3, committer le test seul (Step 4).

- [ ] **Step 3: Implémentation (si rouge)**

Dans `src/tableforge/paths.py`, remplacer le corps de `extension_for` par (en conservant la signature P0) :
```python
def extension_for(asset: str, output_format: Optional[str] = None) -> str:
    if asset == "image":
        return f".{output_format or 'png'}"
    if asset == "video":
        return ".mp4"
    fmt = output_format or "mp3"
    if fmt.startswith(("pcm_", "ulaw_", "alaw_")):
        return ".wav"
    if fmt.startswith("opus_"):
        return ".ogg"
    return ".mp3"
```
(ajouter `from typing import Optional` en tête si absent). Vérifier que `MODALITY_BY_ASSET` contient bien :
```python
MODALITY_BY_ASSET = {"image": "art", "music": "audio", "sfx": "audio", "tts": "audio",
                     "dialogue": "audio", "video": "video"}
```

- [ ] **Step 4: Vert + commit**

```bash
.venv/bin/python -m pytest tests/test_paths_audio.py -v && .venv/bin/python -m pytest -q
```
Attendu : `3 passed` puis suite complète verte.

```bash
git add src/tableforge/paths.py tests/test_paths_audio.py
git commit -m "feat: chemins audio (extension_for mp3/ogg/wav, out/audio/<kind>)"
```
(ou `test: non-régression chemins audio` si Step 3 a été sauté).

---

## Task 4: errors.py — hints HTTP français partagés

**Files:**
- Create: `/home/etienne/Documents/tableforge/src/tableforge/errors.py`
- Test: `/home/etienne/Documents/tableforge/tests/test_errors.py`

**Interfaces:**
- Produces:
  - `hint_for_status(status: int, *, provider_type: str, asset: str, kind: str) -> Optional[str]`
  - `raise_with_hint(response: httpx.Response, *, provider_type: str, asset: str, kind: str) -> None` (lève `RuntimeError` français si la réponse n'est pas un succès ; sinon ne fait rien).

- [ ] **Step 1: Écrire le test rouge**

`tests/test_errors.py` :
```python
import httpx
import pytest

from tableforge.errors import hint_for_status, raise_with_hint


def test_hint_401_mentions_key_permissions():
    hint = hint_for_status(401, provider_type="elevenlabs", asset="music", kind="musiques")
    assert "clé" in hint


def test_hint_402_music_points_to_studio():
    hint = hint_for_status(402, provider_type="elevenlabs", asset="music", kind="musiques")
    assert "/v1/music exige un plan payant" in hint
    assert "forge studio musiques" in hint


def test_hint_402_outside_elevenlabs_music_is_none():
    assert hint_for_status(402, provider_type="seedream", asset="image", kind="cards") is None
    assert hint_for_status(402, provider_type="elevenlabs", asset="sfx", kind="sfx") is None


def test_hint_404_422_429():
    assert "modèle" in hint_for_status(404, provider_type="higgsfield", asset="video", kind="teaser")
    assert "bornes" in hint_for_status(422, provider_type="elevenlabs", asset="sfx", kind="sfx")
    assert "quota" in hint_for_status(429, provider_type="elevenlabs", asset="music", kind="musiques")


def test_hint_unknown_status_is_none():
    assert hint_for_status(500, provider_type="elevenlabs", asset="music", kind="musiques") is None


def test_raise_with_hint_passes_on_success():
    result = raise_with_hint(httpx.Response(200), provider_type="elevenlabs",
                             asset="music", kind="musiques")
    assert result is None


def test_raise_with_hint_raises_french_message_with_hint_and_detail():
    response = httpx.Response(402, text='{"detail": "payment required"}')
    with pytest.raises(RuntimeError) as exc:
        raise_with_hint(response, provider_type="elevenlabs", asset="music", kind="musiques")
    message = str(exc.value)
    assert "elevenlabs a répondu 402" in message
    assert "musiques" in message
    assert "payment required" in message
    assert "forge studio musiques" in message


def test_raise_with_hint_without_hint_still_raises():
    with pytest.raises(RuntimeError, match="a répondu 500"):
        raise_with_hint(httpx.Response(500, text="boom"), provider_type="elevenlabs",
                        asset="music", kind="musiques")
```

- [ ] **Step 2: Vérifier l'échec**

```bash
.venv/bin/python -m pytest tests/test_errors.py -v
```
Attendu : `ModuleNotFoundError: No module named 'tableforge.errors'`.

- [ ] **Step 3: Implémentation**

`src/tableforge/errors.py` :
```python
"""Hints HTTP partagés entre providers — messages d'erreur français actionnables."""
from __future__ import annotations

from typing import Optional

import httpx

_MAX_DETAIL_CHARS = 200


def hint_for_status(status: int, *, provider_type: str, asset: str,
                    kind: str) -> Optional[str]:
    if status == 401:
        return (f"clé refusée par {provider_type} : vérifie la variable d'env "
                "et les permissions de la clé.")
    if status == 402 and provider_type == "elevenlabs" and asset == "music":
        return (f"/v1/music exige un plan payant — utilise `forge studio {kind}` "
                "pour générer via l'interface web.")
    if status == 404:
        return "endpoint ou modèle inconnu : vérifie le slug/model déclaré pour ce provider."
    if status == 422:
        return "paramètres hors bornes : vérifie durées, formats et tailles demandés."
    if status == 429:
        return "quota atteint : réessaie plus tard ou réduis le nombre de cibles."
    return None


def raise_with_hint(response: httpx.Response, *, provider_type: str, asset: str,
                    kind: str) -> None:
    if response.is_success:
        return
    detail = response.text[:_MAX_DETAIL_CHARS].strip()
    message = (f"{provider_type} a répondu {response.status_code} "
               f"pour le kind '{kind}' ({asset})")
    if detail:
        message += f" : {detail}"
    hint = hint_for_status(response.status_code, provider_type=provider_type,
                           asset=asset, kind=kind)
    if hint:
        message += f"\n→ {hint}"
    raise RuntimeError(message)
```

- [ ] **Step 4: Vert + commit**

```bash
.venv/bin/python -m pytest tests/test_errors.py -v && .venv/bin/python -m pytest -q
```
Attendu : `8 passed` puis suite verte.

```bash
git add src/tableforge/errors.py tests/test_errors.py
git commit -m "feat: errors.py — hints HTTP français partagés (401/402/404/422/429)"
```

---

## Task 5: Registre providers — capacités, résolution du nom, options music/sfx

**Files:**
- Modify: `/home/etienne/Documents/tableforge/src/tableforge/providers/base.py`
- Test: `/home/etienne/Documents/tableforge/tests/test_provider_registry.py`

**Interfaces:**
- Consumes: `ProjectConfig`, `KindConfig` (config P0).
- Produces:
  - `SUPPORTED_ASSETS: dict[str, frozenset[str]]` complet (4 types)
  - `resolve_provider_name(project: ProjectConfig, kind_cfg: KindConfig) -> str`
  - `MusicOptions` (`length_ms: Optional[int]`, `extra="forbid"`), `SfxOptions` (`duration_s: Optional[float]`, `loop: Optional[bool]`, `extra="forbid"`)
  - `options_model(provider_type: str, asset: str) -> Optional[type[BaseModel]]`

- [ ] **Step 1: Écrire le test rouge**

`tests/test_provider_registry.py` :
```python
import pytest
from pydantic import ValidationError

from tableforge.config import load_project
from tableforge.providers.base import (
    SUPPORTED_ASSETS,
    options_model,
    resolve_provider_name,
)

FORGE_TWO = """
project: demo
providers:
  ark:
    type: seedream
    base_url: https://ark.x/api/v3
    api_key_env: ARK_API_KEY
    model: seedream-5-0-260128
  eleven: { type: elevenlabs }
kinds:
  musiques:
    asset: music
    prompts: prompts/musiques.yaml
    generate: { with: eleven }
  nappes:
    asset: sfx
    prompts: prompts/nappes.yaml
  fantome:
    asset: music
    prompts: prompts/musiques.yaml
    generate: { with: nexiste }
  mauvais:
    asset: music
    prompts: prompts/musiques.yaml
    generate: { with: ark }
  atelier:
    asset: sfx
    prompts: prompts/sfx.yaml
    generate: { with: manual }
"""

FORGE_NO_CANDIDATE = """
project: demo
providers:
  ark:
    type: seedream
    base_url: https://ark.x/api/v3
    api_key_env: ARK_API_KEY
    model: seedream-5-0-260128
kinds:
  musiques: { asset: music, prompts: prompts/m.yaml }
"""

FORGE_AMBIGUOUS = """
project: demo
providers:
  a: { type: elevenlabs }
  b: { type: elevenlabs }
kinds:
  musiques: { asset: music, prompts: prompts/m.yaml }
"""


def _project(tmp_path, text=FORGE_TWO):
    (tmp_path / "forge.yaml").write_text(text, encoding="utf-8")
    return load_project(tmp_path)


def test_supported_assets_table():
    assert SUPPORTED_ASSETS["seedream"] == frozenset({"image"})
    assert SUPPORTED_ASSETS["elevenlabs"] == frozenset({"music", "sfx", "tts", "dialogue"})
    assert SUPPORTED_ASSETS["higgsfield"] == frozenset({"image", "video"})
    assert SUPPORTED_ASSETS["manual"] == frozenset(
        {"image", "music", "sfx", "tts", "dialogue", "video"})


def test_resolve_explicit_provider(tmp_path):
    project = _project(tmp_path)
    assert resolve_provider_name(project, project.kind("musiques")) == "eleven"


def test_resolve_auto_single_candidate(tmp_path):
    project = _project(tmp_path)
    assert resolve_provider_name(project, project.kind("nappes")) == "eleven"


def test_resolve_manual_is_reserved(tmp_path):
    project = _project(tmp_path)
    assert resolve_provider_name(project, project.kind("atelier")) == "manual"


def test_resolve_unknown_provider_raises(tmp_path):
    project = _project(tmp_path)
    with pytest.raises(ValueError, match="provider 'nexiste' inconnu"):
        resolve_provider_name(project, project.kind("fantome"))


def test_resolve_incapable_provider_raises(tmp_path):
    project = _project(tmp_path)
    with pytest.raises(ValueError, match="ne sait pas générer"):
        resolve_provider_name(project, project.kind("mauvais"))


def test_resolve_no_candidate_raises(tmp_path):
    project = _project(tmp_path, FORGE_NO_CANDIDATE)
    with pytest.raises(ValueError, match="aucun provider"):
        resolve_provider_name(project, project.kind("musiques"))


def test_resolve_ambiguous_lists_candidates(tmp_path):
    project = _project(tmp_path, FORGE_AMBIGUOUS)
    with pytest.raises(ValueError, match="a, b"):
        resolve_provider_name(project, project.kind("musiques"))


def test_options_model_music_forbids_unknown_keys():
    model = options_model("elevenlabs", "music")
    assert model(length_ms=60000).length_ms == 60000
    with pytest.raises(ValidationError):
        model(voice="narrateur")


def test_options_model_sfx_and_unknown_pairs():
    model = options_model("elevenlabs", "sfx")
    opts = model(duration_s=2.0, loop=True)
    assert opts.duration_s == 2.0
    assert opts.loop is True
    assert options_model("elevenlabs", "video") is None
```

- [ ] **Step 2: Vérifier l'échec**

```bash
.venv/bin/python -m pytest tests/test_provider_registry.py -v
```
Attendu : `ImportError` (noms manquants dans `tableforge.providers.base`) ou échecs d'assertion si P0 a des stubs partiels.

- [ ] **Step 3: Implémentation dans providers/base.py**

Ajouter (ou remplacer les stubs P0 du même nom par) les définitions suivantes. Imports à garantir en tête de `providers/base.py` :
```python
from typing import Optional
from pydantic import BaseModel, ConfigDict
from ..config import KindConfig, ProjectConfig
```

```python
SUPPORTED_ASSETS: dict[str, frozenset[str]] = {
    "seedream": frozenset({"image"}),
    "elevenlabs": frozenset({"music", "sfx", "tts", "dialogue"}),
    "higgsfield": frozenset({"image", "video"}),
    "manual": frozenset({"image", "music", "sfx", "tts", "dialogue", "video"}),
}


def resolve_provider_name(project: ProjectConfig, kind_cfg: KindConfig) -> str:
    """Nom du provider d'un kind : `with:` explicite, `manual` réservé, sinon
    auto-résolution si exactement un provider déclaré sait produire l'asset."""
    asset = kind_cfg.asset
    with_ = kind_cfg.generate.with_ if kind_cfg.generate else None
    if with_ == "manual":
        return "manual"
    if with_ is not None:
        if with_ not in project.providers:
            declared = ", ".join(project.providers) or "aucun"
            raise ValueError(
                f"kind '{kind_cfg.name}' : provider '{with_}' inconnu (déclarés : {declared})")
        provider_type = project.providers[with_].type
        if asset not in SUPPORTED_ASSETS[provider_type]:
            raise ValueError(
                f"kind '{kind_cfg.name}' : le provider '{with_}' (type {provider_type}) "
                f"ne sait pas générer l'asset '{asset}'")
        return with_
    candidates = [name for name, cfg in project.providers.items()
                  if asset in SUPPORTED_ASSETS[cfg.type]]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise ValueError(
            f"kind '{kind_cfg.name}' : aucun provider déclaré ne sait générer "
            f"l'asset '{asset}' — déclare-en un dans providers: ou utilise "
            "generate: {with: manual}")
    raise ValueError(
        f"kind '{kind_cfg.name}' : plusieurs providers savent générer '{asset}' "
        f"({', '.join(candidates)}) — précise generate: {{with: …}}")


class MusicOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    length_ms: Optional[int] = None


class SfxOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    duration_s: Optional[float] = None
    loop: Optional[bool] = None


_OPTION_MODELS: dict[tuple[str, str], type[BaseModel]] = {
    ("elevenlabs", "music"): MusicOptions,
    ("elevenlabs", "sfx"): SfxOptions,
}


def options_model(provider_type: str, asset: str) -> Optional[type[BaseModel]]:
    return _OPTION_MODELS.get((provider_type, asset))
```

Si P0 a déjà un `_OPTION_MODELS` (ex. une entrée `("seedream", "image")`), **compléter** le dict existant avec les deux entrées elevenlabs au lieu de le remplacer.

- [ ] **Step 4: Vert + commit**

```bash
.venv/bin/python -m pytest tests/test_provider_registry.py -v && .venv/bin/python -m pytest -q
```
Attendu : `10 passed` puis suite verte.

```bash
git add src/tableforge/providers/base.py tests/test_provider_registry.py
git commit -m "feat: registre providers — capacités, résolution du nom, options music/sfx"
```

---

## Task 6: targets.build_kind_spec — cibles music et sfx

**Files:**
- Modify: `/home/etienne/Documents/tableforge/src/tableforge/targets.py`
- Test: `/home/etienne/Documents/tableforge/tests/test_targets_audio.py`

**Interfaces:**
- Consumes: `catalog.py` (Task 2), `resolve_provider_name` (Task 5), `Target`/`KindSpec` (P0).
- Produces: `build_kind_spec(project, kind, ids=None)` fonctionne pour `asset in ("music", "sfx")` — settings résolus (précédence : entrée > `defaults:` du catalogue > extras de `generate:` du kind), notes de clamp visibles, `output_format` du catalogue propagé.

- [ ] **Step 1: Écrire le test rouge**

`tests/test_targets_audio.py` :
```python
import pytest

from tableforge.config import load_project
from tableforge.targets import build_kind_spec

FORGE = """
project: demo-audio
providers:
  eleven: { type: elevenlabs }
kinds:
  musiques:
    asset: music
    prompts: prompts/musiques.yaml
    generate: { with: eleven }
  nappes:
    asset: sfx
    prompts: prompts/nappes.yaml
    generate: { with: eleven }
  sfx:
    asset: sfx
    prompts: prompts/sfx.yaml
    generate: { with: eleven, duration_s: 2.0 }
"""

MUSIC = """
direction: "Epic orchestral score."
negative: "No vocals."
defaults: { length_ms: 60000 }
output_format: mp3_44100_128
entries:
  menu: { prompt: "Main theme" }
  long: { prompt: "Too long", length_ms: 700000 }
"""

NAPPES = """
direction: "Ambient loop."
defaults: { loop: true, duration_s: 30 }
entries:
  cite: { prompt: "City murmur" }
"""

SFX = """
direction: "Punchy effect."
entries:
  draw: { prompt: "Card swish", duration_s: 0.8 }
  clic: { prompt: "Soft click" }
"""


def _project(tmp_path):
    (tmp_path / "forge.yaml").write_text(FORGE, encoding="utf-8")
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "musiques.yaml").write_text(MUSIC, encoding="utf-8")
    (prompts / "nappes.yaml").write_text(NAPPES, encoding="utf-8")
    (prompts / "sfx.yaml").write_text(SFX, encoding="utf-8")
    return load_project(tmp_path)


def test_music_spec_resolves_targets_and_defaults(tmp_path):
    project = _project(tmp_path)
    spec = build_kind_spec(project, "musiques")
    assert spec.asset == "music"
    assert spec.provider_name == "eleven"
    assert spec.output_format == "mp3_44100_128"
    assert spec.root == project.root
    menu = next(t for t in spec.targets if t.id == "menu")
    assert menu.text == "Main theme. Epic orchestral score. No vocals."
    assert menu.settings == {"length_ms": 60000}
    assert menu.notes == ()


def test_music_length_clamped_with_visible_note(tmp_path):
    spec = build_kind_spec(_project(tmp_path), "musiques")
    long = next(t for t in spec.targets if t.id == "long")
    assert long.settings == {"length_ms": 600000}
    assert any("700000" in note and "600000" in note for note in long.notes)


def test_sfx_loop_and_duration_from_catalog_defaults(tmp_path):
    spec = build_kind_spec(_project(tmp_path), "nappes")
    cite = spec.targets[0]
    assert cite.settings == {"loop": True, "duration_s": 30.0}


def test_sfx_entry_overrides_kind_option(tmp_path):
    spec = build_kind_spec(_project(tmp_path), "sfx")
    draw = next(t for t in spec.targets if t.id == "draw")
    clic = next(t for t in spec.targets if t.id == "clic")
    assert draw.settings["duration_s"] == 0.8   # entrée > option generate: du kind
    assert clic.settings["duration_s"] == 2.0   # option generate: du kind
    assert draw.settings["loop"] is False


def test_ids_filter_and_unknown_id(tmp_path):
    project = _project(tmp_path)
    spec = build_kind_spec(project, "musiques", ids=["menu"])
    assert [t.id for t in spec.targets] == ["menu"]
    with pytest.raises(KeyError, match="aucune entrée"):
        build_kind_spec(project, "musiques", ids=["nope"])


def test_music_kind_without_prompts_raises(tmp_path):
    _project(tmp_path)
    forge = FORGE.replace("    prompts: prompts/musiques.yaml\n", "")
    (tmp_path / "forge.yaml").write_text(forge, encoding="utf-8")
    project = load_project(tmp_path)
    with pytest.raises(ValueError, match="prompts"):
        build_kind_spec(project, "musiques")
```

- [ ] **Step 2: Vérifier l'échec**

```bash
.venv/bin/python -m pytest tests/test_targets_audio.py -v
```
Attendu : échecs `NotImplementedError` (la branche P0 pour les assets non-image).

- [ ] **Step 3: Implémentation**

Dans `src/tableforge/targets.py` :

1. Ajouter les imports :
```python
from .catalog import (DEFAULT_MUSIC_LENGTH_MS, MUSIC_MAX_MS, MUSIC_MIN_MS,
                      SFX_MAX_S, SFX_MIN_S, catalog_entries, clamp_music_length_ms,
                      clamp_sfx_duration_s, get_entry, load_catalog, prompt_for_entry)
from .providers.base import resolve_provider_name
```

2. Dans `build_kind_spec`, **avant** la levée de `NotImplementedError` pour les assets non-image, insérer :
```python
    if kind_cfg.asset in ("music", "sfx"):
        return _audio_spec(project, kind_cfg, ids)
```
(`kind_cfg` est la variable locale P0 issue de `project.kind(kind)` ; adapter le nom si P0 l'a nommée autrement.)

3. Ajouter en fin de module :
```python
def _first_set(*values):
    for value in values:
        if value is not None:
            return value
    return None


def _generate_options(kind_cfg: KindConfig) -> dict:
    if kind_cfg.generate is None:
        return {}
    return dict(kind_cfg.generate.model_extra or {})
```
(Si P0 expose déjà un helper équivalent pour les extras de `generate:`, l'utiliser à la place et ne pas dupliquer.)

```python
def _load_kind_catalog(kind_cfg: KindConfig) -> dict:
    if kind_cfg.prompts is None:
        raise ValueError(
            f"le kind '{kind_cfg.name}' ({kind_cfg.asset}) n'a pas de fichier prompts (catalogue)")
    return load_catalog(kind_cfg.prompts)


def _catalog_ids(catalog_cfg: dict, ids: Optional[list[str]]) -> list[str]:
    if ids:
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


def _audio_spec(project: ProjectConfig, kind_cfg: KindConfig,
                ids: Optional[list[str]]) -> KindSpec:
    catalog_cfg = _load_kind_catalog(kind_cfg)
    options = _generate_options(kind_cfg)
    if kind_cfg.asset == "music":
        targets = _music_targets(catalog_cfg, options, ids)
    else:
        targets = _sfx_targets(catalog_cfg, options, ids)
    return KindSpec(kind=kind_cfg.name, asset=kind_cfg.asset,
                    provider_name=resolve_provider_name(project, kind_cfg),
                    options=options, targets=targets,
                    output_format=catalog_cfg.get("output_format"),
                    root=project.root)
```
(`root=project.root` : voir le point d'adaptation n°1 des Global Constraints.)

- [ ] **Step 4: Vert + commit**

```bash
.venv/bin/python -m pytest tests/test_targets_audio.py -v && .venv/bin/python -m pytest -q
```
Attendu : `6 passed` puis suite verte.

```bash
git add src/tableforge/targets.py tests/test_targets_audio.py
git commit -m "feat: cibles music/sfx dans build_kind_spec (settings, clamps, notes)"
```

---

## Task 7: providers/elevenlabs.py — music + sfx (plan/execute, respx)

**Files:**
- Create: `/home/etienne/Documents/tableforge/src/tableforge/providers/elevenlabs.py`
- Test: `/home/etienne/Documents/tableforge/tests/test_elevenlabs.py`

**Interfaces:**
- Consumes: `ElevenLabsProviderConfig` (config P0), `clamp_*` (Task 2), `raise_with_hint` (Task 4), `asset_path` (Task 3), `AssetJob` (P0).
- Produces:
  - `DEFAULT_TIMEOUT = 180.0`, `MUSIC_PATH = "/v1/music"`, `SFX_PATH = "/v1/sound-generation"`
  - `build_music_request(prompt, *, length_ms, output_format) -> dict` — `{"path", "json": {"prompt", "music_length_ms"}, "params": {"output_format"}}`
  - `build_sfx_request(text, *, duration_s, loop, model, output_format) -> dict` — `{"path", "json": {"text", "model_id", "loop"[, "duration_seconds"]}, "params": {...}}`
  - `ElevenLabsProvider` (frozen, **sans clé** — `api_key_env` seulement) : `from_config`, `plan(spec) -> list[AssetJob]`, `execute(job) -> list[Path]`.

- [ ] **Step 1: Écrire le test rouge**

`tests/test_elevenlabs.py` :
```python
import json
from pathlib import Path

import httpx
import pytest
import respx

from tableforge.config import ElevenLabsProviderConfig
from tableforge.providers.base import AssetJob
from tableforge.providers.elevenlabs import (
    ElevenLabsProvider,
    build_music_request,
    build_sfx_request,
)
from tableforge.targets import KindSpec, Target


def _provider() -> ElevenLabsProvider:
    return ElevenLabsProvider.from_config(ElevenLabsProviderConfig(type="elevenlabs"))


def _music_job(dest: Path) -> AssetJob:
    return AssetJob(
        id="menu", dest=dest,
        request={},
        payload={"path": "/v1/music",
                 "json": {"prompt": "p", "music_length_ms": 90000},
                 "params": {"output_format": "mp3_44100_128"},
                 "asset": "music", "kind": "musiques"})


def test_build_music_request_shape_and_clamp():
    req = build_music_request("A theme", length_ms=700000, output_format="mp3_44100_128")
    assert req["path"] == "/v1/music"
    assert req["json"] == {"prompt": "A theme", "music_length_ms": 600000}
    assert req["params"] == {"output_format": "mp3_44100_128"}


def test_build_sfx_request_with_duration_and_loop():
    req = build_sfx_request("A swish", duration_s=60, loop=True,
                            model="eleven_text_to_sound_v2", output_format="mp3_44100_128")
    assert req["path"] == "/v1/sound-generation"
    assert req["json"] == {"text": "A swish", "model_id": "eleven_text_to_sound_v2",
                           "loop": True, "duration_seconds": 30.0}


def test_build_sfx_request_without_duration_lets_api_choose():
    req = build_sfx_request("A click", duration_s=None, loop=False,
                            model="eleven_text_to_sound_v2", output_format="mp3_44100_128")
    assert "duration_seconds" not in req["json"]
    assert req["json"]["loop"] is False


def test_from_config_stores_env_name_not_key(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-secret")
    provider = _provider()
    assert provider.api_key_env == "ELEVENLABS_API_KEY"
    assert "sk-secret" not in repr(provider)


def test_plan_builds_music_jobs_with_dest():
    spec = KindSpec(kind="musiques", asset="music", provider_name="eleven", options={},
                    targets=(Target(id="menu", text="Theme. Epic.",
                                    settings={"length_ms": 90000}),),
                    output_format=None, root=Path("/proj"))
    jobs = _provider().plan(spec)
    assert len(jobs) == 1
    assert jobs[0].dest == Path("/proj/out/audio/musiques/menu.mp3")
    assert jobs[0].request["json"] == {"prompt": "Theme. Epic.", "music_length_ms": 90000}
    assert jobs[0].payload["asset"] == "music"
    assert jobs[0].payload["kind"] == "musiques"


def test_plan_builds_sfx_jobs_with_loop_and_notes():
    spec = KindSpec(kind="nappes", asset="sfx", provider_name="eleven", options={},
                    targets=(Target(id="cite", text="Murmur. Ambient.",
                                    settings={"loop": True, "duration_s": 30.0},
                                    notes=("clamp",)),),
                    output_format="mp3_44100_128", root=Path("/proj"))
    jobs = _provider().plan(spec)
    assert jobs[0].dest == Path("/proj/out/audio/nappes/cite.mp3")
    assert jobs[0].request["json"]["loop"] is True
    assert jobs[0].request["json"]["duration_seconds"] == 30.0
    assert jobs[0].request["json"]["model_id"] == "eleven_text_to_sound_v2"
    assert jobs[0].notes == ("clamp",)


def test_plan_unsupported_asset_raises():
    spec = KindSpec(kind="narration", asset="tts", provider_name="eleven", options={},
                    targets=(), output_format=None, root=Path("/proj"))
    with pytest.raises(NotImplementedError, match="tts"):
        _provider().plan(spec)


@respx.mock
def test_execute_music_posts_and_writes_bytes(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test")
    route = respx.post("https://api.elevenlabs.io/v1/music").mock(
        return_value=httpx.Response(200, content=b"MP3BYTES"))
    dest = tmp_path / "menu.mp3"
    saved = _provider().execute(_music_job(dest))
    assert saved == [dest]
    assert dest.read_bytes() == b"MP3BYTES"
    request = route.calls.last.request
    assert request.headers["xi-api-key"] == "sk-test"
    assert request.url.params["output_format"] == "mp3_44100_128"
    assert json.loads(request.content) == {"prompt": "p", "music_length_ms": 90000}


@respx.mock
def test_execute_sfx_posts_to_sound_generation(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test")
    route = respx.post("https://api.elevenlabs.io/v1/sound-generation").mock(
        return_value=httpx.Response(200, content=b"SFX"))
    dest = tmp_path / "cite.mp3"
    job = AssetJob(id="cite", dest=dest, request={},
                   payload={"path": "/v1/sound-generation",
                            "json": {"text": "t", "model_id": "eleven_text_to_sound_v2",
                                     "loop": True, "duration_seconds": 30.0},
                            "params": {"output_format": "mp3_44100_128"},
                            "asset": "sfx", "kind": "nappes"})
    _provider().execute(job)
    assert dest.read_bytes() == b"SFX"
    assert json.loads(route.calls.last.request.content)["loop"] is True


@respx.mock
def test_execute_402_raises_studio_hint(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test")
    respx.post("https://api.elevenlabs.io/v1/music").mock(
        return_value=httpx.Response(402, text='{"detail": "payment required"}'))
    with pytest.raises(RuntimeError, match="forge studio musiques"):
        _provider().execute(_music_job(tmp_path / "menu.mp3"))


def test_execute_without_key_raises_french(tmp_path, monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ELEVENLABS_API_KEY"):
        _provider().execute(_music_job(tmp_path / "menu.mp3"))
```

- [ ] **Step 2: Vérifier l'échec**

```bash
.venv/bin/python -m pytest tests/test_elevenlabs.py -v
```
Attendu : `ModuleNotFoundError: No module named 'tableforge.providers.elevenlabs'`.

- [ ] **Step 3: Implémentation**

`src/tableforge/providers/elevenlabs.py` :
```python
"""Provider audio ElevenLabs — REST direct httpx, mockable respx.

P1 : music (POST /v1/music) + sfx/soundscapes (POST /v1/sound-generation, loop).
P2 ajoutera tts et dialogue. `plan()` est pur (aucune clé) ; `execute()` est le
seul point qui lit la clé (dotenv + env) et touche le réseau.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import httpx
from dotenv import load_dotenv

from ..catalog import clamp_music_length_ms, clamp_sfx_duration_s
from ..errors import raise_with_hint
from ..paths import asset_path
from .base import AssetJob

if TYPE_CHECKING:  # pragma: no cover
    from ..config import ElevenLabsProviderConfig
    from ..targets import KindSpec

MUSIC_PATH = "/v1/music"
SFX_PATH = "/v1/sound-generation"
DEFAULT_TIMEOUT = 180.0


def build_music_request(prompt: str, *, length_ms: int, output_format: str) -> dict:
    return {
        "path": MUSIC_PATH,
        "json": {"prompt": prompt, "music_length_ms": clamp_music_length_ms(length_ms)},
        "params": {"output_format": output_format},
    }


def build_sfx_request(text: str, *, duration_s: Optional[float], loop: bool, model: str,
                      output_format: str) -> dict:
    body: dict = {"text": text, "model_id": model, "loop": bool(loop)}
    if duration_s is not None:
        body["duration_seconds"] = clamp_sfx_duration_s(duration_s)
    return {"path": SFX_PATH, "json": body, "params": {"output_format": output_format}}


@dataclass(frozen=True)
class ElevenLabsProvider:
    api_key_env: str
    base_url: str
    output_format: str
    sfx_model: str
    tts_model: str
    dialogue_model: str

    @classmethod
    def from_config(cls, cfg: "ElevenLabsProviderConfig") -> "ElevenLabsProvider":
        return cls(api_key_env=cfg.api_key_env, base_url=cfg.base_url,
                   output_format=cfg.output_format, sfx_model=cfg.sfx_model,
                   tts_model=cfg.tts_model, dialogue_model=cfg.dialogue_model)

    def plan(self, spec: "KindSpec") -> list[AssetJob]:
        output_format = spec.output_format or self.output_format
        jobs: list[AssetJob] = []
        for target in spec.targets:
            if spec.asset == "music":
                req = build_music_request(target.text,
                                          length_ms=target.settings["length_ms"],
                                          output_format=output_format)
            elif spec.asset == "sfx":
                req = build_sfx_request(target.text,
                                        duration_s=target.settings.get("duration_s"),
                                        loop=bool(target.settings.get("loop", False)),
                                        model=self.sfx_model,
                                        output_format=output_format)
            else:
                raise NotImplementedError(
                    f"elevenlabs : asset '{spec.asset}' pas encore pris en charge (P2)")
            dest = asset_path(spec.root, spec.asset, spec.kind, target.id, output_format)
            jobs.append(AssetJob(id=target.id, dest=dest, request=req,
                                 payload={**req, "asset": spec.asset, "kind": spec.kind},
                                 notes=target.notes))
        return jobs

    def _require_key(self) -> str:
        load_dotenv()
        key = os.environ.get(self.api_key_env)
        if not key:
            raise RuntimeError(
                f"{self.api_key_env} manquant : copie .env.example vers .env et renseigne "
                "ta clé ElevenLabs (https://elevenlabs.io/app/settings/api-keys).")
        return key

    def execute(self, job: AssetJob) -> list[Path]:
        key = self._require_key()
        response = httpx.post(
            self.base_url + job.payload["path"],
            headers={"xi-api-key": key},
            json=job.payload["json"],
            params=job.payload["params"],
            timeout=DEFAULT_TIMEOUT,
        )
        raise_with_hint(response, provider_type="elevenlabs",
                        asset=job.payload["asset"], kind=job.payload["kind"])
        dest = Path(job.dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(response.content)
        return [dest]
```

- [ ] **Step 4: Vert + commit**

```bash
.venv/bin/python -m pytest tests/test_elevenlabs.py -v && .venv/bin/python -m pytest -q
```
Attendu : `12 passed` puis suite verte.

```bash
git add src/tableforge/providers/elevenlabs.py tests/test_elevenlabs.py
git commit -m "feat: provider ElevenLabs music + sfx (plan/execute, respx)"
```

---

## Task 8: providers/manual.py — fiches, refus d'exécution

**Files:**
- Create: `/home/etienne/Documents/tableforge/src/tableforge/providers/manual.py`
- Test: `/home/etienne/Documents/tableforge/tests/test_manual.py`

**Interfaces:**
- Produces: `ManualProvider` (frozen, sans champ) : `plan(spec)` → jobs `request={"manual": True, "prompt": …, "settings": …}` (le nom du kind voyage dans `payload["kind"]` car `AssetJob` n'a pas de champ kind) ; `execute(job)` → `RuntimeError` français pointant `forge studio`.

- [ ] **Step 1: Écrire le test rouge**

`tests/test_manual.py` :
```python
from pathlib import Path

import pytest

from tableforge.providers.manual import ManualProvider
from tableforge.targets import KindSpec, Target


def _spec() -> KindSpec:
    return KindSpec(kind="affiche", asset="sfx", provider_name="manual", options={},
                    targets=(Target(id="poster", text="A whoosh. Punchy.",
                                    settings={"loop": False, "duration_s": 1.0}),),
                    output_format=None, root=Path("/proj"))


def test_plan_builds_manual_cards():
    jobs = ManualProvider().plan(_spec())
    assert len(jobs) == 1
    job = jobs[0]
    assert job.dest == Path("/proj/out/audio/affiche/poster.mp3")
    assert job.request == {"manual": True, "prompt": "A whoosh. Punchy.",
                           "settings": {"loop": False, "duration_s": 1.0}}
    assert job.payload["kind"] == "affiche"


def test_execute_refuses_pointing_to_studio():
    job = ManualProvider().plan(_spec())[0]
    with pytest.raises(RuntimeError) as exc:
        ManualProvider().execute(job)
    message = str(exc.value)
    assert "forge studio affiche" in message
    assert str(job.dest) in message
```

- [ ] **Step 2: Vérifier l'échec**

```bash
.venv/bin/python -m pytest tests/test_manual.py -v
```
Attendu : `ModuleNotFoundError: No module named 'tableforge.providers.manual'`.

- [ ] **Step 3: Implémentation**

`src/tableforge/providers/manual.py` :
```python
"""Provider réservé `manual` : plan des fiches, exécution refusée (→ forge studio)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ..paths import asset_path
from .base import AssetJob

if TYPE_CHECKING:  # pragma: no cover
    from ..targets import KindSpec


@dataclass(frozen=True)
class ManualProvider:
    def plan(self, spec: "KindSpec") -> list[AssetJob]:
        jobs: list[AssetJob] = []
        for target in spec.targets:
            dest = asset_path(spec.root, spec.asset, spec.kind, target.id,
                              spec.output_format)
            jobs.append(AssetJob(
                id=target.id, dest=dest,
                request={"manual": True, "prompt": target.text,
                         "settings": dict(target.settings)},
                payload={"kind": spec.kind},
                notes=target.notes))
        return jobs

    def execute(self, job: AssetJob) -> list[Path]:
        kind = job.payload.get("kind", "?")
        raise RuntimeError(
            f"provider manuel : lance `forge studio {kind}` "
            f"puis dépose le fichier à {job.dest}")
```

- [ ] **Step 4: Vert + commit**

```bash
.venv/bin/python -m pytest tests/test_manual.py -v && .venv/bin/python -m pytest -q
```
Attendu : `2 passed` puis suite verte.

```bash
git add src/tableforge/providers/manual.py tests/test_manual.py
git commit -m "feat: provider manual (fiches plan, refus d'exécution vers forge studio)"
```

---

## Task 9: provider_for multi-provider + validate_project (linter)

**Files:**
- Modify: `/home/etienne/Documents/tableforge/src/tableforge/providers/base.py`
- Test: `/home/etienne/Documents/tableforge/tests/test_validate_project.py`

**Interfaces:**
- Consumes: `resolve_provider_name`, `options_model`, `SUPPORTED_ASSETS` (Task 5), `ElevenLabsProvider` (Task 7), `ManualProvider` (Task 8), `SeedreamProvider` (P0).
- Produces:
  - `provider_for(project: ProjectConfig, kind_cfg: KindConfig) -> Provider` — route seedream/elevenlabs/manual ; higgsfield → `ValueError` français (P3).
  - `validate_project(project: ProjectConfig) -> list[str]` — provider inconnu, capacité asset, options invalides (énumère les clés acceptées), voix inconnues, `from_` invalide, sheet sur non-image.

- [ ] **Step 1: Écrire le test rouge**

`tests/test_validate_project.py` :
```python
import pytest

from tableforge.config import load_project
from tableforge.providers.base import provider_for, validate_project
from tableforge.providers.elevenlabs import ElevenLabsProvider
from tableforge.providers.manual import ManualProvider

FORGE_ISSUES = """
project: demo
providers:
  eleven: { type: elevenlabs }
kinds:
  musiques:
    asset: music
    prompts: prompts/musiques.yaml
    generate: { with: eleven, length_ms: 60000 }
  bancale:
    asset: music
    prompts: prompts/musiques.yaml
    generate: { with: eleven, voice: narrateur }
  fantome:
    asset: sfx
    prompts: prompts/sfx.yaml
    generate: { with: inconnu }
  planche:
    asset: music
    prompts: prompts/musiques.yaml
    generate: { with: eleven }
    sheet: {page: A4, cols: 3, rows: 3, card_w_mm: 63, card_h_mm: 88}
  anim:
    asset: video
    from: nulle-part
    generate: { with: manual }
  lecture:
    asset: tts
    data: data/pnj.yaml
    generate: { with: eleven, voice: absente }
  dessins:
    prompts: prompts/dessins.yaml
    template: templates/card
    render_size: {width: 10, height: 10}
    generate: { with: eleven }
"""

FORGE_CLEAN = """
project: demo
providers:
  eleven: { type: elevenlabs }
voices:
  narrateur: JBFqnCBsd6RMkjVDRZzb
kinds:
  musiques:
    asset: music
    prompts: prompts/musiques.yaml
    generate: { with: eleven, length_ms: 60000 }
  atelier:
    asset: sfx
    prompts: prompts/sfx.yaml
    generate: { with: manual }
"""


def _project(tmp_path, text):
    (tmp_path / "forge.yaml").write_text(text, encoding="utf-8")
    return load_project(tmp_path)


def test_validate_flags_all_issue_families(tmp_path):
    issues = validate_project(_project(tmp_path, FORGE_ISSUES))
    text = "\n".join(issues)
    assert "clés acceptées" in text                # bancale : voice interdite pour music
    assert "provider 'inconnu' inconnu" in text    # fantome
    assert "sheet" in text                         # planche : sheet sur non-image
    assert "nulle-part" in text                    # anim : from vers kind inexistant
    assert "voix 'absente' inconnue" in text       # lecture : voix hors map voices:
    assert "ne sait pas générer" in text           # dessins : eleven ne fait pas d'image
    assert len(issues) >= 6


def test_validate_from_must_target_image_kind(tmp_path):
    forge = FORGE_CLEAN + """
  anim:
    asset: video
    from: musiques
    generate: { with: manual }
"""
    issues = validate_project(_project(tmp_path, forge))
    assert any("from" in issue and "image" in issue for issue in issues)


def test_validate_clean_project_returns_empty(tmp_path):
    assert validate_project(_project(tmp_path, FORGE_CLEAN)) == []


def test_provider_for_routes_elevenlabs_and_manual(tmp_path):
    project = _project(tmp_path, FORGE_CLEAN)
    assert isinstance(provider_for(project, project.kind("musiques")), ElevenLabsProvider)
    assert isinstance(provider_for(project, project.kind("atelier")), ManualProvider)
```

- [ ] **Step 2: Vérifier l'échec**

```bash
.venv/bin/python -m pytest tests/test_validate_project.py -v
```
Attendu : `ImportError` sur `validate_project`, ou échecs si P0 avait un stub (ex. `provider_for` levant `NotImplementedError` pour elevenlabs/manual).

- [ ] **Step 3: Implémentation dans providers/base.py**

Remplacer le corps du `provider_for` P0 par :
```python
def provider_for(project: ProjectConfig, kind_cfg: KindConfig) -> Provider:
    name = resolve_provider_name(project, kind_cfg)
    if name == "manual":
        from .manual import ManualProvider
        return ManualProvider()
    cfg = project.providers[name]
    if cfg.type == "seedream":
        from .seedream import SeedreamProvider
        return SeedreamProvider.from_config(cfg)
    if cfg.type == "elevenlabs":
        from .elevenlabs import ElevenLabsProvider
        return ElevenLabsProvider.from_config(cfg)
    raise ValueError(
        f"provider '{name}' : type '{cfg.type}' pas encore pris en charge "
        "pour la génération (higgsfield arrive en P3)")
```
(Imports locaux dans la fonction : ils évitent tout cycle d'import au chargement du package.)

Ajouter `validate_project` :
```python
def validate_project(project: ProjectConfig) -> list[str]:
    """Linter de forge.yaml : liste de problèmes en français (vide si tout est bon)."""
    issues: list[str] = []
    for name, kind_cfg in project.kinds.items():
        issues.extend(_kind_issues(project, name, kind_cfg))
    return issues


def _kind_issues(project: ProjectConfig, name: str, kind_cfg: KindConfig) -> list[str]:
    issues: list[str] = []
    if kind_cfg.sheet is not None and kind_cfg.asset != "image":
        issues.append(f"kind '{name}' : bloc 'sheet' sur un asset {kind_cfg.asset} "
                      "(réservé aux kinds image)")
    if kind_cfg.from_ is not None:
        source = project.kinds.get(kind_cfg.from_)
        if source is None:
            issues.append(f"kind '{name}' : from: '{kind_cfg.from_}' ne désigne "
                          "aucun kind déclaré")
        elif source.asset != "image":
            issues.append(f"kind '{name}' : from: '{kind_cfg.from_}' doit être un kind "
                          f"image (trouvé : {source.asset})")
    if kind_cfg.generate is None:
        return issues
    try:
        provider_name = resolve_provider_name(project, kind_cfg)
    except ValueError as exc:
        issues.append(str(exc))
        return issues
    provider_type = ("manual" if provider_name == "manual"
                     else project.providers[provider_name].type)
    extras = dict(kind_cfg.generate.model_extra or {})
    voice = extras.get("voice")
    if isinstance(voice, str) and voice not in project.voices:
        declared = ", ".join(project.voices) or "aucune"
        issues.append(f"kind '{name}' : voix '{voice}' inconnue (déclarées : {declared})")
    model = options_model(provider_type, kind_cfg.asset)
    if model is not None:
        try:
            model(**extras)
        except ValidationError:
            accepted = ", ".join(model.model_fields) or "aucune"
            issues.append(f"kind '{name}' : options generate: invalides pour "
                          f"{provider_type}/{kind_cfg.asset} (clés acceptées : {accepted})")
    return issues
```
Ajouter l'import `ValidationError` en tête du module : `from pydantic import BaseModel, ConfigDict, ValidationError`.

Note : `resolve_provider_name` porte déjà les messages « provider inconnu », « ne sait pas générer », « aucun provider », « plusieurs providers » — `_kind_issues` les récupère via `str(exc)`.

- [ ] **Step 4: Vert + commit**

```bash
.venv/bin/python -m pytest tests/test_validate_project.py -v && .venv/bin/python -m pytest -q
```
Attendu : `4 passed` puis suite verte.

```bash
git add src/tableforge/providers/base.py tests/test_validate_project.py
git commit -m "feat: provider_for multi-provider + validate_project (linter forge.yaml)"
```

---

## Task 10: Intégration generate_kind audio (dry-run, respx, skip, manual)

`generate_kind` (P0, générique) doit fonctionner sans modification. Cette tâche le prouve.

**Files:**
- Test: `/home/etienne/Documents/tableforge/tests/test_generate_audio.py`
- Modify: `/home/etienne/Documents/tableforge/src/tableforge/generate.py` (uniquement si un test échoue — le contrat P0 est : `spec = build_kind_spec(...)` ; `provider = ensure_provider(provider)` ou `provider_for(...)` ; `jobs = provider.plan(spec)` ; par job : dry_run → `GenerateResult(id, None, job.request)` ; `dest.exists()` et non `force` → `{"skipped": "exists"}` ; sinon `provider.execute(job)`)

**Interfaces:**
- Consumes: `generate_kind(project, kind, ids=None, dry_run=False, force=False, provider=None) -> list[GenerateResult]` (P0).

- [ ] **Step 1: Écrire le test**

`tests/test_generate_audio.py` :
```python
import httpx
import pytest
import respx

from tableforge.config import load_project
from tableforge.generate import generate_kind

FORGE = """
project: demo-audio
providers:
  eleven: { type: elevenlabs }
kinds:
  musiques:
    asset: music
    prompts: prompts/musiques.yaml
    generate: { with: eleven }
  affiche:
    asset: sfx
    prompts: prompts/sfx.yaml
    generate: { with: manual }
"""

MUSIC = """
direction: "Epic score."
defaults: { length_ms: 60000 }
entries:
  menu: { prompt: "Main theme" }
"""

SFX = """
direction: "Punchy."
entries:
  poster: { prompt: "Whoosh", duration_s: 1.0 }
"""


def _project(tmp_path):
    (tmp_path / "forge.yaml").write_text(FORGE, encoding="utf-8")
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "musiques.yaml").write_text(MUSIC, encoding="utf-8")
    (prompts / "sfx.yaml").write_text(SFX, encoding="utf-8")
    return load_project(tmp_path)


def test_music_dry_run_builds_requests_without_network(tmp_path):
    results = generate_kind(_project(tmp_path), "musiques", dry_run=True)
    assert [r.id for r in results] == ["menu"]
    assert results[0].dest is None
    req = results[0].request
    assert req["path"] == "/v1/music"
    assert req["json"]["music_length_ms"] == 60000
    assert "Main theme" in req["json"]["prompt"]


@respx.mock
def test_music_generate_writes_audio_file(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test")
    respx.post("https://api.elevenlabs.io/v1/music").mock(
        return_value=httpx.Response(200, content=b"MP3"))
    project = _project(tmp_path)
    results = generate_kind(project, "musiques")
    dest = project.root / "out" / "audio" / "musiques" / "menu.mp3"
    assert results[0].dest == dest
    assert dest.read_bytes() == b"MP3"


def test_music_skips_existing_without_force(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test")
    project = _project(tmp_path)
    dest = project.root / "out" / "audio" / "musiques" / "menu.mp3"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"old")
    # aucun mock respx actif : tout appel réseau ferait échouer le test
    results = generate_kind(project, "musiques")
    assert results[0].request == {"skipped": "exists"}
    assert dest.read_bytes() == b"old"


def test_manual_dry_run_shows_card(tmp_path):
    results = generate_kind(_project(tmp_path), "affiche", dry_run=True)
    assert results[0].request["manual"] is True
    assert "Whoosh" in results[0].request["prompt"]


def test_manual_generate_refuses_pointing_to_studio(tmp_path):
    with pytest.raises(RuntimeError, match="forge studio affiche"):
        generate_kind(_project(tmp_path), "affiche")
```

- [ ] **Step 2: Lancer**

```bash
.venv/bin/python -m pytest tests/test_generate_audio.py -v
```
Attendu : `5 passed` directement (l'orchestrateur P0 est générique). Si un test échoue, corriger `generate.py` pour respecter exactement le contrat P0 rappelé dans **Files** ci-dessus — sans changer sa signature ni le comportement image (relancer alors toute la suite).

- [ ] **Step 3: Commit**

```bash
.venv/bin/python -m pytest -q
git add tests/test_generate_audio.py
git commit -m "test: intégration generate audio (dry-run, respx, skip-exists, manual)"
```

---

## Task 11: studio.py — fiches studio

**Files:**
- Create: `/home/etienne/Documents/tableforge/src/tableforge/studio.py`
- Test: `/home/etienne/Documents/tableforge/tests/test_studio.py`

**Interfaces:**
- Consumes: `build_kind_spec` (Task 6), `provider_for` (Task 9).
- Produces:
  - `STUDIO_URLS: dict[tuple[str, str], str]`
  - `StudioCard` (frozen) : `kind, id, text, settings, dest, url, notes`
  - `studio_cards(project: ProjectConfig, kind: str, ids: Optional[list[str]] = None) -> list[StudioCard]` — `kind.studio_url` prioritaire sur `STUDIO_URLS` ; fonctionne sans aucune clé API.

- [ ] **Step 1: Écrire le test rouge**

`tests/test_studio.py` :
```python
from tableforge.config import load_project
from tableforge.studio import STUDIO_URLS, studio_cards

FORGE = """
project: demo-studio
providers:
  eleven: { type: elevenlabs }
kinds:
  musiques:
    asset: music
    prompts: prompts/musiques.yaml
    generate: { with: eleven }
  bruitages:
    asset: sfx
    prompts: prompts/sfx.yaml
    generate: { with: eleven }
  affiche:
    asset: sfx
    prompts: prompts/sfx.yaml
    generate: { with: manual }
    studio_url: https://example.test/atelier
"""

MUSIC = """
direction: "Epic score."
defaults: { length_ms: 60000 }
entries:
  menu: { prompt: "Main theme" }
  final: { prompt: "Last stand" }
"""

SFX = """
direction: "Punchy."
entries:
  draw: { prompt: "Card swish", duration_s: 0.8 }
"""


def _project(tmp_path):
    (tmp_path / "forge.yaml").write_text(FORGE, encoding="utf-8")
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "musiques.yaml").write_text(MUSIC, encoding="utf-8")
    (prompts / "sfx.yaml").write_text(SFX, encoding="utf-8")
    return load_project(tmp_path)


def test_music_cards_have_url_text_settings_dest(tmp_path):
    project = _project(tmp_path)
    cards = studio_cards(project, "musiques")
    assert [c.id for c in cards] == ["menu", "final"]
    card = cards[0]
    assert card.kind == "musiques"
    assert card.url == "https://elevenlabs.io/app/music"
    assert card.text == "Main theme. Epic score."
    assert card.settings == {"length_ms": 60000}
    assert card.dest == project.root / "out" / "audio" / "musiques" / "menu.mp3"


def test_sfx_cards_point_to_sound_effects(tmp_path):
    cards = studio_cards(_project(tmp_path), "bruitages")
    assert cards[0].url == "https://elevenlabs.io/app/sound-effects"
    assert cards[0].settings["duration_s"] == 0.8


def test_kind_studio_url_wins_over_defaults(tmp_path):
    cards = studio_cards(_project(tmp_path), "affiche")
    assert cards[0].url == "https://example.test/atelier"


def test_ids_filter(tmp_path):
    cards = studio_cards(_project(tmp_path), "musiques", ids=["final"])
    assert [c.id for c in cards] == ["final"]


def test_studio_urls_table_covers_elevenlabs_assets():
    assert STUDIO_URLS[("elevenlabs", "music")] == "https://elevenlabs.io/app/music"
    assert STUDIO_URLS[("elevenlabs", "sfx")] == "https://elevenlabs.io/app/sound-effects"
    assert STUDIO_URLS[("elevenlabs", "tts")] == "https://elevenlabs.io/app/speech-synthesis"
    assert STUDIO_URLS[("elevenlabs", "dialogue")] == "https://elevenlabs.io/app/speech-synthesis"
```

- [ ] **Step 2: Vérifier l'échec**

```bash
.venv/bin/python -m pytest tests/test_studio.py -v
```
Attendu : `ModuleNotFoundError: No module named 'tableforge.studio'`.

- [ ] **Step 3: Implémentation**

`src/tableforge/studio.py` :
```python
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
                       settings=dict(target.settings), dest=jobs_by_id[target.id].dest,
                       url=url, notes=target.notes)
            for target in spec.targets]
```

- [ ] **Step 4: Vert + commit**

```bash
.venv/bin/python -m pytest tests/test_studio.py -v && .venv/bin/python -m pytest -q
```
Attendu : `5 passed` puis suite verte.

```bash
git add src/tableforge/studio.py tests/test_studio.py
git commit -m "feat: studio.py — fiches studio (texte, réglages, dest, URL)"
```

---

## Task 12: CLI — forge studio, linter forge list, refus pédagogiques

**Files:**
- Modify: `/home/etienne/Documents/tableforge/src/tableforge/cli.py`
- Test: `/home/etienne/Documents/tableforge/tests/test_cli.py` (ajouts en fin de fichier — ne pas toucher aux tests existants)

**Interfaces:**
- Consumes: `studio_cards` (Task 11), `validate_project` (Task 9), `MODALITY_BY_ASSET` (paths).
- Produces:
  - commande `forge studio KIND [--id …] [-p …]`
  - `forge list` : ligne `- <kind> [<asset> via <provider|auto>]: …` + issues du linter (exit 1 s'il y en a)
  - `forge render|board|sheet` sur un kind non-image → `typer.BadParameter` « le kind 'X' est audio (music) — rien à rendre ; utilise forge generate ».

- [ ] **Step 1: Écrire les tests**

Ajouter en fin de `tests/test_cli.py` :
```python
FORGE_AUDIO = """
project: demo-audio
providers:
  eleven: { type: elevenlabs }
kinds:
  musiques:
    asset: music
    prompts: prompts/musiques.yaml
    generate: { with: eleven }
"""

MUSIC_CATALOG = """
direction: "Epic score."
defaults: { length_ms: 60000 }
entries:
  menu: { prompt: "Main theme" }
"""


def _audio_project(tmp_path):
    (tmp_path / "forge.yaml").write_text(FORGE_AUDIO, encoding="utf-8")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "musiques.yaml").write_text(MUSIC_CATALOG, encoding="utf-8")


def test_studio_command_prints_cards(tmp_path):
    _audio_project(tmp_path)
    res = runner.invoke(app, ["studio", "musiques", "--project", str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert "elevenlabs.io/app/music" in res.output
    assert "Main theme" in res.output
    assert "menu.mp3" in res.output
    assert "length_ms=60000" in res.output


def test_list_shows_asset_and_provider(tmp_path):
    _audio_project(tmp_path)
    res = runner.invoke(app, ["list", "--project", str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert "[music via eleven]" in res.output


def test_list_reports_config_issues_and_exits_1(tmp_path):
    _audio_project(tmp_path)
    forge = (tmp_path / "forge.yaml").read_text(encoding="utf-8")
    forge = forge.replace("generate: { with: eleven }",
                          "generate: { with: eleven, voice: bob }")
    (tmp_path / "forge.yaml").write_text(forge, encoding="utf-8")
    res = runner.invoke(app, ["list", "--project", str(tmp_path)])
    assert res.exit_code == 1
    assert "clés acceptées" in res.output


def test_render_refuses_audio_kind(tmp_path):
    import typer

    from tableforge.cli import _render_kind
    from tableforge.config import load_project
    _audio_project(tmp_path)
    cfg = load_project(tmp_path)
    with pytest.raises(typer.BadParameter, match="rien à rendre"):
        _render_kind(cfg, "musiques", None)
```
Ajouter `import pytest` en tête de `tests/test_cli.py` s'il n'y est pas.

- [ ] **Step 2: Vérifier l'échec**

```bash
.venv/bin/python -m pytest tests/test_cli.py -v
```
Attendu : les 4 nouveaux tests échouent (`No such command 'studio'`, `[music via eleven]` absent, exit 0 au lieu de 1, pas de refus).

- [ ] **Step 3: Implémentation**

Dans `src/tableforge/cli.py` :

1. Remplacer la commande `list_kinds` par :
```python
@app.command("list")
def list_kinds(project: Path = ProjectOpt):
    """Liste les kinds déclarés + diagnostics de configuration."""
    from .providers.base import validate_project
    cfg = load_project(project)
    for name, kind in cfg.kinds.items():
        flags = []
        if kind.data:
            flags.append("data" if kind.data.exists() else "data?")
        if kind.prompts:
            flags.append("prompts" if kind.prompts.exists() else "prompts?")
        if kind.template is not None:
            flags.append("template" if kind.template.exists() else "template?")
        sheet = " +sheet" if kind.sheet else ""
        provider = kind.generate.with_ if kind.generate and kind.generate.with_ else "auto"
        typer.echo(f"- {name} [{kind.asset} via {provider}]: {', '.join(flags)}{sheet}")
    issues = validate_project(cfg)
    if issues:
        typer.echo("problèmes de configuration :")
        for issue in issues:
            typer.echo(f"  ! {issue}")
        raise typer.Exit(code=1)
```

2. Ajouter le garde-fou et l'appeler en tête de `_render_kind` (première ligne après `kind_cfg = cfg.kind(kind)`) et dans `sheet` (après `kind_cfg = cfg.kind(kind)`) :
```python
def _require_image_kind(kind_cfg, kind: str) -> None:
    if kind_cfg.asset != "image":
        from .paths import MODALITY_BY_ASSET
        modality = MODALITY_BY_ASSET.get(kind_cfg.asset, kind_cfg.asset)
        raise typer.BadParameter(
            f"le kind '{kind}' est {modality} ({kind_cfg.asset}) — rien à rendre ; "
            "utilise forge generate")
```
(`board` passe par `_render_kind`, il est couvert.)

3. Ajouter la commande `studio` :
```python
@app.command()
def studio(kind: str, project: Path = ProjectOpt,
           id: Optional[List[str]] = typer.Option(None, "--id", help="Limiter à ces ids.")):
    """Fiches studio : texte, réglages, destination, URL de l'écran web."""
    from .studio import studio_cards
    cfg = load_project(project)
    for card in studio_cards(cfg, kind, ids=id or None):
        typer.echo(f"=== {card.kind}/{card.id}")
        if card.url:
            typer.echo(f"    écran   : {card.url}")
        typer.echo(f"    texte   : {card.text}")
        if card.settings:
            settings = ", ".join(f"{k}={v}" for k, v in sorted(card.settings.items()))
            typer.echo(f"    réglages: {settings}")
        for note in card.notes:
            typer.echo(f"    note    : {note}")
        typer.echo(f"    déposer : {card.dest}")
```

- [ ] **Step 4: Vert + commit**

```bash
.venv/bin/python -m pytest tests/test_cli.py -v && .venv/bin/python -m pytest -q
```
Attendu : tous les tests de `test_cli.py` passent (anciens inclus), suite verte.

```bash
git add src/tableforge/cli.py tests/test_cli.py
git commit -m "feat: CLI forge studio + linter forge list + refus non-image"
```

---

## Task 13: Starter enrichi (providers nommés, catalogues audio, .env.example)

**Files:**
- Modify: `/home/etienne/Documents/tableforge/src/tableforge/templates/starter/forge.yaml`
- Modify: `/home/etienne/Documents/tableforge/src/tableforge/templates/starter/.env.example`
- Create: `/home/etienne/Documents/tableforge/src/tableforge/templates/starter/prompts/musiques.yaml`
- Create: `/home/etienne/Documents/tableforge/src/tableforge/templates/starter/prompts/sfx.yaml`
- Test: `/home/etienne/Documents/tableforge/tests/test_scaffold.py` (ajout), `/home/etienne/Documents/tableforge/tests/test_cli.py` (ajout)

**Interfaces:**
- Produces: `forge init` clone un projet au format `providers:` nommés avec kinds `cards`, `musiques`, `sfx` ; `forge list` et `forge generate musiques --dry-run` fonctionnent immédiatement.

- [ ] **Step 1: Écrire les tests**

Ajouter en fin de `tests/test_scaffold.py` :
```python
def test_init_creates_audio_catalogs_and_named_providers(tmp_path):
    target = init_project("mon-jeu", tmp_path)
    forge = (target / "forge.yaml").read_text(encoding="utf-8")
    assert "providers:" in forge
    assert "type: elevenlabs" in forge
    assert (target / "prompts" / "musiques.yaml").exists()
    assert (target / "prompts" / "sfx.yaml").exists()
    env = (target / ".env.example").read_text(encoding="utf-8")
    assert "ARK_API_KEY" in env
    assert "ELEVENLABS_API_KEY" in env
    assert "HIGGSFIELD_API_KEY" in env
    assert "HIGGSFIELD_API_SECRET" in env
```

Ajouter en fin de `tests/test_cli.py` :
```python
def test_starter_audio_dry_run(tmp_path):
    runner.invoke(app, ["init", "g", "--dest", str(tmp_path)])
    res = runner.invoke(app, ["generate", "musiques", "--project",
                              str(tmp_path / "g"), "--dry-run"])
    assert res.exit_code == 0, res.output
    assert "menu" in res.output
```

- [ ] **Step 2: Vérifier l'échec**

```bash
.venv/bin/python -m pytest tests/test_scaffold.py tests/test_cli.py -v
```
Attendu : les 2 nouveaux tests échouent (starter encore au format v1, catalogues absents).

- [ ] **Step 3: Implémentation**

`src/tableforge/templates/starter/forge.yaml` (remplacement complet) :
```yaml
project: __PROJECT_NAME__

providers:                          # les comptes pour lesquels tu as une clé (type: obligatoire)
  ark:
    type: seedream
    base_url: https://ark.ap-southeast.bytepluses.com/api/v3
    api_key_env: ARK_API_KEY        # NOM de la variable d'env (jamais la clé)
    model: seedream-5-0-260128
    default_size: "4704x3520"
    watermark: false
  eleven:
    type: elevenlabs                # tout a un défaut sain (base_url, formats, modèles)

defaults:
  max_refs: 3
  ref_max_px: 1024

kinds:
  cards:
    data: data/cards.yaml
    prompts: prompts/cards.yaml
    template: templates/card
    capture_selector: ".forge-asset"
    render_size: { width: 744, height: 1039 }   # 63×88 mm @300 dpi
    scale: 3
    generate: { with: ark }
    sheet:
      page: A4
      cols: 3
      rows: 3
      card_w_mm: 63
      card_h_mm: 88
      gap_mm: 4
      cut_marks: true

  musiques:                         # pistes d'ambiance (ElevenLabs Music — plan payant ;
    asset: music                    # sinon : forge studio musiques)
    prompts: prompts/musiques.yaml
    generate: { with: eleven }

  sfx:                              # effets sonores one-shot ; nappe = loop: true au catalogue
    asset: sfx
    prompts: prompts/sfx.yaml
    generate: { with: eleven }

# Autres assets à venir : tts, dialogue (voix), video — voir la doc tableforge.
```

`src/tableforge/templates/starter/prompts/musiques.yaml` :
```yaml
# Catalogue MUSIC (ElevenLabs, POST /v1/music).
# Schéma : direction (style commun), negative (replié dans le prompt),
#          defaults.length_ms (bornes 3000..600000 ms), output_format, entries.
direction: >-
  Orchestral fantasy score, cinematic, restrained, seamless loopable bed.
negative: >-
  No lead vocals, no lyrics, no modern electronic instruments.
defaults:
  length_ms: 90000
output_format: mp3_44100_128
entries:
  menu:
    prompt: >-
      Solemn main theme for a title screen, slow strings over a low drone.
  victoire:
    prompt: >-
      Short victory sting, noble brass resolution, about eight seconds.
    length_ms: 10000
```

`src/tableforge/templates/starter/prompts/sfx.yaml` :
```yaml
# Catalogue SFX (ElevenLabs, POST /v1/sound-generation).
# duration_s bornée 0.5..30 s ; loop: true = nappe/soundscape (30 s max).
direction: >-
  Short dry punchy board-game sound effect, tactile, clean, no music, no voice.
output_format: mp3_44100_128
entries:
  pioche:
    prompt: "A single quick paper card being drawn and sliding off a deck, crisp swish."
    duration_s: 0.8
  ambiance:
    prompt: "Quiet tavern background, murmur and fireplace crackle, seamless."
    duration_s: 30
    loop: true
```

`src/tableforge/templates/starter/.env.example` (remplacement complet) :
```bash
# Copier vers .env (jamais committé). Les clés sont lues via providers.<nom>.api_key_env.
ARK_API_KEY=your_ark_api_key_here
# ElevenLabs (audio) : https://elevenlabs.io/app/settings/api-keys
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
# Higgsfield (image/vidéo, phase P3) : https://platform.higgsfield.ai
HIGGSFIELD_API_KEY=your_higgsfield_api_key_here
HIGGSFIELD_API_SECRET=your_higgsfield_api_secret_here
```

- [ ] **Step 4: Vert + commit**

```bash
.venv/bin/python -m pytest tests/test_scaffold.py tests/test_cli.py -v && .venv/bin/python -m pytest -q
```
Attendu : tout passe (y compris `test_init_then_list_then_dry_run` existant — le starter doit être **propre au linter**, exit 0 sur `forge list`).

```bash
git add src/tableforge/templates/starter tests/test_scaffold.py tests/test_cli.py
git commit -m "feat: starter multimodal (providers nommés, catalogues audio, .env.example)"
```

---

## Task 14: examples/couronnes — migration providers: + vrais catalogues audio

Porte les catalogues réels de couronnes-cendres (7 musiques, 6 nappes, 15 SFX) au schéma `entries:`, **sans** les champs `intent` (contrat de câblage du client web, hors périmètre tableforge). Migre `forge.yaml` au format `providers:` nommés — les requêtes image dry-run doivent rester strictement identiques.

**Files:**
- Modify: `/home/etienne/Documents/tableforge/examples/couronnes/forge.yaml`
- Create: `/home/etienne/Documents/tableforge/examples/couronnes/prompts/musiques.yaml`
- Create: `/home/etienne/Documents/tableforge/examples/couronnes/prompts/nappes.yaml`
- Create: `/home/etienne/Documents/tableforge/examples/couronnes/prompts/sfx.yaml`
- Test: `/home/etienne/Documents/tableforge/tests/test_example_couronnes.py` (ajouts en fin de fichier)

**Interfaces:**
- Produces: `load_project(examples/couronnes)` expose les kinds `cards`, `board`, `musiques`, `nappes`, `sfx` ; `validate_project` → `[]` ; dry-run audio complet sans réseau.

- [ ] **Step 1: Écrire les tests**

Ajouter en fin de `tests/test_example_couronnes.py` :
```python
def test_example_music_dry_run_builds_requests():
    cfg = load_project(EXAMPLE)
    results = generate_kind(cfg, "musiques", dry_run=True)
    assert len(results) == 7
    menu = next(r for r in results if r.id == "menu")
    assert menu.request["path"] == "/v1/music"
    assert menu.request["json"]["music_length_ms"] == 90000
    assert "Dark medieval fantasy orchestral score" in menu.request["json"]["prompt"]
    assert "No lead vocals" in menu.request["json"]["prompt"]
    assert menu.request["params"]["output_format"] == "mp3_44100_128"


def test_example_soundscapes_loop_and_duration():
    cfg = load_project(EXAMPLE)
    results = generate_kind(cfg, "nappes", dry_run=True)
    assert len(results) == 6
    fleau = next(r for r in results if r.id == "fleau")
    assert fleau.request["json"]["loop"] is True
    assert fleau.request["json"]["duration_seconds"] == 30.0
    assert fleau.request["json"]["model_id"] == "eleven_text_to_sound_v2"


def test_example_sfx_catalog_complete():
    cfg = load_project(EXAMPLE)
    results = generate_kind(cfg, "sfx", dry_run=True)
    assert len(results) == 15
    draw = next(r for r in results if r.id == "sfx-draw")
    assert draw.request["json"]["duration_seconds"] == 0.8
    assert draw.request["json"]["loop"] is False


def test_example_validates_clean():
    from tableforge.providers.base import validate_project
    cfg = load_project(EXAMPLE)
    assert validate_project(cfg) == []
```

- [ ] **Step 2: Vérifier l'échec**

```bash
.venv/bin/python -m pytest tests/test_example_couronnes.py -v
```
Attendu : les 4 nouveaux tests échouent (`KeyError: kind inconnu : 'musiques'`) ; les 3 anciens passent.

- [ ] **Step 3: Migrer forge.yaml**

`examples/couronnes/forge.yaml` (remplacement complet) :
```yaml
project: couronnes-cendres

providers:
  ark:
    type: seedream
    base_url: https://ark.ap-southeast.bytepluses.com/api/v3
    api_key_env: ARK_API_KEY
    model: seedream-5-0-260128
    default_size: "4704x3520"
    watermark: false
  eleven:
    type: elevenlabs

defaults:
  max_refs: 2
  ref_max_px: 1024

kinds:
  cards:
    data: data/cards.yaml
    prompts: prompts/cards.yaml
    template: templates/card
    capture_selector: ".cc-card"
    render_size: { width: 744, height: 1039 }
    scale: 3
    generate: { with: ark }
    sheet:
      page: A4
      cols: 3
      rows: 3
      card_w_mm: 63
      card_h_mm: 88
      gap_mm: 4
      cut_marks: true
  board:
    data: data/board.yaml
    template: templates/board
    capture_selector: ".cc-board"
    render_size: { width: 2480, height: 3508 }   # A4 @300 dpi
    scale: 1

  musiques:
    asset: music
    prompts: prompts/musiques.yaml
    generate: { with: eleven }

  nappes:                       # soundscapes = sfx avec loop: true (defaults du catalogue)
    asset: sfx
    prompts: prompts/nappes.yaml
    generate: { with: eleven }

  sfx:
    asset: sfx
    prompts: prompts/sfx.yaml
    generate: { with: eleven }
```

Si un test P0 (byte-équivalence ou autre) asserte `cfg.provider` ou `cfg.providers["default"]` **sur l'exemple couronnes**, le mettre à jour vers `cfg.providers["ark"]` : l'alias `default` ne vaut que pour le chemin legacy `provider:`, et l'exemple vient de migrer. Les valeurs du provider étant identiques, les requêtes dry-run image restent byte-identiques.

- [ ] **Step 4: Créer les trois catalogues**

`examples/couronnes/prompts/musiques.yaml` :
```yaml
# Couronnes & Cendres — Catalogue MUSIQUES d'ambiance (ElevenLabs Music, POST /v1/music)
# Génération API   : forge generate musiques        (nécessite un plan payant ElevenLabs)
# Génération STUDIO: forge studio musiques  → coller chaque prompt dans elevenlabs.io/app/music
#                    et enregistrer le résultat à l'emplacement « déposer » indiqué.

direction: >-
  Dark medieval fantasy orchestral score with a somber, weathered tone. Low strings,
  distant war drums, plaintive solo cello, sparse choir pads used as texture only.
  Restrained, cinematic, slow to mid tempo. Cold and grim atmosphere, seamless loopable
  bed with a soft head/tail so it can repeat without an obvious seam.

negative: >-
  No lead vocals, no lyrics, no modern or electronic instruments, no drum machine,
  no upbeat pop, no bright major-key fanfare, no sudden loud transients.

defaults:
  length_ms: 90000
output_format: mp3_44100_128

entries:
  menu:
    prompt: >-
      Solemn brooding main theme for a title screen: slow rising strings over a low drone,
      a lone distant horn, a sense of a ruined kingdom under ash. Noble but mournful.
    length_ms: 90000

  manche-calme:
    prompt: >-
      Quiet exploratory underscore for the early game: sparse plucked strings, soft
      cello, patient and low-tension, leaving room to think. Barely-there percussion.
    length_ms: 120000

  tension:
    prompt: >-
      Rising dread as corruption spreads and the Plague stirs: pulsing low ostinato,
      uneasy dissonant string swells, a slow ticking clock feel building pressure.
    length_ms: 120000

  combat:
    prompt: >-
      Driving battle cue for a clash of banners: urgent staccato strings, pounding war
      drums, brass stabs, relentless and dangerous but still grim and restrained.
    length_ms: 60000

  final:
    prompt: >-
      Climactic endgame theme for the final reckoning: full sombre orchestra, heavy
      drums, a mournful choir swell resolving into cold stillness.
    length_ms: 90000

  victoire:
    prompt: >-
      Short victory sting: a brief noble brass and string resolution, hard-won and
      bittersweet rather than triumphant. About eight seconds.
    length_ms: 10000

  defaite:
    prompt: >-
      Short defeat sting: a descending minor cello line fading into ash and silence.
      About eight seconds.
    length_ms: 10000
```

`examples/couronnes/prompts/nappes.yaml` :
```yaml
# Couronnes & Cendres — Catalogue NAPPES / SOUNDSCAPES de fond
# (ElevenLabs Sound Effects en boucle : loop: true, modèle eleven_text_to_sound_v2)
# API   : forge generate nappes
# STUDIO: forge studio nappes → elevenlabs.io/app/sound-effects, cocher « Loop », durée 30 s.

direction: >-
  Ambient background loop for a dark medieval fantasy board game, low and unobtrusive,
  no musical melody, meant to sit quietly under a score. Seamless, no sudden events.

defaults:
  loop: true
  duration_s: 30
output_format: mp3_44100_128

entries:
  cite:
    prompt: >-
      The Citadel: distant murmur of a crowd in a stone plaza, faint tolling bells,
      fluttering banners, echoing footsteps under high walls.

  marche:
    prompt: >-
      The Market: bustling stalls, muffled haggling voices, clink of coins and
      chains, creaking cart wheels, a low steady hum of trade.

  caserne:
    prompt: >-
      The Barracks: rhythmic distant hammer on an anvil, forge fire crackle,
      clatter of drilling arms, leather and iron in a cold yard.

  confins:
    prompt: >-
      The Marches: bleak windswept frontier, gusting wind over dry grass, distant
      crow calls, creaking timber, desolate and empty.

  sanctuaire:
    prompt: >-
      The Sanctuary: ethereal choral drone, soft shimmering resonance, dripping water
      in a vast crypt, a faint otherworldly ether hum.

  fleau:
    prompt: >-
      The Plague near: a low corrupted rumble of grinding ash, faint whispering embers,
      an oppressive subsonic dread that never quite resolves.
```

`examples/couronnes/prompts/sfx.yaml` :
```yaml
# Couronnes & Cendres — Catalogue EFFETS SONORES (ElevenLabs Sound Effects)
# API   : forge generate sfx
# STUDIO: forge studio sfx → elevenlabs.io/app/sound-effects, régler la durée indiquée.

direction: >-
  Short dry punchy board-game sound effect, dark medieval fantasy, tactile and physical,
  clean with minimal reverb, no music, no voice.

output_format: mp3_44100_128

entries:
  sfx-draw:
    prompt: "A single quick paper card being drawn and sliding off a deck, crisp swish."
    duration_s: 0.8

  sfx-deploy:
    prompt: "A thick playing card being firmly placed down on a wooden table, soft thud."
    duration_s: 0.8

  sfx-pawn-place:
    prompt: "A small wooden game pawn set down onto a wooden board, short hollow knock."
    duration_s: 0.7

  sfx-pawn-move:
    prompt: "A wooden pawn sliding a short distance across a board, brief muted scrape."
    duration_s: 0.7

  sfx-buy:
    prompt: "A small handful of coins clinking together, a bright acquisitive chime tail."
    duration_s: 1.2

  sfx-intrigue:
    prompt: "A dark arcane seal igniting, low occult whoosh with a shivering resonance."
    duration_s: 1.3

  sfx-intrigue-flash:
    prompt: "A burning ember sigil flaring open, hot crackling whoosh, ominous."
    duration_s: 1.3

  sfx-flash-reveal:
    prompt: "A single deep war horn blast and a low gong announcing a conflict."
    duration_s: 1.8

  sfx-combat:
    prompt: "A sharp clash of two steel swords, a single decisive metallic hit."
    duration_s: 1.2

  sfx-attrition:
    prompt: "A body falling and crumbling into a soft heap of ash and dust, grim."
    duration_s: 1.2

  sfx-plague-hop:
    prompt: "A corrupted creature lurching forward, wet grinding ash with a subsonic growl."
    duration_s: 1.3

  sfx-control-flip:
    prompt: "A heavy banner unfurling with a cloth flap and a brief resolving chime."
    duration_s: 1.1

  sfx-round:
    prompt: "A single low bell toll marking the start of a new round, calm and heavy."
    duration_s: 1.6

  sfx-ui-click:
    prompt: "A small soft wooden click for a user interface button press."
    duration_s: 0.5

  sfx-ui-error:
    prompt: "A short low dull thud indicating an invalid action, discouraging."
    duration_s: 0.6
```

- [ ] **Step 5: Vert + vérif manuelle + commit**

```bash
.venv/bin/python -m pytest tests/test_example_couronnes.py -v && .venv/bin/python -m pytest -q
```
Attendu : `7 passed` sur le fichier (3 anciens + 4 nouveaux), suite complète verte (les tests image existants prouvent la non-régression de la migration `providers:`).

Vérification manuelle du rendu CLI :
```bash
.venv/bin/python -m tableforge list -p examples/couronnes
.venv/bin/python -m tableforge generate musiques -p examples/couronnes --dry-run
.venv/bin/python -m tableforge studio nappes -p examples/couronnes --id fleau
```
Attendu : `list` affiche les 5 kinds avec `[image via ark]` / `[music via eleven]` / `[sfx via eleven]` sans problème signalé (exit 0) ; le dry-run liste 7 ids `(dry-run)` ; la fiche studio affiche l'URL sound-effects, le texte, `duration_s=30.0, loop=True` et le chemin `out/audio/nappes/fleau.mp3`.

```bash
git add examples/couronnes tests/test_example_couronnes.py
git commit -m "feat: exemple couronnes — catalogues audio réels + format providers nommés"
```

---

## Task 15: Vérification finale P1 (suite + couverture)

**Files:** aucun (vérification ; commit seulement si correction nécessaire).

- [ ] **Step 1: Suite complète + couverture**

```bash
cd /home/etienne/Documents/tableforge
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest --cov=tableforge --cov-report=term-missing -q
```
Attendu : tous les tests passent ; couverture totale ≥ 80 % (objectif ≈ 96 % sur la logique pure — `catalog.py`, `errors.py`, `targets.py`, `studio.py`, `providers/elevenlabs.py`, `providers/manual.py`, `providers/base.py` doivent être proches de 100 % ; `render.py`/`cli.py`/`__main__.py` sont exclus par la config).

- [ ] **Step 2: Contrôles de périmètre**

```bash
grep -rn "intent" examples/couronnes/prompts/ && echo "ECHEC: intent présent" || echo "OK: pas d'intent"
grep -rn "api_key=" src/tableforge/providers/elevenlabs.py && echo "ECHEC" || echo "OK: pas de clé stockée"
.venv/bin/python -c "import tableforge.targets, tableforge.studio, tableforge.providers.elevenlabs, tableforge.providers.manual; print('imports OK')"
```
Attendu : `OK: pas d'intent`, `OK: pas de clé stockée`, `imports OK` (aucun cycle d'import).

- [ ] **Step 3: État git propre**

```bash
git status --short
```
Attendu : rien à committer. Si un écart de couverture a demandé une correction, la committer en `fix:` ou `test:` avant de clore la phase.
