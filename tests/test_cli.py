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


def test_starter_audio_dry_run(tmp_path):
    runner.invoke(app, ["init", "g", "--dest", str(tmp_path)])
    res = runner.invoke(app, ["generate", "musiques", "--project",
                              str(tmp_path / "g"), "--dry-run"])
    assert res.exit_code == 0, res.output
    assert "menu" in res.output


FORGE_ALL_AUDIO_VIDEO = """
project: demo-all
providers:
  eleven: { type: elevenlabs }
kinds:
  vent:
    asset: sfx
    prompts: prompts/vent.yaml
    generate: { with: eleven }
  sort:
    asset: video
    prompts: prompts/sort.yaml
    generate: { with: manual }
"""

VENT_CATALOG = """
direction: "Short dry wind gust, no music, no voice."
entries:
  rafale:
    prompt: "A short gust of wind through dead leaves."
    duration_s: 1.0
"""

SORT_CATALOG = """
direction: "Slow arcane glow, cinematic."
entries:
  incantation:
    prompt: "A slow arcane glyph ignites in the dark, embers rising."
    duration_s: 5
"""


def test_all_without_kind_orders_audio_before_video_and_warns_missing_keys(tmp_path, monkeypatch):
    """`forge all` sans kind : ordre audio → vidéo, clés/provider manquants en warnings
    (pas d'échec) — seul test de bout en bout de l'orchestration run_all/_run_one_kind."""
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    (tmp_path / "forge.yaml").write_text(FORGE_ALL_AUDIO_VIDEO, encoding="utf-8")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "vent.yaml").write_text(VENT_CATALOG, encoding="utf-8")
    (tmp_path / "prompts" / "sort.yaml").write_text(SORT_CATALOG, encoding="utf-8")

    res = runner.invoke(app, ["all", "--project", str(tmp_path)])

    assert res.exit_code == 0, res.output
    ordre_line = next(line for line in res.output.splitlines()
                      if line.startswith("ordre : "))
    assert ordre_line.index("vent") < ordre_line.index("sort")
    assert res.output.count("génération ignorée") == 2
    assert "(vent : génération ignorée : ELEVENLABS_API_KEY manquant" in res.output
    assert "(sort : génération ignorée : provider manuel" in res.output


FORGE_ART_BRUT_CLI = """
project: demo
providers:
  hf: {type: higgsfield}
kinds:
  art-brut:
    asset: image
    prompts: prompts/art.yaml
    generate: {with: hf}
"""


def test_render_refuses_image_kind_without_template(tmp_path):
    # Arrange
    (tmp_path / "forge.yaml").write_text(FORGE_ART_BRUT_CLI, encoding="utf-8")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "art.yaml").write_text(
        'prompts:\n  lame: "A footman."\n', encoding="utf-8")

    # Act
    res = runner.invoke(app, ["render", "art-brut", "--project", str(tmp_path)])

    # Assert
    assert res.exit_code != 0
    assert "art brut" in res.output


# --- Revue finale de branche : note d'auth en dry-run (item 1) --------------

def test_dry_run_prints_auth_note_naming_env_var(tmp_path):
    # Arrange — kind 'musiques' via le provider nommé 'eleven' (elevenlabs)
    _audio_project(tmp_path)

    # Act
    res = runner.invoke(app, ["generate", "musiques", "--project", str(tmp_path), "--dry-run"])

    # Assert
    assert res.exit_code == 0, res.output
    assert "note d'auth" in res.output
    assert "ELEVENLABS_API_KEY" in res.output


def test_dry_run_prints_manual_note_pointing_to_studio(tmp_path):
    # Arrange — kind 'sort' (video) via generate: {with: manual}
    (tmp_path / "forge.yaml").write_text(FORGE_ALL_AUDIO_VIDEO, encoding="utf-8")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "vent.yaml").write_text(VENT_CATALOG, encoding="utf-8")
    (tmp_path / "prompts" / "sort.yaml").write_text(SORT_CATALOG, encoding="utf-8")

    # Act
    res = runner.invoke(app, ["generate", "sort", "--project", str(tmp_path), "--dry-run"])

    # Assert
    assert res.exit_code == 0, res.output
    assert "note d'auth" in res.output
    assert "forge studio sort" in res.output


# --- Revue finale de branche : clé manquante en vrai lancement (item 11) ----

def test_generate_missing_key_prints_french_message_and_exits_1(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    _audio_project(tmp_path)

    # Act
    res = runner.invoke(app, ["generate", "musiques", "--project", str(tmp_path)])

    # Assert
    assert res.exit_code == 1
    assert "ELEVENLABS_API_KEY" in res.output
    assert "Traceback" not in res.output
