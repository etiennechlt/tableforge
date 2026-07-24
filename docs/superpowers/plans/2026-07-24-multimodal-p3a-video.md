# Multimodal P3a — vidéo Higgsfield (i2v + t2v) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter la génération vidéo via Higgsfield à tableforge : `providers/higgsfield.py` (submit → poll → download, statuts affichés, échecs `failed`/`nsfw` signalés comme remboursés, timeout), résolution des cibles vidéo dans `targets.py` (i2v via `from:` sur un kind image, t2v via catalogue), branchement dans le registre providers, `forge all` sans argument (ordre image → audio → vidéo), fiche studio vidéo, et deux kinds d'exemple dans `examples/couronnes` (`cartes-animees` i2v, `teaser` t2v) vérifiés en dry-run.

**Architecture:** Higgsfield est une API **asynchrone** : `POST /{model_slug}` (JSON) → `{request_id}`, puis `GET /requests/{id}/status` jusqu'à `completed` (ou `failed`/`nsfw`, auto-remboursés), puis téléchargement de l'URL de résultat. Le provider respecte le contrat `plan(spec) -> list[AssetJob]` (pur, sans clé) / `execute(job) -> list[Path]` (seul point réseau/clé) établi en P0. Les cibles vidéo sont résolues par `targets.build_kind_spec` : i2v anime les PNG existants de `out/art/<from>/` (catalogue de mouvement optionnel en override, sous-ensemble obligatoire), t2v prend les entrées du catalogue. La data-URL de l'image source est encodée **au moment du plan** dans `job.payload` mais jamais dans `job.request` (résumé affichable).

**Tech Stack:** Python ≥ 3.10, pydantic v2, httpx (direct, **pas de SDK vendeur**), respx (mocks), PyYAML, typer, Pillow (encodage data-URL), pytest. Venv via **uv**, exécution `.venv/bin/python`.

## Global Constraints

- **Prérequis : P2 mergée.** Ce plan suppose l'état post-P2 du contrat d'interfaces figé (spec `docs/superpowers/specs/2026-07-24-multimodal-providers-design.md`) : `providers/` (base, seedream, elevenlabs, manual), `targets.py`, `catalog.py`, `errors.py`, `studio.py`, `paths.py` étendu, `config.py` avec `HiggsfieldProviderConfig` et `KindConfig.from_`/`asset`/`generate`.
- **Toujours `.venv/bin/python`** — jamais `python`/`pip` système.
- **TDD strict** : test rouge → implémentation minimale → vert → commit conventionnel français.
- **Couverture ≥ 80 %** sur la logique pure (objectif ≈ 96 %) ; `render.py`, `cli.py`, `__main__.py` restent exclus (`pyproject.toml`).
- **Doctrine respx** : tout chemin httpx Higgsfield est couvert par respx — header `Authorization: Key {key}:{secret}` asserté, corps JSON asserté, fichier écrit asserté. Aucun test ne touche le réseau réel. `sleep` injectable dès le premier commit (aucune attente réelle en test).
- **Secrets** : jamais imprimés ni stockés ; les clés sont résolues dans `execute()` uniquement (dotenv + `os.environ`), messages d'erreur français nommant la variable d'env.
- **Immutabilité** : dataclasses `frozen=True`, jamais de mutation d'un dict reçu (copies).
- **Messages utilisateur en français**, code et noms de tests en anglais, tests AAA.
- Modules ≤ ~400 lignes, fonctions < 50 lignes, pas de nombre magique (constantes nommées).
- **Vérification API au moment de l'implémentation** (Task 2, Step 0) : le format exact de la réponse `GET /requests/{id}/status` (supposé `{"status": ..., "results": [{"url": ...}]}`), le nom du champ image i2v (supposé `"image"`), le nom du champ durée (supposé `"duration"`, secondes) et les slugs de modèles doivent être confrontés à `https://docs.higgsfield.ai/docs/how-to/introduction.md` (et la galerie de modèles). Le code ci-dessous embarque des **fallbacks raisonnables** (`_result_url`) ; si la doc contredit une hypothèse, adapte le code ET le test correspondant dans le même commit.

### Points d'ancrage post-P2 à vérifier avant Task 1 (lecture seule, 5 min)

Ce plan est écrit contre le contrat figé ; quatre détails d'implémentation ont pu être fixés en P0–P2 avec des noms légèrement différents. Ouvre les fichiers et note les écarts :

1. `src/tableforge/targets.py` — **`KindSpec` doit porter la racine projet** (nécessaire à `plan()` pour calculer `dest`). Le code de ce plan suppose un champ `root: Path` sur `KindSpec`, renseigné par `build_kind_spec` avec `project.root`. S'il n'existe pas (P1 a pu choisir un autre nom), ajoute-le : champ `root: Path` dans le dataclass frozen `KindSpec` + passage de `project.root` dans chaque construction de `KindSpec` (changement mécanique, les tests P1 restent verts car c'est un champ supplémentaire nommé).
2. `src/tableforge/errors.py` — le type d'exception levé par `raise_with_hint` (ce plan suppose `RuntimeError` enrichi du hint ; si P1 a choisi `httpx.HTTPStatusError` ré-levé, adapte les deux `pytest.raises` concernés dans `tests/test_higgsfield.py`).
3. `tests/` — le nom du fichier de tests du module `providers/base.py` créé en P1 (`ls tests/ | grep -i base`). Les tests de la Task 6 s'ajoutent **dans ce fichier existant** (le plan le nomme `tests/test_providers_base.py`).
4. `src/tableforge/providers/base.py` — la forme du registre `options_model` (dict `(type, asset) -> model` ou chaîne if/elif). La Task 6 donne la sémantique exacte attendue + un snippet pour chaque forme.

---

## Task 1: Verrou de contrat — chemins vidéo (`paths.py`)

Les helpers `MODALITY_BY_ASSET` / `extension_for` / `asset_dir` / `asset_path` datent de P0/P1. Cette tâche pose un test-verrou spécifique vidéo (`out/video/<kind>/<id>.mp4`). Si P0/P1 a déjà tout implémenté conformément au contrat, le test passe immédiatement : commite alors le test seul comme verrou de non-régression.

**Files:**
- Test: `tests/test_paths.py` (ajout en fin de fichier)
- Modify (seulement si le test est rouge): `src/tableforge/paths.py`

**Interfaces:**
- Consumes: `paths.MODALITY_BY_ASSET: dict[str, str]`, `paths.extension_for(asset: str, output_format: Optional[str]) -> str`, `paths.asset_dir(root: Path, asset: str, kind: str) -> Path`, `paths.asset_path(root: Path, asset: str, kind: str, asset_id: str, output_format: Optional[str] = None) -> Path`
- Produces: garantie `asset_path(root, "video", "teaser", "intro") == root/out/video/teaser/intro.mp4`

- [ ] **Step 1 — test (RED attendu seulement si P0/P1 incomplet)**

Ajoute à la fin de `tests/test_paths.py` :

```python
def test_video_paths_use_mp4_under_out_video():
    # Arrange
    root = Path("/proj")

    # Act / Assert
    assert paths.MODALITY_BY_ASSET["video"] == "video"
    assert paths.extension_for("video", None) == ".mp4"
    assert paths.extension_for("video", "whatever") == ".mp4"
    assert paths.asset_dir(root, "video", "teaser") == root / "out" / "video" / "teaser"
    assert (paths.asset_path(root, "video", "teaser", "intro")
            == root / "out" / "video" / "teaser" / "intro.mp4")
```

- [ ] **Step 2 — run**

```bash
.venv/bin/python -m pytest tests/test_paths.py -v
```

Attendu : soit tout PASSE (P0/P1 conforme au contrat → passe au Step 4), soit `test_video_paths_use_mp4_under_out_video` FAILED (`KeyError: 'video'` ou `AttributeError`).

- [ ] **Step 3 — implémentation minimale (uniquement si rouge)**

Dans `src/tableforge/paths.py`, complète les helpers pour couvrir la vidéo, conformément au contrat (le code final complet des quatre helpers) :

```python
MODALITY_BY_ASSET = {"image": "art", "music": "audio", "sfx": "audio", "tts": "audio",
                     "dialogue": "audio", "video": "video"}

_AUDIO_EXTENSIONS = (("mp3_", ".mp3"), ("opus_", ".ogg"), ("pcm_", ".wav"),
                     ("ulaw_", ".wav"), ("alaw_", ".wav"))
_DEFAULT_AUDIO_EXTENSION = ".mp3"


def extension_for(asset: str, output_format: Optional[str] = None) -> str:
    if asset == "image":
        return f".{output_format or 'png'}"
    if asset == "video":
        return ".mp4"
    fmt = output_format or ""
    for prefix, ext in _AUDIO_EXTENSIONS:
        if fmt.startswith(prefix):
            return ext
    return _DEFAULT_AUDIO_EXTENSION


def asset_dir(root: Path, asset: str, kind: str) -> Path:
    return root / "out" / MODALITY_BY_ASSET[asset] / kind


def asset_path(root: Path, asset: str, kind: str, asset_id: str,
               output_format: Optional[str] = None) -> Path:
    return asset_dir(root, asset, kind) / f"{asset_id}{extension_for(asset, output_format)}"
```

(`from typing import Optional` doit être présent en tête de module.)

- [ ] **Step 4 — run PASS**

```bash
.venv/bin/python -m pytest tests/test_paths.py -v
```

Attendu : tous les tests du fichier PASSED.

- [ ] **Step 5 — commit**

```bash
git add tests/test_paths.py src/tableforge/paths.py
git commit -m "test: verrou chemins vidéo out/video/<kind>/<id>.mp4"
```

(Si Step 3 a été nécessaire : `git commit -m "feat: chemins vidéo out/video/<kind>/<id>.mp4 dans paths"`.)

---

## Task 2: `providers/higgsfield.py` — builders purs + `submit`

**Files:**
- Create: `src/tableforge/providers/higgsfield.py`
- Create: `tests/test_higgsfield.py`
- Modify (si respx absent des dev-deps): `pyproject.toml`

**Interfaces:**
- Produces: `build_submit(slug: str, body: dict) -> dict` — `{"path": f"/{slug}", "json": body}` (pur)
- Produces: `submit(cfg, req: dict, *, api_key: str, api_secret: str, kind: str = "video") -> str` — POST `{base_url}{path}`, header `Authorization: Key {api_key}:{api_secret}`, retourne `request_id` ; erreur HTTP → `errors.raise_with_hint` ; réponse sans `request_id` → `RuntimeError` français. (Le kwarg optionnel `kind` est un sur-ensemble du contrat figé : il alimente `raise_with_hint` pour des hints contextualisés.)
- Consumes: `tableforge.config.HiggsfieldProviderConfig`, `tableforge.errors.raise_with_hint`

- [ ] **Step 0 — vérification doc API (lecture seule, pas de code)**

Consulte `https://docs.higgsfield.ai/docs/how-to/introduction.md` : confirme (a) `POST /{model_slug}` → `{"request_id": ...}`, (b) `GET /requests/{id}/status` et la forme de la réponse `completed` (champ contenant l'URL du média — hypothèse `{"status": "completed", "results": [{"url": ...}]}`), (c) le nom du champ image pour l'i2v (hypothèse `"image"`, data-URL acceptée), (d) le nom du champ durée (hypothèse `"duration"` en secondes). Note les écarts : ils s'appliquent aux Tasks 3–5.

- [ ] **Step 1 — dev-dep respx (déjà présent si P1 conforme)**

Vérifie :

```bash
grep -n "respx" pyproject.toml
```

Si absent, dans `pyproject.toml` remplace la ligne `dev = ["pytest", "pytest-cov"]` par :

```toml
dev = ["pytest", "pytest-cov", "respx"]
```

puis :

```bash
uv pip install --python .venv/bin/python -e ".[dev]"
```

Attendu : `respx` listé dans l'installation.

- [ ] **Step 2 — write failing tests**

Crée `tests/test_higgsfield.py` :

```python
import json

import httpx
import pytest
import respx

from tableforge.config import HiggsfieldProviderConfig
from tableforge.providers.higgsfield import build_submit, submit

BASE = "https://platform.higgsfield.ai"


def _cfg(**overrides):
    fields = {"type": "higgsfield", "poll_interval_s": 5.0, "poll_timeout_s": 12.0}
    fields.update(overrides)
    return HiggsfieldProviderConfig(**fields)


def test_build_submit_prefixes_slug_as_path():
    # Arrange / Act
    req = build_submit("bytedance/seedance/v1/image-to-video", {"prompt": "wind"})

    # Assert
    assert req == {"path": "/bytedance/seedance/v1/image-to-video",
                   "json": {"prompt": "wind"}}


def test_build_submit_copies_body():
    # Arrange
    body = {"prompt": "wind"}

    # Act
    req = build_submit("slug", body)
    req["json"]["prompt"] = "mutated"

    # Assert — le dict d'origine n'est pas modifié
    assert body == {"prompt": "wind"}


@respx.mock
def test_submit_posts_body_with_key_header_and_returns_request_id():
    # Arrange
    route = respx.post(f"{BASE}/bytedance/seedance/v1/image-to-video").mock(
        return_value=httpx.Response(200, json={"request_id": "req-42"}))
    req = build_submit("bytedance/seedance/v1/image-to-video", {"prompt": "wind"})

    # Act
    request_id = submit(_cfg(), req, api_key="k", api_secret="s")

    # Assert
    assert request_id == "req-42"
    sent = route.calls.last.request
    assert sent.headers["authorization"] == "Key k:s"
    assert json.loads(sent.content) == {"prompt": "wind"}


@respx.mock
def test_submit_without_request_id_raises_french_error():
    # Arrange
    respx.post(f"{BASE}/some/slug").mock(return_value=httpx.Response(200, json={}))

    # Act / Assert
    with pytest.raises(RuntimeError, match="request_id"):
        submit(_cfg(), build_submit("some/slug", {"prompt": "x"}),
               api_key="k", api_secret="s")


@respx.mock
def test_submit_http_error_goes_through_hints():
    # Arrange — 404 : slug de modèle inconnu
    respx.post(f"{BASE}/bad/slug").mock(return_value=httpx.Response(404, json={}))

    # Act / Assert — raise_with_hint (errors.py, P1) doit lever ; adapte le type
    # d'exception ici si P1 a retenu autre chose que RuntimeError.
    with pytest.raises(RuntimeError):
        submit(_cfg(), build_submit("bad/slug", {"prompt": "x"}),
               api_key="k", api_secret="s")
```

- [ ] **Step 3 — run (RED)**

```bash
.venv/bin/python -m pytest tests/test_higgsfield.py -v
```

Attendu : `ModuleNotFoundError: No module named 'tableforge.providers.higgsfield'` (collection en erreur).

- [ ] **Step 4 — implémentation minimale**

Crée `src/tableforge/providers/higgsfield.py` :

```python
"""Provider vidéo Higgsfield : submit -> poll -> download (httpx direct, API async)."""
from __future__ import annotations

import httpx

from ..errors import raise_with_hint

SUBMIT_TIMEOUT = 60.0


def build_submit(slug: str, body: dict) -> dict:
    return {"path": f"/{slug}", "json": dict(body)}


def _auth_headers(api_key: str, api_secret: str) -> dict:
    return {"Authorization": f"Key {api_key}:{api_secret}"}


def submit(cfg, req: dict, *, api_key: str, api_secret: str, kind: str = "video") -> str:
    response = httpx.post(f"{cfg.base_url}{req['path']}", json=req["json"],
                          headers=_auth_headers(api_key, api_secret),
                          timeout=SUBMIT_TIMEOUT)
    if response.is_error:
        raise_with_hint(response, provider_type="higgsfield", asset="video", kind=kind)
    request_id = response.json().get("request_id")
    if not request_id:
        raise RuntimeError(
            "Higgsfield : réponse de soumission sans 'request_id' — vérifie le slug du "
            "modèle et le format de l'API sur docs.higgsfield.ai.")
    return str(request_id)
```

- [ ] **Step 5 — run PASS**

```bash
.venv/bin/python -m pytest tests/test_higgsfield.py -v
```

Attendu : 5 passed.

- [ ] **Step 6 — commit**

```bash
git add src/tableforge/providers/higgsfield.py tests/test_higgsfield.py pyproject.toml
git commit -m "feat: soumission Higgsfield (build_submit, submit, auth Key)"
```

---

## Task 3: `poll` — transitions, `failed`/`nsfw` remboursés, timeout, URL de résultat

**Files:**
- Modify: `src/tableforge/providers/higgsfield.py`
- Test: `tests/test_higgsfield.py` (ajouts)

**Interfaces:**
- Produces: `poll(cfg, request_id: str, *, api_key: str, api_secret: str, sleep=time.sleep, on_status: Optional[Callable[[str], None]] = None, kind: str = "video") -> dict` — GET `/requests/{id}/status` en boucle ; `on_status` appelé à **chaque changement** de statut ; `completed` → retourne le payload JSON ; `failed`/`nsfw` → `RuntimeError` contenant « requête remboursée automatiquement » ; dépassement de `cfg.poll_timeout_s` → `RuntimeError` mentionnant `poll_timeout_s`.
- Produces: `_result_url(payload: dict) -> str` — extraction avec fallbacks (`results[0].url` → `results[0]` str → `result.url` → `url`), sinon `RuntimeError` pointant docs.higgsfield.ai.
- Consumes: `cfg.poll_interval_s`, `cfg.poll_timeout_s`, `cfg.base_url`

- [ ] **Step 1 — write failing tests**

Ajoute à `tests/test_higgsfield.py` (imports en tête : ajoute `poll` et `_result_url` à l'import depuis `tableforge.providers.higgsfield`) :

```python
def _status_route(sequence):
    return respx.get(f"{BASE}/requests/req-42/status").mock(
        side_effect=[httpx.Response(200, json=payload) for payload in sequence])


@respx.mock
def test_poll_reports_transitions_and_returns_completed_payload():
    # Arrange
    route = _status_route([
        {"status": "queued"},
        {"status": "in_progress"},
        {"status": "completed", "results": [{"url": "https://cdn.x/v.mp4"}]},
    ])
    seen, sleeps = [], []

    # Act
    payload = poll(_cfg(), "req-42", api_key="k", api_secret="s",
                   sleep=sleeps.append, on_status=seen.append)

    # Assert
    assert seen == ["queued", "in_progress", "completed"]
    assert sleeps == [5.0, 5.0]
    assert payload["results"][0]["url"] == "https://cdn.x/v.mp4"
    assert route.calls.last.request.headers["authorization"] == "Key k:s"


@respx.mock
def test_poll_does_not_repeat_unchanged_status():
    # Arrange
    _status_route([{"status": "queued"}, {"status": "queued"},
                   {"status": "completed", "results": [{"url": "u"}]}])
    seen = []

    # Act
    poll(_cfg(), "req-42", api_key="k", api_secret="s",
         sleep=lambda _s: None, on_status=seen.append)

    # Assert
    assert seen == ["queued", "completed"]


@pytest.mark.parametrize("status", ["failed", "nsfw"])
def test_poll_failed_and_nsfw_raise_refunded_error(status):
    # Arrange
    with respx.mock:
        _status_route([{"status": status}])

        # Act / Assert
        with pytest.raises(RuntimeError, match="remboursée automatiquement"):
            poll(_cfg(), "req-42", api_key="k", api_secret="s", sleep=lambda _s: None)


@respx.mock
def test_poll_times_out_with_explicit_error():
    # Arrange — statut qui ne progresse jamais ; timeout 12 s, intervalle 5 s
    respx.get(f"{BASE}/requests/req-42/status").mock(
        return_value=httpx.Response(200, json={"status": "queued"}))
    sleeps = []

    # Act / Assert
    with pytest.raises(RuntimeError, match="poll_timeout_s"):
        poll(_cfg(), "req-42", api_key="k", api_secret="s", sleep=sleeps.append)
    assert sleeps == [5.0, 5.0, 5.0]


def test_result_url_fallbacks():
    # Arrange / Act / Assert — format supposé + fallbacks (à confronter à la doc)
    assert _result_url({"results": [{"url": "a"}]}) == "a"
    assert _result_url({"results": ["b"]}) == "b"
    assert _result_url({"result": {"url": "c"}}) == "c"
    assert _result_url({"url": "d"}) == "d"
    with pytest.raises(RuntimeError, match="docs.higgsfield.ai"):
        _result_url({"status": "completed"})
```

- [ ] **Step 2 — run (RED)**

```bash
.venv/bin/python -m pytest tests/test_higgsfield.py -v
```

Attendu : `ImportError: cannot import name 'poll'`.

- [ ] **Step 3 — implémentation minimale**

Dans `src/tableforge/providers/higgsfield.py`, ajoute (imports en tête : `import time`, `from typing import Callable, Optional`) :

```python
_TERMINAL_FAILURES = ("failed", "nsfw")
_RESULT_URL_KEYS = ("url", "raw_url", "video_url")


def poll(cfg, request_id: str, *, api_key: str, api_secret: str,
         sleep: Callable[[float], None] = time.sleep,
         on_status: Optional[Callable[[str], None]] = None,
         kind: str = "video") -> dict:
    status_url = f"{cfg.base_url}/requests/{request_id}/status"
    headers = _auth_headers(api_key, api_secret)
    elapsed = 0.0
    last_status: Optional[str] = None
    while True:
        response = httpx.get(status_url, headers=headers, timeout=SUBMIT_TIMEOUT)
        if response.is_error:
            raise_with_hint(response, provider_type="higgsfield", asset="video", kind=kind)
        payload = response.json()
        status = str(payload.get("status", ""))
        if status != last_status:
            if on_status is not None:
                on_status(status)
            last_status = status
        if status == "completed":
            return payload
        if status in _TERMINAL_FAILURES:
            raise RuntimeError(
                f"Higgsfield : requête {request_id} terminée en '{status}' "
                "(requête remboursée automatiquement). Ajuste le prompt et relance.")
        if elapsed >= cfg.poll_timeout_s:
            raise RuntimeError(
                f"Higgsfield : délai dépassé pour la requête {request_id} "
                f"(dernier statut : '{status}') — augmente poll_timeout_s "
                f"(actuel : {cfg.poll_timeout_s:g}s) ou réessaie.")
        sleep(cfg.poll_interval_s)
        elapsed += cfg.poll_interval_s


def _result_url(payload: dict) -> str:
    # Format attendu : {"status": "completed", "results": [{"url": ...}]}.
    # Le champ exact DOIT être vérifié contre docs.higgsfield.ai/docs/how-to/
    # introduction.md au moment de l'implémentation — fallbacks raisonnables ici.
    results = payload.get("results")
    if isinstance(results, list) and results:
        first = results[0]
        if isinstance(first, dict):
            for key in _RESULT_URL_KEYS:
                if first.get(key):
                    return str(first[key])
        if isinstance(first, str) and first:
            return first
    result = payload.get("result")
    if isinstance(result, dict):
        for key in _RESULT_URL_KEYS:
            if result.get(key):
                return str(result[key])
    if payload.get("url"):
        return str(payload["url"])
    raise RuntimeError(
        "Higgsfield : réponse 'completed' sans URL de résultat reconnue — vérifie le "
        "format de GET /requests/{id}/status sur docs.higgsfield.ai.")
```

- [ ] **Step 4 — run PASS**

```bash
.venv/bin/python -m pytest tests/test_higgsfield.py -v
```

Attendu : 11 passed.

- [ ] **Step 5 — commit**

```bash
git add src/tableforge/providers/higgsfield.py tests/test_higgsfield.py
git commit -m "feat: poll Higgsfield (transitions, failed/nsfw remboursés, timeout, URL résultat)"
```

---

## Task 4: `HiggsfieldProvider` — options video, `plan()` pur, `execute()` réseau

**Files:**
- Modify: `src/tableforge/providers/higgsfield.py`
- Test: `tests/test_higgsfield.py` (ajouts)

**Interfaces:**
- Produces: `HiggsfieldVideoOptions(BaseModel)` — `extra="forbid"` ; `model: str` (requis), `aspect_ratio: Optional[str]`, `resolution: Optional[str]`, `duration_s: Optional[float]`.
- Produces: `@dataclass(frozen=True) HiggsfieldProvider` — champs `api_key_env, api_secret_env, base_url, default_image_model, poll_interval_s, poll_timeout_s, sleep: Callable[[float], None] = time.sleep` ; `from_config(cls, cfg: HiggsfieldProviderConfig)` (ne résout PAS les clés) ; `plan(self, spec: KindSpec) -> list[AssetJob]` (pur, encode la data-URL i2v dans `payload`, résumé `[image source : …]` dans `request`) ; `execute(self, job: AssetJob) -> list[Path]` (clés via dotenv/env, submit → poll avec transitions `typer.echo` par id → download `.mp4`).
- Consumes: `targets.KindSpec`, `targets.Target` (avec `KindSpec.root: Path`, cf. points d'ancrage), `providers.base.AssetJob`, `paths.asset_path`, `prompts.encode_image_data_url`

- [ ] **Step 1 — write failing tests**

Ajoute à `tests/test_higgsfield.py`. En tête de fichier, complète les imports :

```python
from dataclasses import replace
from pathlib import Path

from PIL import Image
from pydantic import ValidationError

from tableforge.providers.higgsfield import (HiggsfieldProvider, HiggsfieldVideoOptions,
                                             _result_url, build_submit, poll, submit)
from tableforge.targets import KindSpec, Target
```

puis les tests :

```python
def _spec(tmp_path, targets, options=None, kind="teaser"):
    return KindSpec(kind=kind, asset="video", provider_name="higgsfield",
                    options=options or {"model": "kling-video/v2.1/standard/text-to-video"},
                    targets=tuple(targets), output_format=None, root=tmp_path)


def test_video_options_reject_unknown_keys():
    # Arrange / Act / Assert
    with pytest.raises(ValidationError):
        HiggsfieldVideoOptions(model="m", fps=24)


def test_video_options_require_model():
    with pytest.raises(ValidationError):
        HiggsfieldVideoOptions(aspect_ratio="16:9")


def test_plan_t2v_builds_submit_jobs(tmp_path):
    # Arrange
    provider = HiggsfieldProvider.from_config(_cfg())
    spec = _spec(tmp_path,
                 [Target(id="intro", text="A ruined throne room",
                         settings={"duration_s": 8})],
                 options={"model": "kling-video/v2.1/standard/text-to-video",
                          "aspect_ratio": "16:9"})

    # Act
    jobs = provider.plan(spec)

    # Assert
    assert len(jobs) == 1
    job = jobs[0]
    assert job.id == "intro"
    assert job.dest == tmp_path / "out" / "video" / "teaser" / "intro.mp4"
    assert job.request["path"] == "/kling-video/v2.1/standard/text-to-video"
    assert job.request["json"] == {"prompt": "A ruined throne room",
                                   "aspect_ratio": "16:9", "duration": 8}
    assert job.payload["submit"]["json"] == job.request["json"]


def test_plan_kind_duration_is_fallback_only(tmp_path):
    # Arrange — duration_s au niveau kind, surchargée par les settings de la cible
    provider = HiggsfieldProvider.from_config(_cfg())
    options = {"model": "m/slug", "duration_s": 4}
    spec = _spec(tmp_path, [Target(id="a", text="x", settings={"duration_s": 9}),
                            Target(id="b", text="y")], options=options)

    # Act
    jobs = provider.plan(spec)

    # Assert
    assert jobs[0].request["json"]["duration"] == 9
    assert jobs[1].request["json"]["duration"] == 4


def test_plan_i2v_encodes_source_image_only_in_payload(tmp_path):
    # Arrange
    art = tmp_path / "out" / "art" / "cards" / "lame.png"
    art.parent.mkdir(parents=True)
    Image.new("RGB", (8, 8), "red").save(art)
    provider = HiggsfieldProvider.from_config(_cfg())
    spec = _spec(tmp_path, [Target(id="lame", text="wind", source_image=art)],
                 kind="cartes-animees",
                 options={"model": "bytedance/seedance/v1/image-to-video"})

    # Act
    job = provider.plan(spec)[0]

    # Assert — data-URL dans payload, jamais dans request
    assert job.payload["submit"]["json"]["image"].startswith("data:image/jpeg;base64,")
    assert job.request["json"]["image"] == f"[image source : {art}]"
    assert "data:" not in str(job.request)
    assert job.dest == tmp_path / "out" / "video" / "cartes-animees" / "lame.mp4"


def test_plan_i2v_missing_art_defers_error_to_execute(tmp_path):
    # Arrange — l'art n'existe pas : note en dry-run, erreur à l'exécution
    art = tmp_path / "out" / "art" / "cards" / "lame.png"
    note = f"art source manquant : {art} — lance d'abord `forge generate cards`"
    provider = HiggsfieldProvider.from_config(_cfg())
    spec = _spec(tmp_path,
                 [Target(id="lame", text="wind", source_image=art, notes=(note,))],
                 kind="cartes-animees",
                 options={"model": "bytedance/seedance/v1/image-to-video"})

    # Act
    job = provider.plan(spec)[0]

    # Assert
    assert "image" not in job.payload["submit"]["json"]
    assert job.request["json"]["image"] == f"[image source : {art}]"
    assert note in job.notes
    with pytest.raises(RuntimeError, match="art source manquant"):
        provider.execute(job)


def test_plan_rejects_non_video_asset(tmp_path):
    # Arrange — l'image Higgsfield n'arrive qu'en P3b
    provider = HiggsfieldProvider.from_config(_cfg())
    spec = replace(_spec(tmp_path, [Target(id="x", text="x")]), asset="image")

    # Act / Assert
    with pytest.raises(ValueError, match="P3b"):
        provider.plan(spec)


@respx.mock
def test_execute_submits_polls_downloads(tmp_path, monkeypatch, capsys):
    # Arrange
    monkeypatch.setenv("HIGGSFIELD_API_KEY", "k")
    monkeypatch.setenv("HIGGSFIELD_API_SECRET", "s")
    submit_route = respx.post(f"{BASE}/kling-video/v2.1/standard/text-to-video").mock(
        return_value=httpx.Response(200, json={"request_id": "req-42"}))
    respx.get(f"{BASE}/requests/req-42/status").mock(
        return_value=httpx.Response(200, json={
            "status": "completed", "results": [{"url": "https://cdn.x/v.mp4"}]}))
    respx.get("https://cdn.x/v.mp4").mock(
        return_value=httpx.Response(200, content=b"MP4DATA"))
    provider = HiggsfieldProvider.from_config(_cfg())
    job = provider.plan(_spec(tmp_path, [Target(id="intro", text="ruins")]))[0]

    # Act
    saved = provider.execute(job)

    # Assert
    dest = tmp_path / "out" / "video" / "teaser" / "intro.mp4"
    assert saved == [dest]
    assert dest.read_bytes() == b"MP4DATA"
    assert submit_route.calls.last.request.headers["authorization"] == "Key k:s"
    out = capsys.readouterr().out
    assert "intro: completed" in out


def test_execute_requires_both_keys(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.delenv("HIGGSFIELD_API_KEY", raising=False)
    monkeypatch.delenv("HIGGSFIELD_API_SECRET", raising=False)
    provider = HiggsfieldProvider.from_config(_cfg())
    job = provider.plan(_spec(tmp_path, [Target(id="intro", text="x")]))[0]

    # Act / Assert
    with pytest.raises(RuntimeError, match="HIGGSFIELD_API_KEY et HIGGSFIELD_API_SECRET"):
        provider.execute(job)
```

- [ ] **Step 2 — run (RED)**

```bash
.venv/bin/python -m pytest tests/test_higgsfield.py -v
```

Attendu : `ImportError: cannot import name 'HiggsfieldProvider'`.

- [ ] **Step 3 — implémentation minimale**

Dans `src/tableforge/providers/higgsfield.py`, complète les imports de tête :

```python
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import httpx
import typer
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict

from ..config import HiggsfieldProviderConfig
from ..errors import raise_with_hint
from ..paths import asset_path
from ..prompts import encode_image_data_url
from ..targets import KindSpec, Target
from .base import AssetJob
```

et ajoute en fin de module :

```python
DOWNLOAD_TIMEOUT = 300.0


class HiggsfieldVideoOptions(BaseModel):
    """Options acceptées dans generate: pour (higgsfield, video)."""
    model_config = ConfigDict(extra="forbid")
    model: str
    aspect_ratio: Optional[str] = None
    resolution: Optional[str] = None
    duration_s: Optional[float] = None


def _video_body(target: Target, options: HiggsfieldVideoOptions) -> dict:
    body: dict = {"prompt": target.text}
    if options.aspect_ratio:
        body["aspect_ratio"] = options.aspect_ratio
    if options.resolution:
        body["resolution"] = options.resolution
    duration = target.settings.get("duration_s", options.duration_s)
    if duration is not None:
        # Nom du champ côté API à confronter à docs.higgsfield.ai ('duration', secondes).
        body["duration"] = duration
    return body


@dataclass(frozen=True)
class HiggsfieldProvider:
    api_key_env: str
    api_secret_env: str
    base_url: str
    default_image_model: str
    poll_interval_s: float
    poll_timeout_s: float
    sleep: Callable[[float], None] = time.sleep

    @classmethod
    def from_config(cls, cfg: HiggsfieldProviderConfig) -> "HiggsfieldProvider":
        return cls(api_key_env=cfg.api_key_env, api_secret_env=cfg.api_secret_env,
                   base_url=cfg.base_url, default_image_model=cfg.default_image_model,
                   poll_interval_s=cfg.poll_interval_s, poll_timeout_s=cfg.poll_timeout_s)

    def plan(self, spec: KindSpec) -> list[AssetJob]:
        if spec.asset != "video":
            raise ValueError(
                f"provider higgsfield : asset '{spec.asset}' non géré en P3a — seuls "
                "les kinds video sont acceptés (l'image Higgsfield arrive en P3b).")
        options = HiggsfieldVideoOptions(**spec.options)
        jobs: list[AssetJob] = []
        for target in spec.targets:
            body = _video_body(target, options)
            summary_body = dict(body)
            payload: dict = {"kind": spec.kind}
            if target.source_image is not None:
                summary_body["image"] = f"[image source : {target.source_image}]"
                if target.source_image.exists():
                    body = {**body, "image": encode_image_data_url(target.source_image)}
                else:
                    payload["missing_source"] = (
                        f"art source manquant : {target.source_image} — génère d'abord "
                        "l'art du kind source (forge generate).")
            payload["submit"] = build_submit(options.model, body)
            jobs.append(AssetJob(
                id=target.id,
                dest=asset_path(spec.root, "video", spec.kind, target.id),
                request={"path": payload["submit"]["path"], "json": summary_body},
                payload=payload,
                notes=target.notes,
            ))
        return jobs

    def _require_keys(self) -> tuple[str, str]:
        load_dotenv()
        key = os.environ.get(self.api_key_env)
        secret = os.environ.get(self.api_secret_env)
        missing = [name for name, value in ((self.api_key_env, key),
                                            (self.api_secret_env, secret)) if not value]
        if missing:
            raise RuntimeError(
                f"{' et '.join(missing)} manquant(s) : copie .env.example vers .env et "
                "renseigne tes clés (crée-les sur https://platform.higgsfield.ai).")
        return key, secret

    def execute(self, job: AssetJob) -> list[Path]:
        missing_source = job.payload.get("missing_source")
        if missing_source:
            raise RuntimeError(missing_source)
        api_key, api_secret = self._require_keys()
        kind = str(job.payload.get("kind", "video"))
        request_id = submit(self, job.payload["submit"],
                            api_key=api_key, api_secret=api_secret, kind=kind)
        typer.echo(f"  {job.id}: requête higgsfield {request_id}")
        payload = poll(self, request_id, api_key=api_key, api_secret=api_secret,
                       sleep=self.sleep, kind=kind,
                       on_status=lambda status: typer.echo(f"  {job.id}: {status}"))
        url = _result_url(payload)
        response = httpx.get(url, timeout=DOWNLOAD_TIMEOUT)
        response.raise_for_status()
        job.dest.parent.mkdir(parents=True, exist_ok=True)
        job.dest.write_bytes(response.content)
        return [job.dest]
```

Notes : `submit(self, …)` / `poll(self, …)` fonctionnent par duck-typing (le provider porte `base_url`, `poll_interval_s`, `poll_timeout_s` comme la config). Le champ `sleep` rend le poll testable via `dataclasses.replace(provider, sleep=…)` sans monkeypatch.

- [ ] **Step 4 — run PASS**

```bash
.venv/bin/python -m pytest tests/test_higgsfield.py -v
```

Attendu : 20 passed.

- [ ] **Step 5 — commit**

```bash
git add src/tableforge/providers/higgsfield.py tests/test_higgsfield.py
git commit -m "feat: HiggsfieldProvider plan/execute (i2v data-URL, download mp4, transitions)"
```

---

## Task 5: Cibles vidéo dans `targets.py` — i2v (`from:`) et t2v (catalogue)

**Files:**
- Modify: `src/tableforge/targets.py`
- Test: `tests/test_targets.py` (ajouts en fin de fichier)

**Interfaces:**
- Produces: branche `asset == "video"` dans `build_kind_spec(project, kind, ids)` →
  - **i2v** (`kind_cfg.from_` renseigné) : cibles = ids d'art existants `out/art/<from>/*.png` ∪ entrées du catalogue de mouvement (optionnel) ; entrées ∉ (ids du kind source ∪ art existant) → `ValueError` nommant le catalogue ET le fichier d'ids source ; art manquant → note d'avertissement sur la cible (`Target.notes`), l'erreur bloquante vient de `execute` (Task 4) ; `Target.source_image` = `out/art/<from>/<id>.png`.
  - **t2v** (pas de `from_`) : cibles = entrées du catalogue (`prompts:` requis sinon `ValueError`).
  - Précédence `settings["duration_s"]` : entrée > `defaults:` du catalogue (le niveau kind est gérés par `options` côté provider, Task 4).
- Consumes: `catalog.load_catalog`, `catalog.catalog_entries`, `catalog.get_entry`, `catalog.prompt_for_entry`, `paths.asset_dir`, `paths.asset_path`, `prompts.load_prompts`, `data.load_rows`

- [ ] **Step 1 — write failing tests**

Ajoute en fin de `tests/test_targets.py` (réutilise les imports existants du fichier ; ajoute si besoin `from tableforge.targets import build_kind_spec` et `from tableforge.config import load_project`) :

```python
FORGE_VIDEO = """
project: demo
providers:
  ark:
    type: seedream
    base_url: https://ark.x/api/v3
    api_key_env: ARK_API_KEY
    model: seedream-5-0-260128
  hf:
    type: higgsfield
kinds:
  cards:
    prompts: prompts/cards.yaml
    template: templates/card
    render_size: {width: 10, height: 10}
    generate: {with: ark}
  cartes-animees:
    asset: video
    from: cards
    prompts: prompts/cartes-animees.yaml
    generate: {with: hf, model: bytedance/seedance/v1/image-to-video}
  teaser:
    asset: video
    prompts: prompts/teaser.yaml
    generate: {with: hf, model: kling-video/v2.1/standard/text-to-video, aspect_ratio: "16:9"}
"""

CARDS_PROMPTS = """
art_direction: "Dark fantasy."
prompts:
  lame: "A footman."
  emissaire: "A hooded envoy."
"""

MOTION_CATALOG = """
direction: "Slow atmospheric motion, seamless loop."
defaults:
  duration_s: 5
entries:
  lame: {prompt: "The cloak ripples in a cold wind"}
"""

TEASER_CATALOG = """
direction: "Cinematic dark fantasy trailer shot."
entries:
  intro: {prompt: "A ruined throne room, ash rising", duration_s: 8}
"""


def _video_project(tmp_path, motion=MOTION_CATALOG, art_ids=("lame", "emissaire")):
    (tmp_path / "forge.yaml").write_text(FORGE_VIDEO, encoding="utf-8")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "cards.yaml").write_text(CARDS_PROMPTS, encoding="utf-8")
    (tmp_path / "prompts" / "cartes-animees.yaml").write_text(motion, encoding="utf-8")
    (tmp_path / "prompts" / "teaser.yaml").write_text(TEASER_CATALOG, encoding="utf-8")
    art_dir = tmp_path / "out" / "art" / "cards"
    art_dir.mkdir(parents=True)
    for art_id in art_ids:
        (art_dir / f"{art_id}.png").write_bytes(b"png")
    return load_project(tmp_path)


def test_t2v_spec_uses_catalog_entries(tmp_path):
    # Arrange
    project = _video_project(tmp_path)

    # Act
    spec = build_kind_spec(project, "teaser")

    # Assert
    assert spec.asset == "video"
    assert spec.provider_name == "hf"
    assert spec.options == {"model": "kling-video/v2.1/standard/text-to-video",
                            "aspect_ratio": "16:9"}
    assert [t.id for t in spec.targets] == ["intro"]
    target = spec.targets[0]
    assert target.text == "A ruined throne room, ash rising. Cinematic dark fantasy trailer shot."
    assert target.settings == {"duration_s": 8}
    assert target.source_image is None


def test_t2v_without_catalog_raises(tmp_path):
    # Arrange — teaser sans fichier prompts
    forge = FORGE_VIDEO.replace("    prompts: prompts/teaser.yaml\n", "")
    (tmp_path / "forge.yaml").write_text(forge, encoding="utf-8")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "cards.yaml").write_text(CARDS_PROMPTS, encoding="utf-8")
    (tmp_path / "prompts" / "cartes-animees.yaml").write_text(MOTION_CATALOG, encoding="utf-8")
    project = load_project(tmp_path)

    # Act / Assert
    with pytest.raises(ValueError, match="prompts"):
        build_kind_spec(project, "teaser")


def test_i2v_targets_are_union_of_art_and_catalog(tmp_path):
    # Arrange — art pour lame + emissaire, catalogue pour lame seulement
    project = _video_project(tmp_path)

    # Act
    spec = build_kind_spec(project, "cartes-animees")

    # Assert
    assert [t.id for t in spec.targets] == ["emissaire", "lame"]
    lame = next(t for t in spec.targets if t.id == "lame")
    assert lame.text == "The cloak ripples in a cold wind. Slow atmospheric motion, seamless loop."
    assert lame.settings == {"duration_s": 5}
    assert lame.source_image == tmp_path / "out" / "art" / "cards" / "lame.png"
    assert lame.notes == ()
    emissaire = next(t for t in spec.targets if t.id == "emissaire")
    assert emissaire.text == "Slow atmospheric motion, seamless loop."
    assert emissaire.settings == {"duration_s": 5}


def test_i2v_missing_art_adds_warning_note(tmp_path):
    # Arrange — entrée catalogue 'lame' mais aucun art généré
    project = _video_project(tmp_path, art_ids=())

    # Act
    spec = build_kind_spec(project, "cartes-animees")

    # Assert — la cible existe (dry-run possible), avec note d'avertissement
    assert [t.id for t in spec.targets] == ["lame"]
    assert any("art source manquant" in note for note in spec.targets[0].notes)
    assert any("forge generate cards" in note for note in spec.targets[0].notes)


def test_i2v_catalog_entry_outside_source_ids_raises_naming_both_files(tmp_path):
    # Arrange
    bad_catalog = MOTION_CATALOG + "  fantome: {prompt: \"ghost\"}\n"

    # Act / Assert
    project = _video_project(tmp_path, motion=bad_catalog)
    with pytest.raises(ValueError) as excinfo:
        build_kind_spec(project, "cartes-animees")
    message = str(excinfo.value)
    assert "fantome" in message
    assert "cartes-animees.yaml" in message
    assert "cards.yaml" in message


def test_i2v_filters_ids_and_rejects_unknown(tmp_path):
    # Arrange
    project = _video_project(tmp_path)

    # Act
    spec = build_kind_spec(project, "cartes-animees", ids=["lame"])

    # Assert
    assert [t.id for t in spec.targets] == ["lame"]
    with pytest.raises(KeyError, match="inconnu"):
        build_kind_spec(project, "cartes-animees", ids=["nope"])
```

- [ ] **Step 2 — run (RED)**

```bash
.venv/bin/python -m pytest tests/test_targets.py -v
```

Attendu : les 6 nouveaux tests FAILED (`ValueError` « asset 'video' non géré » ou équivalent selon le message P2 de `build_kind_spec` pour un asset inconnu), les tests P1/P2 existants restent PASSED.

- [ ] **Step 3 — implémentation minimale**

Dans `src/tableforge/targets.py` :

1. Complète les imports (garde les existants) :

```python
from .catalog import catalog_entries, get_entry, load_catalog, prompt_for_entry
from .config import KindConfig, ProjectConfig
from .data import load_rows
from .paths import asset_dir, asset_path
from .prompts import load_prompts
```

2. Dans `build_kind_spec`, à l'endroit où les autres assets sont dispatchés (branches `music`/`sfx`/`tts`/`dialogue` de P1/P2), ajoute la branche vidéo — `provider_name` et `options` sont résolus par le mécanisme déjà en place (extras de `generate:` sans `with`) :

```python
    if kind_cfg.asset == "video":
        return KindSpec(kind=kind, asset="video", provider_name=provider_name,
                        options=options, targets=_video_targets(project, kind_cfg, ids),
                        output_format=None, root=project.root)
```

3. Ajoute en fin de module :

```python
def _video_targets(project: ProjectConfig, kind_cfg: KindConfig,
                   ids: Optional[list[str]]) -> tuple[Target, ...]:
    if kind_cfg.from_ is not None:
        return _i2v_targets(project, kind_cfg, ids)
    return _t2v_targets(kind_cfg, ids)


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
        notes: tuple[str, ...] = ()
        if not source_image.exists():
            notes = (f"art source manquant : {source_image} — lance d'abord "
                     f"`forge generate {source_name}`",)
        if target_id in known_entries:
            text = prompt_for_entry(target_id, catalog_cfg)
            settings = _video_settings(catalog_cfg, get_entry(catalog_cfg, target_id))
        else:
            text = str(catalog_cfg.get("direction", "")).strip()
            settings = _video_settings(catalog_cfg, {})
        targets.append(Target(id=target_id, text=text, source_image=source_image,
                              settings=settings, notes=notes))
    return tuple(targets)


def _source_image_ids(source_kind: KindConfig) -> list[str]:
    if source_kind.prompts is not None:
        return list((load_prompts(source_kind.prompts).get("prompts") or {}).keys())
    if source_kind.data is not None:
        return [row.id for row in load_rows(source_kind.data)]
    return []


def _video_settings(cfg: dict, entry: dict) -> dict:
    settings: dict = {}
    for source in (dict(cfg.get("defaults") or {}), entry):
        if source.get("duration_s") is not None:
            settings["duration_s"] = source["duration_s"]
    return settings


def _filter_ids(kind_name: str, target_ids: list[str],
                ids: Optional[list[str]]) -> list[str]:
    if not ids:
        return target_ids
    unknown = sorted(set(ids) - set(target_ids))
    if unknown:
        raise KeyError(
            f"id(s) inconnu(s) pour le kind '{kind_name}' : {', '.join(unknown)} "
            f"(connus : {', '.join(target_ids)})")
    wanted = set(ids)
    return [target_id for target_id in target_ids if target_id in wanted]
```

Si P1 possède déjà un helper équivalent à `_filter_ids` ou `_video_settings` (précédence entrée > defaults utilisée pour music/sfx), réutilise-le (DRY) au lieu de dupliquer — le comportement attendu par les tests fait foi.

- [ ] **Step 4 — run PASS**

```bash
.venv/bin/python -m pytest tests/test_targets.py tests/test_higgsfield.py -v
```

Attendu : tout PASSED.

- [ ] **Step 5 — commit**

```bash
git add src/tableforge/targets.py tests/test_targets.py
git commit -m "feat: cibles vidéo i2v (from:) et t2v (catalogue) dans build_kind_spec"
```

---

## Task 6: Branchement registre — `provider_for`, `options_model`, `validate_project`

**Files:**
- Modify: `src/tableforge/providers/base.py`
- Test: `tests/test_providers_base.py` (fichier de tests du module base créé en P1 — cf. point d'ancrage n°3 ; ajoute les tests en fin de fichier)

**Interfaces:**
- Produces: `SUPPORTED_ASSETS["higgsfield"] == frozenset({"image", "video"})` (conforme au contrat figé ; l'asset image est refusé par `HiggsfieldProvider.plan` avec un message « P3b » jusqu'à la phase suivante).
- Produces: `provider_for(project, kind_cfg)` retourne un `HiggsfieldProvider` pour un provider de type `higgsfield`.
- Produces: `options_model("higgsfield", "video") is HiggsfieldVideoOptions`.
- Consumes: `validate_project` (P1) — les contrôles `from_` (kind inexistant / non-image) et options inconnues existent déjà ; les tests ci-dessous les verrouillent pour la vidéo.

- [ ] **Step 1 — write failing tests**

Dans le fichier de tests du module base (nommé ici `tests/test_providers_base.py`), ajoute :

```python
VIDEO_FORGE = """
project: demo
providers:
  hf:
    type: higgsfield
kinds:
  teaser:
    asset: video
    prompts: prompts/teaser.yaml
    generate: {with: hf, model: kling-video/v2.1/standard/text-to-video}
"""

VIDEO_CATALOG = """
direction: "Cinematic."
entries:
  intro: {prompt: "A ruined throne room"}
"""


def _video_project(tmp_path, forge=VIDEO_FORGE):
    (tmp_path / "forge.yaml").write_text(forge, encoding="utf-8")
    (tmp_path / "prompts").mkdir(exist_ok=True)
    (tmp_path / "prompts" / "teaser.yaml").write_text(VIDEO_CATALOG, encoding="utf-8")
    return load_project(tmp_path)


def test_supported_assets_declare_higgsfield_video():
    assert "video" in SUPPORTED_ASSETS["higgsfield"]


def test_provider_for_returns_higgsfield_provider(tmp_path):
    # Arrange
    project = _video_project(tmp_path)

    # Act
    provider = provider_for(project, project.kind("teaser"))

    # Assert
    from tableforge.providers.higgsfield import HiggsfieldProvider
    assert isinstance(provider, HiggsfieldProvider)
    assert provider.base_url == "https://platform.higgsfield.ai"


def test_options_model_higgsfield_video():
    from tableforge.providers.higgsfield import HiggsfieldVideoOptions
    assert options_model("higgsfield", "video") is HiggsfieldVideoOptions


def test_validate_project_flags_unknown_video_option(tmp_path):
    # Arrange — fps n'est pas une option (higgsfield, video)
    forge = VIDEO_FORGE.replace(
        "generate: {with: hf, model: kling-video/v2.1/standard/text-to-video}",
        "generate: {with: hf, model: kling-video/v2.1/standard/text-to-video, fps: 24}")
    project = _video_project(tmp_path, forge=forge)

    # Act
    issues = validate_project(project)

    # Assert
    assert any("fps" in issue for issue in issues)


def test_validate_project_flags_from_to_unknown_kind(tmp_path):
    # Arrange — from: vers un kind inexistant (contrôle posé en P1, verrouillé ici)
    forge = VIDEO_FORGE.replace("    prompts: prompts/teaser.yaml\n",
                                "    prompts: prompts/teaser.yaml\n    from: nope\n")
    project = _video_project(tmp_path, forge=forge)

    # Act
    issues = validate_project(project)

    # Assert
    assert any("nope" in issue for issue in issues)
```

(Complète les imports du fichier si besoin : `from tableforge.config import load_project` et `from tableforge.providers.base import SUPPORTED_ASSETS, options_model, provider_for, validate_project`.)

- [ ] **Step 2 — run (RED)**

```bash
.venv/bin/python -m pytest tests/test_providers_base.py -v
```

Attendu : `test_provider_for_returns_higgsfield_provider` et `test_options_model_higgsfield_video` FAILED (provider non branché) ; `test_supported_assets_declare_higgsfield_video`, `test_validate_project_flags_from_to_unknown_kind` et éventuellement `test_validate_project_flags_unknown_video_option` peuvent déjà passer si P1 a posé le registre complet — c'est le but du verrou.

- [ ] **Step 3 — implémentation minimale**

Dans `src/tableforge/providers/base.py` :

1. Vérifie/complète le registre de capacités (valeur finale exacte) :

```python
SUPPORTED_ASSETS: dict[str, frozenset[str]] = {
    "seedream": frozenset({"image"}),
    "elevenlabs": frozenset({"music", "sfx", "tts", "dialogue"}),
    "higgsfield": frozenset({"image", "video"}),
    "manual": frozenset({"image", "music", "sfx", "tts", "dialogue", "video"}),
}
```

(L'asset `image` de higgsfield est déclaré conformément au contrat figé mais `HiggsfieldProvider.plan` le refuse avec un message « P3b » — Task 4.)

2. Dans `provider_for`, ajoute la branche de construction (import local pour éviter un import circulaire, même motif que seedream/elevenlabs) :

```python
    if isinstance(provider_cfg, HiggsfieldProviderConfig):
        from .higgsfield import HiggsfieldProvider
        return HiggsfieldProvider.from_config(provider_cfg)
```

(`HiggsfieldProviderConfig` s'importe depuis `..config`, à côté des autres configs déjà importées ; `provider_cfg` est le nom de la variable locale portant la config résolue — adapte au nom réel utilisé par P0/P1.)

3. Dans `options_model`, ajoute l'entrée. Si P1 a un dict de registre :

```python
    ("higgsfield", "video"): _higgsfield_video_options,
```

avec un lazy-loader (même motif que les autres entrées si elles sont lazy) ; si c'est une chaîne if/elif :

```python
    if provider_type == "higgsfield" and asset == "video":
        from .higgsfield import HiggsfieldVideoOptions
        return HiggsfieldVideoOptions
```

Le comportement testé fait foi : `options_model("higgsfield", "video") is HiggsfieldVideoOptions`.

- [ ] **Step 4 — run PASS**

```bash
.venv/bin/python -m pytest tests/test_providers_base.py tests/test_higgsfield.py -v
```

Attendu : tout PASSED.

- [ ] **Step 5 — commit**

```bash
git add src/tableforge/providers/base.py tests/test_providers_base.py
git commit -m "feat: branchement higgsfield (provider_for, options video, verrous validation)"
```

---

## Task 7: Fiche studio vidéo Higgsfield

**Files:**
- Modify: `src/tableforge/studio.py`
- Test: `tests/test_studio.py` (ajouts en fin de fichier)

**Interfaces:**
- Produces: `STUDIO_URLS[("higgsfield", "video")] == "https://higgsfield.ai/create/video"` (URL de l'écran de création vidéo de l'app Higgsfield — à vérifier dans un navigateur au moment de l'implémentation ; `studio_url:` par kind reste prioritaire).
- Consumes: `studio.studio_cards` (P1) — aucun changement de logique, seulement une entrée de plus dans la table.

- [ ] **Step 1 — write failing test**

Ajoute en fin de `tests/test_studio.py` (réutilise `VIDEO_FORGE`/`VIDEO_CATALOG` en les copiant depuis la Task 6 si le fichier n'a pas de fixture équivalente) :

```python
def test_studio_urls_include_higgsfield_video():
    assert STUDIO_URLS[("higgsfield", "video")] == "https://higgsfield.ai/create/video"


def test_studio_cards_for_t2v_kind_carry_url_and_dest(tmp_path):
    # Arrange
    (tmp_path / "forge.yaml").write_text(VIDEO_FORGE, encoding="utf-8")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "teaser.yaml").write_text(VIDEO_CATALOG, encoding="utf-8")
    project = load_project(tmp_path)

    # Act
    cards = studio_cards(project, "teaser")

    # Assert
    assert len(cards) == 1
    card = cards[0]
    assert card.id == "intro"
    assert card.url == "https://higgsfield.ai/create/video"
    assert card.dest == tmp_path / "out" / "video" / "teaser" / "intro.mp4"
    assert "A ruined throne room" in card.text
```

(Imports à compléter en tête du fichier : `from tableforge.studio import STUDIO_URLS, studio_cards` s'ils n'y sont pas déjà, plus les fixtures `VIDEO_FORGE`/`VIDEO_CATALOG`.)

- [ ] **Step 2 — run (RED)**

```bash
.venv/bin/python -m pytest tests/test_studio.py -v
```

Attendu : `KeyError: ('higgsfield', 'video')` sur le premier test.

- [ ] **Step 3 — implémentation minimale**

Dans `src/tableforge/studio.py`, ajoute l'entrée à la table existante :

```python
    ("higgsfield", "video"): "https://higgsfield.ai/create/video",
```

- [ ] **Step 4 — run PASS**

```bash
.venv/bin/python -m pytest tests/test_studio.py -v
```

Attendu : tout PASSED.

- [ ] **Step 5 — commit**

```bash
git add src/tableforge/studio.py tests/test_studio.py
git commit -m "feat: fiche studio higgsfield video"
```

---

## Task 8: `forge all` sans kind — ordre image → audio → vidéo

**Files:**
- Modify: `src/tableforge/generate.py` (helper pur `kinds_in_order`)
- Modify: `src/tableforge/cli.py` (kind optionnel, affichage de l'ordre)
- Test: `tests/test_generate.py` (ajout)

**Interfaces:**
- Produces: `kinds_in_order(project: ProjectConfig) -> list[str]` — tous les kinds, triés par modalité (`art` < `audio` < `video` via `MODALITY_BY_ASSET`), ordre de déclaration conservé au sein d'une modalité (tri stable).
- Produces: `forge all [KIND]` — kind optionnel ; sans kind : affiche `ordre : a → b → c` puis exécute chaque kind ; clé manquante (`RuntimeError`) → avertit et continue (comportement actuel conservé) ; kinds non-image : generate uniquement (pas de render/sheet) ; kinds image sans `prompts:` ni `generate:` (ex. board) : pas de génération, render/sheet inchangés.
- Consumes: `paths.MODALITY_BY_ASSET`, `generate.generate_kind`

- [ ] **Step 1 — write failing test**

Ajoute en fin de `tests/test_generate.py` :

```python
FORGE_MULTIMODAL = """
project: demo
providers:
  ark:
    type: seedream
    base_url: https://ark.x/api/v3
    api_key_env: ARK_API_KEY
    model: seedream-5-0-260128
  eleven:
    type: elevenlabs
  hf:
    type: higgsfield
kinds:
  teaser:
    asset: video
    prompts: prompts/teaser.yaml
    generate: {with: hf, model: kling-video/v2.1/standard/text-to-video}
  nappes:
    asset: sfx
    prompts: prompts/nappes.yaml
    generate: {with: eleven}
  cards:
    prompts: prompts/cards.yaml
    template: templates/card
    render_size: {width: 10, height: 10}
    generate: {with: ark}
  board:
    data: data/board.yaml
    template: templates/board
    render_size: {width: 10, height: 10}
"""


def test_kinds_in_order_image_then_audio_then_video(tmp_path):
    # Arrange — déclaration volontairement dans le désordre (video, audio, image, image)
    (tmp_path / "forge.yaml").write_text(FORGE_MULTIMODAL, encoding="utf-8")
    from tableforge.generate import kinds_in_order
    project = load_project(tmp_path)

    # Act
    order = kinds_in_order(project)

    # Assert — image d'abord (ordre de déclaration conservé), puis audio, puis vidéo
    assert order == ["cards", "board", "nappes", "teaser"]
```

- [ ] **Step 2 — run (RED)**

```bash
.venv/bin/python -m pytest tests/test_generate.py::test_kinds_in_order_image_then_audio_then_video -v
```

Attendu : FAILED — `ImportError: cannot import name 'kinds_in_order'`.

- [ ] **Step 3 — implémentation minimale (helper pur)**

Dans `src/tableforge/generate.py`, ajoute (import en tête : `from .paths import MODALITY_BY_ASSET` — complète la ligne d'import paths existante) :

```python
_MODALITY_ORDER = ("art", "audio", "video")


def kinds_in_order(project: ProjectConfig) -> list[str]:
    rank = {modality: index for index, modality in enumerate(_MODALITY_ORDER)}
    return sorted(project.kinds,
                  key=lambda name: rank[MODALITY_BY_ASSET[project.kinds[name].asset]])
```

- [ ] **Step 4 — run PASS**

```bash
.venv/bin/python -m pytest tests/test_generate.py -v
```

Attendu : tout PASSED.

- [ ] **Step 5 — CLI (hors couverture, smoke via l'exemple en Task 9)**

Dans `src/tableforge/cli.py`, remplace la commande `all` existante par :

```python
@app.command("all")
def run_all(kind: Optional[str] = typer.Argument(None, help="Un kind, ou rien pour tout le projet."),
            project: Path = ProjectOpt):
    """generate (si clé) → render → sheet ; sans kind : tout, ordre image → audio → vidéo."""
    from .generate import kinds_in_order
    cfg = load_project(project)
    names = [kind] if kind else kinds_in_order(cfg)
    if kind is None:
        typer.echo("ordre : " + " → ".join(names))
    for name in names:
        _run_one_kind(cfg, name, project)


def _run_one_kind(cfg, name: str, project: Path) -> None:
    kind_cfg = cfg.kind(name)
    if kind_cfg.prompts is not None or kind_cfg.generate is not None:
        try:
            generate_kind(cfg, name)
        except RuntimeError as exc:
            typer.echo(f"({name} : génération ignorée : {exc})")
    if kind_cfg.asset != "image":
        return
    if kind_cfg.data is not None and kind_cfg.template is not None:
        _render_kind(cfg, name, None)
    if kind_cfg.sheet:
        sheet(name, project)
```

(La commande explicite `forge all cards` garde son comportement actuel ; les kinds audio/vidéo s'arrêtent après la génération ; un kind image sans prompts ni generate — comme `board` — n'appelle plus `generate_kind`, qui lèverait `ValueError`.)

- [ ] **Step 6 — vérification manuelle rapide**

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -c "from tableforge.cli import app; print('ok')"
```

Attendu : suite verte, `ok`.

- [ ] **Step 7 — commit**

```bash
git add src/tableforge/generate.py src/tableforge/cli.py tests/test_generate.py
git commit -m "feat: forge all sans kind, ordre image → audio → vidéo affiché"
```

---

## Task 9: Exemple `couronnes` — kinds `cartes-animees` (i2v) et `teaser` (t2v) + intégration dry-run

**Files:**
- Modify: `examples/couronnes/forge.yaml` (ajouts additifs — ne touche à rien d'existant)
- Create: `examples/couronnes/prompts/cartes-animees.yaml`
- Create: `examples/couronnes/prompts/teaser.yaml`
- Test: `tests/test_example_couronnes.py` (ajouts)

**Interfaces:**
- Consumes: toute la chaîne P3a (`build_kind_spec` video → `provider_for` → `HiggsfieldProvider.plan`) en dry-run pur, sans réseau ni clé.
- Produces: exemple de référence pour un utilisateur non-codeur (i2v + t2v).

- [ ] **Step 1 — write failing tests**

Ajoute en fin de `tests/test_example_couronnes.py` :

```python
def test_example_cartes_animees_dry_run_builds_i2v_requests():
    # Arrange
    cfg = load_project(EXAMPLE)

    # Act — aucun art généré dans le dépôt : cibles = entrées du catalogue de mouvement
    results = generate_kind(cfg, "cartes-animees", dry_run=True)

    # Assert
    assert {r.id for r in results} == {"lame", "couronne-maudite", "pacte-d-ether"}
    lame = next(r for r in results if r.id == "lame")
    assert lame.request["path"] == "/bytedance/seedance/v1/image-to-video"
    assert lame.request["json"]["image"].startswith("[image source :")
    assert "data:" not in str(lame.request)
    assert all(r.dest is None for r in results)


def test_example_teaser_dry_run_builds_t2v_request():
    # Arrange
    cfg = load_project(EXAMPLE)

    # Act
    results = generate_kind(cfg, "teaser", dry_run=True)

    # Assert
    assert [r.id for r in results] == ["intro"]
    request = results[0].request
    assert request["path"] == "/kling-video/v2.1/standard/text-to-video"
    assert request["json"]["aspect_ratio"] == "16:9"
    assert "image" not in request["json"]
```

- [ ] **Step 2 — run (RED)**

```bash
.venv/bin/python -m pytest tests/test_example_couronnes.py -v
```

Attendu : les 2 nouveaux tests FAILED (`KeyError: "kind inconnu : 'cartes-animees' …"`), les tests existants PASSED.

- [ ] **Step 3 — implémentation (fichiers d'exemple)**

Dans `examples/couronnes/forge.yaml` :

1. Ajoute au bloc `providers:` (créé en P1 ; si l'exemple est encore au format legacy `provider:`, c'est que P1/P2 ne sont pas mergées — arrête-toi et vérifie le prérequis) :

```yaml
  higgsfield:
    type: higgsfield
```

2. Ajoute à la fin du bloc `kinds:` :

```yaml
  cartes-animees:
    asset: video
    from: cards
    prompts: prompts/cartes-animees.yaml
    generate: { with: higgsfield, model: bytedance/seedance/v1/image-to-video }

  teaser:
    asset: video
    prompts: prompts/teaser.yaml
    generate:
      with: higgsfield
      model: kling-video/v2.1/standard/text-to-video
      aspect_ratio: "16:9"
```

3. Crée `examples/couronnes/prompts/cartes-animees.yaml` :

```yaml
# Catalogue de mouvement (i2v) : anime les illustrations de out/art/cards/<id>.png.
# Les ids doivent exister dans prompts/cards.yaml (sous-ensemble strict).
direction: >-
  Subtle looping animation of the painted illustration: slow atmospheric motion,
  drifting particles, flickering light. Keep the gouache texture and the exact
  composition intact — no camera cuts, no new elements, seamless loop.

defaults:
  duration_s: 5

entries:
  lame:
    prompt: "The footman's cloak and the forge glow ripple in a cold wind, embers drift upward"
  couronne-maudite:
    prompt: "The cursed crown pulses with violet ether flames, ash spirals slowly into darkness"
  pacte-d-ether:
    prompt: "The fractured ether crystal flickers violet-teal, glowing tendrils crawl along the arm"
```

4. Crée `examples/couronnes/prompts/teaser.yaml` :

```yaml
# Teaser t2v : une seule entrée, générée sans image source.
direction: >-
  Cinematic dark fantasy trailer shot, painterly gouache style in motion, volumetric
  candle-gold light against deep cold shadow, drifting grey ash, film grain. No text,
  no logo, no watermark.

entries:
  intro:
    prompt: "A slow push-in on a ruined throne room, a blackened thorn crown levitating above the empty throne, ash rising into darkness"
    duration_s: 8
```

- [ ] **Step 4 — run PASS**

```bash
.venv/bin/python -m pytest tests/test_example_couronnes.py -v
```

Attendu : tout PASSED.

- [ ] **Step 5 — vérifications manuelles (dry-run, sans clé)**

```bash
.venv/bin/python -m tableforge list -p examples/couronnes
```

Attendu : `cartes-animees` et `teaser` listés avec leur modalité/provider (affichage P1), **aucune issue** de validation.

```bash
.venv/bin/python -m tableforge generate cartes-animees -p examples/couronnes --dry-run
```

Attendu : 3 ids (`couronne-maudite`, `lame`, `pacte-d-ether`) en dry-run, avec la note « art source manquant … forge generate cards » visible (affichage des notes selon P1) et aucune data-URL dans la sortie (`| grep -c "data:image"` → `0`).

```bash
.venv/bin/python -m tableforge generate teaser -p examples/couronnes --dry-run
```

Attendu : `intro` en dry-run, requête `/kling-video/v2.1/standard/text-to-video`, `aspect_ratio: 16:9`.

```bash
.venv/bin/python -m tableforge render cartes-animees -p examples/couronnes; echo "exit=$?"
```

Attendu : refus pédagogique (kind non-image, message P1), exit ≠ 0.

```bash
.venv/bin/python -m tableforge all -p examples/couronnes 2>&1 | head -3
```

Attendu : première ligne `ordre : cards → board → … → cartes-animees → teaser` (image d'abord, vidéo en dernier). Interrompre ensuite (Ctrl-C) si le rendu Playwright démarre — l'ordre affiché suffit ici.

- [ ] **Step 6 — commit**

```bash
git add examples/couronnes/forge.yaml examples/couronnes/prompts/cartes-animees.yaml \
        examples/couronnes/prompts/teaser.yaml tests/test_example_couronnes.py
git commit -m "feat: exemple couronnes — cartes-animees (i2v) et teaser (t2v) en dry-run"
```

---

## Task 10: Vérification finale de phase

**Files:**
- Aucun nouveau fichier (vérification seulement ; corrections éventuelles au fil de l'eau).

**Interfaces:**
- Consumes: toute la suite.

- [ ] **Step 1 — suite complète**

```bash
.venv/bin/python -m pytest -q
```

Attendu : **tout vert**, zéro skip inattendu, zéro warning nouveau.

- [ ] **Step 2 — couverture**

```bash
.venv/bin/python -m pytest -q --cov=tableforge --cov-report=term-missing
```

Attendu : couverture globale **≥ 80 %** (objectif ≈ 96 %) ; `providers/higgsfield.py` couvert par respx (seules d'éventuelles lignes `pragma: no cover` justifiées peuvent manquer — il ne doit pas y en avoir dans ce module) ; `render.py`/`cli.py`/`__main__.py` exclus comme avant.

- [ ] **Step 3 — revue du périmètre**

Vérifie la checklist de phase :
- [ ] `submit`/`poll` : sleep injectable, `on_status`, timeout `poll_timeout_s`, `failed`/`nsfw` → « requête remboursée automatiquement », download `completed` → `.mp4`.
- [ ] Data-URL i2v : présente dans `job.payload`, absente de `job.request` (résumé `[image source : …]`).
- [ ] Catalogue de mouvement ⊄ ids source → erreur nommant les deux fichiers.
- [ ] Art manquant : note en dry-run, `RuntimeError` à l'exécution.
- [ ] `forge all` sans kind : ordre affiché, image → audio → vidéo, clé manquante = avertissement.
- [ ] Aucun secret imprimé nulle part (relis les messages ajoutés).
- [ ] Modules ≤ ~400 lignes (`wc -l src/tableforge/targets.py src/tableforge/providers/higgsfield.py`).

- [ ] **Step 4 — commit final (si retouches en Step 1–3)**

```bash
git add -A && git commit -m "chore: finitions P3a vidéo Higgsfield (suite verte, couverture)"
```

(Ne commite rien si les Steps 1–3 n'ont demandé aucune retouche.)
