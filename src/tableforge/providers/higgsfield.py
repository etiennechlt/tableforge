"""Provider vidéo Higgsfield : submit -> poll -> download (httpx direct, API async).

NB (Step 0, P3a Task 2) — vérification doc API (docs.higgsfield.ai) :
  - `POST /{model_slug}` -> `{"request_id": ...}` : CONFIRMÉ (exemple observé dans la
    doc "how-to/introduction" : `{"request_id": "d7e6c0f3-...", ...}`). C'est le seul
    champ utilisé par ce module (`submit`, ci-dessous).
  - `GET /requests/{id}/status` : endpoint confirmé, et la forme de la réponse
    `completed` DIFFÈRE de l'hypothèse initiale `{"results": [{"url": ...}]}` : la doc
    montre plutôt des clés dédiées par type de média, ex. `"images": [{"url": ...}]`
    pour de la génération d'image et `"video": {"url": ...}` pour de la vidéo.
    `poll()` (Task 3, ci-dessous) consomme ce endpoint ; `_result_url()` utilise la
    clé dédiée `"video"` en priorité et conserve `results[].url`/`result.url`/`url`
    comme replis (l'API peut varier selon le modèle) — voir la docstring de
    `_result_url` pour l'ordre exact.
  - Champ image (i2v) et champ durée : NON CONFIRMÉS par la doc consultée (les
    exemples de la page ne couvrent que `prompt`/`aspect_ratio`/`resolution`).
    Hypothèses à vérifier dans les Tasks 3–5 : `"image"` (data-URL acceptée) et
    `"duration"` (secondes) — non utilisés dans ce module.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import httpx
import typer
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict

from ..config import HiggsfieldProviderConfig
from ..errors import raise_with_hint
from ..paths import asset_path
from ..prompts import encode_image_data_url
from ..targets import KindSpec, Target
from .base import AssetJob

SUBMIT_TIMEOUT = 60.0
_TERMINAL_FAILURES = ("failed", "nsfw")
_RESULT_URL_KEYS = ("url", "raw_url", "video_url")


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


def poll(cfg, request_id: str, *, api_key: str, api_secret: str,
         sleep: Callable[[float], None] = time.sleep,
         on_status: Optional[Callable[[str], None]] = None,
         kind: str = "video") -> dict:
    status_url = f"{cfg.base_url}/requests/{request_id}/status"
    headers = _auth_headers(api_key, api_secret)
    elapsed = 0.0
    last_status: Optional[str] = None
    while True:
        response = httpx.get(status_url, headers=headers, timeout=SUBMIT_TIMEOUT)
        if response.is_error:
            raise_with_hint(response, provider_type="higgsfield", asset="video", kind=kind)
        payload = response.json()
        status = str(payload.get("status", ""))
        if status != last_status:
            if on_status is not None:
                on_status(status)
            last_status = status
        if status == "completed":
            return payload
        if status in _TERMINAL_FAILURES:
            raise RuntimeError(
                f"Higgsfield : requête {request_id} terminée en '{status}' "
                "(requête remboursée automatiquement). Ajuste le prompt et relance.")
        if elapsed >= cfg.poll_timeout_s:
            raise RuntimeError(
                f"Higgsfield : délai dépassé pour la requête {request_id} "
                f"(dernier statut : '{status}') — augmente poll_timeout_s "
                f"(actuel : {cfg.poll_timeout_s:g}s) ou réessaie.")
        sleep(cfg.poll_interval_s)
        elapsed += cfg.poll_interval_s


def _result_url(payload: dict) -> str:
    """Extrait l'URL du résultat d'une réponse `completed`.

    Ordre de priorité (voir NB en tête de module) :
      1. `video.url` — clé DÉDIÉE CONFIRMÉE par docs.higgsfield.ai pour un asset
         vidéo (`{"video": {"url": ...}}`), par symétrie avec `{"images": [...]}`
         pour la génération d'image. C'est la forme attendue en pratique par ce
         module (provider vidéo).
      2. `results[0].url` / `results[0]` (str) — forme hypothétique initiale du
         brief, conservée en repli : l'API peut varier selon le modèle.
      3. `result.url`.
      4. `url` à la racine du payload.
    Si aucune de ces formes ne correspond : RuntimeError pointant vers la doc.
    """
    video = payload.get("video")
    if isinstance(video, dict):
        for key in _RESULT_URL_KEYS:
            if video.get(key):
                return str(video[key])

    results = payload.get("results")
    if isinstance(results, list) and results:
        first = results[0]
        if isinstance(first, dict):
            for key in _RESULT_URL_KEYS:
                if first.get(key):
                    return str(first[key])
        if isinstance(first, str) and first:
            return first

    result = payload.get("result")
    if isinstance(result, dict):
        for key in _RESULT_URL_KEYS:
            if result.get(key):
                return str(result[key])

    if payload.get("url"):
        return str(payload["url"])

    raise RuntimeError(
        "Higgsfield : réponse 'completed' sans URL de résultat reconnue — vérifie le "
        "format de GET /requests/{id}/status sur docs.higgsfield.ai.")


DOWNLOAD_TIMEOUT = 300.0


class HiggsfieldVideoOptions(BaseModel):
    """Options acceptées dans generate: pour (higgsfield, video)."""
    model_config = ConfigDict(extra="forbid")
    model: str
    aspect_ratio: Optional[str] = None
    resolution: Optional[str] = None
    duration_s: Optional[float] = None


def _video_body(target: Target, options: HiggsfieldVideoOptions) -> dict:
    body: dict = {"prompt": target.text}
    if options.aspect_ratio:
        body["aspect_ratio"] = options.aspect_ratio
    if options.resolution:
        body["resolution"] = options.resolution
    duration = target.settings.get("duration_s", options.duration_s)
    if duration is not None:
        # Nom du champ côté API à confronter à docs.higgsfield.ai ('duration', secondes).
        body["duration"] = duration
    return body


@dataclass(frozen=True)
class HiggsfieldProvider:
    api_key_env: str
    api_secret_env: str
    base_url: str
    default_image_model: str
    poll_interval_s: float
    poll_timeout_s: float
    sleep: Callable[[float], None] = time.sleep

    @classmethod
    def from_config(cls, cfg: HiggsfieldProviderConfig) -> "HiggsfieldProvider":
        return cls(api_key_env=cfg.api_key_env, api_secret_env=cfg.api_secret_env,
                   base_url=cfg.base_url, default_image_model=cfg.default_image_model,
                   poll_interval_s=cfg.poll_interval_s, poll_timeout_s=cfg.poll_timeout_s)

    def plan(self, spec: KindSpec) -> list[AssetJob]:
        if spec.asset != "video":
            raise ValueError(
                f"provider higgsfield : asset '{spec.asset}' non géré en P3a — seuls "
                "les kinds video sont acceptés (l'image Higgsfield arrive en P3b).")
        options = HiggsfieldVideoOptions(**spec.options)
        jobs: list[AssetJob] = []
        for target in spec.targets:
            body = _video_body(target, options)
            summary_body = dict(body)
            payload: dict = {"kind": spec.kind}
            if target.source_image is not None:
                summary_body["image"] = f"[image source : {target.source_image}]"
                if target.source_image.exists():
                    body = {**body, "image": encode_image_data_url(target.source_image)}
                else:
                    payload["missing_source"] = (
                        f"art source manquant : {target.source_image} — génère d'abord "
                        "l'art du kind source (forge generate).")
            payload["submit"] = build_submit(options.model, body)
            jobs.append(AssetJob(
                id=target.id,
                dest=asset_path(spec.root, "video", spec.kind, target.id),
                request={"path": payload["submit"]["path"], "json": summary_body},
                payload=payload,
                notes=target.notes,
            ))
        return jobs

    def _require_keys(self) -> tuple[str, str]:
        load_dotenv()
        key = os.environ.get(self.api_key_env)
        secret = os.environ.get(self.api_secret_env)
        missing = [name for name, value in ((self.api_key_env, key),
                                            (self.api_secret_env, secret)) if not value]
        if missing:
            raise RuntimeError(
                f"{' et '.join(missing)} manquant(s) : copie .env.example vers .env et "
                "renseigne tes clés (crée-les sur https://platform.higgsfield.ai).")
        return key, secret

    def execute(self, job: AssetJob) -> list[Path]:
        missing_source = job.payload.get("missing_source")
        if missing_source:
            raise RuntimeError(missing_source)
        api_key, api_secret = self._require_keys()
        kind = str(job.payload.get("kind", "video"))
        request_id = submit(self, job.payload["submit"],
                            api_key=api_key, api_secret=api_secret, kind=kind)
        typer.echo(f"  {job.id}: requête higgsfield {request_id}")
        payload = poll(self, request_id, api_key=api_key, api_secret=api_secret,
                       sleep=self.sleep, kind=kind,
                       on_status=lambda status: typer.echo(f"  {job.id}: {status}"))
        url = _result_url(payload)
        response = httpx.get(url, timeout=DOWNLOAD_TIMEOUT)
        response.raise_for_status()
        job.dest.parent.mkdir(parents=True, exist_ok=True)
        job.dest.write_bytes(response.content)
        return [job.dest]
