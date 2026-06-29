# HANDOFF — tableforge

> Point d'entrée pour **reprendre ce projet dans une session Claude Code neuve**.
> Lis ce fichier, puis `README.md`, puis `docs/superpowers/` (spec + plan).

## 1. Qu'est-ce que c'est

`tableforge` : un **package Python générique** qui génère le matériel d'un jeu de table
(cartes, plateaux/maps, designs, art IA) à partir d'un **dossier projet déclaratif** —
YAML (config + données + prompts) + gabarits HTML/CSS + images de référence. Aucune logique
de jeu. Pensé pour qu'un ami configure son propre jeu sans toucher au code.

Extrait/généralisé de *Couronnes & Cendres* (`/home/etienne/Documents/couronnes-cendres`),
livré ici comme exemple complet dans `examples/couronnes/`.

## 2. État actuel (✅ fait)

- **Moteur générique complet** : `config` (forge.yaml/pydantic), `data` (rows), `prompts`
  (assemblage + refs i2i), `providers` (Seedream configurable, compat OpenAI-images),
  `generate` (orchestration), `render` (HTML→PNG/Playwright), `sheet` (planche PDF), `scaffold`
  (`forge init`), `cli` (`forge`).
- **CLI** : `forge init | list | generate | render | sheet | board | all`.
- **Starter bundlé** (`src/tableforge/templates/starter/`) cloné par `forge init`.
- **Exemple `examples/couronnes/`** : 18 cartes + plateau ; **rendu vérifié** end-to-end
  (cartes 2232×3117, plateau 2480×3508).
- **Tests** : `pytest` — **96 % de couverture** sur la logique. Playwright/réseau smoke-testés.

## 3. Reprendre — commandes essentielles

> ⚠️ Pas de `python`/`pip` système. **Toujours** `.venv/bin/python` (venv via **uv**).

```bash
cd /home/etienne/Documents/tableforge
.venv/bin/python -m pytest -q                                  # tout vert
.venv/bin/python -m tableforge list -p examples/couronnes
.venv/bin/python -m tableforge generate cards -p examples/couronnes --dry-run   # sans réseau
.venv/bin/python -m tableforge render cards -p examples/couronnes --id lame      # PNG (Playwright)
.venv/bin/python -m tableforge generate cards -p examples/couronnes              # art IA  [coûte $]
.venv/bin/python -m tableforge sheet cards -p examples/couronnes                 # planche PDF
```

Si l'environnement est cassé :
```bash
uv venv .venv && uv pip install --python .venv/bin/python -e ".[dev]" && .venv/bin/playwright install chromium
```

## 4. Gotchas critiques

- **Python/venv** : `python3 -m venv` peut échouer (pas d'`ensurepip`). Utiliser **uv**
  (`~/.local/bin/uv`). Venv = `.venv/` (Python 3.14).
- **Seedream / BytePlus Ark** : `ARK_API_KEY` (dans `.env`) est **liée à sa région**
  (`ap-southeast`). Modèle accessible : **`seedream-5-0-260128`** (« -lite » pas dispo partout).
  La clé n'est **jamais** en dur : lue via `provider.api_key_env`. `.env` est gitignored.
- **Rendu** : faces & plateaux via **Playwright (Chromium)** ; planches via `page.pdf()`.
  Faces capturées à `device_scale_factor = scale` (carte 744×1039 ×3 ≈ 900 dpi).
- **CSS** : `combined_css` retire les `@import ... tokens.css` locaux et préfixe
  `templates/tokens.css`. Le `capture_selector` du kind doit matcher l'élément racine du gabarit.
- **Liaison par id** : un asset relie data/prompts/art/render par son `id` (slug). Un nom
  donne un slug via `data.slugify` (accents retirés, ex. « Pacte d'Éther » → `pacte-d-ether`).

## 5. Architecture (repère rapide)

```
src/tableforge/
  config.py     forge.yaml -> modèles pydantic (provider, kinds, sheet, defaults)
  data.py       rows (slugify, Row, load_rows, expand)
  prompts.py    art_direction + prompt_for(id) + reference_data_urls (i2i)
  providers.py  SeedreamProvider (compat OpenAI-images) + build_request
  generate.py   generate_kind (orchestration, dry-run)
  render.py     Jinja2 + Playwright HTML->PNG
  sheet.py      plan_sheet (grille, pur) + build_sheet_pdf (Playwright)
  scaffold.py   forge init (copie le starter)
  paths.py      conventions out/art|render|sheet/<kind>/
  cli.py        `forge` (typer)
  templates/starter/   projet vierge bundlé
examples/couronnes/    exemple complet (port runnable)
tests/                 pytest (96 % logique)
docs/superpowers/      spec + plan d'implémentation
```

## 6. Suites possibles

- Ajouter un kind `tokens` (jetons ronds) ou `back` (dos de carte) à l'exemple.
- Traits de coupe plus riches sur la planche (coins seulement, repères mm).
- Variante de plateau illustrée (réutiliser l'art `generate` du board).
- Multi-fournisseurs (OpenAI/DALL·E) si besoin — aujourd'hui Seedream-configurable.

## 7. Vérifier que tout va bien

```bash
.venv/bin/python -m pytest -q                                   # tous verts
.venv/bin/python -m tableforge render cards -p examples/couronnes --id couronne-maudite
```
Comparer le PNG rendu à `examples/couronnes/out/render/cards/`.
