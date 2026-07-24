import pytest
from pydantic import ValidationError

from tableforge.providers.base import options_model


def test_tts_options_accept_contract_keys():
    model = options_model("elevenlabs", "tts")

    opts = model(voice="narrateur", voice_field="voice", text="{{ name }}",
                 model="eleven_v3", language="fr", seed=3)

    assert opts.voice == "narrateur"
    assert opts.seed == 3


def test_tts_options_reject_unknown_key():
    model = options_model("elevenlabs", "tts")

    with pytest.raises(ValidationError):
        model(pitch=2)


def test_dialogue_options_accept_model_only():
    model = options_model("elevenlabs", "dialogue")

    opts = model(model="eleven_v3")

    assert opts.model == "eleven_v3"


def test_dialogue_options_reject_voice_key():
    model = options_model("elevenlabs", "dialogue")

    with pytest.raises(ValidationError):
        model(voice="narrateur")
