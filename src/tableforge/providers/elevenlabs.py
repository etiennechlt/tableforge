"""Provider audio ElevenLabs — REST direct httpx, mockable respx.

P1 : music (POST /v1/music) + sfx/soundscapes (POST /v1/sound-generation, loop).
P2 ajoutera tts et dialogue. `plan()` est pur (aucune clé) ; `execute()` est le
seul point qui lit la clé (dotenv + env) et touche le réseau.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import httpx
from dotenv import load_dotenv

from ..catalog import clamp_music_length_ms, clamp_sfx_duration_s
from ..errors import raise_with_hint
from ..paths import asset_path
from .base import AssetJob

if TYPE_CHECKING:  # pragma: no cover
    from ..config import ElevenLabsProviderConfig
    from ..targets import KindSpec

MUSIC_PATH = "/v1/music"
SFX_PATH = "/v1/sound-generation"
DEFAULT_TIMEOUT = 180.0


def build_music_request(prompt: str, *, length_ms: int, output_format: str) -> dict:
    return {
        "path": MUSIC_PATH,
        "json": {"prompt": prompt, "music_length_ms": clamp_music_length_ms(length_ms)},
        "params": {"output_format": output_format},
    }


def build_sfx_request(text: str, *, duration_s: Optional[float], loop: bool, model: str,
                      output_format: str) -> dict:
    body: dict = {"text": text, "model_id": model, "loop": bool(loop)}
    if duration_s is not None:
        body["duration_seconds"] = clamp_sfx_duration_s(duration_s)
    return {"path": SFX_PATH, "json": body, "params": {"output_format": output_format}}


@dataclass(frozen=True)
class ElevenLabsProvider:
    api_key_env: str
    base_url: str
    output_format: str
    sfx_model: str
    tts_model: str
    dialogue_model: str

    @classmethod
    def from_config(cls, cfg: "ElevenLabsProviderConfig") -> "ElevenLabsProvider":
        return cls(api_key_env=cfg.api_key_env, base_url=cfg.base_url,
                   output_format=cfg.output_format, sfx_model=cfg.sfx_model,
                   tts_model=cfg.tts_model, dialogue_model=cfg.dialogue_model)

    def plan(self, spec: "KindSpec") -> list[AssetJob]:
        if spec.asset not in ("music", "sfx"):
            raise NotImplementedError(
                f"elevenlabs : asset '{spec.asset}' pas encore pris en charge (P2)")
        output_format = spec.output_format or self.output_format
        jobs: list[AssetJob] = []
        for target in spec.targets:
            if spec.asset == "music":
                req = build_music_request(target.text,
                                          length_ms=target.settings["length_ms"],
                                          output_format=output_format)
            else:
                req = build_sfx_request(target.text,
                                        duration_s=target.settings.get("duration_s"),
                                        loop=bool(target.settings.get("loop", False)),
                                        model=self.sfx_model,
                                        output_format=output_format)
            dest = asset_path(spec.root, spec.asset, spec.kind, target.id, output_format)
            jobs.append(AssetJob(id=target.id, dest=dest, request=req,
                                 payload={**req, "asset": spec.asset, "kind": spec.kind},
                                 notes=target.notes))
        return jobs

    def _require_key(self) -> str:
        load_dotenv()
        key = os.environ.get(self.api_key_env)
        if not key:
            raise RuntimeError(
                f"{self.api_key_env} manquant : copie .env.example vers .env et renseigne "
                "ta clé ElevenLabs (https://elevenlabs.io/app/settings/api-keys).")
        return key

    def execute(self, job: AssetJob) -> list[Path]:
        key = self._require_key()
        response = httpx.post(
            self.base_url + job.payload["path"],
            headers={"xi-api-key": key},
            json=job.payload["json"],
            params=job.payload["params"],
            timeout=DEFAULT_TIMEOUT,
        )
        raise_with_hint(response, provider_type="elevenlabs",
                        asset=job.payload["asset"], kind=job.payload["kind"])
        dest = Path(job.dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(response.content)
        return [dest]
