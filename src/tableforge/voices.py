"""Utilitaires de voix ElevenLabs : bibliothèque du compte + design de voix."""
from __future__ import annotations

import os

import httpx
from dotenv import load_dotenv

from .config import ElevenLabsProviderConfig, ProjectConfig
from .errors import raise_with_hint

DEFAULT_TIMEOUT = 60.0


def elevenlabs_config(project: ProjectConfig) -> ElevenLabsProviderConfig:
    for cfg in project.providers.values():
        if cfg.type == "elevenlabs":
            return cfg
    raise ValueError(
        "aucun provider 'elevenlabs' déclaré dans forge.yaml — ajoute par exemple :\n"
        "providers:\n  eleven:\n    type: elevenlabs")


def resolve_api_key(env_name: str) -> str:
    load_dotenv()
    key = os.environ.get(env_name)
    if not key:
        raise RuntimeError(
            f"{env_name} manquant : copie .env.example vers .env et renseigne ta clé.")
    return key


def fetch_voices(cfg: ElevenLabsProviderConfig, api_key: str) -> list[dict]:
    response = httpx.get(f"{cfg.base_url}/v1/voices",
                         headers={"xi-api-key": api_key}, timeout=DEFAULT_TIMEOUT)
    if response.status_code >= 400:
        raise_with_hint(response, provider_type="elevenlabs", asset="tts", kind="voices")
    return list(response.json().get("voices", []))


def design_previews(cfg: ElevenLabsProviderConfig, api_key: str,
                    description: str) -> list[dict]:
    # NB: schéma de requête/réponse de /v1/text-to-voice/design déduit de la doc
    # ElevenLabs au moment de l'écriture ; champs non re-vérifiés en direct (voir
    # Open Questions du plan P2). À reconfirmer si l'API renvoie une 4xx inattendue.
    response = httpx.post(f"{cfg.base_url}/v1/text-to-voice/design",
                          headers={"xi-api-key": api_key},
                          json={"voice_description": description,
                                "auto_generate_text": True},
                          timeout=DEFAULT_TIMEOUT)
    if response.status_code >= 400:
        raise_with_hint(response, provider_type="elevenlabs", asset="tts", kind="voices")
    return list(response.json().get("previews", []))


def save_voice(cfg: ElevenLabsProviderConfig, api_key: str, *, name: str,
               description: str, generated_voice_id: str) -> str:
    # NB: idem — schéma de /v1/text-to-voice (nom des champs) supposé d'après la doc,
    # à reconfirmer en pratique.
    response = httpx.post(f"{cfg.base_url}/v1/text-to-voice",
                          headers={"xi-api-key": api_key},
                          json={"voice_name": name,
                                "voice_description": description,
                                "generated_voice_id": generated_voice_id},
                          timeout=DEFAULT_TIMEOUT)
    if response.status_code >= 400:
        raise_with_hint(response, provider_type="elevenlabs", asset="tts", kind="voices")
    return str(response.json()["voice_id"])


def format_voice_lines(voices: list[dict], mapping: dict[str, str]) -> list[str]:
    names_by_id = {voice_id: name for name, voice_id in mapping.items()}
    lines: list[str] = []
    for voice in voices:
        voice_id = str(voice.get("voice_id", "?"))
        name = str(voice.get("name", "?"))
        mapped = names_by_id.get(voice_id)
        suffix = f"  → mappée : {mapped}" if mapped else ""
        lines.append(f"- {name}  ({voice_id}){suffix}")
    return lines
