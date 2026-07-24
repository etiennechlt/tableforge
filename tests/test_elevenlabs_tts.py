import json
from pathlib import Path

import httpx
import respx

from tableforge.config import load_project
from tableforge.providers.elevenlabs import (
    DIALOGUE_SOFT_LIMIT,
    ElevenLabsProvider,
    build_dialogue_request,
    build_tts_request,
)
from tableforge.targets import DialogueLine, build_kind_spec


def test_build_tts_request_shapes_path_body_and_params():
    req = build_tts_request("Bonjour.", voice_id="V1", model="eleven_multilingual_v2",
                            language="fr", seed=7, output_format="mp3_44100_128")

    assert req["path"] == "/v1/text-to-speech/V1"
    assert req["json"] == {"text": "Bonjour.", "model_id": "eleven_multilingual_v2",
                           "language_code": "fr", "seed": 7}
    assert req["params"] == {"output_format": "mp3_44100_128"}


def test_build_tts_request_omits_optional_fields():
    req = build_tts_request("Salut", voice_id="V1", model="m", output_format="mp3_44100_128")

    assert "language_code" not in req["json"]
    assert "seed" not in req["json"]


def test_build_dialogue_request_maps_lines_in_order():
    lines = (DialogueLine(voice_id="V1", text="Oyez !"),
             DialogueLine(voice_id="V2", text="Silence."))

    req = build_dialogue_request(lines, model="eleven_v3", output_format="mp3_44100_128")

    assert req["path"] == "/v1/text-to-dialogue"
    assert req["json"] == {"inputs": [{"text": "Oyez !", "voice_id": "V1"},
                                      {"text": "Silence.", "voice_id": "V2"}],
                           "model_id": "eleven_v3"}
    assert req["params"] == {"output_format": "mp3_44100_128"}


def test_dialogue_soft_limit_is_two_thousand_chars():
    assert DIALOGUE_SOFT_LIMIT == 2000
