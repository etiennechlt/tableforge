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
