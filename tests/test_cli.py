import pytest
from typer.testing import CliRunner

from tableforge.cli import app

runner = CliRunner()


def test_init_then_list_then_dry_run(tmp_path):
    res = runner.invoke(app, ["init", "mon-jeu", "--dest", str(tmp_path)])
    assert res.exit_code == 0, res.output
    project = tmp_path / "mon-jeu"

    res = runner.invoke(app, ["list", "--project", str(project)])
    assert res.exit_code == 0
    assert "cards" in res.output

    res = runner.invoke(app, ["generate", "cards", "--project", str(project), "--dry-run"])
    assert res.exit_code == 0
    assert "heros" in res.output


def test_unknown_kind_errors(tmp_path):
    runner.invoke(app, ["init", "g", "--dest", str(tmp_path)])
    res = runner.invoke(app, ["render", "nope", "--project", str(tmp_path / "g")])
    assert res.exit_code != 0


FORGE_AUDIO = """
project: demo-audio
providers:
  eleven: { type: elevenlabs }
kinds:
  musiques:
    asset: music
    prompts: prompts/musiques.yaml
    generate: { with: eleven }
"""

MUSIC_CATALOG = """
direction: "Epic score."
defaults: { length_ms: 60000 }
entries:
  menu: { prompt: "Main theme" }
"""


def _audio_project(tmp_path):
    (tmp_path / "forge.yaml").write_text(FORGE_AUDIO, encoding="utf-8")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "musiques.yaml").write_text(MUSIC_CATALOG, encoding="utf-8")


def test_studio_command_prints_cards(tmp_path):
    _audio_project(tmp_path)
    res = runner.invoke(app, ["studio", "musiques", "--project", str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert "elevenlabs.io/app/music" in res.output
    assert "Main theme" in res.output
    assert "menu.mp3" in res.output
    assert "length_ms=60000" in res.output


def test_list_shows_asset_and_provider(tmp_path):
    _audio_project(tmp_path)
    res = runner.invoke(app, ["list", "--project", str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert "[music via eleven]" in res.output


def test_list_reports_config_issues_and_exits_1(tmp_path):
    _audio_project(tmp_path)
    forge = (tmp_path / "forge.yaml").read_text(encoding="utf-8")
    forge = forge.replace("generate: { with: eleven }",
                          "generate: { with: eleven, voice: bob }")
    (tmp_path / "forge.yaml").write_text(forge, encoding="utf-8")
    res = runner.invoke(app, ["list", "--project", str(tmp_path)])
    assert res.exit_code == 1
    assert "clés acceptées" in res.output


def test_render_refuses_audio_kind(tmp_path):
    import typer

    from tableforge.cli import _render_kind
    from tableforge.config import load_project
    _audio_project(tmp_path)
    cfg = load_project(tmp_path)
    with pytest.raises(typer.BadParameter, match="rien à rendre"):
        _render_kind(cfg, "musiques", None)
