# Multimodal P3b — Images Higgsfield + Documentation finale — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Étendre `HiggsfieldProvider` à l'asset `image` (Soul + Seedream via Higgsfield :
slug configurable, options `aspect_ratio`/`resolution`/`style_id`/`style_strength`/`seed`,
refs i2i depuis les `style_refs` du fichier prompts image existant), sortie `out/art/<kind>/<id>.png`
en réutilisant strictement le chemin `submit → poll → download` livré en P3a — puis livrer la
phase finale de documentation (HANDOFF.md réécrit, README.md EN/FR enrichi, CLAUDE.md mis à jour,
commentaires datés sur les shims de compat v1) et la vérification finale du chantier.

**Architecture:** Contrat `plan()/execute()` figé (voir la spec
`docs/superpowers/specs/2026-07-24-multimodal-providers-design.md` et le contrat d'interfaces
du chantier). `plan()` reste pur et sans clé : il produit des `AssetJob` (frozen) dont `payload`
contient la requête complète (`{"path": f"/{slug}", "json": body}` via `build_submit`) et
`request` le résumé affichable (data-URLs masquées). `execute()` reste l'unique point
réseau/clé : `submit → poll → download`, **partagé** entre image et vidéo (aucun branchement
par asset dans `execute`, aucune duplication). La résolution des cibles image (prompt assemblé
`prompt_for` + refs `reference_data_urls`) est déjà faite par `targets.build_kind_spec` — rien
à changer côté `targets.py`.

**Tech Stack:** Python ≥ 3.10, pydantic v2, httpx (+ respx en test), pyyaml, typer, pytest,
dataclasses frozen. Pas de SDK vendeur pour Higgsfield.

## Global Constraints

- **Prérequis dur : P0 → P3a mergées.** Avant toute tâche, vérifier l'état :
  ```bash
  ls src/tableforge/providers/higgsfield.py src/tableforge/providers/base.py \
     src/tableforge/targets.py src/tableforge/catalog.py src/tableforge/paths.py
  .venv/bin/python -m pytest -q          # DOIT être vert avant de commencer
  grep -n "respx" pyproject.toml         # respx doit être dans les dev-deps (posé en P1)
  ```
  Si l'un de ces fichiers manque ou si la suite est rouge : **STOP**, ce plan ne s'exécute pas.
- **Toujours `.venv/bin/python`** — jamais de `python`/`pip` système (venv via uv ;
  bootstrap : `uv venv .venv && uv pip install --python .venv/bin/python -e ".[dev]" && .venv/bin/playwright install chromium`).
- **TDD strict** : test rouge → run (échec constaté) → implémentation minimale → run vert →
  commit. Les tests « verrous » (qui peuvent être verts d'emblée si une phase amont a déjà
  posé le comportement) sont légitimes : constater le résultat du run, committer le verrou,
  et n'implémenter que si rouge.
- **Couverture ≥ 80 %** sur la logique pure (objectif ≈ 96 %). `render.py`, `cli.py`,
  `__main__.py` restent exclus (cf. `[tool.coverage.run] omit` dans `pyproject.toml`).
- **Doctrine réseau** : tout chemin httpx Higgsfield est testé **respx** — asserter le header
  `Authorization: Key {key}:{secret}`, le corps JSON et le fichier écrit. Le chemin SDK OpenAI
  de Seedream reste `pragma: no cover`. Aucun test ne touche le vrai réseau.
- **Secrets** : jamais en dur, jamais imprimés. Les clés sont lues via `api_key_env`/
  `api_secret_env` dans `execute()` uniquement (dotenv + os.environ).
- **Immutabilité** : dataclasses `frozen=True`, pas de mutation d'objets reçus.
  Modules ≤ ~400 lignes. Messages d'erreur en **français**. Code et noms de tests en anglais,
  structure AAA (style des tests existants).
- **Ne pas toucher au chemin Seedream** : la byte-équivalence v1 est verrouillée par les tests
  P0 — s'ils cassent, la modification est fausse.
- **Commits conventionnels en français** (`feat:`, `fix:`, `test:`, `docs:`, `chore:`),
  un commit par cycle vert.
- **Points d'adaptation P3a** : ce plan a été écrit avant le merge de P3a. Les noms *internes*
  de `providers/higgsfield.py` (méthode de plan vidéo, aides de téléchargement, forme exacte du
  JSON de statut `completed`) sont fixés par P3a. Chaque tâche concernée contient un encadré
  `ADAPTATION` : lire le fichier réel + ses tests (`tests/test_higgsfield*.py`) et refléter
  **exactement** les conventions P3a. Les signatures publiques du contrat (`build_submit`,
  `submit`, `poll`, `HiggsfieldProvider.plan/execute`, `AssetJob`, `KindSpec`, `asset_path`)
  ne se renégocient pas.
- Le contrat ne liste pas explicitement le champ qui porte la racine projet dans `KindSpec`
  (nécessaire à `asset_path(root, ...)` dans `plan()`). P0 a dû l'ajouter (hypothèse de ce
  plan : `KindSpec.root: Path`). Vérifier dans `src/tableforge/targets.py` et adapter les
  constructions de `KindSpec` des tests de ce plan si le mécanisme diffère — les assertions,
  elles, ne changent pas.

---

## Task 1 : Verrou capacités + modèle d'options image Higgsfield

`SUPPORTED_ASSETS["higgsfield"]` doit contenir `image` (déjà au contrat — P3a a pu ne livrer
que `video`), et `options_model("higgsfield", "image")` doit renvoyer un modèle pydantic
`extra="forbid"` avec exactement `{model?, aspect_ratio?, resolution?, style_id?,
style_strength?, seed?}`.

**Files:**
- Create: `tests/test_higgsfield_image.py`
- Modify: `src/tableforge/providers/base.py`

**Interfaces:**
- Consumes: `SUPPORTED_ASSETS: dict[str, frozenset[str]]`,
  `options_model(provider_type: str, asset: str) -> Optional[type[BaseModel]]`
  (existants, `src/tableforge/providers/base.py`).
- Produces: `class HiggsfieldImageOptions(BaseModel)` (extra="forbid") enregistrée pour la
  paire `("higgsfield", "image")` ; `SUPPORTED_ASSETS["higgsfield"] == frozenset({"image", "video"})`.

**Étapes :**

- [ ] Créer `tests/test_higgsfield_image.py` avec ce contenu exact :

  ```python
  """Tests P3b — images via Higgsfield : capacités, options, plan, execute."""
  from pathlib import Path

  import pytest
  from pydantic import ValidationError

  from tableforge.providers.base import SUPPORTED_ASSETS, options_model


  def test_supported_assets_higgsfield_includes_image():
      # Arrange / Act
      supported = SUPPORTED_ASSETS["higgsfield"]

      # Assert
      assert "image" in supported
      assert "video" in supported


  def test_options_model_higgsfield_image_accepts_contract_keys():
      # Arrange
      model = options_model("higgsfield", "image")

      # Act
      opts = model(model="bytedance/seedream/v4/text-to-image", aspect_ratio="3:4",
                   resolution="2k", style_id="9b68b243", style_strength=0.7, seed=42)

      # Assert
      assert opts.model == "bytedance/seedream/v4/text-to-image"
      assert opts.aspect_ratio == "3:4"
      assert opts.style_strength == 0.7
      assert opts.seed == 42


  def test_options_model_higgsfield_image_rejects_unknown_key():
      # Arrange
      model = options_model("higgsfield", "image")

      # Act / Assert
      with pytest.raises(ValidationError):
          model(sise="2k")
  ```

- [ ] Lancer `.venv/bin/python -m pytest tests/test_higgsfield_image.py -v` — attendu :
  **ROUGE** si P3a n'a déclaré que `video` (échec de
  `test_supported_assets_higgsfield_includes_image` et/ou `options_model` renvoie `None`
  → `TypeError: 'NoneType' object is not callable`). Si les 3 tests sont **déjà verts**
  (P1/P3a conformes au contrat complet), sauter l'étape d'implémentation : ces tests
  deviennent le verrou de non-régression — committer directement.

- [ ] Implémentation minimale dans `src/tableforge/providers/base.py` :

  1. Ajouter la classe d'options (à côté des autres modèles d'options existants) :

  ```python
  class HiggsfieldImageOptions(BaseModel):
      """Options `generate:` d'un kind image servi par Higgsfield (contrat P3b)."""
      model_config = ConfigDict(extra="forbid")
      model: Optional[str] = None
      aspect_ratio: Optional[str] = None
      resolution: Optional[str] = None
      style_id: Optional[str] = None
      style_strength: Optional[float] = None
      seed: Optional[int] = None
  ```

  2. Enregistrer la paire dans la table consultée par `options_model` (P1 a posé une table
     type `_OPTIONS_MODELS: dict[tuple[str, str], type[BaseModel]]` — utiliser la structure
     réellement en place) :

  ```python
  _OPTIONS_MODELS[("higgsfield", "image")] = HiggsfieldImageOptions
  ```

  3. Mettre la capacité au niveau du contrat :

  ```python
  SUPPORTED_ASSETS = {
      "seedream": frozenset({"image"}),
      "elevenlabs": frozenset({"music", "sfx", "tts", "dialogue"}),
      "higgsfield": frozenset({"image", "video"}),
      "manual": frozenset({"image", "music", "sfx", "tts", "dialogue", "video"}),
  }
  ```

  > **ADAPTATION** : ne pas réécrire la table `SUPPORTED_ASSETS` si elle existe déjà sous
  > cette forme — seulement s'assurer que l'entrée `"higgsfield"` contient `"image"`.
  > `ConfigDict`/`Optional` sont déjà importés dans `base.py` (posés en P1) ; sinon les
  > ajouter (`from pydantic import BaseModel, ConfigDict` ; `from typing import Optional`).

- [ ] Lancer `.venv/bin/python -m pytest tests/test_higgsfield_image.py -v` — attendu :
  `3 passed`.
- [ ] Lancer `.venv/bin/python -m pytest -q` — attendu : tout vert (aucune régression).
- [ ] Commit :
  ```bash
  git add src/tableforge/providers/base.py tests/test_higgsfield_image.py
  git commit -m "feat: capacité image higgsfield + modèle d'options (extra=forbid)"
  ```

---

## Task 2 : `HiggsfieldProvider` — branche `plan()` image (slug, options, refs i2i)

`plan(spec)` avec `spec.asset == "image"` produit un `AssetJob` par cible : slug =
`options["model"]` sinon `cfg.default_image_model` ; body `{prompt, aspect_ratio?,
resolution?, style_id?, style_strength?, seed?}` ; refs i2i (data-URLs déjà résolues par
`build_kind_spec` depuis les `style_refs` du fichier prompts image) dans un champ dédié du
body ; `dest = out/art/<kind>/<id>.png` ; `request` masque les data-URLs.

**Files:**
- Modify: `src/tableforge/providers/higgsfield.py`
- Test: `tests/test_higgsfield_image.py`

**Interfaces:**
- Consumes: `build_submit(slug: str, body: dict) -> dict` (P3a, renvoie
  `{"path": f"/{slug}", "json": body}`) ; `KindSpec`, `Target` (`src/tableforge/targets.py`) ;
  `AssetJob` (`src/tableforge/providers/base.py`) ;
  `asset_path(root: Path, asset: str, kind: str, asset_id: str, output_format: Optional[str] = None) -> Path`
  (`src/tableforge/paths.py`) ; `HiggsfieldProviderConfig` (`src/tableforge/config.py`).
- Produces:
  - `IMAGE_REF_FIELD: str = "image_refs"` (constante module, nom **à vérifier** — voir note) ;
  - `build_image_body(prompt: str, *, options: dict, refs: Sequence[str] = ()) -> dict` ;
  - `HiggsfieldProvider._plan_image(self, spec: KindSpec) -> list[AssetJob]` ;
  - `HiggsfieldProvider.plan(self, spec: KindSpec) -> list[AssetJob]` (dispatch image/vidéo).

> **NOTE CONTRAT (à reporter en commentaire dans le code)** : le nom exact du champ du body
> qui porte les images de référence i2i (Soul / Seedream via Higgsfield) doit être **vérifié
> contre https://docs.higgsfield.ai** au moment de l'implémentation — même réserve que le
> champ `"image"` i2v posé en P3a. Ce plan retient `IMAGE_REF_FIELD = "image_refs"` comme
> valeur par défaut ; si les docs disent autre chose, changer **uniquement** la valeur de la
> constante (les tests l'importent, ils suivront).

**Étapes :**

- [ ] Ajouter à `tests/test_higgsfield_image.py` (à la suite du contenu de la Task 1) :

  ```python
  from tableforge.config import HiggsfieldProviderConfig
  from tableforge.providers.higgsfield import (IMAGE_REF_FIELD, HiggsfieldProvider,
                                               build_image_body)
  from tableforge.targets import KindSpec, Target


  def _provider() -> HiggsfieldProvider:
      return HiggsfieldProvider.from_config(HiggsfieldProviderConfig(type="higgsfield"))


  def _image_spec(root, *, options=None, refs=(), notes=(),
                  text="A footman. Dark fantasy.") -> KindSpec:
      target = Target(id="lame", text=text, refs=tuple(refs), notes=tuple(notes))
      return KindSpec(kind="cards-soul", asset="image", provider_name="higgsfield",
                      options=dict(options or {}), targets=(target,),
                      output_format=None, root=Path(root))


  def test_build_image_body_keeps_only_contract_options():
      # Arrange
      options = {"model": "x/y/z", "aspect_ratio": "3:4", "style_strength": 0.7}

      # Act
      body = build_image_body("A footman.", options=options)

      # Assert
      assert body == {"prompt": "A footman.", "aspect_ratio": "3:4",
                      "style_strength": 0.7}   # "model" est le slug, pas le body


  def test_plan_image_uses_default_soul_slug_and_art_dest(tmp_path):
      # Arrange
      spec = _image_spec(tmp_path)

      # Act
      jobs = _provider().plan(spec)

      # Assert
      assert len(jobs) == 1
      job = jobs[0]
      assert job.id == "lame"
      assert job.payload["path"] == "/higgsfield-ai/soul/standard"
      assert job.payload["json"] == {"prompt": "A footman. Dark fantasy."}
      assert job.dest == tmp_path / "out" / "art" / "cards-soul" / "lame.png"


  def test_plan_image_honours_model_and_style_options(tmp_path):
      # Arrange
      spec = _image_spec(tmp_path, options={
          "model": "bytedance/seedream/v4/text-to-image", "aspect_ratio": "3:4",
          "resolution": "2k", "style_id": "9b68b243", "style_strength": 0.7, "seed": 42})

      # Act
      job = _provider().plan(spec)[0]

      # Assert
      assert job.payload["path"] == "/bytedance/seedream/v4/text-to-image"
      assert job.payload["json"]["aspect_ratio"] == "3:4"
      assert job.payload["json"]["resolution"] == "2k"
      assert job.payload["json"]["style_id"] == "9b68b243"
      assert job.payload["json"]["style_strength"] == 0.7
      assert job.payload["json"]["seed"] == 42
      assert "model" not in job.payload["json"]


  def test_plan_image_hides_reference_data_urls_in_request(tmp_path):
      # Arrange
      refs = ("data:image/jpeg;base64,AAA", "data:image/jpeg;base64,BBB")
      spec = _image_spec(tmp_path, refs=refs)

      # Act
      job = _provider().plan(spec)[0]

      # Assert
      assert job.payload["json"][IMAGE_REF_FIELD] == list(refs)
      assert job.request["json"][IMAGE_REF_FIELD] == "[2 référence(s), data-URLs omises]"
      assert "data:image" not in str(job.request)


  def test_plan_image_propagates_target_notes(tmp_path):
      # Arrange
      spec = _image_spec(tmp_path, notes=("avertissement",))

      # Act
      job = _provider().plan(spec)[0]

      # Assert
      assert job.notes == ("avertissement",)
  ```

  > **ADAPTATION** : (a) si `KindSpec` ne porte pas la racine projet sous le nom `root`
  > (lire `src/tableforge/targets.py` — c'est le mécanisme posé en P0 pour que `plan()`
  > calcule `dest`), adapter `_image_spec` au champ réel ; (b) si `HiggsfieldProvider` n'a
  > pas de `from_config` (symétrie seedream/elevenlabs attendue), construire le provider
  > comme le font les tests vidéo P3a existants dans `tests/test_higgsfield*.py`. Les
  > assertions restent identiques.

- [ ] Lancer `.venv/bin/python -m pytest tests/test_higgsfield_image.py -v` — attendu :
  **ROUGE** — `ImportError: cannot import name 'IMAGE_REF_FIELD' from
  'tableforge.providers.higgsfield'`.

- [ ] Implémentation minimale dans `src/tableforge/providers/higgsfield.py`.

  1. Imports (compléter l'en-tête existant si absents) :

  ```python
  import copy
  from typing import Sequence
  from ..paths import asset_path
  ```

  2. Ajouter en fin de module (section commentée) :

  ```python
  # --- P3b : images (Soul / Seedream servis par Higgsfield) --------------------

  IMAGE_REF_FIELD = "image_refs"
  # NOTE contrat P3b : nom du champ des références i2i à VÉRIFIER contre
  # https://docs.higgsfield.ai (modèles Soul / bytedance-seedream) au moment de
  # l'implémentation — même réserve que le champ "image" (i2v) posé en P3a.
  # Si les docs diffèrent, ne changer QUE la valeur de cette constante.

  _IMAGE_OPTION_KEYS = ("aspect_ratio", "resolution", "style_id", "style_strength", "seed")


  def build_image_body(prompt: str, *, options: dict,
                       refs: Sequence[str] = ()) -> dict:
      """Corps JSON d'une génération d'image (options déjà validées, extra=forbid)."""
      body: dict = {"prompt": prompt}
      for key in _IMAGE_OPTION_KEYS:
          value = options.get(key)
          if value is not None:
              body[key] = value
      if refs:
          body[IMAGE_REF_FIELD] = list(refs)
      return body
  ```

  3. Ajouter les méthodes à `HiggsfieldProvider` (dataclass frozen existante) :

  ```python
      def _plan_image(self, spec: KindSpec) -> list[AssetJob]:
          slug = spec.options.get("model") or self.default_image_model
          jobs: list[AssetJob] = []
          for target in spec.targets:
              body = build_image_body(target.text, options=spec.options,
                                      refs=target.refs)
              payload = build_submit(slug, body)
              request = copy.deepcopy(payload)
              refs = request["json"].get(IMAGE_REF_FIELD)
              if refs is not None:
                  request["json"][IMAGE_REF_FIELD] = (
                      f"[{len(refs)} référence(s), data-URLs omises]")
              dest = asset_path(spec.root, "image", spec.kind, target.id,
                                spec.output_format or "png")
              jobs.append(AssetJob(id=target.id, dest=dest, request=request,
                                   payload=payload, notes=target.notes))
          return jobs

      def plan(self, spec: KindSpec) -> list[AssetJob]:
          if spec.asset == "image":
              return self._plan_image(spec)
          return self._plan_video(spec)
  ```

  > **ADAPTATION** : si P3a a écrit le plan vidéo directement dans `plan()` (pas de
  > `_plan_video`), déplacer le corps vidéo **tel quel, sans le modifier** dans une méthode
  > `_plan_video(self, spec)` et poser le dispatch ci-dessus. Si P3a a déjà un dispatch,
  > n'ajouter que la branche image. `default_image_model` vient de
  > `HiggsfieldProviderConfig` (défaut `"higgsfield-ai/soul/standard"`) et doit déjà être un
  > champ du provider (contrat P3a) ; sinon l'ajouter au `from_config`.

- [ ] Lancer `.venv/bin/python -m pytest tests/test_higgsfield_image.py -v` — attendu :
  `8 passed` (3 de la Task 1 + 5 nouveaux).
- [ ] Lancer `.venv/bin/python -m pytest -q` — attendu : tout vert (les tests vidéo P3a ne
  bougent pas).
- [ ] Commit :
  ```bash
  git add src/tableforge/providers/higgsfield.py tests/test_higgsfield_image.py
  git commit -m "feat: plan images higgsfield (soul/seedream, options, refs i2i)"
  ```

---

## Task 3 : Verrou — `execute()` partagé image/vidéo (respx, zéro duplication)

Un job image passe dans le **même** `execute()` que la vidéo : `submit` (POST `/{slug}`,
header `Authorization: Key {key}:{secret}`) → `poll` (GET `/requests/{id}/status`) →
téléchargement des octets vers `job.dest`. Aucun code image-spécifique dans `execute`.

**Files:**
- Test: `tests/test_higgsfield_image.py`
- Modify (seulement si le verrou est rouge): `src/tableforge/providers/higgsfield.py`

**Interfaces:**
- Consumes: `HiggsfieldProvider.execute(self, job: AssetJob) -> list[Path]` (P3a),
  `submit(cfg, req, *, api_key, api_secret) -> str`,
  `poll(cfg, request_id, *, api_key, api_secret, sleep=time.sleep, on_status=None) -> dict` (P3a).
- Produces: rien de nouveau — preuve par test que le chemin est unique.

**Étapes :**

- [ ] Ajouter à `tests/test_higgsfield_image.py` :

  ```python
  import httpx
  import respx


  @respx.mock
  def test_execute_image_job_reuses_submit_poll_download(tmp_path, monkeypatch):
      # Arrange
      monkeypatch.setenv("HIGGSFIELD_API_KEY", "k")
      monkeypatch.setenv("HIGGSFIELD_API_SECRET", "s")
      provider = _provider()
      job = provider.plan(_image_spec(tmp_path))[0]
      submit_route = respx.post(
          "https://platform.higgsfield.ai/higgsfield-ai/soul/standard"
      ).mock(return_value=httpx.Response(200, json={"request_id": "req-1"}))
      respx.get("https://platform.higgsfield.ai/requests/req-1/status").mock(
          return_value=httpx.Response(200, json={
              "status": "completed",
              "result": {"url": "https://cdn.higgsfield.ai/out/lame.png"}}))
      respx.get("https://cdn.higgsfield.ai/out/lame.png").mock(
          return_value=httpx.Response(200, content=b"PNGDATA"))

      # Act
      saved = provider.execute(job)

      # Assert
      assert saved == [job.dest]
      assert job.dest.read_bytes() == b"PNGDATA"
      sent = submit_route.calls.last.request
      assert sent.headers["Authorization"] == "Key k:s"
      assert b'"prompt": "A footman. Dark fantasy."' in sent.content or \
             b'"prompt":"A footman. Dark fantasy."' in sent.content
  ```

  > **ADAPTATION (obligatoire avant de lancer)** : ouvrir les tests vidéo P3a
  > (`tests/test_higgsfield*.py`) et **copier la forme exacte du JSON de statut `completed`**
  > qu'ils moquent (l'emplacement de l'URL de résultat — `result.url`, `results[0].url`,
  > `urls`… — est fixé par le parseur P3a). Remplacer le payload du mock `/status` ci-dessus
  > par cette forme. Le statut est `completed` dès le premier GET : un `poll` bien écrit ne
  > dort pas dans ce cas (sinon, injecter le `sleep` comme le font les tests P3a).

- [ ] Lancer
  `.venv/bin/python -m pytest tests/test_higgsfield_image.py::test_execute_image_job_reuses_submit_poll_download -v`
  — attendu : **VERT du premier coup** si `execute` P3a est bien piloté par
  `job.payload`/`job.dest` (c'est le point du verrou). Si **ROUGE** : la correction est de
  réduire `execute` à l'unique chemin payload-piloté — **jamais** d'ajouter un
  `if spec.asset == "image"` :

  ```python
      def execute(self, job: AssetJob) -> list[Path]:
          api_key, api_secret = self._require_keys()   # noms P3a réels
          request_id = submit(self._as_config(), job.payload,
                              api_key=api_key, api_secret=api_secret)
          status = poll(self._as_config(), request_id,
                        api_key=api_key, api_secret=api_secret,
                        on_status=lambda state: typer.echo(f"{job.id}: {state}"))
          job.dest.parent.mkdir(parents=True, exist_ok=True)
          return [_download_result(status, job.dest)]   # aide P3a réelle
  ```

  (Adapter les noms `_require_keys`/`_as_config`/`_download_result` à ceux réellement posés
  en P3a — le point non négociable est : un seul chemin, piloté par `job.payload` et
  `job.dest`, pas de branche par asset.)

- [ ] Lancer `.venv/bin/python -m pytest -q` — attendu : tout vert.
- [ ] Commit :
  ```bash
  git add tests/test_higgsfield_image.py src/tableforge/providers/higgsfield.py
  git commit -m "test: verrou execute higgsfield partagé image/vidéo (respx)"
  ```
  (Ne mettre `src/…/higgsfield.py` dans le commit que s'il a réellement changé.)

---

## Task 4 : « Art brut » légal — linter muet + refus pédagogique de `render`

Un kind `asset: image` **sans** `template:`/`render_size:` est légal (art brut :
`out/art/<kind>/` seulement). `validate_project` ne le signale pas ; `forge render` refuse
avec un message pédagogique français.

**Files:**
- Modify: `src/tableforge/cli.py`
- Test: `tests/test_higgsfield_image.py` (linter), `tests/test_cli.py` (refus render)

**Interfaces:**
- Consumes: `validate_project(project: ProjectConfig) -> list[str]`
  (`src/tableforge/providers/base.py`), `load_project` (`src/tableforge/config.py`),
  `_render_kind` (`src/tableforge/cli.py`, version post-P1 avec refus des kinds non-image).
- Produces: garde `template is None` dans `_render_kind`
  (message : « le kind '<k>' est de l'art brut (pas de template) — rien à rendre ;
  utilise `forge generate <k>` »).

**Étapes :**

- [ ] Ajouter à `tests/test_higgsfield_image.py` :

  ```python
  from tableforge.config import load_project
  from tableforge.providers.base import validate_project

  FORGE_ART_BRUT = """
  project: demo
  providers:
    hf: {type: higgsfield}
  kinds:
    art-brut:
      asset: image
      prompts: prompts/art.yaml
      generate: {with: hf, aspect_ratio: "3:4"}
  """

  PROMPTS_ART_BRUT = """
  prompts:
    lame: "A footman."
  """


  def _art_brut_project(tmp_path):
      (tmp_path / "forge.yaml").write_text(FORGE_ART_BRUT, encoding="utf-8")
      (tmp_path / "prompts").mkdir()
      (tmp_path / "prompts" / "art.yaml").write_text(PROMPTS_ART_BRUT, encoding="utf-8")
      return load_project(tmp_path)


  def test_validate_project_accepts_image_kind_without_template(tmp_path):
      # Arrange
      project = _art_brut_project(tmp_path)

      # Act
      issues = validate_project(project)

      # Assert
      assert issues == []
  ```

- [ ] Ajouter à la fin de `tests/test_cli.py` (le module a déjà `runner = CliRunner()` et
  `from tableforge.cli import app` en tête) :

  ```python
  FORGE_ART_BRUT_CLI = """
  project: demo
  providers:
    hf: {type: higgsfield}
  kinds:
    art-brut:
      asset: image
      prompts: prompts/art.yaml
      generate: {with: hf}
  """


  def test_render_refuses_image_kind_without_template(tmp_path):
      # Arrange
      (tmp_path / "forge.yaml").write_text(FORGE_ART_BRUT_CLI, encoding="utf-8")
      (tmp_path / "prompts").mkdir()
      (tmp_path / "prompts" / "art.yaml").write_text(
          'prompts:\n  lame: "A footman."\n', encoding="utf-8")

      # Act
      res = runner.invoke(app, ["render", "art-brut", "--project", str(tmp_path)])

      # Assert
      assert res.exit_code != 0
      assert "art brut" in res.output
  ```

- [ ] Lancer
  `.venv/bin/python -m pytest tests/test_higgsfield_image.py::test_validate_project_accepts_image_kind_without_template tests/test_cli.py::test_render_refuses_image_kind_without_template -v`
  — attendu : le test linter peut être **déjà vert** (verrou : le committer tel quel) ;
  le test CLI est **ROUGE** (soit `AttributeError: 'NoneType' object has no attribute …`
  dans `_render_kind`, soit exit 0 — selon l'état P1).

- [ ] Implémentation minimale dans `src/tableforge/cli.py`, fonction `_render_kind`, juste
  après le refus pédagogique des kinds non-image posé en P1 (et avant l'accès à
  `kind_cfg.data`) :

  ```python
      if kind_cfg.template is None:
          raise typer.BadParameter(
              f"le kind '{kind}' est de l'art brut (pas de template) — rien à rendre ; "
              f"utilise `forge generate {kind}`")
  ```

  > **ADAPTATION** : si `validate_project` signalait l'absence de template sur un kind
  > image (test linter rouge), retirer ce contrôle-là pour les kinds image **avec**
  > `generate:` — l'absence de template n'est une issue que si le kind n'a ni `generate:`
  > ni `template:` (il ne produit alors rien).

- [ ] Lancer `.venv/bin/python -m pytest tests/test_cli.py tests/test_higgsfield_image.py -v`
  — attendu : tous verts.
- [ ] Lancer `.venv/bin/python -m pytest -q` — attendu : tout vert.
- [ ] Commit :
  ```bash
  git add src/tableforge/cli.py tests/test_cli.py tests/test_higgsfield_image.py
  git commit -m "feat: refus pédagogique de render sur un kind image sans template (art brut)"
  ```

---

## Task 5 : Exemple couronnes — kind `cards-soul` (3 entrées, dry-run)

Ajouter à `examples/couronnes` un kind image servi par Higgsfield Soul, **sans template**
(art brut), avec 3 entrées et une référence de style, testé en dry-run pur.

**Files:**
- Create: `examples/couronnes/prompts/cards-soul.yaml`
- Modify: `examples/couronnes/forge.yaml`
- Test: `tests/test_example_couronnes.py`

**Interfaces:**
- Consumes: `load_project`, `generate_kind` (imports déjà présents en tête de
  `tests/test_example_couronnes.py`) ; le provider `higgsfield` déclaré dans le
  `forge.yaml` de l'exemple (posé en P3a pour `cartes-animees`).
- Produces: kind `cards-soul` (asset image, provider higgsfield, dry-run
  `request["path"] == "/higgsfield-ai/soul/standard"`).

**Étapes :**

- [ ] Ajouter à `tests/test_example_couronnes.py` (les imports `load_project`,
  `generate_kind`, `EXAMPLE` existent déjà en tête) :

  ```python
  def test_example_cards_soul_dry_run_targets_higgsfield_soul():
      # Arrange
      cfg = load_project(EXAMPLE)

      # Act
      results = generate_kind(cfg, "cards-soul", dry_run=True)

      # Assert
      assert sorted(r.id for r in results) == ["couronne-maudite", "emissaire", "lame"]
      lame = next(r for r in results if r.id == "lame")
      assert lame.request["path"] == "/higgsfield-ai/soul/standard"
      assert "footman" in lame.request["json"]["prompt"]
      assert lame.request["json"]["aspect_ratio"] == "3:4"
      assert "data:image" not in str(lame.request)
      assert all(r.dest is None for r in results)
  ```

- [ ] Lancer
  `.venv/bin/python -m pytest tests/test_example_couronnes.py::test_example_cards_soul_dry_run_targets_higgsfield_soul -v`
  — attendu : **ROUGE** — `KeyError: "kind inconnu : 'cards-soul' …"`.

- [ ] Créer `examples/couronnes/prompts/cards-soul.yaml` avec ce contenu exact :

  ```yaml
  # Variante d'art « Soul » (Higgsfield) — 3 cartes témoins, art brut (pas de template).
  art_direction: >-
    Painterly dark medieval fantasy portrait, cinematic chiaroscuro with one warm
    candle-gold key light against deep cold shadow, muted grim palette, aged
    illuminated manuscript texture. No text, no border — illustration only.

  negative: >-
    Avoid: any text, letters, watermark, card frame or border, bright cheerful colors,
    photographic realism.

  style_refs:
    - reference/02-Lame.png

  prompts:
    lame: "A weary low-ranking footman in a patched gambeson gripping a nicked iron sword point-down in a muddy barracks yard."
    emissaire: "A hooded emissary in a dust-worn traveling cloak holding out a sealed letter with a red wax seal."
    couronne-maudite: "A blackened thorn-wrought crown levitating above an empty throne, wreathed in cold violet ether flames."
  ```

- [ ] Modifier `examples/couronnes/forge.yaml` (état post-P3a) :

  1. Vérifier que le bloc `providers:` contient une entrée de type higgsfield (P3a l'a
     ajoutée pour `cartes-animees`). Si — et seulement si — elle manque, l'ajouter :

  ```yaml
    higgsfield:
      type: higgsfield          # clés : HIGGSFIELD_API_KEY + HIGGSFIELD_API_SECRET
  ```

  2. Ajouter sous `kinds:` (au même niveau d'indentation que `cards:`) :

  ```yaml
    cards-soul:                 # variante d'art via Higgsfield Soul — art brut (pas de template)
      asset: image
      prompts: prompts/cards-soul.yaml
      generate: { with: higgsfield, aspect_ratio: "3:4" }
  ```

  > **ADAPTATION** : si P3a a nommé le provider autrement que `higgsfield` (p.ex. `hf`),
  > aligner la valeur de `with:` sur le nom réellement déclaré — ne pas déclarer deux
  > providers higgsfield.

- [ ] Lancer `.venv/bin/python -m pytest tests/test_example_couronnes.py -v` — attendu :
  tous verts (dont les tests P0→P3a de l'exemple, inchangés).
- [ ] Vérification visuelle CLI (lecture seule) :
  ```bash
  .venv/bin/python -m tableforge generate cards-soul -p examples/couronnes --dry-run
  ```
  Attendu : 3 lignes `lame: (dry-run)`, `emissaire: (dry-run)`, `couronne-maudite: (dry-run)`
  (ordre du catalogue), aucune data-URL affichée, aucune clé exigée.
  ```bash
  .venv/bin/python -m tableforge list -p examples/couronnes
  ```
  Attendu : `cards-soul` listé (asset image, provider higgsfield), **aucune issue** du linter.
- [ ] Lancer `.venv/bin/python -m pytest -q` — attendu : tout vert.
- [ ] Commit :
  ```bash
  git add examples/couronnes/forge.yaml examples/couronnes/prompts/cards-soul.yaml \
          tests/test_example_couronnes.py
  git commit -m "feat(exemple): kind cards-soul higgsfield dans couronnes (dry-run)"
  ```

---

## Task 6 : Docs — HANDOFF.md réécrit (état multimodal)

**Files:**
- Modify: `HANDOFF.md` (réécriture complète)

**Interfaces:** aucune (documentation).

**Étapes :**

- [ ] Vérifier la surface réelle avant d'écrire (les noms exacts priment sur ce plan) :
  ```bash
  .venv/bin/python -m tableforge --help          # liste des commandes réelles
  .venv/bin/python -m tableforge list -p examples/couronnes   # kinds réels de l'exemple
  ls src/tableforge/providers/
  ```
  Ajuster dans le contenu ci-dessous : la liste des kinds de l'exemple (section 2) et la
  cheatsheet (section 3) pour refléter **exactement** ces sorties (noms de kinds P1/P2/P3a :
  `musiques`, `sfx`, `nappes`, `narration`, `cartes-animees`… tels que livrés).

- [ ] Remplacer **intégralement** le contenu de `HANDOFF.md` par :

  ```markdown
  # HANDOFF — tableforge

  > Point d'entrée pour **reprendre ce projet dans une session Claude Code neuve**.
  > Lis ce fichier, puis `README.md`, puis `docs/superpowers/` (spec + plans).

  ## 1. Qu'est-ce que c'est

  `tableforge` : un **package Python générique** qui génère le matériel d'un jeu de table —
  cartes, plateaux/maps, **art IA, musiques, SFX/nappes, voix (TTS), dialogues, vidéos** —
  à partir d'un **dossier projet déclaratif** : YAML (config + données + prompts/catalogues)
  + gabarits HTML/CSS + images de référence. Aucune logique de jeu. Pensé pour qu'un ami
  non-codeur configure son jeu sans toucher au code.

  Extrait/généralisé de *Couronnes & Cendres*, livré ici comme exemple complet dans
  `examples/couronnes/`.

  ## 2. État actuel (✅ fait)

  - **Moteur multimodal** : `asset: image | music | sfx | tts | dialogue | video` par kind.
  - **Providers nommés** (`providers:` dans forge.yaml, union discriminée par `type:`) :
    `seedream` (BytePlus Ark, images), `elevenlabs` (music/sfx+loop/tts/dialogue),
    `higgsfield` (images Soul/Seedream + vidéo i2v/t2v, API async), `manual` (réservé,
    outils sans API → `forge studio`).
  - **Contrat plan/execute** : `plan()` pur et sans clé (dry-run, `forge studio`, linter) ;
    `execute()` = seul point réseau/clé. Un seul orchestrateur `generate_kind` pour tout.
  - **CLI** : `forge init | list (linter) | generate | studio | voices | render | board |
    sheet | all` (`all` : ordre fixe image → audio → vidéo, affiché avant exécution).
  - **Rétro-compat v1** : bloc `provider:` anonyme normalisé en `providers.default` (type
    seedream implicite sur ce seul chemin) ; byte-équivalence des requêtes v1 verrouillée
    par test ; shims datés — revoir 2026-10.
  - **Exemple `examples/couronnes/`** : cartes + plateau (seedream), `cards-soul`
    (higgsfield, art brut sans template), catalogues audio (musiques, sfx, nappes),
    narration TTS, cartes animées (i2v). Intégration testée en **dry-run pur**.
  - **Tests** : pytest, couverture ≥ 80 % sur la logique pure ; réseau mocké **respx**.

  ## 3. Reprendre — commandes essentielles

  > ⚠️ Pas de `python`/`pip` système. **Toujours** `.venv/bin/python` (venv via **uv**).

  ```bash
  cd /home/etienne/Documents/tableforge
  .venv/bin/python -m pytest -q                                        # tout vert
  .venv/bin/python -m tableforge list -p examples/couronnes            # linter + état
  .venv/bin/python -m tableforge generate cards -p examples/couronnes --dry-run
  .venv/bin/python -m tableforge generate musiques -p examples/couronnes --dry-run
  .venv/bin/python -m tableforge generate cards-soul -p examples/couronnes --dry-run
  .venv/bin/python -m tableforge studio musiques -p examples/couronnes # fiches copier-coller
  .venv/bin/python -m tableforge render cards -p examples/couronnes --id lame
  .venv/bin/python -m tableforge sheet cards -p examples/couronnes
  ```

  Si l'environnement est cassé :
  ```bash
  uv venv .venv && uv pip install --python .venv/bin/python -e ".[dev]" && .venv/bin/playwright install chromium
  ```

  ## 4. Gotchas critiques

  - **Python/venv** : utiliser **uv** (`~/.local/bin/uv`). Venv = `.venv/`.
  - **Secrets** : les clés ne sont **jamais** en dur ni imprimées — lues via `*_env`
    (`.env` gitignored) dans `execute()` uniquement. Dry-run/studio/erreurs n'affichent
    que des **noms** de variables.
  - **ElevenLabs** : header `xi-api-key` ; `/v1/music` exige un **plan payant** → un 402
    renvoie l'astuce « utilise `forge studio <kind>` ». `loop` (nappes) exige
    `eleven_text_to_sound_v2`. Dialogue > 2 000 caractères : avertissement, pas d'erreur.
    Bornes clampées et **visibles en dry-run** : musique 3 000–600 000 ms, SFX 0,5–30 s.
  - **Higgsfield** : API **async** — `POST /{slug}` → `request_id`, puis
    `GET /requests/{id}/status` (`queued|in_progress|completed|failed|nsfw`), transitions
    affichées par id, sleep injectable dans les tests. `failed`/`nsfw` = **requête
    auto-remboursée**. Deux clés : `HIGGSFIELD_API_KEY` + `HIGGSFIELD_API_SECRET` (header
    `Authorization: Key {key}:{secret}`). Les **slugs de modèles évoluent** — vérifier la
    galerie docs.higgsfield.ai ; idem pour les noms des champs de référence (`image` i2v,
    `IMAGE_REF_FIELD` i2i).
  - **Seedream / Ark** : `ARK_API_KEY` liée à sa région (`ap-southeast`) ; modèle
    `seedream-5-0-260128`. Chemin SDK OpenAI en `pragma: no cover` (smoke).
  - **Rendu** : Playwright/Chromium ; `combined_css` (tokens préfixés) ; le
    `capture_selector` du kind doit matcher la racine du gabarit. Un kind image **sans**
    `template:` est légal (« art brut ») : `generate` seulement, `render` refuse avec un
    message pédagogique.
  - **Liaison par id** : data/prompts/catalogues/art/render/audio/vidéo reliés par le slug
    (`data.slugify`, ex. « Pacte d'Éther » → `pacte-d-ether`).

  ## 5. Architecture (repère rapide)

  ```
  src/tableforge/
    config.py       forge.yaml -> pydantic : providers nommés (par type:), voices,
                    kinds multimodaux (asset/from/generate/studio_url), normalisation legacy
    data.py         rows (slugify, Row, load_rows, expand)
    prompts.py      schéma image : art_direction + prompt_for(id) + reference_data_urls (i2i)
    catalog.py      catalogues non-image (direction/negative/defaults/entries) + clamps
    targets.py      build_kind_spec : cibles par asset (ids, textes, voix, refs, settings)
    providers/
      base.py       AssetJob, Protocol plan/execute, SUPPORTED_ASSETS, options extra=forbid,
                    provider_for (auto-résolution), validate_project (linter), _LegacyAdapter
      seedream.py   images Ark (compat OpenAI-images)
      elevenlabs.py music / sfx+loop / tts / dialogue (httpx direct)
      higgsfield.py images Soul/Seedream + vidéo i2v/t2v (submit -> poll -> download)
      manual.py     provider réservé `manual` (renvoie vers forge studio)
    generate.py     orchestrateur unique toutes modalités (dry-run, skip-exists, --force)
    studio.py       fiches studio (prompt, réglages, dest, URL du bon écran)
    errors.py       hints HTTP partagés en français (401/402/404/422/429)
    paths.py        out/art|audio|video|render|sheet + extension_for (mp3/ogg/wav/mp4/png)
    render.py       Jinja2 + Playwright HTML->PNG
    sheet.py        planche PDF (plan_sheet pur + build_sheet_pdf)
    scaffold.py     forge init (starter multimodal commenté + .env.example)
    cli.py          `forge` (typer)
    templates/starter/   projet vierge bundlé
  examples/couronnes/    exemple complet multimodal
  tests/                 pytest (respx pour tout httpx)
  docs/superpowers/      spec + plans (P0 -> P3b + docs)
  ```

  ## 6. Suites possibles

  - `forge voices design` complet si coupé (ligne de coupe n°1), presets Soul, teaser t2v.
  - **Supprimer les shims v1** (`ProjectConfig.provider`, ré-exports
    `providers/__init__.py`) quand examples et starter n'utilisent plus le format v1 —
    **revoir 2026-10**.
  - Lecture/streaming des médias : hors périmètre (tableforge produit des fichiers).

  ## 7. Vérifier que tout va bien

  ```bash
  .venv/bin/python -m pytest -q                                   # tous verts
  .venv/bin/python -m tableforge list -p examples/couronnes       # tous les kinds, 0 issue
  .venv/bin/python -m tableforge render cards -p examples/couronnes --id couronne-maudite
  ```
  Comparer le PNG rendu à `examples/couronnes/out/render/cards/`.
  ```

- [ ] Vérifier que chaque commande citée dans le fichier existe réellement :
  ```bash
  .venv/bin/python -m tableforge --help
  ```
  Attendu : `init`, `list`, `generate`, `studio`, `voices`, `render`, `board`, `sheet`,
  `all` présents. Si une commande citée manque (ligne de coupe exercée en P2), retirer la
  ligne correspondante du HANDOFF.
- [ ] Commit :
  ```bash
  git add HANDOFF.md
  git commit -m "docs: HANDOFF — état multimodal, architecture, gotchas providers"
  ```

---

## Task 7 : Docs — README.md, sections nouvelles modalités (EN principal + FR)

Éditions ciblées du README actuel (anchors = texte exact du fichier en l'état, non touché
par P0→P3a). Chaque édition est un remplacement exact `Remplacer / Par`.

**Files:**
- Modify: `README.md`

**Interfaces:** aucune (documentation).

**Étapes :**

- [ ] **EN-1 — bandeau + intro.** Remplacer :
  ```
  > **Config-driven game asset generator** — cards, boards/maps, AI art, print sheets.
  ```
  Par :
  ```
  > **Config-driven game asset generator** — cards, boards/maps, AI art, music, SFX, voices, video, print sheets.
  ```
  Puis remplacer :
  ```
  **Config-driven game asset generator**: cards, boards/maps, print-ready designs, and
  **AI art generation** — all from a declarative project folder. You describe your game
  in YAML + CSS + reference images; `tableforge` produces the PNGs and print sheets.
  No game logic, no code to write for a new project.
  ```
  Par :
  ```
  **Config-driven game asset generator**: cards, boards/maps, print-ready designs, and
  **AI-generated art, music, sound effects, voices, dialogue and video** — all from a
  declarative project folder. You describe your game in YAML + CSS + reference images;
  `tableforge` produces the PNGs, audio files, videos and print sheets.
  No game logic, no code to write for a new project.
  ```

- [ ] **EN-2 — tableau des commandes.** Remplacer le tableau de la section `### Commands`
  (les 9 lignes de `| Command | Effect |` à ``| `forge all <kind>` | … |``) par :
  ```
  | Command | Effect |
  |---|---|
  | `forge init <name>` | Scaffolds a blank project (refuses a non-empty folder). |
  | `forge list -p <project>` | Lists kinds (asset, provider, file state) and lints the whole config. |
  | `forge generate <kind> [--id X] [--dry-run] [--force]` | Generates the kind's assets (any modality) → `out/art\|audio\|video/<kind>/`. |
  | `forge studio <kind> [--id X]` | Prints copy-paste cards (prompt, settings, target path, studio URL) for manual tools. |
  | `forge voices list` | Lists your ElevenLabs voices and checks the `voices:` map. |
  | `forge voices design "<desc>" --name NAME [--save]` | Designs a new ElevenLabs voice from a text description. |
  | `forge render <kind> [--id X]` | PNG designs → `out/render/<kind>/` (image kinds with a template). |
  | `forge sheet <kind>` | Print-ready PDF sheet → `out/sheet/<kind>.pdf`. |
  | `forge board <kind>` | Full-page render (board / map). |
  | `forge all [kind]` | Everything, in fixed order image → audio → video (order printed first). |
  ```

- [ ] **EN-3 — nouvelle section modalités.** Insérer juste **avant** la ligne
  `### Configuration` (section EN) :
  ```
  ### Modalities & providers

  Each kind declares an `asset:` (default `image`) and, via `generate: { with: <name> }`,
  the provider that produces it. Providers are named accounts declared once under
  `providers:` — "the services I have an API key for".

  | `asset:` | Providers | Output |
  |---|---|---|
  | `image` | `seedream` (BytePlus Ark) · `higgsfield` (Soul, Seedream-v4) | `out/art/<kind>/<id>.png` |
  | `music` | `elevenlabs` | `out/audio/<kind>/<id>.mp3` |
  | `sfx` (incl. loopable soundscapes) | `elevenlabs` | `out/audio/<kind>/<id>.mp3` |
  | `tts` / `dialogue` | `elevenlabs` | `out/audio/<kind>/<id>.mp3` |
  | `video` (`from:` = image-to-video, otherwise text-to-video) | `higgsfield` | `out/video/<kind>/<id>.mp4` |

  Tools without a public API (e.g. ElevenLabs image/video) use the reserved `manual`
  provider: `forge generate` refuses and `forge studio <kind>` prints ready-to-paste cards
  (prompt, settings, destination path, direct URL to the right screen).

  API keys are only ever referenced by env-var **name** (`api_key_env`), read from `.env`
  (gitignored) at execution time. `--dry-run` shows the exact request without any network
  call. If `with:` is omitted, the provider is auto-resolved when exactly one declared
  provider supports the kind's asset.
  ```

- [ ] **EN-4 — exemple forge.yaml.** Dans la sous-section `#### forge.yaml` (EN), remplacer
  le bloc yaml complet (de ```` ```yaml ```` à ```` ``` ````) par :
  ```yaml
  project: my-game

  providers:                    # "the accounts I have a key for"
    ark:
      type: seedream            # type is REQUIRED under providers:
      base_url: https://ark.ap-southeast.bytepluses.com/api/v3
      api_key_env: ARK_API_KEY  # NAME of the env var (never the key itself)
      model: seedream-5-0-260128
    eleven:
      type: elevenlabs          # sane defaults (base_url, formats, models)
    higgsfield:
      type: higgsfield          # keys: HIGGSFIELD_API_KEY + HIGGSFIELD_API_SECRET

  voices:                       # human names -> ElevenLabs voice ids
    narrator: JBFqnCBsd6RMkjVDRZzb

  defaults:
    max_refs: 3                 # max number of i2i reference images
    ref_max_px: 1024            # downscale refs before sending

  kinds:
    cards:                      # image kind (asset: image is the default)
      data: data/cards.yaml
      prompts: prompts/cards.yaml
      template: templates/card
      render_size: { width: 744, height: 1039 }
      scale: 3
      generate: { with: ark }
      sheet: { page: A4, cols: 3, rows: 3, card_w_mm: 63, card_h_mm: 88 }

    cards-soul:                 # raw AI art via Higgsfield Soul (no template needed)
      asset: image
      prompts: prompts/cards-soul.yaml
      generate: { with: higgsfield, aspect_ratio: "3:4" }

    narration:                  # TTS from data rows (Jinja template over row fields)
      asset: tts
      data: data/cards.yaml
      generate: { with: eleven, voice: narrator, text: "{{ name }}. {{ eff }}", language: en }

    musiques:                   # music from a catalog file
      asset: music
      prompts: prompts/musiques.yaml
      generate: { with: eleven }

    cartes-animees:             # image-to-video: animates out/art/cards/<id>.png
      asset: video
      from: cards
      generate: { with: higgsfield, model: bytedance/seedance/v1/image-to-video }
  ```
  Puis ajouter immédiatement sous ce bloc :
  ```
  A v1 `forge.yaml` (single anonymous `provider:` block, no `generate:`) is still fully
  supported — it is normalized to `providers: {default: …}` at load time.
  ```

- [ ] **EN-5 — section provider.** Remplacer la section `### Image provider` (titre + son
  paragraphe) par :
  ```
  ### Providers

  - **seedream** — BytePlus Ark, **OpenAI-images**-compatible endpoint (`base_url`,
    `model`, `api_key_env` in config, so other compatible endpoints work too).
    Reference images (i2i) supported.
  - **elevenlabs** — music (`/v1/music`, requires a paid plan — on 402 the CLI points to
    `forge studio`), SFX and loopable soundscapes, TTS and multi-voice dialogue. Voices
    are declared once in the `voices:` map (name → voice_id) and referenced by name.
  - **higgsfield** — async API (submit → poll, failed/NSFW requests auto-refunded):
    images (Soul / Seedream-v4, `aspect_ratio`, `style_id`, `style_strength`, reference
    images) and video (image-to-video via `from:`, text-to-video otherwise). Needs
    `HIGGSFIELD_API_KEY` + `HIGGSFIELD_API_SECRET`.
  - **manual** — reserved provider for tools without an API; pairs with `forge studio`
    and an optional `studio_url:` on the kind.

  Keys are **never** stored: they are read at runtime from the env variables named in the
  provider block (via `.env`, gitignored) and never printed.
  ```

- [ ] **EN-6 — arborescence.** Dans la section `### Concept` (EN), remplacer la ligne :
  ```
    out/                   generated art, rendered PNGs, PDF sheets  (gitignored)
  ```
  Par :
  ```
    out/                   generated art/audio/video, rendered PNGs, PDF sheets  (gitignored)
  ```

- [ ] **FR-1 — intro.** Remplacer :
  ```
  **Générateur d'assets de jeu piloté par configuration** : cartes (*card*), plateaux / maps,
  designs, et **génération d'art IA** — le tout à partir d'un dossier projet déclaratif.
  ```
  Par :
  ```
  **Générateur d'assets de jeu piloté par configuration** : cartes (*card*), plateaux / maps,
  designs, et **génération IA d'art, de musiques, de SFX, de voix, de dialogues et de
  vidéos** — le tout à partir d'un dossier projet déclaratif.
  ```

- [ ] **FR-2 — tableau des commandes.** Remplacer le tableau de la section `### Commandes`
  par la traduction du tableau EN-2 :
  ```
  | Commande | Effet |
  |---|---|
  | `forge init <nom>` | Scaffold un projet vierge (refuse un dossier non vide). |
  | `forge list -p <projet>` | Liste les kinds (asset, provider, état des fichiers) et linte toute la config. |
  | `forge generate <kind> [--id X] [--dry-run] [--force]` | Génère les assets du kind (toute modalité) → `out/art\|audio\|video/<kind>/`. |
  | `forge studio <kind> [--id X]` | Fiches copier-coller (prompt, réglages, chemin de dépôt, URL du studio) pour les outils manuels. |
  | `forge voices list` | Liste tes voix ElevenLabs et vérifie la map `voices:`. |
  | `forge voices design "<desc>" --name NOM [--save]` | Conçoit une nouvelle voix ElevenLabs depuis une description. |
  | `forge render <kind> [--id X]` | Designs PNG → `out/render/<kind>/` (kinds image avec template). |
  | `forge sheet <kind>` | Planche d'impression PDF → `out/sheet/<kind>.pdf`. |
  | `forge board <kind>` | Rendu plein page (plateau / map). |
  | `forge all [kind]` | Tout, dans l'ordre fixe image → audio → vidéo (ordre affiché avant exécution). |
  ```

- [ ] **FR-3 — section modalités.** Insérer juste **avant** la ligne `### Configuration`
  (section FR) la traduction de EN-3 :
  ```
  ### Modalités et fournisseurs

  Chaque kind déclare un `asset:` (défaut `image`) et, via `generate: { with: <nom> }`,
  le provider qui le produit. Les providers sont des comptes nommés déclarés une fois sous
  `providers:` — « les services pour lesquels j'ai une clé API ».

  | `asset:` | Providers | Sortie |
  |---|---|---|
  | `image` | `seedream` (BytePlus Ark) · `higgsfield` (Soul, Seedream-v4) | `out/art/<kind>/<id>.png` |
  | `music` | `elevenlabs` | `out/audio/<kind>/<id>.mp3` |
  | `sfx` (dont nappes en boucle) | `elevenlabs` | `out/audio/<kind>/<id>.mp3` |
  | `tts` / `dialogue` | `elevenlabs` | `out/audio/<kind>/<id>.mp3` |
  | `video` (`from:` = image-to-video, sinon text-to-video) | `higgsfield` | `out/video/<kind>/<id>.mp4` |

  Les outils sans API publique (p. ex. l'image/vidéo d'ElevenLabs) passent par le provider
  réservé `manual` : `forge generate` refuse et `forge studio <kind>` imprime des fiches
  prêtes à coller (prompt, réglages, chemin de dépôt, URL du bon écran).

  Les clés API ne sont référencées que par **nom** de variable d'env (`api_key_env`), lues
  depuis `.env` (gitignored) à l'exécution. `--dry-run` montre la requête exacte sans aucun
  appel réseau. Si `with:` est omis, le provider est auto-résolu quand exactement un
  provider déclaré sait produire l'asset du kind.
  ```

- [ ] **FR-4 — exemple forge.yaml + section fournisseur.** Dans la sous-section
  `#### forge.yaml` (FR), remplacer le bloc yaml complet par le même bloc que EN-4 (les
  commentaires peuvent être traduits en français), suivi de :
  ```
  Un `forge.yaml` v1 (bloc `provider:` anonyme, sans `generate:`) reste entièrement
  supporté — il est normalisé en `providers: {default: …}` au chargement.
  ```
  Puis remplacer la section `### Fournisseur d'images` (titre + paragraphe) par la
  traduction de EN-5 (titre : `### Fournisseurs`).

- [ ] **FR-5 — arborescence.** Dans la section `### Concept` (FR), remplacer :
  ```
    out/                   art généré, PNG rendus, planches PDF  (gitignored)
  ```
  Par :
  ```
    out/                   art/audio/vidéo générés, PNG rendus, planches PDF  (gitignored)
  ```

- [ ] Vérifier la cohérence doc ↔ code :
  ```bash
  .venv/bin/python -m tableforge --help
  ```
  Attendu : toutes les commandes documentées existent (si `voices design` a été coupé en
  P2 — ligne de coupe n°1 — retirer sa ligne des deux tableaux).
- [ ] Commit :
  ```bash
  git add README.md
  git commit -m "docs: README — modalités audio/vidéo et providers nommés (EN/FR)"
  ```

---

## Task 8 : Docs — CLAUDE.md (doctrine réseau, cheatsheet, kinds multimodaux)

**Files:**
- Modify: `CLAUDE.md` (réécriture complète)

**Interfaces:** aucune (documentation).

**Étapes :**

- [ ] Remplacer **intégralement** le contenu de `CLAUDE.md` par :

  ```markdown
  # CLAUDE.md — conventions de session

  Conventions pour travailler sur `tableforge` dans Claude Code. Lis d'abord `HANDOFF.md`.

  ## Environnement

  - **Toujours `.venv/bin/python`** — pas de `python`/`pip` système. Venv créé via **uv**.
  - Bootstrap si besoin :
    `uv venv .venv && uv pip install --python .venv/bin/python -e ".[dev]" && .venv/bin/playwright install chromium`.

  ## Avant de dire « c'est fait »

  - Lancer `.venv/bin/python -m pytest -q` — **doit être vert**.
  - Pour une vérif visuelle : rendre une carte de l'exemple et regarder le PNG.

  ## Discipline

  - **TDD** pour toute nouvelle logique (test rouge → impl minimale → vert → commit).
  - Couverture **≥ 80 %** sur la logique pure. Le rendu navigateur (`render.py`) et la CLI
    sont exclus de la couverture (smoke-testés).
  - **Doctrine réseau** : tout chemin httpx (ElevenLabs, Higgsfield, téléchargements) est
    testé avec **respx** — asserter les headers (`xi-api-key`, `Authorization: Key`), le
    corps JSON **et** le fichier écrit. Le chemin SDK OpenAI de Seedream reste
    `pragma: no cover` (smoke). Aucun test ne touche le vrai réseau. Le poll Higgsfield a
    un `sleep` injectable : jamais d'attente réelle en test.
  - **Contrat providers** : `plan()` pur et sans clé ; `execute()` = seul point réseau/clé.
    Les clés sont lues via `*_env` (dotenv + env) et ne sont **jamais** imprimées.
  - Modules courts (≤ ~400 lignes), données immuables (dataclasses frozen), erreurs
    explicites **en français**.
  - Commits conventionnels (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).

  ## Cheatsheet

  ```bash
  .venv/bin/python -m pytest -q
  .venv/bin/python -m tableforge list -p examples/couronnes            # linter + état
  .venv/bin/python -m tableforge generate cards -p examples/couronnes --dry-run
  .venv/bin/python -m tableforge generate musiques -p examples/couronnes --dry-run
  .venv/bin/python -m tableforge studio musiques -p examples/couronnes
  .venv/bin/python -m tableforge voices list -p examples/couronnes
  .venv/bin/python -m tableforge render cards -p examples/couronnes --id lame
  .venv/bin/python -m tableforge sheet cards -p examples/couronnes
  .venv/bin/python -m tableforge all -p examples/couronnes             # image → audio → vidéo
  ```

  ## Où est quoi

  - Moteur : `src/tableforge/*.py` + `src/tableforge/providers/` (tableau dans `HANDOFF.md`).
  - Starter cloné par `forge init` : `src/tableforge/templates/starter/`.
  - Exemple complet : `examples/couronnes/`.
  - Spec & plans : `docs/superpowers/specs/` et `docs/superpowers/plans/`.
  - **Shims de compat v1** (`ProjectConfig.provider`, ré-exports `providers/__init__.py`) :
    à supprimer quand examples et starter n'utilisent plus le format v1 — **revoir 2026-10**.

  ## Ajouter un kind à un projet

  1. Déclarer le kind dans `forge.yaml` : `asset:` (`image` par défaut, sinon
     `music | sfx | tts | dialogue | video`) et `generate: { with: <provider>, ...options }`
     (`with:` omis = auto-résolution si un seul provider sait faire l'asset). Pour une
     image **rendue** : ajouter `template`, `render_size`, `sheet?` ; sans template =
     art brut (`generate` seulement).
  2. Selon l'asset : `data/<kind>.yaml` (rows avec `id`) et/ou le fichier `prompts:` —
     schéma **image** (`art_direction`, `prompts:`, `style_refs`, `negative`, `overrides`)
     ou **catalogue** non-image (`direction`, `negative`, `defaults`, `entries:`).
  3. Kind `video` i2v : `from: <kind image>` (anime `out/art/<from>/<id>.png` ; ids = ceux
     du kind source). Sans `from:` = t2v (ids = entries du catalogue).
  4. Voix (tts/dialogue) : déclarer la map `voices:` (nom → voice_id) et référencer par
     **nom** (`generate.voice`, `voice_field:`, ou `voice:` d'une entrée de catalogue).
  5. `forge list` (linter) → `forge generate <kind> --dry-run` → `forge generate <kind>`
     (ou `forge studio <kind>` pour un provider `manual`).
  ```

- [ ] Vérifier que la cheatsheet est exacte (chaque commande existe) :
  ```bash
  .venv/bin/python -m tableforge --help
  .venv/bin/python -m tableforge voices --help
  ```
  Attendu : commandes présentes ; sinon ajuster la cheatsheet (ne documenter que l'existant).
- [ ] Commit :
  ```bash
  git add CLAUDE.md
  git commit -m "docs: CLAUDE.md — doctrine réseau respx, cheatsheet studio/voices, kinds multimodaux"
  ```

---

## Task 9 : Commentaires datés sur les shims de compat v1

**Files:**
- Modify: `src/tableforge/config.py`, `src/tableforge/providers/__init__.py`

**Interfaces:** aucune (commentaires uniquement — zéro changement de comportement).

**Étapes :**

- [ ] Dans `src/tableforge/config.py`, remplacer la docstring/le commentaire de la propriété
  `provider` de `ProjectConfig` par :

  ```python
      @property
      def provider(self) -> AnyProviderConfig:
          """DEPRECATED — shim de compat v1 (bloc `provider:` anonyme).

          À supprimer quand examples/ et le starter n'utilisent plus le format v1 —
          revoir 2026-10.
          """
          return self.providers["default"]
  ```

- [ ] Dans `src/tableforge/providers/__init__.py`, remplacer la docstring de module par :

  ```python
  """Ré-exports de compat v1 (`from tableforge.providers import SeedreamProvider`…).

  Shim de compat : à supprimer quand examples/ et le starter n'utilisent plus le
  format v1 — revoir 2026-10.
  """
  ```

  (Conserver tels quels tous les ré-exports existants sous la docstring.)

- [ ] Lancer `.venv/bin/python -m pytest -q` — attendu : tout vert (commentaires only).
- [ ] Commit :
  ```bash
  git add src/tableforge/config.py src/tableforge/providers/__init__.py
  git commit -m "chore: commentaires datés sur les shims de compat v1 (revoir 2026-10)"
  ```

---

## Task 10 : Vérification finale du chantier

**Files:** aucun (lecture/exécution seulement — pas de commit attendu).

**Interfaces:** aucune.

**Étapes :**

- [ ] Suite complète :
  ```bash
  .venv/bin/python -m pytest -q
  ```
  Attendu : **tous les tests verts**, zéro skip inexpliqué.

- [ ] Couverture affichée :
  ```bash
  .venv/bin/python -m pytest --cov=tableforge --cov-report=term
  ```
  Attendu : ligne `TOTAL … ≥ 80%` (objectif ≈ 96 % ; `render.py`, `cli.py`, `__main__.py`
  exclus par `pyproject.toml` ; chemin SDK Seedream en `pragma: no cover`). Si < 80 % :
  identifier les lignes découvertes (`--cov-report=term-missing`) et compléter les tests
  unitaires de la logique pure concernée (cycle TDD + commit `test:` dédié) avant de clore.

- [ ] Linter/état de l'exemple :
  ```bash
  .venv/bin/python -m tableforge list -p examples/couronnes
  ```
  Attendu : **tous** les kinds listés avec leur asset et leur provider — au minimum
  `cards` (image/seedream), `board`, `cards-soul` (image/higgsfield) et les kinds
  audio/vidéo livrés en P1–P3a (`musiques`, `sfx`, `nappes`, `narration`,
  `cartes-animees`, selon les noms réels) — et **aucune issue** de `validate_project`.

- [ ] Dry-runs témoins (aucune clé requise, aucun réseau) :
  ```bash
  .venv/bin/python -m tableforge generate cards -p examples/couronnes --dry-run
  .venv/bin/python -m tableforge generate cards-soul -p examples/couronnes --dry-run
  ```
  Attendu : 18 lignes `(dry-run)` pour `cards`, 3 pour `cards-soul`, aucune data-URL ni
  secret affiché.

- [ ] État git propre :
  ```bash
  git status --short && git log --oneline -12
  ```
  Attendu : arbre propre ; les commits de ce plan apparaissent dans l'ordre (Task 1 → 9).
  Aucune modification en attente. Si un correctif a été nécessaire pendant cette tâche,
  il a son propre commit (`fix:` ou `test:`) — sinon cette tâche ne committe rien.
