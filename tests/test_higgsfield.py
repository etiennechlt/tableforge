import json

import httpx
import pytest
import respx

from tableforge.config import HiggsfieldProviderConfig
from tableforge.providers.higgsfield import build_submit, submit

BASE = "https://platform.higgsfield.ai"


def _cfg(**overrides):
    fields = {"type": "higgsfield", "poll_interval_s": 5.0, "poll_timeout_s": 12.0}
    fields.update(overrides)
    return HiggsfieldProviderConfig(**fields)


def test_build_submit_prefixes_slug_as_path():
    # Arrange / Act
    req = build_submit("bytedance/seedance/v1/image-to-video", {"prompt": "wind"})

    # Assert
    assert req == {"path": "/bytedance/seedance/v1/image-to-video",
                   "json": {"prompt": "wind"}}


def test_build_submit_copies_body():
    # Arrange
    body = {"prompt": "wind"}

    # Act
    req = build_submit("slug", body)
    req["json"]["prompt"] = "mutated"

    # Assert — le dict d'origine n'est pas modifié
    assert body == {"prompt": "wind"}


@respx.mock
def test_submit_posts_body_with_key_header_and_returns_request_id():
    # Arrange
    route = respx.post(f"{BASE}/bytedance/seedance/v1/image-to-video").mock(
        return_value=httpx.Response(200, json={"request_id": "req-42"}))
    req = build_submit("bytedance/seedance/v1/image-to-video", {"prompt": "wind"})

    # Act
    request_id = submit(_cfg(), req, api_key="k", api_secret="s")

    # Assert
    assert request_id == "req-42"
    sent = route.calls.last.request
    assert sent.headers["authorization"] == "Key k:s"
    assert json.loads(sent.content) == {"prompt": "wind"}


@respx.mock
def test_submit_without_request_id_raises_french_error():
    # Arrange
    respx.post(f"{BASE}/some/slug").mock(return_value=httpx.Response(200, json={}))

    # Act / Assert
    with pytest.raises(RuntimeError, match="request_id"):
        submit(_cfg(), build_submit("some/slug", {"prompt": "x"}),
               api_key="k", api_secret="s")


@respx.mock
def test_submit_http_error_goes_through_hints():
    # Arrange — 404 : slug de modèle inconnu
    respx.post(f"{BASE}/bad/slug").mock(return_value=httpx.Response(404, json={}))

    # Act / Assert — raise_with_hint (errors.py, P1) doit lever ; adapte le type
    # d'exception ici si P1 a retenu autre chose que RuntimeError.
    with pytest.raises(RuntimeError):
        submit(_cfg(), build_submit("bad/slug", {"prompt": "x"}),
               api_key="k", api_secret="s")
