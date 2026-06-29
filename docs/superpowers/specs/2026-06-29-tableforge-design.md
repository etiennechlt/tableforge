# tableforge — Design / Spec

> Boîte à outils **générique, pilotée par configuration**, pour générer le matériel d'un jeu
> de table : **cartes (card), cartes (map)/plateau, designs, et génération d'art IA**.
> Extraite et généralisée du projet *Couronnes & Cendres*. Livrée avec un scaffold
> (`forge init`) et un **exemple complet qui marche** (`examples/couronnes/`).

Date : 2026-06-29 · Statut : approuvé pour planification

---

## 1. Objectif

Permettre à n'importe qui (sans toucher au code) de produire le matériel d'un jeu à partir
d'un **dossier projet** déclaratif :

- **génération d'art IA** depuis des **prompts configurables** + **images de référence** (i2i) ;
- **rendu de cartes / designs** via gabarits **HTML/CSS/Jinja2 → PNG** (Playwright) ;
- **planches d'impression PDF** (grille A4/Letter, fond perdu, traits de coupe) ;
- **plateau / map** (rendu pleine page).

L'aspect « configurable » est le cœur : **prompts**, **images de référence**, **données**,
**gabarits CSS** vivent tous dans le dossier projet, jamais en dur dans le code.

### Non-objectifs (YAGNI)

- Pas de moteur de règles de jeu / logique de partie.
- Pas d'abstraction multi-fournisseurs : **un seul provider Seedream**, mais **entièrement
  configurable** (endpoint / clé / modèle) → fonctionne aussi avec tout endpoint
  **compatible OpenAI-images**.
- Pas de ReportLab : **toute la mise en page passe par HTML/CSS** (un seul modèle mental).
- Pas d'interface web.

---

## 2. Concepts

| Terme | Définition |
|---|---|
| **Projet** | Un dossier autonome : `forge.yaml` + `data/` + `prompts/` + `templates/` + `reference/` + `out/`. |
| **Kind** | Un type d'asset nommé (`cards`, `board`, `tokens`, `map`…). Déclaré dans `forge.yaml`. |
| **Row** | Une ligne de `data/<kind>.yaml` : un dict arbitraire avec un `id` **obligatoire** (ou `name` → slug). Passé tel quel au gabarit. |
| **Art** | `out/art/<kind>/<id>.png` — illustration IA générée depuis `prompts/<kind>.yaml`. |
| **Render** | `out/render/<kind>/<id>.png` — design composé (gabarit + row + art). |
| **Sheet** | `out/sheet/<kind>.pdf` — planche d'impression (grille des renders). |

**Convention de liaison** : l'art et le render d'une row sont retrouvés par son `id`
(le slug). C'est la seule « magie » : `data` ↔ `prompts` ↔ `art` ↔ `render` partagent l'`id`.

---

## 3. Format des fichiers de configuration

### 3.1 `forge.yaml` (validé, pydantic, fail-fast)

```yaml
project: mon-jeu

provider:
  base_url: https://ark.ap-southeast.bytepluses.com/api/v3
  api_key_env: ARK_API_KEY          # NOM de la variable d'env, jamais la clé
  model: seedream-5-0-260128
  default_size: "4704x3520"         # 4K, ratio 4:3
  watermark: false
  output_format: png

defaults:
  max_refs: 3                       # nb max d'images de référence i2i
  ref_max_px: 1024                  # downscale des refs avant encodage data-URL

kinds:
  cards:
    data: data/cards.yaml
    prompts: prompts/cards.yaml
    template: templates/card        # dossier : template.html.j2 + style.css
    capture_selector: ".forge-card" # élément à screenshoter (défaut ".forge-asset")
    render_size: { width: 744, height: 1039 }   # px @1x (63×88 mm @300 dpi)
    scale: 3                        # device_scale_factor (netteté impression)
    art_size: "4704x3520"           # surcharge optionnelle de provider.default_size
    sheet:
      page: A4                      # A4 | Letter
      cols: 3
      rows: 3
      gap_mm: 4
      bleed_mm: 0
      cut_marks: true

  board:
    data: data/board.yaml           # une seule row → un seul render
    template: templates/board
    render_size: { width: 2480, height: 3508 }   # A4 @300 dpi
    scale: 1
    # pas de bloc `sheet` → pas de planche
```

Validation : champs requis présents, `page ∈ {A4, Letter}`, dimensions > 0, chemins
résolus relativement à la racine projet, message clair si un fichier référencé manque.

### 3.2 `prompts/<kind>.yaml`

```yaml
art_direction: >-                   # bloc de style commun, préfixé à chaque sujet
  Dark medieval fantasy illustration, painterly gouache ...
negative: >-                        # consignes « à éviter », suffixées à chaque prompt
  Avoid: any text, watermark, border, modern objects ...
style_refs:                         # ancres i2i communes (chemins relatifs projet)
  - reference/02-lame.png
prompts:                            # un sujet par id
  plaidoyer: "A ragged commoner kneeling ..."
  lame: "A weary footman gripping a nicked sword ..."
overrides:                          # surcharges par id (généralise l'ancien « corrupted »)
  couronne-maudite:
    suffix: "Corrupted variant: sickly violet-teal ether glow ..."
    style_refs: [reference/xx-couronne-maudite.png]   # refs ajoutées pour cet id
```

`prompt_for(id)` = `art_direction` + sujet + `overrides[id].suffix?` + `negative`.
Références i2i = `style_refs` (+ `overrides[id].style_refs`), encodées en data-URL,
limitées à `defaults.max_refs`, downscalées à `defaults.ref_max_px`.

### 3.3 `data/<kind>.yaml`

```yaml
rows:
  - id: plaidoyer          # OU name: "Plaidoyer" → id auto-sluggifié
    name: "Plaidoyer"
    cat: depart
    eff: "Piocher 1 carte."
    inf: 1
    qty: 1                 # nb d'exemplaires (utilisé par `sheet`)
  - ...
```

Seul `id` (ou `name`) est requis **par le moteur**. Tous les autres champs sont libres et
définis par le gabarit. Une row sans prompt ni art se rend quand même (emplacement d'art vide).

### 3.4 Contrat de gabarit `templates/<kind>/`

- `template.html.j2` (Jinja2) reçoit le contexte :
  - tous les champs de la row à plat (`name`, `eff`, …) **et** `row` (le dict complet) ;
  - `art_url` : data-URL du PNG d'art, ou `None` ;
  - `css` : CSS combiné inliné ;
  - `meta` : infos projet (`project`, `kind`).
- `style.css` : CSS du composant.
- `templates/tokens.css` (à la racine `templates/` du projet) : design tokens partagés.
  CSS combiné = `tokens.css` + `style.css` (les `@import ... tokens.css` locaux sont retirés).
- L'élément capturé est `capture_selector` (défaut `.forge-asset`).

---

## 4. Commandes (CLI `forge`)

| Commande | Effet |
|---|---|
| `forge init <nom> [dest]` | Scaffold un projet vierge commenté (copie du starter bundlé). Refuse un dossier non vide. |
| `forge list [--project P]` | Liste les kinds déclarés et l'état (data/prompts/template présents). |
| `forge generate <kind> [--id X ...] [--dry-run] [--force]` | Art IA → `out/art/<kind>/`. `--dry-run` = aucune requête réseau (affiche les requêtes). |
| `forge render <kind> [--id X ...]` | Compose les designs → `out/render/<kind>/`. |
| `forge sheet <kind>` | Planche d'impression PDF → `out/sheet/<kind>.pdf`. |
| `forge board <kind>` | Alias de `render` pour un kind pleine page (sortie `out/render/<kind>/`). |
| `forge all <kind>` | `generate` (si clé dispo) → `render` → `sheet`. |

Options globales : `--project PATH` (défaut = cwd). Chaque commande échoue avec un message
clair si le kind est inconnu ou un fichier requis manque.

---

## 5. Architecture des modules (`src/tableforge/`)

| Module | Responsabilité | Couverture |
|---|---|---|
| `config.py` | Modèles pydantic (`ProjectConfig`, `ProviderConfig`, `KindConfig`, `SheetConfig`) + `load_project()`. Résolution des chemins, fail-fast. | testé |
| `data.py` | `load_rows(kind_cfg)` → `list[Row]` (dict + `.id`), `slugify`, `expand(rows)` par `qty`. | testé |
| `prompts.py` | `load_prompts()`, `prompt_for(id, cfg)`, `reference_data_urls(cfg, root, id=None)`. | testé |
| `providers.py` | `SeedreamProvider.from_config()` (clé via `api_key_env`), `build_request()`, `generate()`. Compat OpenAI-images via SDK `openai` + `extra_body`. | testé (réseau mocké) |
| `generate.py` | `generate_kind(project, kind, ids, dry_run)` → orchestration, sauvegarde PNG. | testé (dry-run) |
| `render.py` | `render_html(kind_cfg, row, art_path)` (string) + `render_png(...)` via Playwright. | smoke |
| `sheet.py` | `plan_sheet(items, sheet_cfg)` (maths de grille, pur) + `render_sheet_html()` + `build_sheet_pdf()` via Playwright `page.pdf()`. | layout testé |
| `scaffold.py` | `init_project(name, dest)` : copie le starter bundlé, substitue le nom, refuse dossier non vide. | testé |
| `paths.py` | Conventions `out/art|render|sheet/<kind>/`. | testé |
| `cli.py` | App `typer` : `init / list / generate / render / sheet / board / all`. | smoke (CliRunner) |
| `templates/` | **Données packagées** : starter de projet + `tokens.css` par défaut (via `importlib.resources`). | — |

Principes (règles globales de l'utilisateur) : modules courts (<~150 lignes, 1 responsabilité),
données immuables, validation aux frontières, aucune clé en dur, erreurs explicites.

---

## 6. Provider Seedream (générique)

Repris de `seedream.py`, rendu paramétrable :

- `SeedreamProvider.from_config(provider_cfg)` lit la clé dans `os.environ[provider_cfg.api_key_env]`,
  erreur claire si absente.
- `build_request(prompt, size, refs)` → args `client.images.generate` avec
  `extra_body = {watermark, sequential_image_generation:"auto", output_format, image:[refs]?}`.
- `generate(...)` appelle l'API (SDK `openai`, `base_url` = Ark), sauve le(s) PNG.
- `summarize_request()` pour `--dry-run` (refs remplacées par leur nombre).

Compatibilité : tout endpoint OpenAI-images-compatible (Ark/BytePlus par défaut ;
d'autres via `base_url` + `model` + `api_key_env`).

---

## 7. Planche d'impression (`sheet.py`, sans ReportLab)

`plan_sheet(items, sheet_cfg)` (fonction **pure**, testée) calcule :
- nb de pages = `ceil(len(items_expanded) / (cols*rows))` après `expand` par `qty` ;
- position (mm) de chaque vignette dans la grille (cols × rows, `gap_mm`, `bleed_mm`) ;
- coordonnées des traits de coupe si `cut_marks`.

`render_sheet_html(plan, render_pngs)` génère un HTML avec `@page { size: A4 }`, une grille
CSS, les PNG en data-URL. `build_sheet_pdf()` rend via Playwright `page.pdf()`.

---

## 8. Exemple livré (`examples/couronnes/`)

Port **runnable** de Couronnes & Cendres démontrant chaque capacité :
- `forge.yaml` : kinds `cards` (avec `sheet`) + `board`.
- `data/cards.yaml` : les 18 cartes Économie (départ / marché / premium).
- `prompts/cards.yaml` : `art_direction` + 18 sujets + `overrides` pour les 4 premium (suffix corruption).
- `templates/card/` : gabarit + CSS adaptés au contexte générique (porté de `design/card/`).
- `templates/board/` : un plateau pleine page.
- `reference/` : 1–2 images de référence (ancres i2i).

`render` et `sheet` marchent **hors-ligne** (art absent → emplacement vide, ou art placeholder).
`generate` nécessite une clé `ARK_API_KEY`.

---

## 9. Tests (objectif ≥ 80 % sur la logique pure)

- **config** : forge.yaml valide/invalide, résolution de chemins, champs manquants.
- **data** : `load_rows`, `id` depuis `name`, `slugify`, `expand` par `qty`, `id` manquant → erreur.
- **prompts** : assemblage `prompt_for` (suffix/negative), `overrides`, encodage refs (nombre, downscale), prompt manquant → erreur.
- **providers** : forme de `build_request` (model/size/refs/extra_body), clé manquante → erreur (env mocké).
- **generate** : `dry_run` produit la bonne requête, pas d'appel réseau.
- **sheet** : `plan_sheet` (grille N items → cols×rows, nb pages, positions, `qty`, traits de coupe).
- **scaffold** : `init` crée les fichiers attendus, refuse un dossier non vide, substitue le nom.
- **paths** : conventions de chemins.
- **cli** : smoke `typer.testing.CliRunner` (chemins `--dry-run`).
- **render/sheet navigateur** : smoke (skip si Chromium absent), exclus de la couverture (comme l'existant).

---

## 10. Stack & environnement

- Python ≥ 3.10, packaging **hatchling**, env via **uv** (pas de `python`/`pip` système).
- Dépendances : `openai`, `httpx`, `pillow`, `pyyaml`, `jinja2`, `pydantic>=2`,
  `python-dotenv`, `typer`, `playwright`. Dev : `pytest`, `pytest-cov`.
- Bootstrap : `uv venv .venv && uv pip install --python .venv/bin/python -e . && .venv/bin/playwright install chromium`.
- Livré avec `README.md`, `HANDOFF.md` (reprise session Claude Code), `CLAUDE.md` (conventions), `.env.example`, `.gitignore`.

---

## 11. Livrables

1. Package `tableforge` installable (CLI `forge`).
2. Starter bundlé + `forge init`.
3. Exemple complet `examples/couronnes/`.
4. Tests (≥ 80 % logique) verts.
5. Docs : README + HANDOFF + CLAUDE.md + cette spec.
