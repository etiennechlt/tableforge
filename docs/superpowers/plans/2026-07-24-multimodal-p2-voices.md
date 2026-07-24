# Multimodal P2 — Voix (TTS, dialogues, `forge voices`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Étendre tableforge aux assets vocaux ElevenLabs : cibles TTS (trois sources : rows+gabarit Jinja, catalogue, précédence des voix), dialogues multi-voix, map `voices:`, builders/plan/execute ElevenLabs TTS+dialogue (respx), options validées, fiches studio speech-synthesis, utilitaire `forge voices list` / `forge voices design`, starter et exemple `couronnes` enrichis.

**Architecture:** On étend les modules livrés par P0/P1 conformément au CONTRAT D'INTERFACES FIGÉ du chantier multimodal : `targets.build_kind_spec` gagne les branches `tts` et `dialogue` (pur, sans clé) ; `providers/elevenlabs.py` gagne `build_tts_request`/`build_dialogue_request` et les branches correspondantes de `plan()` (l'`execute()` générique P1 — POST `payload["path"]` + header `xi-api-key` — est réutilisé tel quel) ; `providers/base.py` gagne les modèles d'options `("elevenlabs","tts")` / `("elevenlabs","dialogue")` et la détection des voix inconnues dans `validate_project` ; `studio.py` gagne les URLs speech-synthesis ; un nouveau module `voices.py` (httpx pur, couvert respx) porte la logique de `forge voices`, la CLI restant une enveloppe mince hors couverture.

**Tech Stack:** Python ≥ 3.10, pydantic v2, jinja2 (`StrictUndefined`), httpx (jamais de SDK vendeur), respx (mocks), typer, pytest + pytest-cov, PyYAML.

## Global Constraints

- **Prérequis : P1 mergée.** Ce plan suppose présents (contrat figé) : `src/tableforge/targets.py` (`Target`, `DialogueLine`, `KindSpec`, `build_kind_spec`), `src/tableforge/catalog.py` (`load_catalog`, `catalog_entries`, `get_entry`), `src/tableforge/providers/{base,seedream,elevenlabs,manual}.py` (`AssetJob`, `Provider`, `provider_for`, `options_model`, `validate_project`, `ElevenLabsProvider` music+sfx), `src/tableforge/studio.py` (`STUDIO_URLS`, `studio_cards`), `src/tableforge/errors.py` (`raise_with_hint`), `paths.asset_path`/`extension_for`, `generate.generate_kind` généralisé, CLI `forge studio` + refus pédagogiques. La Task 1 vérifie tout cela avant de commencer.
- **Ancrages P1 :** quand une étape insère du code dans une fonction P1 (dispatch de `build_kind_spec`, boucle de `ElevenLabsProvider.plan`, registre consulté par `options_model`, dict `STUDIO_URLS`), le code ajouté est donné **complet** et n'utilise que des interfaces du contrat ; seul le point d'insertion (nom de variable locale, if/elif vs mapping) est à adapter mécaniquement au code P1 réel, sans changer ni le code ajouté ni les signatures publiques.
- **Contrat figé :** ne renégocier aucune signature du CONTRAT D'INTERFACES (voir la spec `docs/superpowers/specs/2026-07-24-multimodal-providers-design.md`).
- **Environnement :** toujours `.venv/bin/python`, jamais le python système. Toutes les commandes se lancent depuis `/home/etienne/Documents/tableforge`.
- **TDD strict :** test rouge → implémentation minimale → test vert → suite complète verte → commit. Aucune étape sans code.
- **Couverture ≥ 80 %** sur la logique pure (objectif ≈ 96 %). `render.py`, `cli.py`, `__main__.py` restent exclus (cf. `pyproject.toml`) — d'où le module `voices.py` séparé, couvert par respx, la CLI restant mince.
- **Doctrine réseau :** tout chemin httpx est testé avec **respx** (header `xi-api-key`, corps JSON, params, fichier écrit assertés). Aucun appel réseau réel dans les tests. Le chemin SDK OpenAI de Seedream reste `pragma: no cover`.
- **Style :** dataclasses `frozen=True`, données immuables, messages d'erreur **en français**, secrets jamais imprimés (noms de variables d'env uniquement), modules ≤ ~400 lignes, code et noms de tests **en anglais**, tests AAA.
- **Commits conventionnels en français** (`feat:`, `fix:`, `test:`, `docs:`, `chore:`), un commit par tâche.
- **Ligne de coupe documentée :** la Task 13 (`forge voices design`) est coupable sans casser le reste (c'est la ligne de coupe n°1 de la spec). Les Tasks 1–12 et 14 forment le noyau non négociable de P2.

---

### Task 1 : Vérifier les prérequis P1 et la dépendance respx

**Files:**
- Modify (seulement si respx absent) : `/home/etienne/Documents/tableforge/pyproject.toml`

**Interfaces:**
- Consumes : l'arbre post-P1 (modules listés dans Global Constraints).
- Produces : rien (vérification) ; au besoin, `respx` dans `[project.optional-dependencies] dev`.

**Étapes :**

- [ ] 1.1 Vérifier que la suite P1 est verte :
  ```bash
  cd /home/etienne/Documents/tableforge && .venv/bin/python -m pytest -q
  ```
  Attendu : `... passed` (0 failed). Si rouge : **STOP**, P1 n'est pas mergée — ce plan ne s'applique pas encore.
- [ ] 1.2 Vérifier la présence des modules P1 :
  ```bash
  ls src/tableforge/targets.py src/tableforge/catalog.py src/tableforge/studio.py \
     src/tableforge/errors.py src/tableforge/providers/base.py \
     src/tableforge/providers/elevenlabs.py src/tableforge/providers/manual.py
  ```
  Attendu : les 7 chemins listés sans erreur.
- [ ] 1.3 Vérifier les symboles du contrat consommés par P2 :
  ```bash
  .venv/bin/python -c "
  from tableforge.targets import Target, DialogueLine, KindSpec, build_kind_spec
  from tableforge.catalog import load_catalog, catalog_entries, get_entry
  from tableforge.providers.base import AssetJob, options_model, provider_for, validate_project
  from tableforge.providers.elevenlabs import ElevenLabsProvider
  from tableforge.studio import STUDIO_URLS, studio_cards
  from tableforge.paths import asset_path, extension_for
  print('contrat P1 OK')"
  ```
  Attendu : `contrat P1 OK`.
- [ ] 1.4 Vérifier respx :
  ```bash
  .venv/bin/python -c "import respx; print(respx.__version__)"
  ```
  Attendu : un numéro de version. **Si `ModuleNotFoundError`** : dans `/home/etienne/Documents/tableforge/pyproject.toml`, remplacer
  ```toml
  dev = ["pytest", "pytest-cov"]
  ```
  par
  ```toml
  dev = ["pytest", "pytest-cov", "respx"]
  ```
  puis :
  ```bash
  uv pip install --python .venv/bin/python -e ".[dev]"
  .venv/bin/python -c "import respx; print(respx.__version__)"
  git add pyproject.toml && git commit -m "chore: ajouter respx aux dépendances de dev"
  ```
- [ ] 1.5 Si aucun changement n'a été nécessaire : pas de commit pour cette tâche.

---

### Task 2 : `targets.py` — résolution des voix + cibles TTS depuis un catalogue

**Files:**
- Modify : `/home/etienne/Documents/tableforge/src/tableforge/targets.py`
- Test (Create) : `/home/etienne/Documents/tableforge/tests/test_targets_voices.py`

**Interfaces:**
- Consumes : `catalog.load_catalog(path) -> dict`, `catalog.catalog_entries(cfg) -> dict`, `catalog.get_entry(cfg, entry_id) -> dict` (une entrée `str` devient `{"prompt": str}`), `config.ProjectConfig.voices: dict[str, str]`, `config.KindConfig` (`asset`, `prompts`, `name`).
- Produces (privées à `targets.py`, consommées par `build_kind_spec`) :
  ```python
  def _resolve_voice(name: str, voices: dict[str, str], *, kind: str) -> str  # KeyError FR si inconnu
  def _catalog_output_format(kind_cfg: KindConfig) -> Optional[str]
  def _tts_targets_from_catalog(project: ProjectConfig, kind_cfg: KindConfig,
                                options: dict, ids: Optional[list[str]]) -> tuple[Target, ...]
  def _tts_targets(project: ProjectConfig, kind_cfg: KindConfig,
                   options: dict, ids: Optional[list[str]]) -> tuple[Target, ...]
  ```
  Et `build_kind_spec(project, "kind-tts")` renvoie un `KindSpec(asset="tts", …)` avec `Target(id, text, voice_id)` par entrée.

**Étapes :**

- [ ] 2.1 **Test rouge** — créer `/home/etienne/Documents/tableforge/tests/test_targets_voices.py` :
  ```python
  from pathlib import Path

  import pytest

  from tableforge.config import load_project
  from tableforge.targets import build_kind_spec

  FORGE = """
  project: demo
  providers:
    eleven:
      type: elevenlabs
  voices:
    narrateur: id-narrateur
    heraut: id-heraut
    vieille-reine: id-vieille-reine
  kinds:
    regles:
      asset: tts
      prompts: prompts/regles.yaml
      generate: { with: eleven, voice: narrateur }
    narration:
      asset: tts
      data: data/cards.yaml
      generate: { with: eleven, voice: narrateur, text: "{{ name }}. {{ eff }}", language: fr }
    pnj:
      asset: tts
      data: data/pnj.yaml
      generate: { with: eleven, text: "{{ replique }}", voice_field: voice, voice: narrateur }
    dialogues:
      asset: dialogue
      prompts: prompts/dialogues.yaml
      generate: { with: eleven }
    sans-source:
      asset: tts
      generate: { with: eleven, voice: narrateur }
  """

  REGLES = """
  output_format: mp3_22050_32
  entries:
    mise-en-place: { text: "Placez le plateau." }
    rappel: { text: "Un sceau par lieu.", voice: heraut }
    annonce: "Bienvenue à la table."
  """


  def _write(tmp_path: Path, rel: str, content: str) -> None:
      path = tmp_path / rel
      path.parent.mkdir(parents=True, exist_ok=True)
      path.write_text(content, encoding="utf-8")


  def _project(tmp_path: Path, files: dict[str, str] | None = None):
      _write(tmp_path, "forge.yaml", FORGE)
      for rel, content in (files or {}).items():
          _write(tmp_path, rel, content)
      return load_project(tmp_path)


  def test_tts_catalog_targets_use_default_voice(tmp_path):
      project = _project(tmp_path, {"prompts/regles.yaml": REGLES})

      spec = build_kind_spec(project, "regles")

      assert spec.asset == "tts"
      target = next(t for t in spec.targets if t.id == "mise-en-place")
      assert target.text == "Placez le plateau."
      assert target.voice_id == "id-narrateur"


  def test_tts_catalog_entry_voice_overrides_default(tmp_path):
      project = _project(tmp_path, {"prompts/regles.yaml": REGLES})

      spec = build_kind_spec(project, "regles")

      rappel = next(t for t in spec.targets if t.id == "rappel")
      assert rappel.voice_id == "id-heraut"


  def test_tts_catalog_accepts_bare_string_entries(tmp_path):
      project = _project(tmp_path, {"prompts/regles.yaml": REGLES})

      spec = build_kind_spec(project, "regles")

      annonce = next(t for t in spec.targets if t.id == "annonce")
      assert annonce.text == "Bienvenue à la table."
      assert annonce.voice_id == "id-narrateur"


  def test_tts_catalog_output_format_flows_to_spec(tmp_path):
      project = _project(tmp_path, {"prompts/regles.yaml": REGLES})

      spec = build_kind_spec(project, "regles")

      assert spec.output_format == "mp3_22050_32"


  def test_tts_unknown_voice_lists_declared_voices(tmp_path):
      catalog = 'entries:\n  x: { text: "Bonjour.", voice: fantome }\n'
      project = _project(tmp_path, {"prompts/regles.yaml": catalog})

      with pytest.raises(KeyError, match="voix inconnue") as excinfo:
          build_kind_spec(project, "regles")

      assert "narrateur" in str(excinfo.value)


  def test_tts_catalog_entry_without_voice_anywhere_raises(tmp_path):
      forge_no_default = FORGE.replace(
          "generate: { with: eleven, voice: narrateur }\n    narration",
          "generate: { with: eleven }\n    narration")
      _write(tmp_path, "forge.yaml", forge_no_default)
      _write(tmp_path, "prompts/regles.yaml", 'entries:\n  x: { text: "Bonjour." }\n')
      project = load_project(tmp_path)

      with pytest.raises(ValueError, match="aucune voix"):
          build_kind_spec(project, "regles")


  def test_tts_kind_without_text_or_prompts_raises(tmp_path):
      project = _project(tmp_path)

      with pytest.raises(ValueError, match="prompts"):
          build_kind_spec(project, "sans-source")
  ```
- [ ] 2.2 Lancer :
  ```bash
  .venv/bin/python -m pytest tests/test_targets_voices.py -v
  ```
  Attendu : **7 échecs** (`ValueError`/`NotImplementedError`/`KeyError` selon la garde P1 pour un asset non géré — peu importe le message, aucun test ne passe).
- [ ] 2.3 **Implémentation** — dans `/home/etienne/Documents/tableforge/src/tableforge/targets.py` :
  1. Compléter les imports en tête de fichier (ajouter ce qui manque, sans dupliquer l'existant P1) :
     ```python
     from .catalog import catalog_entries, get_entry, load_catalog
     ```
  2. Ajouter à la fin du fichier :
     ```python
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
         cfg = load_catalog(kind_cfg.prompts)
         target_ids = ids or list(catalog_entries(cfg))
         default_voice = options.get("voice")
         targets: list[Target] = []
         for entry_id in target_ids:
             entry = get_entry(cfg, entry_id)
             text = entry.get("text") or entry.get("prompt")
             if not text:
                 raise ValueError(
                     f"kind '{kind_cfg.name}', entrée '{entry_id}' : champ 'text' requis")
             voice_name = entry.get("voice") or default_voice
             if not voice_name:
                 raise ValueError(
                     f"kind '{kind_cfg.name}', entrée '{entry_id}' : aucune voix — déclare "
                     "generate.voice ou un champ voice dans l'entrée")
             voice_id = _resolve_voice(str(voice_name), project.voices, kind=kind_cfg.name)
             targets.append(Target(id=entry_id, text=str(text).strip(), voice_id=voice_id))
         return tuple(targets)


     def _tts_targets(project: ProjectConfig, kind_cfg: KindConfig,
                      options: dict, ids: Optional[list[str]]) -> tuple[Target, ...]:
         if kind_cfg.prompts is not None:
             return _tts_targets_from_catalog(project, kind_cfg, options, ids)
         raise ValueError(
             f"le kind tts '{kind_cfg.name}' : déclare generate.text + data, "
             "ou un fichier prompts (catalogue)")
     ```
  3. Brancher `build_kind_spec` : dans le dispatch par `kind_cfg.asset` de P1 (if/elif ou mapping de fonctions — adapter mécaniquement), ajouter la branche `tts` qui produit les deux valeurs déjà utilisées par les branches P1 (`targets` et `output_format`) :
     ```python
     elif kind_cfg.asset == "tts":
         targets = _tts_targets(project, kind_cfg, options, ids)
         output_format = _catalog_output_format(kind_cfg)
     ```
     (`options` est le dict d'extras de `generate:` que P1 passe déjà aux branches music/sfx.)
- [ ] 2.4 Relancer :
  ```bash
  .venv/bin/python -m pytest tests/test_targets_voices.py -v
  ```
  Attendu : `7 passed`.
- [ ] 2.5 Suite complète :
  ```bash
  .venv/bin/python -m pytest -q
  ```
  Attendu : verte.
- [ ] 2.6 Commit :
  ```bash
  git add src/tableforge/targets.py tests/test_targets_voices.py
  git commit -m "feat: cibles TTS depuis catalogue et résolution des voix nommées"
  ```

---

### Task 3 : `targets.py` — cibles TTS depuis les rows (gabarit Jinja + `voice_field`)

**Files:**
- Modify : `/home/etienne/Documents/tableforge/src/tableforge/targets.py`
- Test (Modify) : `/home/etienne/Documents/tableforge/tests/test_targets_voices.py`

**Interfaces:**
- Consumes : `data.load_rows(path) -> list[Row]` (`Row.id`, `Row.data: dict`, `Row.get`), `jinja2.Template(..., undefined=jinja2.StrictUndefined)`.
- Produces :
  ```python
  def _tts_targets_from_rows(project: ProjectConfig, kind_cfg: KindConfig,
                             options: dict, ids: Optional[list[str]]) -> tuple[Target, ...]
  ```
  Précédence des voix : `row[voice_field]` > (pas d'entrée de catalogue sur ce chemin) > `options["voice"]`. Décisions : `qty` ignoré (un audio par id unique, pas d'`expand`) ; `voice_field` absent d'une row → repli sur `generate.voice` ; erreur seulement si aucune voix ne se résout.

**Étapes :**

- [ ] 3.1 **Test rouge** — ajouter à la fin de `/home/etienne/Documents/tableforge/tests/test_targets_voices.py` :
  ```python
  CARDS = """
  rows:
    - { id: lame, name: "Lame", eff: "Gagner 1 Fer.", qty: 2 }
    - { id: emissaire, name: "Émissaire", eff: "+1 influence." }
  """

  PNJ = """
  rows:
    - { id: reine, voice: vieille-reine, replique: "Les couronnes passent." }
    - { id: garde, replique: "Halte." }
  """


  def test_tts_rows_render_jinja_template(tmp_path):
      project = _project(tmp_path, {"data/cards.yaml": CARDS})

      spec = build_kind_spec(project, "narration")

      assert [t.id for t in spec.targets] == ["lame", "emissaire"]  # qty ignoré : 1 audio par id
      lame = spec.targets[0]
      assert lame.text == "Lame. Gagner 1 Fer."
      assert lame.voice_id == "id-narrateur"


  def test_tts_rows_missing_template_field_raises_french_error(tmp_path):
      cards = 'rows:\n  - { id: lame, name: "Lame" }\n'
      project = _project(tmp_path, {"data/cards.yaml": cards})

      with pytest.raises(ValueError, match="champ manquant") as excinfo:
          build_kind_spec(project, "narration")

      assert "lame" in str(excinfo.value)


  def test_tts_voice_field_beats_default_voice(tmp_path):
      project = _project(tmp_path, {"data/pnj.yaml": PNJ})

      spec = build_kind_spec(project, "pnj")

      reine = next(t for t in spec.targets if t.id == "reine")
      assert reine.voice_id == "id-vieille-reine"
      assert reine.text == "Les couronnes passent."


  def test_tts_voice_field_falls_back_to_default_when_row_has_no_voice(tmp_path):
      project = _project(tmp_path, {"data/pnj.yaml": PNJ})

      spec = build_kind_spec(project, "pnj")

      garde = next(t for t in spec.targets if t.id == "garde")
      assert garde.voice_id == "id-narrateur"


  def test_tts_rows_unknown_id_raises(tmp_path):
      project = _project(tmp_path, {"data/cards.yaml": CARDS})

      with pytest.raises(KeyError, match="inconnu"):
          build_kind_spec(project, "narration", ids=["absent"])


  def test_tts_rows_filter_by_ids(tmp_path):
      project = _project(tmp_path, {"data/cards.yaml": CARDS})

      spec = build_kind_spec(project, "narration", ids=["emissaire"])

      assert [t.id for t in spec.targets] == ["emissaire"]
  ```
- [ ] 3.2 Lancer :
  ```bash
  .venv/bin/python -m pytest tests/test_targets_voices.py -v
  ```
  Attendu : les 7 tests de la Task 2 passent, les **6 nouveaux échouent** (le chemin rows n'existe pas : `ValueError … fichier prompts`).
- [ ] 3.3 **Implémentation** — dans `/home/etienne/Documents/tableforge/src/tableforge/targets.py` :
  1. Compléter les imports :
     ```python
     import jinja2

     from .data import load_rows
     ```
  2. Ajouter avant `_tts_targets` :
     ```python
     def _tts_targets_from_rows(project: ProjectConfig, kind_cfg: KindConfig,
                                options: dict, ids: Optional[list[str]]) -> tuple[Target, ...]:
         if kind_cfg.data is None:
             raise ValueError(
                 f"le kind tts '{kind_cfg.name}' utilise generate.text mais n'a pas de data")
         rows = load_rows(kind_cfg.data)
         if ids:
             wanted = set(ids)
             missing = wanted - {row.id for row in rows}
             if missing:
                 raise KeyError(
                     f"kind '{kind_cfg.name}' : id(s) inconnu(s) : {', '.join(sorted(missing))}")
             rows = [row for row in rows if row.id in wanted]
         template = jinja2.Template(str(options["text"]), undefined=jinja2.StrictUndefined)
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
     ```
  3. Remplacer le début de `_tts_targets` :
     ```python
     def _tts_targets(project: ProjectConfig, kind_cfg: KindConfig,
                      options: dict, ids: Optional[list[str]]) -> tuple[Target, ...]:
         if kind_cfg.prompts is not None:
     ```
     par :
     ```python
     def _tts_targets(project: ProjectConfig, kind_cfg: KindConfig,
                      options: dict, ids: Optional[list[str]]) -> tuple[Target, ...]:
         if options.get("text") is not None:
             return _tts_targets_from_rows(project, kind_cfg, options, ids)
         if kind_cfg.prompts is not None:
     ```
- [ ] 3.4 Relancer :
  ```bash
  .venv/bin/python -m pytest tests/test_targets_voices.py -v
  ```
  Attendu : `13 passed`.
- [ ] 3.5 Suite complète : `.venv/bin/python -m pytest -q` → verte.
- [ ] 3.6 Commit :
  ```bash
  git add src/tableforge/targets.py tests/test_targets_voices.py
  git commit -m "feat: cibles TTS depuis les rows (gabarit Jinja, voice_field)"
  ```

---

### Task 4 : `targets.py` — cibles dialogue multi-voix

**Files:**
- Modify : `/home/etienne/Documents/tableforge/src/tableforge/targets.py`
- Test (Modify) : `/home/etienne/Documents/tableforge/tests/test_targets_voices.py`

**Interfaces:**
- Consumes : `DialogueLine(voice_id, text)` (contrat, existe depuis P0/P1), catalogue `entries.<id>.lines: [{voice, text}]`.
- Produces :
  ```python
  def _dialogue_targets(project: ProjectConfig, kind_cfg: KindConfig,
                        options: dict, ids: Optional[list[str]]) -> tuple[Target, ...]
  ```
  `Target.lines` = `tuple[DialogueLine, ...]` (voix résolues) ; `Target.text` = transcription lisible `"nom: texte"` par ligne (affichage studio/dry-run). L'avertissement de longueur (`DIALOGUE_SOFT_LIMIT`) est ajouté en Task 6 côté provider (évite un import `targets → providers`).

**Étapes :**

- [ ] 4.1 **Test rouge** — ajouter à la fin de `/home/etienne/Documents/tableforge/tests/test_targets_voices.py` :
  ```python
  DIALOGUES = """
  entries:
    intro:
      lines:
        - { voice: heraut, text: "Oyez !" }
        - { voice: vieille-reine, text: "Silence." }
  """


  def test_dialogue_targets_resolve_lines_to_voice_ids(tmp_path):
      project = _project(tmp_path, {"prompts/dialogues.yaml": DIALOGUES})

      spec = build_kind_spec(project, "dialogues")

      assert spec.asset == "dialogue"
      intro = spec.targets[0]
      assert [line.voice_id for line in intro.lines] == ["id-heraut", "id-vieille-reine"]
      assert [line.text for line in intro.lines] == ["Oyez !", "Silence."]
      assert intro.text == "heraut: Oyez !\nvieille-reine: Silence."


  def test_dialogue_entry_without_lines_raises(tmp_path):
      catalog = 'entries:\n  intro: { prompt: "pas des lines" }\n'
      project = _project(tmp_path, {"prompts/dialogues.yaml": catalog})

      with pytest.raises(ValueError, match="lines"):
          build_kind_spec(project, "dialogues")


  def test_dialogue_line_missing_voice_raises(tmp_path):
      catalog = 'entries:\n  intro:\n    lines:\n      - { text: "Sans voix." }\n'
      project = _project(tmp_path, {"prompts/dialogues.yaml": catalog})

      with pytest.raises(ValueError, match="requis"):
          build_kind_spec(project, "dialogues")


  def test_dialogue_unknown_voice_lists_declared_voices(tmp_path):
      catalog = 'entries:\n  intro:\n    lines:\n      - { voice: spectre, text: "Bouh." }\n'
      project = _project(tmp_path, {"prompts/dialogues.yaml": catalog})

      with pytest.raises(KeyError, match="voix inconnue") as excinfo:
          build_kind_spec(project, "dialogues")

      assert "heraut" in str(excinfo.value)
  ```
- [ ] 4.2 Lancer :
  ```bash
  .venv/bin/python -m pytest tests/test_targets_voices.py -v
  ```
  Attendu : 13 passent, **4 nouveaux échouent**.
- [ ] 4.3 **Implémentation** — dans `/home/etienne/Documents/tableforge/src/tableforge/targets.py` :
  1. Ajouter à la fin du fichier :
     ```python
     def _dialogue_targets(project: ProjectConfig, kind_cfg: KindConfig,
                           options: dict, ids: Optional[list[str]]) -> tuple[Target, ...]:
         if kind_cfg.prompts is None:
             raise ValueError(f"le kind dialogue '{kind_cfg.name}' n'a pas de fichier prompts")
         cfg = load_catalog(kind_cfg.prompts)
         target_ids = ids or list(catalog_entries(cfg))
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
     ```
  2. Brancher le dispatch de `build_kind_spec` (même point d'insertion qu'en 2.3.3) :
     ```python
     elif kind_cfg.asset == "dialogue":
         targets = _dialogue_targets(project, kind_cfg, options, ids)
         output_format = _catalog_output_format(kind_cfg)
     ```
- [ ] 4.4 Relancer :
  ```bash
  .venv/bin/python -m pytest tests/test_targets_voices.py -v
  ```
  Attendu : `17 passed`.
- [ ] 4.5 Suite complète : `.venv/bin/python -m pytest -q` → verte.
- [ ] 4.6 Commit :
  ```bash
  git add src/tableforge/targets.py tests/test_targets_voices.py
  git commit -m "feat: cibles dialogue multi-voix (lines, voix résolues)"
  ```

---

### Task 5 : `providers/elevenlabs.py` — builders purs TTS et dialogue

**Files:**
- Modify : `/home/etienne/Documents/tableforge/src/tableforge/providers/elevenlabs.py`
- Test (Create) : `/home/etienne/Documents/tableforge/tests/test_elevenlabs_tts.py`

**Interfaces:**
- Consumes : `targets.DialogueLine`.
- Produces (contrat figé) :
  ```python
  DIALOGUE_SOFT_LIMIT = 2000

  def build_tts_request(text: str, *, voice_id: str, model: str, language: Optional[str] = None,
                        seed: Optional[int] = None, output_format: str) -> dict
      # {"path": f"/v1/text-to-speech/{voice_id}",
      #  "json": {"text", "model_id"[, "language_code", "seed"]},
      #  "params": {"output_format"}}

  def build_dialogue_request(lines: Sequence[DialogueLine], *, model: str, output_format: str) -> dict
      # {"path": "/v1/text-to-dialogue",
      #  "json": {"inputs": [{"text", "voice_id"}, ...], "model_id"},
      #  "params": {"output_format"}}
  ```

**Étapes :**

- [ ] 5.1 **Test rouge** — créer `/home/etienne/Documents/tableforge/tests/test_elevenlabs_tts.py` :
  ```python
  import json
  from pathlib import Path

  import httpx
  import respx

  from tableforge.config import load_project
  from tableforge.providers.elevenlabs import (
      DIALOGUE_SOFT_LIMIT,
      ElevenLabsProvider,
      build_dialogue_request,
      build_tts_request,
  )
  from tableforge.targets import DialogueLine, build_kind_spec


  def test_build_tts_request_shapes_path_body_and_params():
      req = build_tts_request("Bonjour.", voice_id="V1", model="eleven_multilingual_v2",
                              language="fr", seed=7, output_format="mp3_44100_128")

      assert req["path"] == "/v1/text-to-speech/V1"
      assert req["json"] == {"text": "Bonjour.", "model_id": "eleven_multilingual_v2",
                             "language_code": "fr", "seed": 7}
      assert req["params"] == {"output_format": "mp3_44100_128"}


  def test_build_tts_request_omits_optional_fields():
      req = build_tts_request("Salut", voice_id="V1", model="m", output_format="mp3_44100_128")

      assert "language_code" not in req["json"]
      assert "seed" not in req["json"]


  def test_build_dialogue_request_maps_lines_in_order():
      lines = (DialogueLine(voice_id="V1", text="Oyez !"),
               DialogueLine(voice_id="V2", text="Silence."))

      req = build_dialogue_request(lines, model="eleven_v3", output_format="mp3_44100_128")

      assert req["path"] == "/v1/text-to-dialogue"
      assert req["json"] == {"inputs": [{"text": "Oyez !", "voice_id": "V1"},
                                        {"text": "Silence.", "voice_id": "V2"}],
                             "model_id": "eleven_v3"}
      assert req["params"] == {"output_format": "mp3_44100_128"}


  def test_dialogue_soft_limit_is_two_thousand_chars():
      assert DIALOGUE_SOFT_LIMIT == 2000
  ```
- [ ] 5.2 Lancer :
  ```bash
  .venv/bin/python -m pytest tests/test_elevenlabs_tts.py -v
  ```
  Attendu : `ImportError` (« cannot import name 'build_tts_request' … ») — **rouge**.
- [ ] 5.3 **Implémentation** — dans `/home/etienne/Documents/tableforge/src/tableforge/providers/elevenlabs.py`, sous les builders music/sfx de P1 (vérifier que `Sequence` est importé depuis `typing` et `DialogueLine` depuis `..targets` — compléter les imports sinon) :
  ```python
  DIALOGUE_SOFT_LIMIT = 2000


  def build_tts_request(text: str, *, voice_id: str, model: str,
                        language: Optional[str] = None, seed: Optional[int] = None,
                        output_format: str) -> dict:
      body: dict = {"text": text, "model_id": model}
      if language:
          body["language_code"] = language
      if seed is not None:
          body["seed"] = seed
      return {"path": f"/v1/text-to-speech/{voice_id}", "json": body,
              "params": {"output_format": output_format}}


  def build_dialogue_request(lines: Sequence[DialogueLine], *, model: str,
                             output_format: str) -> dict:
      inputs = [{"text": line.text, "voice_id": line.voice_id} for line in lines]
      return {"path": "/v1/text-to-dialogue",
              "json": {"inputs": inputs, "model_id": model},
              "params": {"output_format": output_format}}
  ```
- [ ] 5.4 Relancer :
  ```bash
  .venv/bin/python -m pytest tests/test_elevenlabs_tts.py -v
  ```
  Attendu : `4 passed`.
- [ ] 5.5 Suite complète : `.venv/bin/python -m pytest -q` → verte.
- [ ] 5.6 Commit :
  ```bash
  git add src/tableforge/providers/elevenlabs.py tests/test_elevenlabs_tts.py
  git commit -m "feat: builders ElevenLabs TTS et dialogue"
  ```

---

### Task 6 : `ElevenLabsProvider.plan/execute` étendus aux assets tts et dialogue

**Files:**
- Modify : `/home/etienne/Documents/tableforge/src/tableforge/providers/elevenlabs.py`
- Test (Modify) : `/home/etienne/Documents/tableforge/tests/test_elevenlabs_tts.py`

**Interfaces:**
- Consumes : `KindSpec` (`asset`, `kind`, `options`, `targets`, `output_format`), `AssetJob(id, dest, request, payload, notes)`, la boucle `plan()` P1 (qui calcule déjà, par cible, `dest = asset_path(...)` et le format effectif `fmt = spec.output_format or self.output_format`), l'`execute()` générique P1 (POST `base_url + payload["path"]`, `json=payload["json"]`, `params=payload["params"]`, header `xi-api-key`, `raise_with_hint`, octets → `dest`).
- Produces : `plan()` gère `spec.asset in {"tts", "dialogue"}` ; note d'avertissement au-delà de `DIALOGUE_SOFT_LIMIT` caractères cumulés ; helper privé :
  ```python
  def _dialogue_length_notes(lines: Sequence[DialogueLine]) -> tuple[str, ...]
  ```

**Étapes :**

- [ ] 6.1 **Test rouge** — ajouter à la fin de `/home/etienne/Documents/tableforge/tests/test_elevenlabs_tts.py` :
  ```python
  FORGE = """
  project: demo
  providers:
    eleven:
      type: elevenlabs
  voices:
    narrateur: id-narrateur
    heraut: id-heraut
  kinds:
    narration:
      asset: tts
      data: data/cards.yaml
      generate: { with: eleven, voice: narrateur, text: "{{ name }}. {{ eff }}", language: fr }
    dialogues:
      asset: dialogue
      prompts: prompts/dialogues.yaml
      generate: { with: eleven }
  """

  CARDS = """
  rows:
    - { id: lame, name: "Lame", eff: "Gagner 1 Fer." }
  """

  DIALOGUES = """
  entries:
    intro:
      lines:
        - { voice: heraut, text: "Oyez !" }
        - { voice: narrateur, text: "Silence." }
  """


  def _project(tmp_path: Path, dialogues: str = DIALOGUES):
      (tmp_path / "forge.yaml").write_text(FORGE, encoding="utf-8")
      (tmp_path / "data").mkdir()
      (tmp_path / "data" / "cards.yaml").write_text(CARDS, encoding="utf-8")
      (tmp_path / "prompts").mkdir()
      (tmp_path / "prompts" / "dialogues.yaml").write_text(dialogues, encoding="utf-8")
      return load_project(tmp_path)


  def test_plan_tts_builds_jobs_with_audio_dest(tmp_path):
      project = _project(tmp_path)
      spec = build_kind_spec(project, "narration", ids=["lame"])
      provider = ElevenLabsProvider.from_config(project.providers["eleven"])

      jobs = provider.plan(spec)

      assert len(jobs) == 1
      job = jobs[0]
      assert job.id == "lame"
      assert job.dest == project.root / "out" / "audio" / "narration" / "lame.mp3"
      assert job.payload["path"] == "/v1/text-to-speech/id-narrateur"
      assert job.payload["json"]["text"] == "Lame. Gagner 1 Fer."
      assert job.payload["json"]["model_id"] == "eleven_multilingual_v2"
      assert job.payload["json"]["language_code"] == "fr"
      assert job.payload["params"] == {"output_format": "mp3_44100_128"}


  def test_plan_dialogue_builds_jobs_with_default_model(tmp_path):
      project = _project(tmp_path)
      spec = build_kind_spec(project, "dialogues")
      provider = ElevenLabsProvider.from_config(project.providers["eleven"])

      jobs = provider.plan(spec)

      job = jobs[0]
      assert job.dest == project.root / "out" / "audio" / "dialogues" / "intro.mp3"
      assert job.payload["path"] == "/v1/text-to-dialogue"
      assert job.payload["json"]["model_id"] == "eleven_v3"
      assert job.payload["json"]["inputs"][0] == {"text": "Oyez !", "voice_id": "id-heraut"}


  def test_plan_dialogue_flags_text_longer_than_soft_limit(tmp_path):
      long_text = "x" * (DIALOGUE_SOFT_LIMIT + 100)
      dialogues = ('entries:\n  long:\n    lines:\n'
                   f'      - {{ voice: heraut, text: "{long_text}" }}\n')
      project = _project(tmp_path, dialogues=dialogues)
      spec = build_kind_spec(project, "dialogues")
      provider = ElevenLabsProvider.from_config(project.providers["eleven"])

      jobs = provider.plan(spec)

      assert any("2000" in note for note in jobs[0].notes)


  @respx.mock
  def test_execute_tts_posts_key_header_and_writes_file(tmp_path, monkeypatch):
      monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test")
      project = _project(tmp_path)
      spec = build_kind_spec(project, "narration", ids=["lame"])
      provider = ElevenLabsProvider.from_config(project.providers["eleven"])
      job = provider.plan(spec)[0]
      route = respx.post("https://api.elevenlabs.io/v1/text-to-speech/id-narrateur").mock(
          return_value=httpx.Response(200, content=b"MP3DATA"))

      saved = provider.execute(job)

      assert saved == [job.dest]
      assert job.dest.read_bytes() == b"MP3DATA"
      request = route.calls.last.request
      assert request.headers["xi-api-key"] == "sk-test"
      assert request.url.params["output_format"] == "mp3_44100_128"
      body = json.loads(request.content)
      assert body["text"] == "Lame. Gagner 1 Fer."
      assert body["model_id"] == "eleven_multilingual_v2"


  @respx.mock
  def test_execute_dialogue_posts_inputs_and_writes_file(tmp_path, monkeypatch):
      monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test")
      project = _project(tmp_path)
      spec = build_kind_spec(project, "dialogues")
      provider = ElevenLabsProvider.from_config(project.providers["eleven"])
      job = provider.plan(spec)[0]
      route = respx.post("https://api.elevenlabs.io/v1/text-to-dialogue").mock(
          return_value=httpx.Response(200, content=b"AUDIO"))

      saved = provider.execute(job)

      assert saved == [job.dest]
      assert job.dest.read_bytes() == b"AUDIO"
      body = json.loads(route.calls.last.request.content)
      assert body["inputs"] == [{"text": "Oyez !", "voice_id": "id-heraut"},
                                {"text": "Silence.", "voice_id": "id-narrateur"}]
      assert body["model_id"] == "eleven_v3"


  def test_generate_kind_tts_dry_run_goes_through_provider_plan(tmp_path):
      from tableforge.generate import generate_kind

      project = _project(tmp_path)

      results = generate_kind(project, "narration", dry_run=True)

      assert [r.id for r in results] == ["lame"]
      assert results[0].dest is None
      assert results[0].request["path"] == "/v1/text-to-speech/id-narrateur"
  ```
- [ ] 6.2 Lancer :
  ```bash
  .venv/bin/python -m pytest tests/test_elevenlabs_tts.py -v
  ```
  Attendu : les 4 tests builders passent, les **6 nouveaux échouent** (`plan()` P1 ne connaît pas l'asset tts/dialogue).
- [ ] 6.3 **Implémentation** — dans `/home/etienne/Documents/tableforge/src/tableforge/providers/elevenlabs.py` :
  1. Ajouter le helper (sous `build_dialogue_request`) :
     ```python
     def _dialogue_length_notes(lines: Sequence[DialogueLine]) -> tuple[str, ...]:
         total = sum(len(line.text) for line in lines)
         if total <= DIALOGUE_SOFT_LIMIT:
             return ()
         return (f"dialogue long : {total} caractères (> {DIALOGUE_SOFT_LIMIT}) — "
                 "l'API ElevenLabs peut tronquer ou refuser",)
     ```
  2. Dans la boucle `for target in spec.targets:` de `plan()` (P1), qui calcule déjà `fmt = spec.output_format or self.output_format` et `dest = asset_path(...)` puis construit la requête selon `spec.asset`, insérer les deux branches (mêmes conventions que les branches music/sfx P1 : `request` sert à la fois de `request` affichable et de `payload` — aucune donnée secrète ni data-URL dans ces requêtes) :
     ```python
     elif spec.asset == "tts":
         request = build_tts_request(
             target.text,
             voice_id=target.voice_id,
             model=spec.options.get("model") or self.tts_model,
             language=spec.options.get("language"),
             seed=spec.options.get("seed"),
             output_format=fmt,
         )
         notes = target.notes
     elif spec.asset == "dialogue":
         request = build_dialogue_request(
             target.lines,
             model=spec.options.get("model") or self.dialogue_model,
             output_format=fmt,
         )
         notes = target.notes + _dialogue_length_notes(target.lines)
     ```
     puis vérifier que la construction du job de la boucle P1 utilise bien ces variables (forme contractuelle) :
     ```python
     jobs.append(AssetJob(id=target.id, dest=dest, request=request,
                          payload=request, notes=notes))
     ```
  3. `execute()` : **aucune modification attendue** — l'exécuteur générique P1 (POST `payload["path"]`) couvre tts et dialogue. Si les deux tests `execute` échouent encore après 6.3.2, c'est que l'`execute` P1 filtre par asset : y supprimer le filtre, pas dupliquer la logique.
- [ ] 6.4 Relancer :
  ```bash
  .venv/bin/python -m pytest tests/test_elevenlabs_tts.py -v
  ```
  Attendu : `10 passed`.
- [ ] 6.5 Suite complète : `.venv/bin/python -m pytest -q` → verte.
- [ ] 6.6 Commit :
  ```bash
  git add src/tableforge/providers/elevenlabs.py tests/test_elevenlabs_tts.py
  git commit -m "feat: plan/execute ElevenLabs pour les assets tts et dialogue"
  ```

---

### Task 7 : `providers/base.py` — modèles d'options tts et dialogue (`extra="forbid"`)

**Files:**
- Modify : `/home/etienne/Documents/tableforge/src/tableforge/providers/base.py`
- Test (Create) : `/home/etienne/Documents/tableforge/tests/test_options_voices.py`

**Interfaces:**
- Consumes : `options_model(provider_type: str, asset: str) -> Optional[type[BaseModel]]` et son registre P1 (mapping `(provider_type, asset) -> modèle`).
- Produces :
  ```python
  class ElevenLabsTtsOptions(BaseModel):       # extra="forbid"
      voice: Optional[str]; voice_field: Optional[str]; text: Optional[str]
      model: Optional[str]; language: Optional[str]; seed: Optional[int]

  class ElevenLabsDialogueOptions(BaseModel):  # extra="forbid"
      model: Optional[str]
  ```
  enregistrées sous `("elevenlabs", "tts")` et `("elevenlabs", "dialogue")`.

**Étapes :**

- [ ] 7.1 **Test rouge** — créer `/home/etienne/Documents/tableforge/tests/test_options_voices.py` :
  ```python
  import pytest
  from pydantic import ValidationError

  from tableforge.providers.base import options_model


  def test_tts_options_accept_contract_keys():
      model = options_model("elevenlabs", "tts")

      opts = model(voice="narrateur", voice_field="voice", text="{{ name }}",
                   model="eleven_v3", language="fr", seed=3)

      assert opts.voice == "narrateur"
      assert opts.seed == 3


  def test_tts_options_reject_unknown_key():
      model = options_model("elevenlabs", "tts")

      with pytest.raises(ValidationError):
          model(pitch=2)


  def test_dialogue_options_accept_model_only():
      model = options_model("elevenlabs", "dialogue")

      opts = model(model="eleven_v3")

      assert opts.model == "eleven_v3"


  def test_dialogue_options_reject_voice_key():
      model = options_model("elevenlabs", "dialogue")

      with pytest.raises(ValidationError):
          model(voice="narrateur")
  ```
- [ ] 7.2 Lancer :
  ```bash
  .venv/bin/python -m pytest tests/test_options_voices.py -v
  ```
  Attendu : **4 échecs** (`options_model` renvoie `None` pour ces couples → `TypeError: 'NoneType' object is not callable`).
- [ ] 7.3 **Implémentation** — dans `/home/etienne/Documents/tableforge/src/tableforge/providers/base.py` :
  1. À côté des modèles d'options P1 (vérifier les imports `BaseModel, ConfigDict` de pydantic et `Optional` de typing) :
     ```python
     class ElevenLabsTtsOptions(BaseModel):
         model_config = ConfigDict(extra="forbid")
         voice: Optional[str] = None
         voice_field: Optional[str] = None
         text: Optional[str] = None
         model: Optional[str] = None
         language: Optional[str] = None
         seed: Optional[int] = None


     class ElevenLabsDialogueOptions(BaseModel):
         model_config = ConfigDict(extra="forbid")
         model: Optional[str] = None
     ```
  2. Dans le registre consulté par `options_model` (mapping P1 `(provider_type, asset) -> modèle`), ajouter :
     ```python
     ("elevenlabs", "tts"): ElevenLabsTtsOptions,
     ("elevenlabs", "dialogue"): ElevenLabsDialogueOptions,
     ```
- [ ] 7.4 Relancer :
  ```bash
  .venv/bin/python -m pytest tests/test_options_voices.py -v
  ```
  Attendu : `4 passed`.
- [ ] 7.5 Suite complète : `.venv/bin/python -m pytest -q` → verte (les options des fixtures tts de ce plan — voice/voice_field/text/model/language/seed — sont toutes acceptées par le nouveau modèle).
- [ ] 7.6 Commit :
  ```bash
  git add src/tableforge/providers/base.py tests/test_options_voices.py
  git commit -m "feat: options tts et dialogue validées (extra=forbid)"
  ```

---

### Task 8 : `validate_project` — détection des voix inconnues (generate / entries / rows)

**Files:**
- Modify : `/home/etienne/Documents/tableforge/src/tableforge/providers/base.py`
- Test (Create) : `/home/etienne/Documents/tableforge/tests/test_validate_voices.py`

**Interfaces:**
- Consumes : `validate_project(project) -> list[str]` (P1), `targets.build_kind_spec`.
- Produces : `validate_project` liste une issue française par kind tts/dialogue dont la résolution des cibles échoue (voix inconnue où qu'elle soit déclarée — `generate.voice`, entrée de catalogue, row via `voice_field` —, champ Jinja manquant, fichier absent…). Stratégie : envelopper `build_kind_spec` en try/except pour ces kinds — la détection profite de toute la logique de résolution des Tasks 2–4.

**Étapes :**

- [ ] 8.1 **Test rouge** — créer `/home/etienne/Documents/tableforge/tests/test_validate_voices.py` :
  ```python
  from pathlib import Path

  from tableforge.config import load_project
  from tableforge.providers.base import validate_project

  FORGE = """
  project: demo
  providers:
    eleven:
      type: elevenlabs
  voices:
    narrateur: id-narrateur
  kinds:
    regles:
      asset: tts
      prompts: prompts/regles.yaml
      generate: { with: eleven, voice: fantome }
    dialogues:
      asset: dialogue
      prompts: prompts/dialogues.yaml
      generate: { with: eleven }
  """

  REGLES = 'entries:\n  x: { text: "Bonjour." }\n'
  DIALOGUES = 'entries:\n  intro:\n    lines:\n      - { voice: spectre, text: "Bouh." }\n'


  def _project(tmp_path: Path, forge: str):
      (tmp_path / "forge.yaml").write_text(forge, encoding="utf-8")
      (tmp_path / "prompts").mkdir()
      (tmp_path / "prompts" / "regles.yaml").write_text(REGLES, encoding="utf-8")
      (tmp_path / "prompts" / "dialogues.yaml").write_text(DIALOGUES, encoding="utf-8")
      return load_project(tmp_path)


  def test_validate_flags_unknown_voice_in_generate(tmp_path):
      issues = validate_project(_project(tmp_path, FORGE))

      assert any("fantome" in issue for issue in issues)
      assert any("narrateur" in issue for issue in issues)


  def test_validate_flags_unknown_voice_in_dialogue_lines(tmp_path):
      issues = validate_project(_project(tmp_path, FORGE))

      assert any("spectre" in issue for issue in issues)


  def test_validate_accepts_known_voices(tmp_path):
      forge_ok = FORGE.replace("voice: fantome", "voice: narrateur")
      dialogues_ok = DIALOGUES.replace("voice: spectre", "voice: narrateur")
      project = _project(tmp_path, forge_ok)
      (project.root / "prompts" / "dialogues.yaml").write_text(dialogues_ok, encoding="utf-8")

      issues = validate_project(project)

      assert issues == []
  ```
- [ ] 8.2 Lancer :
  ```bash
  .venv/bin/python -m pytest tests/test_validate_voices.py -v
  ```
  Attendu : les 2 premiers tests **échouent** (aucune issue voix) ; le 3e peut déjà passer. **Cas particulier :** si les 3 passent déjà (le `validate_project` P1 enveloppe déjà `build_kind_spec` pour tous les kinds), sauter 8.3, committer les tests seuls en 8.6 avec le message `test: validate_project détecte les voix inconnues`.
- [ ] 8.3 **Implémentation** — dans `/home/etienne/Documents/tableforge/src/tableforge/providers/base.py`, dans `validate_project`, après les contrôles P1 (provider inconnu, capacités, options) et avant le `return`, ajouter (import en tête de fichier : `from ..targets import build_kind_spec` — déjà présent si P1 importe `KindSpec` du même module) :
  ```python
      for name, kind_cfg in project.kinds.items():
          if kind_cfg.asset not in ("tts", "dialogue"):
              continue
          try:
              build_kind_spec(project, name)
          except (KeyError, ValueError, FileNotFoundError) as exc:
              message = exc.args[0] if exc.args else str(exc)
              issues.append(f"kind '{name}' : {message}")
  ```
  (`issues` est la liste accumulée par le `validate_project` P1 — adapter le nom si besoin.)
- [ ] 8.4 Relancer :
  ```bash
  .venv/bin/python -m pytest tests/test_validate_voices.py -v
  ```
  Attendu : `3 passed`.
- [ ] 8.5 Suite complète : `.venv/bin/python -m pytest -q` → verte.
- [ ] 8.6 Commit :
  ```bash
  git add src/tableforge/providers/base.py tests/test_validate_voices.py
  git commit -m "feat: validate_project détecte les voix inconnues (generate, entries, rows)"
  ```

---

### Task 9 : `studio.py` — fiches studio pour tts et dialogue

**Files:**
- Modify : `/home/etienne/Documents/tableforge/src/tableforge/studio.py`
- Test (Create) : `/home/etienne/Documents/tableforge/tests/test_studio_voices.py`

**Interfaces:**
- Consumes : `STUDIO_URLS: dict[tuple[str, str], str]` (P1 : music/sfx), `studio_cards(project, kind, ids=None) -> list[StudioCard]`.
- Produces : deux nouvelles clés dans `STUDIO_URLS` :
  ```python
  ("elevenlabs", "tts"): "https://elevenlabs.io/app/speech-synthesis",
  ("elevenlabs", "dialogue"): "https://elevenlabs.io/app/speech-synthesis",
  ```

**Étapes :**

- [ ] 9.1 **Test rouge** — créer `/home/etienne/Documents/tableforge/tests/test_studio_voices.py` :
  ```python
  from tableforge.config import load_project
  from tableforge.studio import STUDIO_URLS, studio_cards

  FORGE = """
  project: demo
  providers:
    eleven:
      type: elevenlabs
  voices:
    narrateur: id-narrateur
  kinds:
    regles:
      asset: tts
      prompts: prompts/regles.yaml
      generate: { with: eleven, voice: narrateur }
  """

  REGLES = 'entries:\n  mise-en-place: { text: "Placez le plateau." }\n'


  def test_studio_urls_point_to_speech_synthesis():
      assert STUDIO_URLS[("elevenlabs", "tts")] == "https://elevenlabs.io/app/speech-synthesis"
      assert STUDIO_URLS[("elevenlabs", "dialogue")] == "https://elevenlabs.io/app/speech-synthesis"


  def test_studio_cards_for_tts_kind(tmp_path):
      (tmp_path / "forge.yaml").write_text(FORGE, encoding="utf-8")
      (tmp_path / "prompts").mkdir()
      (tmp_path / "prompts" / "regles.yaml").write_text(REGLES, encoding="utf-8")
      project = load_project(tmp_path)

      cards = studio_cards(project, "regles")

      assert len(cards) == 1
      card = cards[0]
      assert card.id == "mise-en-place"
      assert card.kind == "regles"
      assert card.url == "https://elevenlabs.io/app/speech-synthesis"
      assert card.dest.name == "mise-en-place.mp3"
  ```
- [ ] 9.2 Lancer :
  ```bash
  .venv/bin/python -m pytest tests/test_studio_voices.py -v
  ```
  Attendu : `test_studio_urls_point_to_speech_synthesis` **échoue** (`KeyError`) ; le second échoue ou passe selon le repli P1 (`url=None`).
- [ ] 9.3 **Implémentation** — dans `/home/etienne/Documents/tableforge/src/tableforge/studio.py`, ajouter au dict `STUDIO_URLS` :
  ```python
      ("elevenlabs", "tts"): "https://elevenlabs.io/app/speech-synthesis",
      ("elevenlabs", "dialogue"): "https://elevenlabs.io/app/speech-synthesis",
  ```
- [ ] 9.4 Relancer :
  ```bash
  .venv/bin/python -m pytest tests/test_studio_voices.py -v
  ```
  Attendu : `2 passed`.
- [ ] 9.5 Suite complète : `.venv/bin/python -m pytest -q` → verte.
- [ ] 9.6 Commit :
  ```bash
  git add src/tableforge/studio.py tests/test_studio_voices.py
  git commit -m "feat: fiches studio speech-synthesis pour tts et dialogue"
  ```

---

### Task 10 : module `voices.py` + CLI `forge voices list`

**Files:**
- Create : `/home/etienne/Documents/tableforge/src/tableforge/voices.py`
- Modify : `/home/etienne/Documents/tableforge/src/tableforge/cli.py`
- Test (Create) : `/home/etienne/Documents/tableforge/tests/test_voices.py`

**Interfaces:**
- Consumes : `config.ElevenLabsProviderConfig` (`base_url`, `api_key_env`), `config.ProjectConfig` (`providers`, `voices`), `errors.raise_with_hint(response, *, provider_type, asset, kind)`.
- Produces (`src/tableforge/voices.py`) :
  ```python
  DEFAULT_TIMEOUT = 60.0
  def elevenlabs_config(project: ProjectConfig) -> ElevenLabsProviderConfig   # ValueError FR si aucun
  def resolve_api_key(env_name: str) -> str                                   # dotenv + env, RuntimeError FR
  def fetch_voices(cfg: ElevenLabsProviderConfig, api_key: str) -> list[dict] # GET /v1/voices
  def format_voice_lines(voices: list[dict], mapping: dict[str, str]) -> list[str]
  ```
  CLI : sous-application `forge voices` avec la commande `list`.

**Étapes :**

- [ ] 10.1 **Test rouge** — créer `/home/etienne/Documents/tableforge/tests/test_voices.py` :
  ```python
  from pathlib import Path

  import httpx
  import pytest
  import respx
  from typer.testing import CliRunner

  from tableforge.cli import app
  from tableforge.config import ElevenLabsProviderConfig, load_project
  from tableforge.voices import (
      elevenlabs_config,
      fetch_voices,
      format_voice_lines,
      resolve_api_key,
  )

  runner = CliRunner()

  FORGE = """
  project: demo
  providers:
    eleven:
      type: elevenlabs
  voices:
    narrateur: id-abc
  kinds: {}
  """


  def _project(tmp_path: Path, forge: str = FORGE):
      (tmp_path / "forge.yaml").write_text(forge, encoding="utf-8")
      return load_project(tmp_path)


  def test_elevenlabs_config_requires_declared_provider(tmp_path):
      forge = FORGE.replace("type: elevenlabs", "type: manual").replace("eleven:", "outil:")
      project = _project(tmp_path, forge)

      with pytest.raises(ValueError, match="elevenlabs"):
          elevenlabs_config(project)


  def test_resolve_api_key_missing_raises_french_error(monkeypatch):
      monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

      with pytest.raises(RuntimeError, match="ELEVENLABS_API_KEY"):
          resolve_api_key("ELEVENLABS_API_KEY")


  def test_format_voice_lines_marks_mapped_voices():
      voices = [{"voice_id": "id-abc", "name": "George"},
                {"voice_id": "id-zzz", "name": "Alice"}]

      lines = format_voice_lines(voices, {"narrateur": "id-abc"})

      assert lines[0] == "- George  (id-abc)  → mappée : narrateur"
      assert lines[1] == "- Alice  (id-zzz)"


  @respx.mock
  def test_fetch_voices_sends_api_key_header():
      cfg = ElevenLabsProviderConfig(type="elevenlabs")
      route = respx.get("https://api.elevenlabs.io/v1/voices").mock(
          return_value=httpx.Response(200, json={"voices": [{"voice_id": "v", "name": "N"}]}))

      voices = fetch_voices(cfg, "sk-test")

      assert voices == [{"voice_id": "v", "name": "N"}]
      assert route.calls.last.request.headers["xi-api-key"] == "sk-test"


  @respx.mock
  def test_cli_voices_list_shows_mapping(tmp_path, monkeypatch):
      monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test")
      (tmp_path / "forge.yaml").write_text(FORGE, encoding="utf-8")
      respx.get("https://api.elevenlabs.io/v1/voices").mock(
          return_value=httpx.Response(200, json={"voices": [
              {"voice_id": "id-abc", "name": "George"},
              {"voice_id": "id-zzz", "name": "Alice"},
          ]}))

      res = runner.invoke(app, ["voices", "list", "--project", str(tmp_path)])

      assert res.exit_code == 0, res.output
      assert "George" in res.output and "id-abc" in res.output
      assert "mappée : narrateur" in res.output
      alice_line = next(line for line in res.output.splitlines() if "Alice" in line)
      assert "mappée" not in alice_line
  ```
- [ ] 10.2 Lancer :
  ```bash
  .venv/bin/python -m pytest tests/test_voices.py -v
  ```
  Attendu : `ModuleNotFoundError: No module named 'tableforge.voices'` — **rouge**.
- [ ] 10.3 **Implémentation** — créer `/home/etienne/Documents/tableforge/src/tableforge/voices.py` :
  ```python
  """Utilitaires de voix ElevenLabs : bibliothèque du compte + design de voix."""
  from __future__ import annotations

  import os

  import httpx
  from dotenv import load_dotenv

  from .config import ElevenLabsProviderConfig, ProjectConfig
  from .errors import raise_with_hint

  DEFAULT_TIMEOUT = 60.0


  def elevenlabs_config(project: ProjectConfig) -> ElevenLabsProviderConfig:
      for cfg in project.providers.values():
          if cfg.type == "elevenlabs":
              return cfg
      raise ValueError(
          "aucun provider 'elevenlabs' déclaré dans forge.yaml — ajoute par exemple :\n"
          "providers:\n  eleven:\n    type: elevenlabs")


  def resolve_api_key(env_name: str) -> str:
      load_dotenv()
      key = os.environ.get(env_name)
      if not key:
          raise RuntimeError(
              f"{env_name} manquant : copie .env.example vers .env et renseigne ta clé.")
      return key


  def fetch_voices(cfg: ElevenLabsProviderConfig, api_key: str) -> list[dict]:
      response = httpx.get(f"{cfg.base_url}/v1/voices",
                           headers={"xi-api-key": api_key}, timeout=DEFAULT_TIMEOUT)
      if response.status_code >= 400:
          raise_with_hint(response, provider_type="elevenlabs", asset="tts", kind="voices")
      return list(response.json().get("voices", []))


  def format_voice_lines(voices: list[dict], mapping: dict[str, str]) -> list[str]:
      names_by_id = {voice_id: name for name, voice_id in mapping.items()}
      lines: list[str] = []
      for voice in voices:
          voice_id = str(voice.get("voice_id", "?"))
          name = str(voice.get("name", "?"))
          mapped = names_by_id.get(voice_id)
          suffix = f"  → mappée : {mapped}" if mapped else ""
          lines.append(f"- {name}  ({voice_id}){suffix}")
      return lines
  ```
  Puis dans `/home/etienne/Documents/tableforge/src/tableforge/cli.py`, ajouter après la définition de `app` et `ProjectOpt` :
  ```python
  voices_app = typer.Typer(add_completion=False, help="Utilitaires de voix ElevenLabs.")
  app.add_typer(voices_app, name="voices")


  @voices_app.command("list")
  def voices_list(project: Path = ProjectOpt):
      """Liste les voix du compte ElevenLabs et le mapping voices: du projet."""
      from .voices import elevenlabs_config, fetch_voices, format_voice_lines, resolve_api_key
      cfg = load_project(project)
      try:
          eleven = elevenlabs_config(cfg)
      except ValueError as exc:
          raise typer.BadParameter(str(exc)) from exc
      key = resolve_api_key(eleven.api_key_env)
      lines = format_voice_lines(fetch_voices(eleven, key), cfg.voices)
      if not lines:
          typer.echo("aucune voix sur ce compte")
          return
      for line in lines:
          typer.echo(line)
  ```
- [ ] 10.4 Relancer :
  ```bash
  .venv/bin/python -m pytest tests/test_voices.py -v
  ```
  Attendu : `5 passed`.
- [ ] 10.5 Suite complète : `.venv/bin/python -m pytest -q` → verte.
- [ ] 10.6 Commit :
  ```bash
  git add src/tableforge/voices.py src/tableforge/cli.py tests/test_voices.py
  git commit -m "feat: forge voices list (bibliothèque ElevenLabs + mapping voices:)"
  ```

---

### Task 11 : starter — exemple narration commenté + catalogue `regles-audio.yaml`

**Files:**
- Modify : `/home/etienne/Documents/tableforge/src/tableforge/templates/starter/forge.yaml`
- Create : `/home/etienne/Documents/tableforge/src/tableforge/templates/starter/prompts/regles-audio.yaml`
- Test (Modify) : `/home/etienne/Documents/tableforge/tests/test_scaffold.py`

**Interfaces:**
- Consumes : `scaffold.init_project(name, dest)` (copie du starter, inchangé).
- Produces : starter documentant les kinds vocaux (bloc commenté, aucun kind actif ajouté — `forge init` reste 100 % image par défaut).

**Étapes :**

- [ ] 11.1 **Test rouge** — ajouter à la fin de `/home/etienne/Documents/tableforge/tests/test_scaffold.py` :
  ```python
  def test_init_ships_commented_tts_examples(tmp_path):
      target = init_project("mon-jeu", tmp_path)

      forge = (target / "forge.yaml").read_text(encoding="utf-8")
      assert "# narration:" in forge
      assert "asset: tts" in forge
      assert "voices:" in forge
      catalog = (target / "prompts" / "regles-audio.yaml").read_text(encoding="utf-8")
      assert "entries:" in catalog
      assert "text:" in catalog
  ```
- [ ] 11.2 Lancer :
  ```bash
  .venv/bin/python -m pytest tests/test_scaffold.py -v
  ```
  Attendu : le nouveau test **échoue** (`AssertionError` sur `# narration:`), les tests P0/P1 passent.
- [ ] 11.3 **Implémentation** :
  1. Créer `/home/etienne/Documents/tableforge/src/tableforge/templates/starter/prompts/regles-audio.yaml` :
     ```yaml
     # Catalogue TTS « libre » (kind sans data) : chaque entrée porte un champ text.
     # Utilisé par le kind d'exemple regles-audio (commenté dans forge.yaml).
     entries:
       mise-en-place: { text: "Placez le plateau au centre. Chaque joueur prend cinq cartes." }
       rappel-regle: { text: "Une seule carte peut être jouée par tour." }
     ```
  2. Ajouter à la **fin** de `/home/etienne/Documents/tableforge/src/tableforge/templates/starter/forge.yaml` (après le dernier kind ; conserver tel quel tout le contenu P1 existant) :
     ```yaml

     # --- Voix (ElevenLabs) : exemples à décommenter -----------------------------
     # 1. Déclare un provider elevenlabs (clé : ELEVENLABS_API_KEY dans .env) :
     # providers:
     #   eleven:
     #     type: elevenlabs
     # 2. Déclare tes voix (noms humains -> voice_id, cf. `forge voices list`) :
     # voices:
     #   narrateur: JBFqnCBsd6RMkjVDRZzb
     # 3. Ajoute des kinds vocaux :
     #   narration:                  # lit chaque carte (gabarit Jinja sur les rows)
     #     asset: tts
     #     data: data/cards.yaml
     #     generate:
     #       with: eleven
     #       voice: narrateur
     #       text: "{{ name }}. {{ eff }}"
     #       language: fr
     #   regles-audio:               # catalogue libre : voir prompts/regles-audio.yaml
     #     asset: tts
     #     prompts: prompts/regles-audio.yaml
     #     generate: { with: eleven, voice: narrateur, language: fr }
     ```
- [ ] 11.4 Relancer :
  ```bash
  .venv/bin/python -m pytest tests/test_scaffold.py -v
  ```
  Attendu : tous verts (dont `test_init_ships_commented_tts_examples`).
- [ ] 11.5 Suite complète : `.venv/bin/python -m pytest -q` → verte (le starter reste chargeable : le bloc ajouté est intégralement commenté).
- [ ] 11.6 Commit :
  ```bash
  git add src/tableforge/templates/starter/forge.yaml \
          src/tableforge/templates/starter/prompts/regles-audio.yaml tests/test_scaffold.py
  git commit -m "feat: starter — exemples TTS commentés et catalogue regles-audio"
  ```

---

### Task 12 : `examples/couronnes` — narration, voix-pnj, dialogues

**Files:**
- Modify : `/home/etienne/Documents/tableforge/examples/couronnes/forge.yaml`
- Create : `/home/etienne/Documents/tableforge/examples/couronnes/data/pnj.yaml`
- Create : `/home/etienne/Documents/tableforge/examples/couronnes/prompts/dialogues.yaml`
- Test (Modify) : `/home/etienne/Documents/tableforge/tests/test_example_couronnes.py`

**Interfaces:**
- Consumes : `data/cards.yaml` de l'exemple (rows avec champs `name` et `eff` — vérifiés), le `forge.yaml` post-P1 (format `providers:` avec `ark` + `eleven`).
- Produces : map `voices:` + 3 kinds vocaux dans l'exemple, testés en **dry-run pur** (aucun réseau). Les voice_id sont les voix premade publiques ElevenLabs reprises de la spec (George, Sarah, Josh).

**Étapes :**

- [ ] 12.1 **Test rouge** — ajouter à la fin de `/home/etienne/Documents/tableforge/tests/test_example_couronnes.py` :
  ```python
  def test_example_narration_reads_name_and_eff():
      from tableforge.targets import build_kind_spec

      cfg = load_project(EXAMPLE)

      spec = build_kind_spec(cfg, "narration", ids=["lame"])

      assert spec.asset == "tts"
      target = spec.targets[0]
      assert target.text == "Lame. Gagner 1 Fer."
      assert target.voice_id == cfg.voices["narrateur"]


  def test_example_pnj_rows_pick_their_own_voice():
      from tableforge.targets import build_kind_spec

      cfg = load_project(EXAMPLE)

      spec = build_kind_spec(cfg, "voix-pnj")

      reine = next(t for t in spec.targets if t.id == "reine")
      assert reine.voice_id == cfg.voices["vieille-reine"]
      assert "cendres" in reine.text


  def test_example_dialogues_resolve_all_lines():
      from tableforge.targets import build_kind_spec

      cfg = load_project(EXAMPLE)

      spec = build_kind_spec(cfg, "dialogues")

      intro = next(t for t in spec.targets if t.id == "intro")
      assert [line.voice_id for line in intro.lines] == [
          cfg.voices["heraut"], cfg.voices["vieille-reine"]]


  def test_example_project_validates_clean():
      from tableforge.providers.base import validate_project

      cfg = load_project(EXAMPLE)

      assert validate_project(cfg) == []
  ```
- [ ] 12.2 Lancer :
  ```bash
  .venv/bin/python -m pytest tests/test_example_couronnes.py -v
  ```
  Attendu : les 3 tests P0/P1 passent, les **4 nouveaux échouent** (`KeyError: kind inconnu : 'narration'`).
- [ ] 12.3 **Implémentation** :
  1. Dans `/home/etienne/Documents/tableforge/examples/couronnes/forge.yaml`, insérer entre le bloc `providers:` (état post-P1) et `defaults:` :
     ```yaml
     voices:                       # noms humains -> voice_id ElevenLabs (voix premade publiques)
       narrateur:     JBFqnCBsd6RMkjVDRZzb
       vieille-reine: EXAVITQu4vr4xnSDxMaL
       heraut:        TxGEqnHWrfWFTfGW9XjX
     ```
  2. Ajouter à la fin du bloc `kinds:` du même fichier (même indentation que `cards:` ; `eleven` est le nom du provider elevenlabs déclaré en P1 — adapter le `with:` si P1 a retenu un autre nom) :
     ```yaml
       narration:                  # lit chaque carte : gabarit Jinja sur les rows de cards
         asset: tts
         data: data/cards.yaml
         generate:
           with: eleven
           voice: narrateur
           text: "{{ name }}. {{ eff }}"
           language: fr
       voix-pnj:                   # une voix par personnage via voice_field
         asset: tts
         data: data/pnj.yaml
         generate: { with: eleven, text: "{{ replique }}", voice_field: voice }
       dialogues:                  # scènes multi-voix
         asset: dialogue
         prompts: prompts/dialogues.yaml
         generate: { with: eleven }
     ```
  3. Créer `/home/etienne/Documents/tableforge/examples/couronnes/data/pnj.yaml` :
     ```yaml
     rows:
       - { id: reine, voice: vieille-reine, replique: "Les couronnes passent, les cendres restent." }
       - { id: heraut, voice: heraut, replique: "Oyez ! Le conseil des guildes est ouvert." }
     ```
  4. Créer `/home/etienne/Documents/tableforge/examples/couronnes/prompts/dialogues.yaml` :
     ```yaml
     entries:
       intro:
         lines:
           - { voice: heraut, text: "La reine se meurt. Le trône appelle un nouveau sang." }
           - { voice: vieille-reine, text: "Que les prétendants s'avancent, et que les cendres jugent." }
       fin-de-partie:
         lines:
           - { voice: heraut, text: "Le décompte est fait. Une seule couronne demeure." }
     ```
- [ ] 12.4 Relancer :
  ```bash
  .venv/bin/python -m pytest tests/test_example_couronnes.py -v
  ```
  Attendu : `7 passed`.
- [ ] 12.5 Vérification manuelle (dry-run pur, aucune clé requise) :
  ```bash
  .venv/bin/python -m tableforge generate narration -p examples/couronnes --dry-run --id lame
  .venv/bin/python -m tableforge generate dialogues -p examples/couronnes --dry-run
  .venv/bin/python -m tableforge studio narration -p examples/couronnes --id lame
  ```
  Attendu : chaque commande sort en code 0 ; le dry-run affiche `lame: (dry-run)` (et la requête résumée selon l'affichage P1) ; la fiche studio affiche le texte « Lame. Gagner 1 Fer. » et l'URL speech-synthesis.
- [ ] 12.6 Suite complète : `.venv/bin/python -m pytest -q` → verte.
- [ ] 12.7 Commit :
  ```bash
  git add examples/couronnes/forge.yaml examples/couronnes/data/pnj.yaml \
          examples/couronnes/prompts/dialogues.yaml tests/test_example_couronnes.py
  git commit -m "feat: exemple couronnes — narration, voix-pnj et dialogues"
  ```

---

### Task 13 : `forge voices design` (LIGNE DE COUPE — coupable sans impact sur les Tasks 1–12)

> Ligne de coupe n°1 de la spec : si le budget est dépassé, **couper cette tâche entière**. Rien d'autre dans P2 n'en dépend.

**Files:**
- Modify : `/home/etienne/Documents/tableforge/src/tableforge/voices.py`
- Modify : `/home/etienne/Documents/tableforge/src/tableforge/cli.py`
- Test (Modify) : `/home/etienne/Documents/tableforge/tests/test_voices.py`

**Interfaces:**
- Consumes : `elevenlabs_config`, `resolve_api_key`, `raise_with_hint` (Task 10).
- Produces :
  ```python
  def design_previews(cfg: ElevenLabsProviderConfig, api_key: str, description: str) -> list[dict]
      # POST /v1/text-to-voice/design {"voice_description", "auto_generate_text": True}
      # -> response["previews"] : [{"generated_voice_id", ...}]
  def save_voice(cfg: ElevenLabsProviderConfig, api_key: str, *, name: str, description: str,
                 generated_voice_id: str) -> str
      # POST /v1/text-to-voice {"voice_name", "voice_description", "generated_voice_id"}
      # -> response["voice_id"]
  ```
  CLI : `forge voices design "<desc>" [--name NOM] [--save]` — sans `--save`, liste les `generated_voice_id` des aperçus ; avec `--save --name NOM`, enregistre le **premier** aperçu et affiche le `voice_id` à coller dans `forge.yaml`. Les corps/réponses exacts de l'API voice-design sont à re-vérifier sur https://elevenlabs.io/docs au moment de l'implémentation (voir Open Questions du plan).

**Étapes :**

- [ ] 13.1 **Test rouge** — ajouter à la fin de `/home/etienne/Documents/tableforge/tests/test_voices.py` :
  ```python
  import json


  @respx.mock
  def test_design_previews_posts_description():
      from tableforge.voices import design_previews

      cfg = ElevenLabsProviderConfig(type="elevenlabs")
      route = respx.post("https://api.elevenlabs.io/v1/text-to-voice/design").mock(
          return_value=httpx.Response(200, json={"previews": [
              {"generated_voice_id": "gen-1"}, {"generated_voice_id": "gen-2"}]}))

      previews = design_previews(cfg, "sk-test", "vieille reine rauque")

      assert [p["generated_voice_id"] for p in previews] == ["gen-1", "gen-2"]
      request = route.calls.last.request
      assert request.headers["xi-api-key"] == "sk-test"
      body = json.loads(request.content)
      assert body["voice_description"] == "vieille reine rauque"


  @respx.mock
  def test_save_voice_returns_voice_id():
      from tableforge.voices import save_voice

      cfg = ElevenLabsProviderConfig(type="elevenlabs")
      route = respx.post("https://api.elevenlabs.io/v1/text-to-voice").mock(
          return_value=httpx.Response(200, json={"voice_id": "id-new"}))

      voice_id = save_voice(cfg, "sk-test", name="vieille-reine",
                            description="vieille reine rauque", generated_voice_id="gen-1")

      assert voice_id == "id-new"
      body = json.loads(route.calls.last.request.content)
      assert body == {"voice_name": "vieille-reine",
                      "voice_description": "vieille reine rauque",
                      "generated_voice_id": "gen-1"}


  @respx.mock
  def test_cli_voices_design_without_save_lists_previews(tmp_path, monkeypatch):
      monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test")
      (tmp_path / "forge.yaml").write_text(FORGE, encoding="utf-8")
      respx.post("https://api.elevenlabs.io/v1/text-to-voice/design").mock(
          return_value=httpx.Response(200, json={"previews": [
              {"generated_voice_id": "gen-1"}]}))

      res = runner.invoke(app, ["voices", "design", "vieille reine rauque",
                                "--project", str(tmp_path)])

      assert res.exit_code == 0, res.output
      assert "gen-1" in res.output
      assert "--save" in res.output


  @respx.mock
  def test_cli_voices_design_save_prints_yaml_snippet(tmp_path, monkeypatch):
      monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test")
      (tmp_path / "forge.yaml").write_text(FORGE, encoding="utf-8")
      respx.post("https://api.elevenlabs.io/v1/text-to-voice/design").mock(
          return_value=httpx.Response(200, json={"previews": [
              {"generated_voice_id": "gen-1"}]}))
      respx.post("https://api.elevenlabs.io/v1/text-to-voice").mock(
          return_value=httpx.Response(200, json={"voice_id": "id-new"}))

      res = runner.invoke(app, ["voices", "design", "vieille reine rauque",
                                "--name", "vieille-reine", "--save",
                                "--project", str(tmp_path)])

      assert res.exit_code == 0, res.output
      assert "id-new" in res.output
      assert "vieille-reine: id-new" in res.output


  def test_cli_voices_design_save_requires_name(tmp_path, monkeypatch):
      monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test")
      (tmp_path / "forge.yaml").write_text(FORGE, encoding="utf-8")

      res = runner.invoke(app, ["voices", "design", "desc", "--save",
                                "--project", str(tmp_path)])

      assert res.exit_code != 0
  ```
- [ ] 13.2 Lancer :
  ```bash
  .venv/bin/python -m pytest tests/test_voices.py -v
  ```
  Attendu : les 5 tests de la Task 10 passent, les **5 nouveaux échouent** (`ImportError`/commande inconnue).
- [ ] 13.3 **Implémentation** :
  1. Ajouter à la fin de `/home/etienne/Documents/tableforge/src/tableforge/voices.py` :
     ```python
     def design_previews(cfg: ElevenLabsProviderConfig, api_key: str,
                         description: str) -> list[dict]:
         response = httpx.post(f"{cfg.base_url}/v1/text-to-voice/design",
                               headers={"xi-api-key": api_key},
                               json={"voice_description": description,
                                     "auto_generate_text": True},
                               timeout=DEFAULT_TIMEOUT)
         if response.status_code >= 400:
             raise_with_hint(response, provider_type="elevenlabs", asset="tts", kind="voices")
         return list(response.json().get("previews", []))


     def save_voice(cfg: ElevenLabsProviderConfig, api_key: str, *, name: str,
                    description: str, generated_voice_id: str) -> str:
         response = httpx.post(f"{cfg.base_url}/v1/text-to-voice",
                               headers={"xi-api-key": api_key},
                               json={"voice_name": name,
                                     "voice_description": description,
                                     "generated_voice_id": generated_voice_id},
                               timeout=DEFAULT_TIMEOUT)
         if response.status_code >= 400:
             raise_with_hint(response, provider_type="elevenlabs", asset="tts", kind="voices")
         return str(response.json()["voice_id"])
     ```
  2. Ajouter à `/home/etienne/Documents/tableforge/src/tableforge/cli.py`, sous `voices_list` :
     ```python
     @voices_app.command("design")
     def voices_design(description: str,
                       name: Optional[str] = typer.Option(None, "--name",
                                                          help="Nom de la voix à enregistrer."),
                       save: bool = typer.Option(False, "--save",
                                                 help="Enregistrer le premier aperçu."),
                       project: Path = ProjectOpt):
         """Génère des aperçus de voix depuis une description ; --save enregistre la première."""
         from .voices import design_previews, elevenlabs_config, resolve_api_key, save_voice
         cfg = load_project(project)
         try:
             eleven = elevenlabs_config(cfg)
         except ValueError as exc:
             raise typer.BadParameter(str(exc)) from exc
         if save and not name:
             raise typer.BadParameter("--save exige --name NOM")
         key = resolve_api_key(eleven.api_key_env)
         previews = design_previews(eleven, key, description)
         if not previews:
             typer.echo("aucun aperçu renvoyé par l'API")
             raise typer.Exit(1)
         for preview in previews:
             typer.echo(f"- aperçu : {preview.get('generated_voice_id')}")
         if not save:
             typer.echo("relance avec --save --name NOM pour enregistrer la première voix")
             return
         voice_id = save_voice(eleven, key, name=name, description=description,
                               generated_voice_id=str(previews[0]["generated_voice_id"]))
         typer.echo(f"voix enregistrée : {voice_id}")
         typer.echo("à coller dans forge.yaml :")
         typer.echo("voices:")
         typer.echo(f"  {name}: {voice_id}")
     ```
- [ ] 13.4 Relancer :
  ```bash
  .venv/bin/python -m pytest tests/test_voices.py -v
  ```
  Attendu : `10 passed`.
- [ ] 13.5 Suite complète : `.venv/bin/python -m pytest -q` → verte.
- [ ] 13.6 Commit :
  ```bash
  git add src/tableforge/voices.py src/tableforge/cli.py tests/test_voices.py
  git commit -m "feat: forge voices design (aperçus et enregistrement de voix)"
  ```

---

### Task 14 : Vérification finale de la phase

**Files:** aucun (vérification ; corrections éventuelles = micro-cycles TDD supplémentaires).

**Interfaces:** l'ensemble des livrables P2.

**Étapes :**

- [ ] 14.1 Suite complète :
  ```bash
  .venv/bin/python -m pytest -q
  ```
  Attendu : tout vert, 0 failed.
- [ ] 14.2 Couverture :
  ```bash
  .venv/bin/python -m pytest -q --cov=tableforge --cov-report=term-missing
  ```
  Attendu : total ≥ 80 % (objectif ≈ 96 % ; `render.py`/`cli.py`/`__main__.py` exclus par `pyproject.toml`). Si `targets.py`, `voices.py` ou `providers/elevenlabs.py` ont des lignes non couvertes significatives, ajouter un test ciblé (cycle rouge→vert) avant de conclure.
- [ ] 14.3 Vérifications CLI de bout en bout (dry-run pur, aucune clé nécessaire) :
  ```bash
  .venv/bin/python -m tableforge list -p examples/couronnes
  .venv/bin/python -m tableforge generate narration -p examples/couronnes --dry-run --id lame
  .venv/bin/python -m tableforge generate dialogues -p examples/couronnes --dry-run
  .venv/bin/python -m tableforge studio dialogues -p examples/couronnes --id intro
  .venv/bin/python -m tableforge render narration -p examples/couronnes ; echo "exit=$?"
  ```
  Attendu : `list` affiche les kinds vocaux (`narration`, `voix-pnj`, `dialogues`) avec leur asset/provider et **aucune issue** ; les deux `generate --dry-run` sortent en code 0 avec une ligne par id ; `studio` affiche la fiche intro avec l'URL speech-synthesis ; `render narration` **échoue en code ≠ 0** avec le refus pédagogique P1 (« le kind 'narration' est audio (tts) — rien à rendre… »), d'où le `echo "exit=$?"` qui doit afficher une valeur non nulle.
- [ ] 14.4 Journal git propre :
  ```bash
  git status --short && git log --oneline -12
  ```
  Attendu : arbre propre ; un commit conventionnel par tâche livrée (Tasks 2–13, plus Task 1 si respx a été ajouté).
- [ ] 14.5 Si tout est vert : la phase P2 est livrée. Sinon, corriger en micro-cycles TDD (test rouge → fix → vert → `fix:` commit) avant de clore.
