import pytest

from tableforge.config import load_project
from tableforge.targets import build_kind_spec

FORGE = """
project: demo-audio
providers:
  eleven: { type: elevenlabs }
kinds:
  musiques:
    asset: music
    prompts: prompts/musiques.yaml
    generate: { with: eleven }
  nappes:
    asset: sfx
    prompts: prompts/nappes.yaml
    generate: { with: eleven }
  sfx:
    asset: sfx
    prompts: prompts/sfx.yaml
    generate: { with: eleven, duration_s: 2.0 }
"""

MUSIC = """
direction: "Epic orchestral score."
negative: "No vocals."
defaults: { length_ms: 60000 }
output_format: mp3_44100_128
entries:
  menu: { prompt: "Main theme" }
  long: { prompt: "Too long", length_ms: 700000 }
"""

NAPPES = """
direction: "Ambient loop."
defaults: { loop: true, duration_s: 30 }
entries:
  cite: { prompt: "City murmur" }
"""

SFX = """
direction: "Punchy effect."
entries:
  draw: { prompt: "Card swish", duration_s: 0.8 }
  clic: { prompt: "Soft click" }
"""


def _project(tmp_path):
    (tmp_path / "forge.yaml").write_text(FORGE, encoding="utf-8")
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "musiques.yaml").write_text(MUSIC, encoding="utf-8")
    (prompts / "nappes.yaml").write_text(NAPPES, encoding="utf-8")
    (prompts / "sfx.yaml").write_text(SFX, encoding="utf-8")
    return load_project(tmp_path)


def test_music_spec_resolves_targets_and_defaults(tmp_path):
    project = _project(tmp_path)
    spec = build_kind_spec(project, "musiques")
    assert spec.asset == "music"
    assert spec.provider_name == "eleven"
    assert spec.output_format == "mp3_44100_128"
    assert spec.root == project.root
    menu = next(t for t in spec.targets if t.id == "menu")
    assert menu.text == "Main theme. Epic orchestral score. No vocals."
    assert menu.settings == {"length_ms": 60000}
    assert menu.notes == ()


def test_music_length_clamped_with_visible_note(tmp_path):
    spec = build_kind_spec(_project(tmp_path), "musiques")
    long = next(t for t in spec.targets if t.id == "long")
    assert long.settings == {"length_ms": 600000}
    assert any("700000" in note and "600000" in note for note in long.notes)


def test_sfx_loop_and_duration_from_catalog_defaults(tmp_path):
    spec = build_kind_spec(_project(tmp_path), "nappes")
    cite = spec.targets[0]
    assert cite.settings == {"loop": True, "duration_s": 30.0}


def test_sfx_entry_overrides_kind_option(tmp_path):
    spec = build_kind_spec(_project(tmp_path), "sfx")
    draw = next(t for t in spec.targets if t.id == "draw")
    clic = next(t for t in spec.targets if t.id == "clic")
    assert draw.settings["duration_s"] == 0.8   # entrée > option generate: du kind
    assert clic.settings["duration_s"] == 2.0   # option generate: du kind
    assert draw.settings["loop"] is False


def test_ids_filter_and_unknown_id(tmp_path):
    project = _project(tmp_path)
    spec = build_kind_spec(project, "musiques", ids=["menu"])
    assert [t.id for t in spec.targets] == ["menu"]
    with pytest.raises(KeyError, match="aucune entrée"):
        build_kind_spec(project, "musiques", ids=["nope"])


def test_music_kind_without_prompts_raises(tmp_path):
    _project(tmp_path)
    forge = FORGE.replace("    prompts: prompts/musiques.yaml\n", "")
    (tmp_path / "forge.yaml").write_text(forge, encoding="utf-8")
    project = load_project(tmp_path)
    with pytest.raises(ValueError, match="prompts"):
        build_kind_spec(project, "musiques")
