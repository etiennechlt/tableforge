"""Provider vidéo Higgsfield : submit -> poll -> download (httpx direct, API async).

NB (Step 0, P3a Task 2) — vérification doc API (docs.higgsfield.ai) :
  - `POST /{model_slug}` -> `{"request_id": ...}` : CONFIRMÉ (exemple observé dans la
    doc "how-to/introduction" : `{"request_id": "d7e6c0f3-...", ...}`). C'est le seul
    champ utilisé par ce module (`submit`, ci-dessous).
  - `GET /requests/{id}/status` : endpoint confirmé, mais la forme de la réponse
    `completed` DIFFÈRE de l'hypothèse initiale `{"results": [{"url": ...}]}` : la doc
    montre plutôt des clés dédiées par type de média, ex. `"images": [{"url": ...}]`
    pour de la génération d'image et `"video": {"url": ...}` pour de la vidéo — à
    reconfirmer et adapter dans les Tasks 3–5 (poll/download), ce module-ci ne
    consomme pas ce endpoint.
  - Champ image (i2v) et champ durée : NON CONFIRMÉS par la doc consultée (les
    exemples de la page ne couvrent que `prompt`/`aspect_ratio`/`resolution`).
    Hypothèses à vérifier dans les Tasks 3–5 : `"image"` (data-URL acceptée) et
    `"duration"` (secondes) — non utilisés dans ce module.
"""
from __future__ import annotations

import httpx

from ..errors import raise_with_hint

SUBMIT_TIMEOUT = 60.0


def build_submit(slug: str, body: dict) -> dict:
    return {"path": f"/{slug}", "json": dict(body)}


def _auth_headers(api_key: str, api_secret: str) -> dict:
    return {"Authorization": f"Key {api_key}:{api_secret}"}


def submit(cfg, req: dict, *, api_key: str, api_secret: str, kind: str = "video") -> str:
    response = httpx.post(f"{cfg.base_url}{req['path']}", json=req["json"],
                          headers=_auth_headers(api_key, api_secret),
                          timeout=SUBMIT_TIMEOUT)
    if response.is_error:
        raise_with_hint(response, provider_type="higgsfield", asset="video", kind=kind)
    request_id = response.json().get("request_id")
    if not request_id:
        raise RuntimeError(
            "Higgsfield : réponse de soumission sans 'request_id' — vérifie le slug du "
            "modèle et le format de l'API sur docs.higgsfield.ai.")
    return str(request_id)
