from tableforge.config import load_project
from tableforge.studio import STUDIO_URLS, studio_cards

FORGE = """
project: demo-studio
providers:
  eleven: { type: elevenlabs }
kinds:
  musiques:
    asset: music
    prompts: prompts/musiques.yaml
    generate: { with: eleven }
  bruitages:
    asset: sfx
    prompts: prompts/sfx.yaml
    generate: { with: eleven }
  affiche:
    asset: sfx
    prompts: prompts/sfx.yaml
    generate: { with: manual }
    studio_url: https://example.test/atelier
  manuel_sans_url:
    asset: sfx
    prompts: prompts/sfx.yaml
    generate: { with: manual }
"""

MUSIC = """
direction: "Epic score."
defaults: { length_ms: 60000 }
entries:
  menu: { prompt: "Main theme" }
  final: { prompt: "Last stand" }
"""

SFX = """
direction: "Punchy."
entries:
  draw: { prompt: "Card swish", duration_s: 0.8 }
"""


def _project(tmp_path):
    (tmp_path / "forge.yaml").write_text(FORGE, encoding="utf-8")
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "musiques.yaml").write_text(MUSIC, encoding="utf-8")
    (prompts / "sfx.yaml").write_text(SFX, encoding="utf-8")
    return load_project(tmp_path)


def test_music_cards_have_url_text_settings_dest(tmp_path):
    project = _project(tmp_path)
    cards = studio_cards(project, "musiques")
    assert [c.id for c in cards] == ["menu", "final"]
    card = cards[0]
    assert card.kind == "musiques"
    assert card.url == "https://elevenlabs.io/app/music"
    assert card.text == "Main theme. Epic score."
    assert card.settings == {"length_ms": 60000}
    assert card.dest == project.root / "out" / "audio" / "musiques" / "menu.mp3"


def test_sfx_cards_point_to_sound_effects(tmp_path):
    cards = studio_cards(_project(tmp_path), "bruitages")
    assert cards[0].url == "https://elevenlabs.io/app/sound-effects"
    assert cards[0].settings["duration_s"] == 0.8


def test_kind_studio_url_wins_over_defaults(tmp_path):
    cards = studio_cards(_project(tmp_path), "affiche")
    assert cards[0].url == "https://example.test/atelier"


def test_manual_kind_without_studio_url_has_no_url(tmp_path):
    cards = studio_cards(_project(tmp_path), "manuel_sans_url")
    assert cards[0].url is None


def test_ids_filter(tmp_path):
    cards = studio_cards(_project(tmp_path), "musiques", ids=["final"])
    assert [c.id for c in cards] == ["final"]


def test_studio_urls_table_covers_elevenlabs_assets():
    assert STUDIO_URLS[("elevenlabs", "music")] == "https://elevenlabs.io/app/music"
    assert STUDIO_URLS[("elevenlabs", "sfx")] == "https://elevenlabs.io/app/sound-effects"
    assert STUDIO_URLS[("elevenlabs", "tts")] == "https://elevenlabs.io/app/speech-synthesis"
    assert STUDIO_URLS[("elevenlabs", "dialogue")] == "https://elevenlabs.io/app/speech-synthesis"
