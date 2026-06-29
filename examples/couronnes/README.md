# Exemple — Couronnes & Cendres

Projet tableforge complet (18 cartes Économie + plateau). Démontre prompts, images de
référence (i2i), overrides de corruption, rendu HTML→PNG et planche d'impression.

```bash
forge list -p examples/couronnes
forge generate cards -p examples/couronnes --dry-run    # vérifie les prompts (pas de réseau)
forge generate cards -p examples/couronnes              # art IA (ARK_API_KEY requis)  [coûte $]
forge render cards   -p examples/couronnes              # faces PNG
forge sheet cards    -p examples/couronnes              # planche A4 PDF
forge board board    -p examples/couronnes              # plateau
```
