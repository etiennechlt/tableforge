# tableforge

**Générateur d'assets de jeu piloté par configuration** : cartes (*card*), plateaux / maps,
designs, et **génération d'art IA** — le tout à partir d'un dossier projet déclaratif.
Tu décris ton jeu en YAML + CSS + images de référence, `tableforge` produit les PNG et les
planches d'impression. Aucune logique de jeu, aucun code à écrire pour un nouveau projet.

Extrait et généralisé du projet *Couronnes & Cendres* (livré comme exemple complet dans
`examples/couronnes/`).

## Installation

> Pas de `python`/`pip` système ici : on utilise **uv**.

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/playwright install chromium      # nécessaire pour render/sheet/board
```

La commande s'appelle `forge` (via `.venv/bin/forge` ou `.venv/bin/python -m tableforge`).

## Démarrage rapide

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

## Concept

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

## Commandes

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

## Configuration

### `forge.yaml`

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

### `prompts/<kind>.yaml`

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

### `data/<kind>.yaml`

```yaml
rows:
  - { id: heros, name: "Héros", cost: 3, eff: "...", qty: 2 }
```

Seul `id` (ou `name` → slug) est requis par le moteur. Tous les autres champs sont libres
et passés au gabarit. `qty` est utilisé par `sheet` pour répéter une carte.

### Contrat de gabarit

`templates/<kind>/template.html.j2` reçoit : tous les champs de la row à plat
(`{{ name }}`, `{{ cost }}`…) **et** `{{ row }}` (le dict complet), `{{ art_url }}`
(data-URL du PNG d'art ou `None`), `{{ css }}` (CSS combiné inliné), `{{ meta }}`
(`{project, kind}`). Le CSS combiné = `templates/tokens.css` + `templates/<kind>/style.css`
(les `@import ... tokens.css` locaux sont retirés). L'élément capturé est `capture_selector`.

## Fournisseur d'images

Provider **Seedream** (BytePlus Ark), compatible **OpenAI-images** : `base_url`, `model` et
`api_key_env` sont en config, donc d'autres endpoints OpenAI-compatibles fonctionnent aussi.
La clé n'est **jamais** stockée : elle est lue à l'exécution depuis la variable d'env nommée
par `api_key_env` (via `.env`, gitignored).

## Exemple

`examples/couronnes/` est un projet complet (18 cartes Économie + plateau) qui démontre
prompts, images de référence, overrides de corruption, rendu et planche. Voir son `README.md`.

## Développement

```bash
.venv/bin/python -m pytest                 # tests
.venv/bin/python -m pytest --cov=tableforge --cov-report=term-missing
```

Le rendu navigateur (`render.py`) et la CLI sont exclus de la couverture (smoke-testés).
Voir `docs/superpowers/` pour la spec et le plan d'implémentation.
