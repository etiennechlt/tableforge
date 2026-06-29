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
- Couverture **≥ 80 %** sur la logique pure (objectif actuel : 96 %). Le rendu navigateur
  (`render.py`) et la CLI sont exclus de la couverture (smoke-testés).
- **Aucun secret en dur** : la clé IA est lue via `provider.api_key_env`, jamais committée.
- Modules courts, données immuables, erreurs explicites (cf. style global).
- Commits conventionnels (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).

## Cheatsheet

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m tableforge list -p examples/couronnes
.venv/bin/python -m tableforge generate cards -p examples/couronnes --dry-run
.venv/bin/python -m tableforge render cards   -p examples/couronnes --id lame
.venv/bin/python -m tableforge sheet cards    -p examples/couronnes
```

## Où est quoi

- Moteur : `src/tableforge/*.py` (voir le tableau dans `HANDOFF.md`).
- Starter cloné par `forge init` : `src/tableforge/templates/starter/`.
- Exemple complet : `examples/couronnes/`.
- Spec & plan : `docs/superpowers/specs/` et `docs/superpowers/plans/`.

## Ajouter un kind à un projet

1. Déclarer le kind dans `forge.yaml` (data, prompts, template, render_size, sheet?).
2. Créer `data/<kind>.yaml` (rows avec `id`), `prompts/<kind>.yaml`, `templates/<kind>/`.
3. `forge generate <kind> --dry-run` puis `forge render <kind>`.
