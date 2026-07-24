import httpx
import pytest
import respx

from tableforge.config import load_project
from tableforge.generate import generate_kind

FORGE = """
project: demo-audio
providers:
  eleven: { type: elevenlabs }
kinds:
  musiques:
    asset: music
    prompts: prompts/musiques.yaml
    generate: { with: eleven }
  affiche:
    asset: sfx
    prompts: prompts/sfx.yaml
    generate: { with: manual }
"""

MUSIC = """
direction: "Epic score."
defaults: { length_ms: 60000 }
entries:
  menu: { prompt: "Main theme" }
"""

SFX = """
direction: "Punchy."
entries:
  poster: { prompt: "Whoosh", duration_s: 1.0 }
"""


def _project(tmp_path):
    (tmp_path / "forge.yaml").write_text(FORGE, encoding="utf-8")
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "musiques.yaml").write_text(MUSIC, encoding="utf-8")
    (prompts / "sfx.yaml").write_text(SFX, encoding="utf-8")
    return load_project(tmp_path)


def test_music_dry_run_builds_requests_without_network(tmp_path):
    results = generate_kind(_project(tmp_path), "musiques", dry_run=True)
    assert [r.id for r in results] == ["menu"]
    assert results[0].dest is None
    req = results[0].request
    assert req["path"] == "/v1/music"
    assert req["json"]["music_length_ms"] == 60000
    assert "Main theme" in req["json"]["prompt"]


@respx.mock
def test_music_generate_writes_audio_file(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test")
    respx.post("https://api.elevenlabs.io/v1/music").mock(
        return_value=httpx.Response(200, content=b"MP3"))
    project = _project(tmp_path)
    results = generate_kind(project, "musiques")
    dest = project.root / "out" / "audio" / "musiques" / "menu.mp3"
    assert results[0].dest == dest
    assert dest.read_bytes() == b"MP3"


def test_music_skips_existing_without_force(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test")
    project = _project(tmp_path)
    dest = project.root / "out" / "audio" / "musiques" / "menu.mp3"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"old")
    # aucun mock respx actif : tout appel réseau ferait échouer le test
    results = generate_kind(project, "musiques")
    assert results[0].request == {"skipped": "exists"}
    assert dest.read_bytes() == b"old"


def test_manual_dry_run_shows_card(tmp_path):
    results = generate_kind(_project(tmp_path), "affiche", dry_run=True)
    assert results[0].request["manual"] is True
    assert "Whoosh" in results[0].request["prompt"]


def test_manual_generate_refuses_pointing_to_studio(tmp_path):
    with pytest.raises(RuntimeError, match="forge studio affiche"):
        generate_kind(_project(tmp_path), "affiche")


# --- Item 1 (revue P2) : les notes de clamp d'un AssetJob doivent survivre
# jusqu'au GenerateResult, sinon un clamp silencieux passe inaperçu en dry-run.

FORGE_CLAMP = """
project: demo-audio-clamp
providers:
  eleven: { type: elevenlabs }
kinds:
  musiques:
    asset: music
    prompts: prompts/musiques.yaml
    generate: { with: eleven }
"""

MUSIC_CLAMP = """
direction: "Epic score."
entries:
  boss: { prompt: "Boss theme", length_ms: 700000 }
"""


def _clamp_project(tmp_path):
    (tmp_path / "forge.yaml").write_text(FORGE_CLAMP, encoding="utf-8")
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "musiques.yaml").write_text(MUSIC_CLAMP, encoding="utf-8")
    return load_project(tmp_path)


def test_music_length_clamp_note_reaches_dry_run_result(tmp_path):
    results = generate_kind(_clamp_project(tmp_path), "musiques", dry_run=True)

    assert len(results) == 1
    assert any("600000" in note for note in results[0].notes)


def test_cli_generate_dry_run_prints_clamp_note(tmp_path):
    from typer.testing import CliRunner

    from tableforge.cli import app

    _clamp_project(tmp_path)
    runner = CliRunner()
    res = runner.invoke(app, ["generate", "musiques", "--project", str(tmp_path), "--dry-run"])

    assert res.exit_code == 0, res.output
    assert "note : " in res.output
    assert "600000" in res.output
