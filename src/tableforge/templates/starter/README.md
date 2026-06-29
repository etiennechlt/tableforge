# __PROJECT_NAME__

Projet tableforge. Commandes :

```bash
forge list
forge generate cards --dry-run     # vérifie les prompts sans appel réseau
forge generate cards               # art IA (nécessite ARK_API_KEY dans .env)  [coûte $]
forge render cards                 # designs PNG -> out/render/cards/
forge sheet cards                  # planche d'impression -> out/sheet/cards.pdf
```

Édite `data/cards.yaml` (tes cartes), `prompts/cards.yaml` (tes sujets + images de référence),
`templates/card/style.css` (ton style). Mets tes images de référence dans `reference/`.
