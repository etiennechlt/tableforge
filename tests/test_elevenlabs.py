import json
from pathlib import Path

import httpx
import pytest
import respx

from tableforge.config import ElevenLabsProviderConfig, load_project
from tableforge.providers.base import AssetJob
from tableforge.providers.elevenlabs import (
    ElevenLabsProvider,
    build_music_request,
    build_sfx_request,
)
from tableforge.targets import KindSpec, Target, build_kind_spec


def _provider() -> ElevenLabsProvider:
    return ElevenLabsProvider.from_config(ElevenLabsProviderConfig(type="elevenlabs"))


def _music_job(dest: Path) -> AssetJob:
    return AssetJob(
        id="menu", dest=dest,
        request={},
        payload={"path": "/v1/music",
                 "json": {"prompt": "p", "music_length_ms": 90000},
                 "params": {"output_format": "mp3_44100_128"},
                 "asset": "music", "kind": "musiques"})


def test_build_music_request_shape_and_clamp():
    req = build_music_request("A theme", length_ms=700000, output_format="mp3_44100_128")
    assert req["path"] == "/v1/music"
    assert req["json"] == {"prompt": "A theme", "music_length_ms": 600000}
    assert req["params"] == {"output_format": "mp3_44100_128"}


def test_build_sfx_request_with_duration_and_loop():
    req = build_sfx_request("A swish", duration_s=60, loop=True,
                            model="eleven_text_to_sound_v2", output_format="mp3_44100_128")
    assert req["path"] == "/v1/sound-generation"
    assert req["json"] == {"text": "A swish", "model_id": "eleven_text_to_sound_v2",
                           "loop": True, "duration_seconds": 30.0}


def test_build_sfx_request_without_duration_lets_api_choose():
    req = build_sfx_request("A click", duration_s=None, loop=False,
                            model="eleven_text_to_sound_v2", output_format="mp3_44100_128")
    assert "duration_seconds" not in req["json"]
    assert req["json"]["loop"] is False


def test_from_config_stores_env_name_not_key(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-secret")
    provider = _provider()
    assert provider.api_key_env == "ELEVENLABS_API_KEY"
    assert "sk-secret" not in repr(provider)


def test_plan_builds_music_jobs_with_dest():
    spec = KindSpec(kind="musiques", asset="music", provider_name="eleven", options={},
                    targets=(Target(id="menu", text="Theme. Epic.",
                                    settings={"length_ms": 90000}),),
                    output_format=None, root=Path("/proj"))
    jobs = _provider().plan(spec)
    assert len(jobs) == 1
    assert jobs[0].dest == Path("/proj/out/audio/musiques/menu.mp3")
    assert jobs[0].request["json"] == {"prompt": "Theme. Epic.", "music_length_ms": 90000}
    assert jobs[0].payload["asset"] == "music"
    assert jobs[0].payload["kind"] == "musiques"


def test_plan_builds_sfx_jobs_with_loop_and_notes():
    spec = KindSpec(kind="nappes", asset="sfx", provider_name="eleven", options={},
                    targets=(Target(id="cite", text="Murmur. Ambient.",
                                    settings={"loop": True, "duration_s": 30.0},
                                    notes=("clamp",)),),
                    output_format="mp3_44100_128", root=Path("/proj"))
    jobs = _provider().plan(spec)
    assert jobs[0].dest == Path("/proj/out/audio/nappes/cite.mp3")
    assert jobs[0].request["json"]["loop"] is True
    assert jobs[0].request["json"]["duration_seconds"] == 30.0
    assert jobs[0].request["json"]["model_id"] == "eleven_text_to_sound_v2"
    assert jobs[0].notes == ("clamp",)


def test_plan_unsupported_asset_raises():
    spec = KindSpec(kind="clip", asset="video", provider_name="eleven", options={},
                    targets=(), output_format=None, root=Path("/proj"))
    with pytest.raises(NotImplementedError, match="video"):
        _provider().plan(spec)


@respx.mock
def test_execute_music_posts_and_writes_bytes(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test")
    route = respx.post("https://api.elevenlabs.io/v1/music").mock(
        return_value=httpx.Response(200, content=b"MP3BYTES"))
    dest = tmp_path / "menu.mp3"
    saved = _provider().execute(_music_job(dest))
    assert saved == [dest]
    assert dest.read_bytes() == b"MP3BYTES"
    request = route.calls.last.request
    assert request.headers["xi-api-key"] == "sk-test"
    assert request.url.params["output_format"] == "mp3_44100_128"
    assert json.loads(request.content) == {"prompt": "p", "music_length_ms": 90000}


@respx.mock
def test_execute_sfx_posts_to_sound_generation(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test")
    route = respx.post("https://api.elevenlabs.io/v1/sound-generation").mock(
        return_value=httpx.Response(200, content=b"SFX"))
    dest = tmp_path / "cite.mp3"
    job = AssetJob(id="cite", dest=dest, request={},
                   payload={"path": "/v1/sound-generation",
                            "json": {"text": "t", "model_id": "eleven_text_to_sound_v2",
                                     "loop": True, "duration_seconds": 30.0},
                            "params": {"output_format": "mp3_44100_128"},
                            "asset": "sfx", "kind": "nappes"})
    _provider().execute(job)
    assert dest.read_bytes() == b"SFX"
    assert json.loads(route.calls.last.request.content)["loop"] is True


@respx.mock
def test_execute_402_raises_studio_hint(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test")
    respx.post("https://api.elevenlabs.io/v1/music").mock(
        return_value=httpx.Response(402, text='{"detail": "payment required"}'))
    with pytest.raises(RuntimeError, match="forge studio musiques"):
        _provider().execute(_music_job(tmp_path / "menu.mp3"))


def test_execute_without_key_raises_french(tmp_path, monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ELEVENLABS_API_KEY"):
        _provider().execute(_music_job(tmp_path / "menu.mp3"))


# --- Item de revue Task 6 : verrouiller le chemin CLAMP NOTE sfx (targets.py
# lignes 143-144) de bout en bout, via build_kind_spec -> plan. ---

FORGE_SFX_CLAMP = """
project: demo-clamp
providers:
  eleven: { type: elevenlabs }
kinds:
  nappes:
    asset: sfx
    prompts: prompts/nappes.yaml
    generate: { with: eleven }
"""

NAPPES_CLAMP = """
direction: "Ambient loop."
entries:
  cite: { prompt: "City murmur", duration_s: 45 }
"""


def test_sfx_duration_clamp_note_end_to_end_through_plan(tmp_path):
    (tmp_path / "forge.yaml").write_text(FORGE_SFX_CLAMP, encoding="utf-8")
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "nappes.yaml").write_text(NAPPES_CLAMP, encoding="utf-8")
    project = load_project(tmp_path)

    spec = build_kind_spec(project, "nappes")
    cite = spec.targets[0]
    assert cite.settings["duration_s"] == 30.0
    assert any("45" in note and "30.0" in note for note in cite.notes)

    jobs = _provider().plan(spec)
    job = jobs[0]
    assert job.request["json"]["duration_seconds"] == 30.0
    assert job.notes == cite.notes
    assert any("hors bornes" in note for note in job.notes)
