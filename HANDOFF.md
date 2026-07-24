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

- **Moteur multimodal** : `asset: image | music | sfx | tts | dialogue | video` par kind
  (`config.py`, `AssetType`).
- **Providers nommés** (`providers:` dans forge.yaml, map nommée + union discriminée par
  `type:`) : `seedream` (BytePlus Ark, images), `elevenlabs` (music / sfx+loop / tts /
  dialogue), `higgsfield` (images Soul/Seedream + vidéo i2v/t2v, API async), `manual`
  (réservé, outils sans API → `forge studio`).
- **Contrat plan/execute** : `plan()` pur et sans clé (dry-run, `forge studio`, linter) ;
  `execute()` = seul point réseau/clé. Un seul orchestrateur `generate_kind` (`generate.py`)
  pour toutes les modalités.
- **CLI** : `forge init | list (linter) | generate | studio | voices | render | board |
  sheet | all` (`all` sans kind : ordre fixe **image → audio → vidéo**, affiché avant
  exécution ; generate seulement si la clé du provider est présente).
- **Rétro-compat v1** : bloc `provider:` anonyme (singulier) normalisé en
  `providers.default` (type `seedream` implicite sur ce seul chemin) ; byte-équivalence
  des requêtes v1 verrouillée par test (`tests/*byte*`) ; shims datés dans `config.py`
  (`has_legacy`/`is_legacy`) — **revoir 2026-10**.
- **Exemple `examples/couronnes/`** (11 kinds, `forge list` = 0 issue) : `cards` + `board`
  (seedream), `musiques` / `nappes` / `sfx` (catalogues audio ElevenLabs), `narration` /
  `voix-pnj` (TTS, une voix fixe vs `voice_field`), `dialogues` (multi-voix), `cards-soul`
  (Higgsfield Soul, **art brut** sans template), `cartes-animees` (i2v `from: cards`),
  `teaser` (t2v). Intégration testée en **dry-run pur** (aucun appel réseau réel).
- **Tests** : pytest, 297 tests verts, couverture ~99 % sur la logique pure ; réseau mocké
  **respx** partout où `httpx` est utilisé.

## 3. Reprendre — commandes essentielles

> ⚠️ Pas de `python`/`pip` système. **Toujours** `.venv/bin/python` (venv via **uv**).

```bash
cd /home/etienne/Documents/tableforge
.venv/bin/python -m pytest -q                                        # tout vert
.venv/bin/python -m tableforge list -p examples/couronnes             # linter + état (11 kinds)
.venv/bin/python -m tableforge generate cards -p examples/couronnes --dry-run
.venv/bin/python -m tableforge generate musiques -p examples/couronnes --dry-run
.venv/bin/python -m tableforge generate cards-soul -p examples/couronnes --dry-run
.venv/bin/python -m tableforge studio musiques -p examples/couronnes  # fiches copier-coller
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
  (`.env` gitignored) **dans `execute()` uniquement**. Dry-run/studio/erreurs n'affichent
  que des **noms** de variables, jamais la valeur.
- **ElevenLabs** (`providers/elevenlabs.py`) : header `xi-api-key` ; `/v1/music` exige un
  **plan payant** → un 402 renvoie l'astuce « utilise `forge studio <kind>` »
  (`errors.py:raise_with_hint`). `loop` (nappes) exige `eleven_text_to_sound_v2`. Dialogue
  > 2 000 caractères (`DIALOGUE_SOFT_LIMIT`) : avertissement, pas d'erreur. Bornes
  clampées et **visibles en dry-run** : musique 3 000–600 000 ms, SFX 0,5–30 s
  (`catalog.py:clamp_music_length_ms` / `clamp_sfx_duration_s`).
- **Higgsfield** (`providers/higgsfield.py`) : API **async** — `POST /{model_slug}` →
  `request_id`, puis `GET /requests/{id}/status` (`queued|in_progress|completed|failed|
  nsfw`), transitions affichées par id, sleep injectable dans les tests. `failed`/`nsfw` =
  **requête auto-remboursée**. Deux clés : `HIGGSFIELD_API_KEY` + `HIGGSFIELD_API_SECRET`
  (header `Authorization: Key {key}:{secret}`). **Schémas API partiellement vérifiés**
  (NB en tête de `higgsfield.py`, doc consultée le 2026-07-24) : `request_id` et la forme
  `completed` (`{"images":[{"url":...}]}` / `{"video":{"url":...}}`) sont **confirmés** ;
  le champ image d'entrée en i2v (`"image"`) et le champ `"duration"` sont des
  **hypothèses non confirmées** (non utilisés par ce module) ; le nom du champ de
  références i2i (`IMAGE_REF_FIELD = "image_refs"`) porte la même réserve (note P3b dans
  le module). Les **slugs de modèles évoluent** — vérifier la galerie
  docs.higgsfield.ai avant toute exécution réelle.
- **Seedream / Ark** : `ARK_API_KEY` liée à sa région (`ap-southeast`) ; modèle
  `seedream-5-0-260128`. Chemin SDK OpenAI en `pragma: no cover` (smoke).
- **Rendu** : Playwright/Chromium ; `combined_css` (tokens préfixés) ; le
  `capture_selector` du kind doit matcher la racine du gabarit. Un kind image **sans**
  `template:` est légal (« art brut » — ex. `cards-soul`) : `generate` seulement,
  `render` refuse avec un message pédagogique (« est de l'art brut (pas de template) —
  rien à rendre »).
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
  voices.py       `forge voices list|design` (mapping voice_id, aperçus ElevenLabs)
  paths.py        out/art|audio|video|render|sheet + extension_for (mp3/ogg/wav/mp4/png)
  render.py       Jinja2 + Playwright HTML->PNG
  sheet.py        planche PDF (plan_sheet pur + build_sheet_pdf)
  scaffold.py     forge init (starter multimodal commenté + .env.example)
  cli.py          `forge` (typer)
  templates/starter/   projet vierge bundlé
examples/couronnes/    exemple complet multimodal (11 kinds)
tests/                 pytest (respx pour tout httpx)
docs/superpowers/      spec + plans (P0 -> P3b + docs)
```

## 6. Suites possibles

- `forge voices design` complet si coupé (ligne de coupe n°1), presets Soul, teaser t2v.
- **Vérifier réellement** les hypothèses Higgsfield non confirmées (champ `image` i2v,
  `duration`, `IMAGE_REF_FIELD`/`image_refs`) contre un vrai run une fois la clé
  disponible ; mettre à jour le NB de `higgsfield.py` en conséquence.
- **Supprimer les shims v1** (`ProjectConfig.provider`, ré-exports
  `providers/__init__.py`) quand examples et starter n'utilisent plus le format v1 —
  **revoir 2026-10**.
- Lecture/streaming des médias : hors périmètre (tableforge produit des fichiers).

## 7. Vérifier que tout va bien

```bash
.venv/bin/python -m pytest -q                                   # tous verts (297)
.venv/bin/python -m tableforge list -p examples/couronnes       # tous les kinds, 0 issue
.venv/bin/python -m tableforge render cards -p examples/couronnes --id couronne-maudite
```
Comparer le PNG rendu à `examples/couronnes/out/render/cards/`.

## 8. Pour aller plus loin

- Spec : `docs/superpowers/specs/2026-06-29-tableforge-design.md` (socle v1) et
  `docs/superpowers/specs/2026-07-24-multimodal-providers-design.md` (design multimodal :
  providers nommés, asset/plan/execute, catalogues, voix, vidéo).
- Plans exécutés : `docs/superpowers/plans/2026-06-29-tableforge.md` puis
  `2026-07-24-multimodal-p0-refactor.md` (socle providers/asset), `-p1-audio.md`
  (musique/sfx/tts), `-p2-voices.md` (dialogues + voix), `-p3a-video.md` (Higgsfield
  vidéo), `-p3b-images-docs.md` (Soul/i2i + cette passe de docs).
- Journal de phase détaillé (tâche par tâche, revues, watch-items reportés) :
  `.superpowers/sdd/progress.md`.
