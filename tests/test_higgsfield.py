import json

import httpx
import pytest
import respx

from tableforge.config import HiggsfieldProviderConfig
from tableforge.providers.higgsfield import _result_url, build_submit, poll, submit

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


def _status_route(sequence):
    return respx.get(f"{BASE}/requests/req-42/status").mock(
        side_effect=[httpx.Response(200, json=payload) for payload in sequence])


@respx.mock
def test_poll_reports_transitions_and_returns_completed_payload():
    # Arrange — payload 'completed' au format VÉRIFIÉ (Task 2) : clé dédiée
    # "video" (dict avec "url"), pas "results[].url".
    route = _status_route([
        {"status": "queued"},
        {"status": "in_progress"},
        {"status": "completed", "video": {"url": "https://cdn.x/v.mp4"}},
    ])
    seen, sleeps = [], []

    # Act
    payload = poll(_cfg(), "req-42", api_key="k", api_secret="s",
                   sleep=sleeps.append, on_status=seen.append)

    # Assert
    assert seen == ["queued", "in_progress", "completed"]
    assert sleeps == [5.0, 5.0]
    assert payload["video"]["url"] == "https://cdn.x/v.mp4"
    assert route.calls.last.request.headers["authorization"] == "Key k:s"


@respx.mock
def test_poll_does_not_repeat_unchanged_status():
    # Arrange
    _status_route([{"status": "queued"}, {"status": "queued"},
                   {"status": "completed", "video": {"url": "u"}}])
    seen = []

    # Act
    poll(_cfg(), "req-42", api_key="k", api_secret="s",
         sleep=lambda _s: None, on_status=seen.append)

    # Assert
    assert seen == ["queued", "completed"]


@pytest.mark.parametrize("status", ["failed", "nsfw"])
def test_poll_failed_and_nsfw_raise_refunded_error(status):
    # Arrange
    with respx.mock:
        _status_route([{"status": status}])

        # Act / Assert
        with pytest.raises(RuntimeError, match="remboursée automatiquement"):
            poll(_cfg(), "req-42", api_key="k", api_secret="s", sleep=lambda _s: None)


@respx.mock
def test_poll_http_error_goes_through_hints():
    # Arrange — 404 : request_id inconnu/expiré
    respx.get(f"{BASE}/requests/req-42/status").mock(return_value=httpx.Response(404, json={}))

    # Act / Assert
    with pytest.raises(RuntimeError):
        poll(_cfg(), "req-42", api_key="k", api_secret="s", sleep=lambda _s: None)


@respx.mock
def test_poll_times_out_with_explicit_error():
    # Arrange — statut qui ne progresse jamais ; timeout 12 s, intervalle 5 s
    respx.get(f"{BASE}/requests/req-42/status").mock(
        return_value=httpx.Response(200, json={"status": "queued"}))
    sleeps = []

    # Act / Assert
    with pytest.raises(RuntimeError, match="poll_timeout_s"):
        poll(_cfg(), "req-42", api_key="k", api_secret="s", sleep=sleeps.append)
    assert sleeps == [5.0, 5.0, 5.0]


def test_result_url_uses_verified_video_key():
    # Arrange / Act / Assert — schéma CONFIRMÉ (Task 2, docs.higgsfield.ai) :
    # {"video": {"url": ...}} pour un asset vidéo.
    assert _result_url({"status": "completed",
                        "video": {"url": "https://cdn.x/v.mp4"}}) == "https://cdn.x/v.mp4"


def test_result_url_prefers_video_key_over_fallback_shapes():
    # Arrange / Act / Assert — quand "video" est présent, il gagne sur "results"
    payload = {"video": {"url": "primary"}, "results": [{"url": "secondary"}]}
    assert _result_url(payload) == "primary"


def test_result_url_fallbacks_when_video_key_absent():
    # Arrange / Act / Assert — formes de repli (l'API peut varier selon le modèle)
    assert _result_url({"results": [{"url": "a"}]}) == "a"
    assert _result_url({"results": ["b"]}) == "b"
    assert _result_url({"result": {"url": "c"}}) == "c"
    assert _result_url({"url": "d"}) == "d"
    with pytest.raises(RuntimeError, match="docs.higgsfield.ai"):
        _result_url({"status": "completed"})
