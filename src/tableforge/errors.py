"""Hints HTTP partagés entre providers — messages d'erreur français actionnables."""
from __future__ import annotations

from typing import Optional

import httpx

_MAX_DETAIL_CHARS = 200


def hint_for_status(status: int, *, provider_type: str, asset: str,
                    kind: str) -> Optional[str]:
    if status == 401:
        return (f"clé refusée par {provider_type} : vérifie la variable d'env "
                "et les permissions de la clé.")
    if status == 402 and provider_type == "elevenlabs" and asset == "music":
        return (f"/v1/music exige un plan payant — utilise `forge studio {kind}` "
                "pour générer via l'interface web.")
    if status == 404:
        return "endpoint ou modèle inconnu : vérifie le slug/model déclaré pour ce provider."
    if status == 422:
        return "paramètres hors bornes : vérifie durées, formats et tailles demandés."
    if status == 429:
        return "quota atteint : réessaie plus tard ou réduis le nombre de cibles."
    return None


def raise_with_hint(response: httpx.Response, *, provider_type: str, asset: str,
                    kind: str) -> None:
    if response.is_success:
        return
    detail = response.text[:_MAX_DETAIL_CHARS].strip()
    message = (f"{provider_type} a répondu {response.status_code} "
               f"pour le kind '{kind}' ({asset})")
    if detail:
        message += f" : {detail}"
    hint = hint_for_status(response.status_code, provider_type=provider_type,
                           asset=asset, kind=kind)
    if hint:
        message += f"\n→ {hint}"
    raise RuntimeError(message)
