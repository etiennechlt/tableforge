import json
from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from tableforge.cli import app
from tableforge.config import ElevenLabsProviderConfig, load_project
from tableforge.voices import (
    elevenlabs_config,
    fetch_voices,
    format_voice_lines,
    resolve_api_key,
)

runner = CliRunner()

FORGE = """
project: demo
providers:
  eleven:
    type: elevenlabs
voices:
  narrateur: id-abc
kinds: {}
"""


def _project(tmp_path: Path, forge: str = FORGE):
    (tmp_path / "forge.yaml").write_text(forge, encoding="utf-8")
    return load_project(tmp_path)


def test_elevenlabs_config_requires_declared_provider(tmp_path):
    # "manual" est un type réservé/rejeté par config.py (cf. fix P1) : on utilise un
    # autre type de provider valide mais non-elevenlabs pour exercer ce cas.
    forge = FORGE.replace("type: elevenlabs", "type: higgsfield").replace("eleven:", "outil:")
    project = _project(tmp_path, forge)

    with pytest.raises(ValueError, match="elevenlabs"):
        elevenlabs_config(project)


def test_resolve_api_key_missing_raises_french_error(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="ELEVENLABS_API_KEY"):
        resolve_api_key("ELEVENLABS_API_KEY")


def test_format_voice_lines_marks_mapped_voices():
    voices = [{"voice_id": "id-abc", "name": "George"},
              {"voice_id": "id-zzz", "name": "Alice"}]

    lines = format_voice_lines(voices, {"narrateur": "id-abc"})

    assert lines[0] == "- George  (id-abc)  → mappée : narrateur"
    assert lines[1] == "- Alice  (id-zzz)"


@respx.mock
def test_fetch_voices_sends_api_key_header():
    cfg = ElevenLabsProviderConfig(type="elevenlabs")
    route = respx.get("https://api.elevenlabs.io/v1/voices").mock(
        return_value=httpx.Response(200, json={"voices": [{"voice_id": "v", "name": "N"}]}))

    voices = fetch_voices(cfg, "sk-test")

    assert voices == [{"voice_id": "v", "name": "N"}]
    assert route.calls.last.request.headers["xi-api-key"] == "sk-test"


@respx.mock
def test_cli_voices_list_shows_mapping(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test")
    (tmp_path / "forge.yaml").write_text(FORGE, encoding="utf-8")
    respx.get("https://api.elevenlabs.io/v1/voices").mock(
        return_value=httpx.Response(200, json={"voices": [
            {"voice_id": "id-abc", "name": "George"},
            {"voice_id": "id-zzz", "name": "Alice"},
        ]}))

    res = runner.invoke(app, ["voices", "list", "--project", str(tmp_path)])

    assert res.exit_code == 0, res.output
    assert "George" in res.output and "id-abc" in res.output
    assert "mappée : narrateur" in res.output
    alice_line = next(line for line in res.output.splitlines() if "Alice" in line)
    assert "mappée" not in alice_line


def test_cli_voices_list_without_api_key_shows_clean_error(tmp_path, monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    (tmp_path / "forge.yaml").write_text(FORGE, encoding="utf-8")

    res = runner.invoke(app, ["voices", "list", "--project", str(tmp_path)])

    assert res.exit_code != 0
    assert "ELEVENLABS_API_KEY" in res.output
    assert "Traceback" not in res.output


def test_cli_voices_design_without_api_key_shows_clean_error(tmp_path, monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    (tmp_path / "forge.yaml").write_text(FORGE, encoding="utf-8")

    res = runner.invoke(app, ["voices", "design", "vieille reine rauque",
                              "--project", str(tmp_path)])

    assert res.exit_code != 0
    assert "ELEVENLABS_API_KEY" in res.output
    assert "Traceback" not in res.output


@respx.mock
def test_design_previews_posts_description():
    from tableforge.voices import design_previews

    cfg = ElevenLabsProviderConfig(type="elevenlabs")
    route = respx.post("https://api.elevenlabs.io/v1/text-to-voice/design").mock(
        return_value=httpx.Response(200, json={"previews": [
            {"generated_voice_id": "gen-1"}, {"generated_voice_id": "gen-2"}]}))

    previews = design_previews(cfg, "sk-test", "vieille reine rauque")

    assert [p["generated_voice_id"] for p in previews] == ["gen-1", "gen-2"]
    request = route.calls.last.request
    assert request.headers["xi-api-key"] == "sk-test"
    body = json.loads(request.content)
    assert body["voice_description"] == "vieille reine rauque"


@respx.mock
def test_save_voice_returns_voice_id():
    from tableforge.voices import save_voice

    cfg = ElevenLabsProviderConfig(type="elevenlabs")
    route = respx.post("https://api.elevenlabs.io/v1/text-to-voice").mock(
        return_value=httpx.Response(200, json={"voice_id": "id-new"}))

    voice_id = save_voice(cfg, "sk-test", name="vieille-reine",
                          description="vieille reine rauque", generated_voice_id="gen-1")

    assert voice_id == "id-new"
    body = json.loads(route.calls.last.request.content)
    assert body == {"voice_name": "vieille-reine",
                    "voice_description": "vieille reine rauque",
                    "generated_voice_id": "gen-1"}


@respx.mock
def test_cli_voices_design_without_save_lists_previews(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test")
    (tmp_path / "forge.yaml").write_text(FORGE, encoding="utf-8")
    respx.post("https://api.elevenlabs.io/v1/text-to-voice/design").mock(
        return_value=httpx.Response(200, json={"previews": [
            {"generated_voice_id": "gen-1"}]}))

    res = runner.invoke(app, ["voices", "design", "vieille reine rauque",
                              "--project", str(tmp_path)])

    assert res.exit_code == 0, res.output
    assert "gen-1" in res.output
    assert "--save" in res.output


@respx.mock
def test_cli_voices_design_save_prints_yaml_snippet(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test")
    (tmp_path / "forge.yaml").write_text(FORGE, encoding="utf-8")
    respx.post("https://api.elevenlabs.io/v1/text-to-voice/design").mock(
        return_value=httpx.Response(200, json={"previews": [
            {"generated_voice_id": "gen-1"}]}))
    respx.post("https://api.elevenlabs.io/v1/text-to-voice").mock(
        return_value=httpx.Response(200, json={"voice_id": "id-new"}))

    res = runner.invoke(app, ["voices", "design", "vieille reine rauque",
                              "--name", "vieille-reine", "--save",
                              "--project", str(tmp_path)])

    assert res.exit_code == 0, res.output
    assert "id-new" in res.output
    assert "vieille-reine: id-new" in res.output


def test_cli_voices_design_save_requires_name(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test")
    (tmp_path / "forge.yaml").write_text(FORGE, encoding="utf-8")

    res = runner.invoke(app, ["voices", "design", "desc", "--save",
                              "--project", str(tmp_path)])

    assert res.exit_code != 0
