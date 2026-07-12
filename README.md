# tableforge

> **Config-driven game asset generator** — cards, boards/maps, AI art, print sheets.
> [English](#english) · [Français](#français)

## English

**Config-driven game asset generator**: cards, boards/maps, print-ready designs, and
**AI art generation** — all from a declarative project folder. You describe your game
in YAML + CSS + reference images; `tableforge` produces the PNGs and print sheets.
No game logic, no code to write for a new project.

Extracted and generalized from the *Couronnes & Cendres* board game project (shipped
as a complete example in `examples/couronnes/`).

### Installation

> No system `python`/`pip` here: this uses **uv**.

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/playwright install chromium      # required for render/sheet/board
```

The command is called `forge` (via `.venv/bin/forge` or `.venv/bin/python -m tableforge`).

### Quick start

```bash
forge init my-game                 # scaffolds a blank, commented project
cd my-game
# edit forge.yaml, data/cards.yaml, prompts/cards.yaml, templates/card/style.css
cp .env.example .env               # fill in your ARK_API_KEY
forge generate cards --dry-run     # check the prompts without a network call
forge generate cards               # AI art -> out/art/cards/        [costs credits]
forge render cards                 # PNG designs -> out/render/cards/
forge sheet cards                  # A4 PDF sheet -> out/sheet/cards.pdf
```

### Concept

A **project** declares **kinds** (asset types). Each kind links *data + prompts +
an HTML/CSS template*. Three operations act on it: `generate` (AI art), `render`
(HTML→PNG), `sheet` (PDF sheet). **Everything is tied together by `id`** (the slug):
`data` ↔ `prompts` ↔ `out/art/<kind>/<id>.png` ↔ `out/render/<kind>/<id>.png`.

```
my-game/
  forge.yaml             config: AI provider, kinds, defaults
  data/<kind>.yaml       data rows (1 row = 1 asset), id required
  prompts/<kind>.yaml    art_direction + subject per id + style_refs + negative + overrides
  templates/<kind>/      template.html.j2 + style.css
  templates/tokens.css   shared design tokens
  reference/             reference images (i2i)
  out/                   generated art, rendered PNGs, PDF sheets  (gitignored)
```

### Commands

| Command | Effect |
|---|---|
| `forge init <name>` | Scaffolds a blank project (refuses a non-empty folder). |
| `forge list -p <project>` | Lists kinds and their state (data/prompts/template present). |
| `forge generate <kind> [--id X] [--dry-run] [--force]` | AI art → `out/art/<kind>/`. |
| `forge render <kind> [--id X]` | PNG designs → `out/render/<kind>/`. |
| `forge sheet <kind>` | Print-ready PDF sheet → `out/sheet/<kind>.pdf`. |
| `forge board <kind>` | Full-page render (board / map). |
| `forge all <kind>` | `generate` (if a key is set) → `render` → `sheet`. |

`-p/--project` points to the project folder (defaults to the current directory).

### Configuration

#### `forge.yaml`

```yaml
project: my-game
provider:
  base_url: https://ark.ap-southeast.bytepluses.com/api/v3
  api_key_env: ARK_API_KEY          # NAME of the env var (never the key itself)
  model: seedream-5-0-260128        # any OpenAI-images-compatible endpoint works
  default_size: "4704x3520"
defaults:
  max_refs: 3                       # max number of i2i reference images
  ref_max_px: 1024                  # downscale refs before sending
kinds:
  cards:
    data: data/cards.yaml
    prompts: prompts/cards.yaml
    template: templates/card
    capture_selector: ".forge-asset"          # element to capture (default)
    render_size: { width: 744, height: 1039 } # px @1x
    scale: 3                                   # device_scale_factor (print sharpness)
    art_size: "4704x3520"                      # optional override of default_size
    sheet:
      page: A4                                 # A4 | Letter
      cols: 3
      rows: 3
      card_w_mm: 63                            # physical card size (required for the sheet)
      card_h_mm: 88
      gap_mm: 4
      cut_marks: true
```

#### `prompts/<kind>.yaml`

```yaml
art_direction: >- ...        # shared style block, prefixed to every subject
negative: >- ...             # "avoid this" instructions, appended to every prompt
style_refs: [reference/a.png]   # shared i2i anchors
prompts:
  heros: "A lone armored hero ..."
overrides:                   # per-id overrides
  relique: { suffix: "Add a faint glow.", style_refs: [reference/relique.png] }
```

Final prompt = `art_direction` + subject + `overrides[id].suffix?` + `negative`.

#### `data/<kind>.yaml`

```yaml
rows:
  - { id: heros, name: "Hero", cost: 3, eff: "...", qty: 2 }
```

Only `id` (or `name` → slug) is required by the engine. All other fields are free-form
and passed to the template. `qty` is used by `sheet` to repeat a card.

#### Template contract

`templates/<kind>/template.html.j2` receives: every field of the row, flattened
(`{{ name }}`, `{{ cost }}`…), plus `{{ row }}` (the full dict), `{{ art_url }}`
(the art PNG as a data URL, or `None`), `{{ css }}` (combined, inlined CSS), `{{ meta }}`
(`{project, kind}`). The combined CSS = `templates/tokens.css` + `templates/<kind>/style.css`
(local `@import ... tokens.css` statements are stripped out). The captured element is
`capture_selector`.

### Image provider

**Seedream** (BytePlus Ark) provider, **OpenAI-images**-compatible: `base_url`, `model`,
and `api_key_env` are all set in config, so other OpenAI-compatible endpoints work too.
The key is **never** stored: it is read at runtime from the env variable named by
`api_key_env` (via `.env`, gitignored).

### Example

`examples/couronnes/` is a complete project (18 Economy cards + a board) demonstrating
prompts, reference images, corruption overrides, rendering, and print sheets. See its
`README.md`.

### Development

```bash
.venv/bin/python -m pytest                 # tests
.venv/bin/python -m pytest --cov=tableforge --cov-report=term-missing
```

Browser rendering (`render.py`) and the CLI are excluded from coverage (smoke-tested
instead). See `docs/superpowers/` for the spec and implementation plan.

## Français

**Générateur d'assets de jeu piloté par configuration** : cartes (*card*), plateaux / maps,
designs, et **génération d'art IA** — le tout à partir d'un dossier projet déclaratif.
Tu décris ton jeu en YAML + CSS + images de référence, `tableforge` produit les PNG et les
planches d'impression. Aucune logique de jeu, aucun code à écrire pour un nouveau projet.

Extrait et généralisé du projet *Couronnes & Cendres* (livré comme exemple complet dans
`examples/couronnes/`).

### Installation

> Pas de `python`/`pip` système ici : on utilise **uv**.

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/playwright install chromium      # nécessaire pour render/sheet/board
```

La commande s'appelle `forge` (via `.venv/bin/forge` ou `.venv/bin/python -m tableforge`).

### Démarrage rapide

```bash
forge init mon-jeu                 # crée un projet vierge commenté
cd mon-jeu
# édite forge.yaml, data/cards.yaml, prompts/cards.yaml, templates/card/style.css
cp .env.example .env               # renseigne ta clé ARK_API_KEY
forge generate cards --dry-run     # vérifie les prompts sans appel réseau
forge generate cards               # art IA -> out/art/cards/        [coûte des crédits]
forge render cards                 # designs PNG -> out/render/cards/
forge sheet cards                  # planche A4 PDF -> out/sheet/cards.pdf
```

### Concept

Un **projet** déclare des **kinds** (types d'asset). Chaque kind lie *données + prompts +
gabarit HTML/CSS*. Trois opérations agissent dessus : `generate` (art IA), `render`
(HTML→PNG), `sheet` (planche PDF). **Tout est relié par l'`id`** (le slug) :
`data` ↔ `prompts` ↔ `out/art/<kind>/<id>.png` ↔ `out/render/<kind>/<id>.png`.

```
mon-jeu/
  forge.yaml             config : fournisseur IA, kinds, défauts
  data/<kind>.yaml       lignes de données (1 ligne = 1 asset), id obligatoire
  prompts/<kind>.yaml    art_direction + sujet par id + style_refs + negative + overrides
  templates/<kind>/      template.html.j2 + style.css
  templates/tokens.css   design tokens partagés
  reference/             images de référence (i2i)
  out/                   art généré, PNG rendus, planches PDF  (gitignored)
```

### Commandes

| Commande | Effet |
|---|---|
| `forge init <nom>` | Scaffold un projet vierge (refuse un dossier non vide). |
| `forge list -p <projet>` | Liste les kinds et l'état (data/prompts/template présents). |
| `forge generate <kind> [--id X] [--dry-run] [--force]` | Art IA → `out/art/<kind>/`. |
| `forge render <kind> [--id X]` | Designs PNG → `out/render/<kind>/`. |
| `forge sheet <kind>` | Planche d'impression PDF → `out/sheet/<kind>.pdf`. |
| `forge board <kind>` | Rendu plein page (plateau / map). |
| `forge all <kind>` | `generate` (si clé) → `render` → `sheet`. |

`-p/--project` pointe le dossier projet (défaut : dossier courant).

### Configuration

#### `forge.yaml`

```yaml
project: mon-jeu
provider:
  base_url: https://ark.ap-southeast.bytepluses.com/api/v3
  api_key_env: ARK_API_KEY          # NOM de la variable d'env (jamais la clé en clair)
  model: seedream-5-0-260128        # tout endpoint compatible OpenAI-images marche
  default_size: "4704x3520"
defaults:
  max_refs: 3                       # nb max d'images de référence i2i
  ref_max_px: 1024                  # downscale des refs avant envoi
kinds:
  cards:
    data: data/cards.yaml
    prompts: prompts/cards.yaml
    template: templates/card
    capture_selector: ".forge-asset"          # élément à capturer (défaut)
    render_size: { width: 744, height: 1039 } # px @1x
    scale: 3                                   # device_scale_factor (netteté impression)
    art_size: "4704x3520"                      # surcharge optionnelle du default_size
    sheet:
      page: A4                                 # A4 | Letter
      cols: 3
      rows: 3
      card_w_mm: 63                            # taille physique de la carte (requis pour la planche)
      card_h_mm: 88
      gap_mm: 4
      cut_marks: true
```

#### `prompts/<kind>.yaml`

```yaml
art_direction: >- ...        # bloc de style commun, préfixé à chaque sujet
negative: >- ...             # consignes « à éviter », suffixées à chaque prompt
style_refs: [reference/a.png]   # ancres i2i communes
prompts:
  heros: "A lone armored hero ..."
overrides:                   # surcharges par id
  relique: { suffix: "Add a faint glow.", style_refs: [reference/relique.png] }
```

Prompt final = `art_direction` + sujet + `overrides[id].suffix?` + `negative`.

#### `data/<kind>.yaml`

```yaml
rows:
  - { id: heros, name: "Héros", cost: 3, eff: "...", qty: 2 }
```

Seul `id` (ou `name` → slug) est requis par le moteur. Tous les autres champs sont libres
et passés au gabarit. `qty` est utilisé par `sheet` pour répéter une carte.

#### Contrat de gabarit

`templates/<kind>/template.html.j2` reçoit : tous les champs de la row à plat
(`{{ name }}`, `{{ cost }}`…) **et** `{{ row }}` (le dict complet), `{{ art_url }}`
(data-URL du PNG d'art ou `None`), `{{ css }}` (CSS combiné inliné), `{{ meta }}`
(`{project, kind}`). Le CSS combiné = `templates/tokens.css` + `templates/<kind>/style.css`
(les `@import ... tokens.css` locaux sont retirés). L'élément capturé est `capture_selector`.

### Fournisseur d'images

Provider **Seedream** (BytePlus Ark), compatible **OpenAI-images** : `base_url`, `model` et
`api_key_env` sont en config, donc d'autres endpoints OpenAI-compatibles fonctionnent aussi.
La clé n'est **jamais** stockée : elle est lue à l'exécution depuis la variable d'env nommée
par `api_key_env` (via `.env`, gitignored).

### Exemple

`examples/couronnes/` est un projet complet (18 cartes Économie + plateau) qui démontre
prompts, images de référence, overrides de corruption, rendu et planche. Voir son `README.md`.

### Développement

```bash
.venv/bin/python -m pytest                 # tests
.venv/bin/python -m pytest --cov=tableforge --cov-report=term-missing
```

Le rendu navigateur (`render.py`) et la CLI sont exclus de la couverture (smoke-testés).
Voir `docs/superpowers/` pour la spec et le plan d'implémentation.
