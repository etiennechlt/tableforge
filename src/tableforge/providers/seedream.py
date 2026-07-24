"""Provider d'images Seedream (BytePlus Ark, compatible OpenAI-images), configurable."""
from __future__ import annotations

import base64
import copy
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv

from ..config import ProviderConfig
from ..paths import asset_path
from .base import AssetJob

DEFAULT_SEQUENTIAL = "auto"


def build_request(*, model: str, size: str, refs: list[str], watermark: bool,
                  output_format: str, sequential: str = DEFAULT_SEQUENTIAL,
                  response_format: str = "url") -> dict:
    extra: dict = {
        "watermark": watermark,
        "sequential_image_generation": sequential,
        "output_format": output_format,
    }
    if refs:
        extra["image"] = list(refs)
    return {"model": model, "prompt": "", "size": size,
            "response_format": response_format, "extra_body": extra}


def summarize_request(req: dict) -> dict:
    summary = copy.deepcopy(req)
    images = summary.get("extra_body", {}).get("image")
    if images is not None:
        summary["extra_body"]["image"] = f"[{len(images)} référence(s), data-URLs omises]"
    return summary


def _save_image(item, dest: Path) -> Path:
    dest = Path(dest)
    b64 = getattr(item, "b64_json", None)
    if b64:
        dest.write_bytes(base64.b64decode(b64))
        return dest
    url = getattr(item, "url", None)
    if not url:
        raise RuntimeError("réponse sans image (ni url ni b64_json)")
    response = httpx.get(url, timeout=120.0)
    response.raise_for_status()
    dest.write_bytes(response.content)
    return dest


@dataclass(frozen=True)
class SeedreamProvider:
    api_key: Optional[str]
    base_url: str
    model: str
    default_size: str
    watermark: bool
    output_format: str
    api_key_env: Optional[str] = None

    @classmethod
    def from_config(cls, cfg: ProviderConfig) -> "SeedreamProvider":
        # v1 (compat tests) : résout la clé IMMÉDIATEMENT et échoue si absente.
        load_dotenv()
        key = os.environ.get(cfg.api_key_env)
        if not key:
            raise RuntimeError(
                f"{cfg.api_key_env} manquant : copie .env.example vers .env et renseigne ta clé.")
        return cls(api_key=key, base_url=cfg.base_url, model=cfg.model,
                   default_size=cfg.default_size, watermark=cfg.watermark,
                   output_format=cfg.output_format, api_key_env=cfg.api_key_env)

    @classmethod
    def from_provider_config(cls, cfg: ProviderConfig) -> "SeedreamProvider":
        # v2 : keyless — la clé n'est lue qu'à execute() (_require_key).
        return cls(api_key=None, base_url=cfg.base_url, model=cfg.model,
                   default_size=cfg.default_size, watermark=cfg.watermark,
                   output_format=cfg.output_format, api_key_env=cfg.api_key_env)

    def _require_key(self) -> str:
        if self.api_key:
            return self.api_key
        load_dotenv()
        key = os.environ.get(self.api_key_env or "")
        if not key:
            raise RuntimeError(
                f"{self.api_key_env} manquant : copie .env.example vers .env et renseigne ta clé.")
        return key

    def build(self, prompt: str, size: Optional[str] = None,
              refs: Optional[list[str]] = None) -> dict:
        req = build_request(model=self.model, size=size or self.default_size,
                            refs=refs or [], watermark=self.watermark,
                            output_format=self.output_format)
        req["prompt"] = prompt
        return req

    def plan(self, spec) -> list[AssetJob]:
        jobs = []
        for target in spec.targets:
            size = target.settings.get("size") or self.default_size
            refs = list(target.refs)
            request = summarize_request(self.build(target.text, size=size, refs=refs))
            dest = asset_path(spec.root, spec.asset, spec.kind, target.id,
                              spec.output_format)
            jobs.append(AssetJob(id=target.id, dest=dest, request=request,
                                 payload={"prompt": target.text, "size": size,
                                          "refs": refs},
                                 notes=tuple(target.notes)))
        return jobs

    def execute(self, job: AssetJob) -> list[Path]:  # pragma: no cover — réseau
        return self.generate(job.payload["prompt"], job.dest,
                             size=job.payload.get("size"),
                             refs=job.payload.get("refs") or None)

    def _client(self):  # pragma: no cover
        from openai import OpenAI
        return OpenAI(api_key=self._require_key(), base_url=self.base_url,
                      max_retries=3, timeout=180.0)

    def generate(self, prompt: str, dest: Path, size: Optional[str] = None,
                 refs: Optional[list[str]] = None) -> list[Path]:  # pragma: no cover
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        response = self._client().images.generate(**self.build(prompt, size, refs))
        saved = [_save_image(response.data[0], dest)]
        for index, item in enumerate(response.data[1:], start=2):
            saved.append(_save_image(item, dest.with_name(f"{dest.stem}-{index}.png")))
        return saved
