# __PROJECT_NAME__

Projet tableforge. Commandes :

```bash
forge list
forge generate cards --dry-run     # vérifie les prompts sans appel réseau
forge generate cards               # art IA (nécessite ARK_API_KEY dans .env)  [coûte $]
forge render cards                 # designs PNG -> out/render/cards/
forge sheet cards                  # planche d'impression -> out/sheet/cards.pdf

forge generate musiques --dry-run  # ambiances (nécessite ELEVENLABS_API_KEY)  [coûte $]
forge generate sfx --dry-run       # effets sonores
forge studio musiques              # /v1/music exige un plan payant ElevenLabs :
                                    # fiches copier-coller (texte, réglages, dest) si pas de clé
forge voices list                  # voix du compte + mapping voices: du projet

forge all                          # generate (si clé) -> render -> sheet, tout le projet
```

Édite `data/cards.yaml` (tes cartes), `prompts/cards.yaml` (tes sujets + images de référence),
`templates/card/style.css` (ton style). Mets tes images de référence dans `reference/`.

Audio (musiques/sfx) : édite `prompts/musiques.yaml` et `prompts/sfx.yaml`. Le fichier
`forge.yaml` contient aussi, en commentaire, un exemple de kind vocal (TTS) à décommenter
si tu veux ajouter de la narration ou des voix de personnages.
