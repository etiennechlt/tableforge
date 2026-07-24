# tableforge

> **Config-driven game asset generator** — cards, boards/maps, AI art, music, SFX, voices, video, print sheets.
> [English](#english) · [Français](#français)

## English

**Config-driven game asset generator**: cards, boards/maps, print-ready designs, and
**AI-generated art, music, sound effects, voices, dialogue and video** — all from a
declarative project folder. You describe your game in YAML + CSS + reference images;
`tableforge` produces the PNGs, audio files, videos and print sheets.
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
  out/                   generated art/audio/video, rendered PNGs, PDF sheets  (gitignored)
```

### Commands

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

`-p/--project` points to the project folder (defaults to the current directory).

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

### Configuration

#### `forge.yaml`

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

A v1 `forge.yaml` (single anonymous `provider:` block, no `generate:`) is still fully
supported — it is normalized to `providers: {default: …}` at load time.

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
designs, et **génération IA d'art, de musiques, de SFX, de voix, de dialogues et de
vidéos** — le tout à partir d'un dossier projet déclaratif.
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
  out/                   art/audio/vidéo générés, PNG rendus, planches PDF  (gitignored)
```

### Commandes

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

`-p/--project` pointe le dossier projet (défaut : dossier courant).

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

### Configuration

#### `forge.yaml`

```yaml
project: mon-jeu

providers:                    # « les comptes pour lesquels j'ai une clé »
  ark:
    type: seedream            # type OBLIGATOIRE sous providers:
    base_url: https://ark.ap-southeast.bytepluses.com/api/v3
    api_key_env: ARK_API_KEY  # NOM de la variable d'env (jamais la clé en clair)
    model: seedream-5-0-260128
  eleven:
    type: elevenlabs          # défauts raisonnables (base_url, formats, modèles)
  higgsfield:
    type: higgsfield          # clés : HIGGSFIELD_API_KEY + HIGGSFIELD_API_SECRET

voices:                       # noms humains -> voice_id ElevenLabs
  narrator: JBFqnCBsd6RMkjVDRZzb

defaults:
  max_refs: 3                 # nb max d'images de référence i2i
  ref_max_px: 1024            # downscale des refs avant envoi

kinds:
  cards:                      # kind image (asset: image est le défaut)
    data: data/cards.yaml
    prompts: prompts/cards.yaml
    template: templates/card
    render_size: { width: 744, height: 1039 }
    scale: 3
    generate: { with: ark }
    sheet: { page: A4, cols: 3, rows: 3, card_w_mm: 63, card_h_mm: 88 }

  cards-soul:                 # art IA brut via Higgsfield Soul (pas de template)
    asset: image
    prompts: prompts/cards-soul.yaml
    generate: { with: higgsfield, aspect_ratio: "3:4" }

  narration:                  # TTS depuis les rows de données (gabarit Jinja sur les champs)
    asset: tts
    data: data/cards.yaml
    generate: { with: eleven, voice: narrator, text: "{{ name }}. {{ eff }}", language: fr }

  musiques:                   # musique depuis un catalogue
    asset: music
    prompts: prompts/musiques.yaml
    generate: { with: eleven }

  cartes-animees:             # image-to-video : anime out/art/cards/<id>.png
    asset: video
    from: cards
    generate: { with: higgsfield, model: bytedance/seedance/v1/image-to-video }
```

Un `forge.yaml` v1 (bloc `provider:` anonyme, sans `generate:`) reste entièrement
supporté — il est normalisé en `providers: {default: …}` au chargement.

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

### Fournisseurs

- **seedream** — BytePlus Ark, endpoint compatible **OpenAI-images** (`base_url`,
  `model`, `api_key_env` en config, donc d'autres endpoints compatibles fonctionnent
  aussi). Images de référence (i2i) supportées.
- **elevenlabs** — musique (`/v1/music`, nécessite un plan payant — sur 402 la CLI
  renvoie vers `forge studio`), SFX et nappes en boucle, TTS et dialogues multi-voix.
  Les voix sont déclarées une fois dans la map `voices:` (nom → voice_id) et référencées
  par nom.
- **higgsfield** — API asynchrone (soumission → sondage, requêtes échouées/NSFW
  remboursées automatiquement) : images (Soul / Seedream-v4, `aspect_ratio`, `style_id`,
  `style_strength`, images de référence) et vidéo (image-to-video via `from:`, sinon
  text-to-video). Nécessite `HIGGSFIELD_API_KEY` + `HIGGSFIELD_API_SECRET`.
- **manual** — provider réservé pour les outils sans API ; s'utilise avec `forge studio`
  et un `studio_url:` optionnel sur le kind.

Les clés ne sont **jamais** stockées : elles sont lues à l'exécution depuis les variables
d'env nommées dans le bloc provider (via `.env`, gitignored) et jamais affichées.

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
