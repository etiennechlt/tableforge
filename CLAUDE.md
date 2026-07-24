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
