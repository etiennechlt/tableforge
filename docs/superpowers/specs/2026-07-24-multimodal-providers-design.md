# Spec — tableforge multimodal : providers nommés, audio ElevenLabs, images/vidéo Higgsfield

> Validée le 2026-07-24 (brainstorming + panel de design 3 propositions / 3 juges).
> Étend tableforge d'un générateur d'images mono-provider vers un générateur
> multi-provider et multi-modalités : **image, musique, SFX/soundscapes, TTS, dialogue, vidéo**.

## 1. Contexte et objectif

tableforge génère le matériel d'un jeu de table depuis un dossier projet déclaratif.
Aujourd'hui : une seule modalité (image), un seul provider (Seedream/Ark, bloc
`provider:` anonyme). Le projet d'origine *Couronnes & Cendres* a développé à côté
un sous-système audio ElevenLabs éprouvé (musique, SFX, soundscapes en boucle,
catalogues YAML, mode studio). Objectif : généraliser tout cela dans tableforge,
et ajouter les voix (TTS/dialogues) et la vidéo (Higgsfield).

Contrainte produit n°1 : **un ami non-codeur configure son jeu sans toucher au code.**
L'ergonomie du `forge.yaml` prime.

### Décisions d'entrée (recherche vérifiée, juillet 2026)

- **ElevenLabs audio** : API publique complète — Music (`POST /v1/music`), SFX
  (`POST /v1/sound-generation`, `loop` avec `eleven_text_to_sound_v2`), TTS
  (`POST /v1/text-to-speech/{voice_id}`, français OK), Dialogue
  (`POST /v1/text-to-dialogue`), Voice design (`/v1/text-to-voice/design` → create).
  Auth header `xi-api-key`. `/v1/music` exige un plan payant → le mode studio compte.
- **ElevenLabs image/vidéo : PAS d'API publique** (UI seulement ; « Studio API » sur
  demande commerciale). Donc pas de provider API — couvert par le provider `manual`
  + `forge studio`.
- **Higgsfield** (`platform.higgsfield.ai`) : API publique async — auth
  `Authorization: Key {key}:{secret}`, `POST /{model_slug}` → `request_id`,
  `GET /requests/{id}/status` (`queued|in_progress|completed|failed|nsfw`).
  Slugs image (Soul `higgsfield-ai/soul/standard`, `bytedance/seedream/v4/text-to-image`)
  et vidéo (Seedance/Kling, i2v et t2v). Échecs/NSFW auto-remboursés.
- Convention projet : **httpx direct, pas de SDK vendeur** ; mocks respx.

## 2. Périmètre

**Inclus** : architecture multi-provider/multi-modalité ; provider ElevenLabs
(music, sfx+loop, tts, dialogue, utilitaire voice design) ; provider Higgsfield
(image Soul/Seedream, vidéo i2v et t2v) ; provider `manual` ; mode studio généralisé ;
map `voices:` ; rétro-compat totale des `forge.yaml` v1 ; starter et exemple enrichis.

**Exclus** : intégration API de l'offre image/vidéo d'ElevenLabs (pas d'API publique) ;
lecture/streaming des médias (tableforge génère des fichiers, point) ; le pont web
de couronnes-cendres (QR, AnimIntent) qui reste dans ce projet-là.

**Lignes de coupe** (dans l'ordre, si besoin de réduire) :
`forge voices design` → teaser t2v → presets Soul.

## 3. Surface de configuration (contrat utilisateur)

### 3.1 forge.yaml — exemple de référence

```yaml
project: couronnes-cendres

providers:                    # « les comptes pour lesquels j'ai une clé »
  ark:
    type: seedream            # type OBLIGATOIRE dans providers: (pas de défaut ici)
    base_url: https://ark.ap-southeast.bytepluses.com/api/v3
    api_key_env: ARK_API_KEY
    model: seedream-5-0-260128
  eleven:
    type: elevenlabs          # tout a un défaut sain (base_url, formats, modèles)
  higgsfield:
    type: higgsfield          # clés : HIGGSFIELD_API_KEY + HIGGSFIELD_API_SECRET

voices:                       # noms humains -> voice_id ElevenLabs
  narrateur:     JBFqnCBsd6RMkjVDRZzb
  vieille-reine: EXAVITQu4vr4xnSDxMaL
  heraut:        TxGEqnHWrfWFTfGW9XjX

kinds:
  cards:                      # kind image inchangé (asset: image par défaut)
    data: data/cards.yaml
    prompts: prompts/cards.yaml
    template: templates/card
    render_size: { width: 744, height: 1039 }
    scale: 3
    generate: { with: ark }
    sheet: { page: A4, cols: 3, rows: 3, card_w_mm: 63, card_h_mm: 88 }

  narration:                  # TTS par carte : texte tiré des rows
    asset: tts
    data: data/cards.yaml
    generate:
      with: eleven
      voice: narrateur                # nom -> voices:
      text: "{{ name }}. {{ eff }}"   # gabarit Jinja sur les champs de la row
      language: fr

  voix-pnj:                   # TTS : une voix par personnage
    asset: tts
    data: data/pnj.yaml               # rows: - {id: reine, voice: vieille-reine, replique: "…"}
    generate: { with: eleven, text: "{{ replique }}", voice_field: voice }

  regles-audio:               # TTS : catalogue libre (pas de data)
    asset: tts
    prompts: prompts/regles-audio.yaml
    generate: { with: eleven, voice: narrateur, language: fr }

  sfx:
    asset: sfx
    prompts: prompts/sfx.yaml
    generate: { with: eleven }

  nappes:                     # soundscapes = sfx avec loop: true dans le catalogue
    asset: sfx
    prompts: prompts/nappes.yaml
    generate: { with: eleven }

  musiques:
    asset: music
    prompts: prompts/musiques.yaml
    generate: { with: eleven }

  dialogues:                  # multi-voix
    asset: dialogue
    prompts: prompts/dialogues.yaml
    generate: { with: eleven }

  cartes-animees:             # vidéo i2v : anime out/art/cards/<id>.png
    asset: video
    from: cards                        # présence de `from:` => image-to-video
    prompts: prompts/cartes-animees.yaml   # optionnel : prompt de mouvement par id
    generate: { with: higgsfield, model: bytedance/seedance/v1/image-to-video }

  teaser:                     # vidéo t2v (pas de `from:`)
    asset: video
    prompts: prompts/teaser.yaml
    generate: { with: higgsfield, model: kling-video/v2.1/standard/text-to-video, aspect_ratio: "16:9" }

  affiche:                    # outil SANS API : provider réservé `manual`
    prompts: prompts/affiche.yaml
    generate: { with: manual }
    studio_url: https://elevenlabs.io/app/image-video
```

### 3.2 Règles de moindre surprise

1. **Rétro-compat totale.** Un `forge.yaml` v1 (bloc `provider:` anonyme, aucun
   `generate:`) reste valide : normalisé en `providers: {default: …}` (type
   `seedream` implicite **uniquement** sur ce chemin legacy) et chaque kind image
   avec `prompts:` reçoit `generate: {with: default}`. Si `provider:` et
   `providers:` coexistent → erreur explicite.
2. **`with:` omis** : auto-résolution si exactement un provider déclaré sait faire
   l'`asset:` du kind ; sinon erreur listant les candidats.
3. **`asset:`** ∈ `image | music | sfx | tts | dialogue | video`, défaut `image`.
4. **Précédence des voix** (tts) : champ de row (`voice_field`) > entrée de
   catalogue (`voice:`) > défaut du kind (`generate.voice`). Les valeurs sont des
   **noms** de la map `voices:` (jamais des IDs bruts dans les données).
5. **Sorties** : `out/art/<kind>/` (image, inchangé), `out/audio/<kind>/`,
   `out/video/<kind>/`. Extension dérivée du format : `mp3_*` → `.mp3`,
   `opus_*` → `.ogg`, `pcm_*`/`ulaw_*`/`alaw_*` → `.wav`, vidéo → `.mp4`,
   image → `output_format` du provider (défaut `.png`).
6. **`with: manual`** (réservé, aucune déclaration, jamais choisi par
   l'auto-résolution) : `forge generate` refuse en pointant vers `forge studio` ;
   la fiche studio inclut `studio_url:` si présent.
7. **`from:` sur un kind video** ⇒ i2v depuis `out/art/<from>/<id>.png` ; ids =
   ceux du kind source (le catalogue de mouvement, s'il existe, doit être un
   sous-ensemble — erreur nommant les deux fichiers sinon). Sans `from:` ⇒ t2v,
   ids = entries du catalogue.

### 3.3 Catalogues non-image (fichiers `prompts:` des kinds audio/vidéo)

Schéma commun (porté de couronnes-cendres) :

```yaml
direction: "Dark medieval fantasy orchestral score…"   # suffixe de style partagé
negative: "No lead vocals, no lyrics…"                 # replié DANS le prompt (pas de champ API)
output_format: mp3_44100_128                           # optionnel, défaut provider
defaults:                                              # optionnel, par asset
  length_ms: 90000        # music
  duration_s: 30          # sfx
  loop: true              # sfx (soundscapes)
entries:
  menu:      { prompt: "…", length_ms: 120000 }        # music
  pioche:    { prompt: "…", duration_s: 0.8 }          # sfx
  mise-en-place: { text: "…" }                         # tts (catalogue)
  intro:                                                # dialogue
    lines:
      - { voice: heraut, text: "…" }
      - { voice: vieille-reine, text: "…" }
```

Assemblage du prompt : `"<sujet sans point final>. <direction> <negative>"` —
même logique que les images. Bornes API clampées avec mention visible en dry-run :
musique 3 000–600 000 ms ; SFX 0,5–30 s. Les kinds image gardent leur schéma
actuel (`art_direction`, `style_refs`, `prompts:`, `overrides:`) inchangé.

## 4. Architecture moteur

### 4.1 Modules

```
src/tableforge/
  config.py            # modèles étendus : union discriminée de providers (par type:),
                       #   KindConfig + asset/from/generate/studio_url, map voices,
                       #   normalisation legacy provider: -> providers.default
  data.py              # inchangé
  prompts.py           # schéma image existant, inchangé
  catalog.py           # NOUVEAU — catalogues non-image + assemblage prompt + clamps
  targets.py           # NOUVEAU — résolution des cibles par kind : ids + texte/prompt,
                       #   gabarits Jinja sur rows, résolution des voix (précédence)
  providers/           # NOUVEAU package
    __init__.py        #   ré-exports compat (SeedreamProvider, build_request…)
    base.py            #   AssetJob (frozen), Protocol plan()/execute(), registre,
                       #   modèles d'options par (provider, asset) extra="forbid"
    seedream.py        #   l'existant déplacé (git mv), comportement identique
    elevenlabs.py      #   builders purs music/sfx/tts/dialogue ({json, params}) + POST httpx
    higgsfield.py      #   submit -> poll (statuts affichés, sleep injectable, timeout)
    manual.py          #   ManualProvider : generate refuse, studio guide
  generate.py          # UN orchestrateur toutes modalités (skip-exists, --force, --id, dry-run)
  studio.py            # NOUVEAU — fiches studio (prompt, réglages, dest, URL)
  paths.py             # asset_path(root, modality, kind, id, ext) ; helpers actuels conservés
  errors.py            # NOUVEAU — hints HTTP partagés en français
  render.py, sheet.py, scaffold.py, cli.py   # retouches légères
```

Tous les modules restent ≤ ~400 lignes ; si `config.py` dépasse, extraire la
normalisation dans `config_load.py`.

### 4.2 Contrat plan/execute

- `plan(kind) -> list[AssetJob]` : **pur, sans clé API**. Résout cibles, prompts,
  voix, options, destination. Consommé par `--dry-run`, `forge studio`,
  `forge list` (linter). `AssetJob` (frozen) : `id`, `dest`, `request`
  (résumé sans data-URLs ni secrets), `notes` (clamps, avertissements).
- `execute(job) -> list[Path]` : seul point qui lit `api_key_env` (dotenv + env,
  erreur française si absente) et touche le réseau.
- Conséquence : le dry-run actuel qui bypasse le provider (duplication de
  `build_request` dans generate.py) disparaît — un seul chemin de construction.
- Un seul orchestrateur `generate_kind` pour toutes les modalités : pas de
  divergence `--force`/skip entre pipelines.
- Higgsfield : poll synchrone avec affichage des transitions par id
  (`queued → in_progress → completed`), sleep injectable, timeout configurable
  (`poll_interval_s`, `poll_timeout_s` dans le bloc provider).

### 4.3 `forge all`

Ordre fixe **image → audio → vidéo** (l'art existe avant d'être animé, sans DAG).
L'ordre résolu est affiché avant exécution. Clé manquante → avertit et continue
(comportement actuel). i2v avec art manquant : avertissement en dry-run/studio,
erreur bloquante (nommant les deux fichiers) à l'exécution seulement.

## 5. Surface CLI

| Commande | Évolution |
|---|---|
| `forge list` | Linter : validation complète (options extra=forbid, capacités provider/asset, voix, cohérence i2v) + affichage modalité/provider/état des fichiers par kind |
| `forge generate <kind>` | Surface inchangée (`--id`, `--dry-run`, `--force`), toutes modalités ; dry-run affiche requête résumée + note d'auth (noms de variables d'env uniquement) |
| `forge studio <kind> [--id]` | NOUVELLE : fiche par entrée — prompt assemblé, réglages, chemin de dépôt attendu, URL du bon écran (app/music, app/sound-effects, app/speech-synthesis, ou `studio_url:`) |
| `forge voices` | NOUVEL utilitaire : `list` (bibliothèque + vérif map `voices:`), `design "<description>"` (aperçus → sauvegarde). Ligne de coupe n°1 |
| `forge render / board / sheet` | Inchangées ; refus pédagogique sur kind non-image (« le kind 'narration' est audio (tts) — rien à rendre ») |
| `forge all [kind]` | Ordre image → audio → vidéo |
| `forge init` | Starter enrichi : kinds audio/vidéo commentés, catalogues d'exemple, `.env.example` documentant `ARK_API_KEY`, `ELEVENLABS_API_KEY`, `HIGGSFIELD_API_KEY`/`_SECRET` |

## 6. Gestion des erreurs

- **Chargement** : erreur si `provider:` + `providers:` coexistent ; clé inconnue
  dans `generate:` → énumère les clés acceptées pour ce (provider, asset) ; voix
  inconnue → liste les voix déclarées ; `type:` manquant dans `providers:` →
  « type requis : seedream | elevenlabs | higgsfield ».
- **HTTP** (`errors.py`, partagé dès le 2e provider) : 401 permissions de la clé ;
  **402 → « /v1/music exige un plan payant — utilise `forge studio musiques` »** ;
  404 slug de modèle inconnu ; 422 bornes ; 429 quota.
- **Exécution** : variable d'env absente → nomme la variable + URL où créer la clé.
  Clamps visibles dans le dry-run, jamais silencieux. Dialogue > ~2 000 caractères :
  avertissement (constante, pas d'erreur dure).
- **Secrets** : jamais imprimés (dry-run, studio, erreurs — noms de variables only).
- Requêtes Higgsfield `failed`/`nsfw` : signalées comme auto-remboursées.

## 7. Stratégie de test

- **Verrou P0 : byte-équivalence** — un forge.yaml v1 intact (fixture inline +
  `examples/couronnes`) produit des requêtes dry-run *identiques* avant/après le
  refactor (comparaison des dicts, pas seulement « tests verts »).
- **Doctrine réseau** (à inscrire dans CLAUDE.md) : chemins httpx
  ElevenLabs/Higgsfield **couverts par respx** (headers `xi-api-key` /
  `Authorization: Key`, corps JSON, fichier écrit) ; chemin SDK OpenAI de Seedream
  reste `pragma: no cover` + smoke.
- Poll Higgsfield : sleep injectable dès le premier commit ; transitions,
  failed/nsfw, timeout testés sans attente réelle.
- Builders purs, clamps, gabarits, précédence des voix, catalogues, normalisation
  config : unitaires AAA. CLI : dry-run, fiches studio, hints, refus pédagogiques.
- Un `test_<module>.py` par nouveau module ; les tests existants ne bougent pas en
  P0 (ré-exports depuis `providers/__init__.py`).
- `examples/couronnes` enrichi des vrais catalogues portés (7 musiques, 15 SFX,
  6 nappes) + narration + cartes-animées ; intégration en dry-run pur.
- Couverture ≥ 80 % logique pure (objectif : rester ≈ 96 %). TDD systématique.

## 8. Phasage

| Phase | Contenu | Livrable |
|---|---|---|
| **P0** | Refactor à comportement constant : package `providers/` (git mv + ré-exports), split plan/execute Seedream, dry-run via provider, `asset_path`, providers nommés + alias legacy + erreur de coexistence, test byte-équivalence | Harnais de non-régression, zéro feature |
| **P1** | `catalog.py`, provider ElevenLabs (music + sfx/loop), orchestrateur généralisé, `forge studio`, ManualProvider, `errors.py`, starter + `.env.example`, exemple enrichi (sfx/nappes/musiques) | L'audio éprouvé de couronnes-cendres, généralisé |
| **P2** | TTS (rows + gabarit, catalogues), dialogues, map `voices:` + `voice_field` + précédence, `forge voices` | Narration, PNJ, règles lues |
| **P3a** | Higgsfield submit/poll, vidéo i2v (`from:`) + t2v, `out/video/` | Cartes animées + teasers |
| **P3b** | Images via Higgsfield (Soul + Seedream, `style_id`/`style_strength`, refs i2i) | Second provider d'images |
| **Fin** | HANDOFF/README/CLAUDE.md, critère de suppression daté des shims de compat | Doc de reprise |

Chaque phase : suite verte, livrable, commit(s) conventionnels.

## 9. Références API (pour l'implémentation)

- ElevenLabs — base `https://api.elevenlabs.io`, header `xi-api-key`,
  `output_format` en query param, réponse = octets audio :
  - Music : `POST /v1/music` `{prompt, music_length_ms}` (3 000–600 000).
  - SFX : `POST /v1/sound-generation` `{text, model_id, loop, duration_seconds?}`
    (0,5–30 s) ; défaut `eleven_text_to_sound_v2` (loop exige v2).
  - TTS : `POST /v1/text-to-speech/{voice_id}` `{text, model_id, language_code?,
    voice_settings?, seed?}` ; défaut `eleven_multilingual_v2` (stable, fr),
    `eleven_v3` possible (expressif, tags `[whispers]`…).
  - Dialogue : `POST /v1/text-to-dialogue` `{inputs: [{text, voice_id}], model_id}`
    (défaut `eleven_v3`, max 10 voix, ~2 000 caractères).
  - Voice design : `POST /v1/text-to-voice/design` → aperçus
    (`generated_voice_id` + mp3 base64) → `POST /v1/text-to-voice` pour sauvegarder.
  - Formats : `mp3_44100_128` (défaut), `opus_*`, `pcm_*`, `ulaw_*`, `alaw_*`.
- Higgsfield — base `https://platform.higgsfield.ai`, header
  `Authorization: Key {api_key}:{api_secret}` :
  - `POST /{model_slug}` (JSON `{prompt, aspect_ratio?, resolution?, style_id?,
    style_strength?, image?…}`) → `{request_id}`.
  - `GET /requests/{id}/status` → `queued|in_progress|completed|failed|nsfw`
    + URLs de résultat ; `POST /requests/{id}/cancel`.
  - Slugs de référence : `higgsfield-ai/soul/standard`,
    `bytedance/seedream/v4/text-to-image`, `bytedance/seedance/v1/image-to-video`,
    `kling-video/v2.1/standard/text-to-video` (vérifier la galerie de modèles au
    moment de l'implémentation — les slugs évoluent).
- Env : `ELEVENLABS_API_KEY` (+ `ELEVENLABS_BASE_URL`, `ELEVENLABS_SFX_MODEL`
  optionnels), `HIGGSFIELD_API_KEY` + `HIGGSFIELD_API_SECRET`, `ARK_API_KEY`.
