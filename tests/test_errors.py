import httpx
import pytest

from tableforge.errors import hint_for_status, raise_with_hint


def test_hint_401_mentions_key_permissions():
    hint = hint_for_status(401, provider_type="elevenlabs", asset="music", kind="musiques")
    assert "clé" in hint


def test_hint_402_music_points_to_studio():
    hint = hint_for_status(402, provider_type="elevenlabs", asset="music", kind="musiques")
    assert "/v1/music exige un plan payant" in hint
    assert "forge studio musiques" in hint


def test_hint_402_outside_elevenlabs_music_is_none():
    assert hint_for_status(402, provider_type="seedream", asset="image", kind="cards") is None
    assert hint_for_status(402, provider_type="elevenlabs", asset="sfx", kind="sfx") is None


def test_hint_404_422_429():
    assert "modèle" in hint_for_status(404, provider_type="higgsfield", asset="video", kind="teaser")
    assert "bornes" in hint_for_status(422, provider_type="elevenlabs", asset="sfx", kind="sfx")
    assert "quota" in hint_for_status(429, provider_type="elevenlabs", asset="music", kind="musiques")


def test_hint_unknown_status_is_none():
    assert hint_for_status(500, provider_type="elevenlabs", asset="music", kind="musiques") is None


def test_raise_with_hint_passes_on_success():
    result = raise_with_hint(httpx.Response(200), provider_type="elevenlabs",
                             asset="music", kind="musiques")
    assert result is None


def test_raise_with_hint_raises_french_message_with_hint_and_detail():
    response = httpx.Response(402, text='{"detail": "payment required"}')
    with pytest.raises(RuntimeError) as exc:
        raise_with_hint(response, provider_type="elevenlabs", asset="music", kind="musiques")
    message = str(exc.value)
    assert "elevenlabs a répondu 402" in message
    assert "musiques" in message
    assert "payment required" in message
    assert "forge studio musiques" in message


def test_raise_with_hint_without_hint_still_raises():
    with pytest.raises(RuntimeError, match="a répondu 500"):
        raise_with_hint(httpx.Response(500, text="boom"), provider_type="elevenlabs",
                        asset="music", kind="musiques")
