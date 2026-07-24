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


VIDEO_FORGE = """
project: demo
providers:
  hf:
    type: higgsfield
kinds:
  teaser:
    asset: video
    prompts: prompts/teaser.yaml
    generate: {with: hf, model: kling-video/v2.1/standard/text-to-video}
"""

VIDEO_CATALOG = """
direction: "Cinematic."
entries:
  intro: {prompt: "A ruined throne room"}
"""


def test_studio_urls_include_higgsfield_video():
    assert STUDIO_URLS[("higgsfield", "video")] == "https://higgsfield.ai/create/video"


def test_studio_urls_include_higgsfield_image():
    assert STUDIO_URLS[("higgsfield", "image")] == "https://higgsfield.ai/create/image"


def test_studio_cards_for_t2v_kind_carry_url_and_dest(tmp_path):
    # Arrange
    (tmp_path / "forge.yaml").write_text(VIDEO_FORGE, encoding="utf-8")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "teaser.yaml").write_text(VIDEO_CATALOG, encoding="utf-8")
    project = load_project(tmp_path)

    # Act
    cards = studio_cards(project, "teaser")

    # Assert
    assert len(cards) == 1
    card = cards[0]
    assert card.id == "intro"
    assert card.url == "https://higgsfield.ai/create/video"
    assert card.dest == tmp_path / "out" / "video" / "teaser" / "intro.mp4"
    assert "A ruined throne room" in card.text


# --- Revue finale de branche (item 7) : les réglages à None (ex. size sans
# art_size ni default_size côté provider) sont omis de la fiche, pas affichés
# "size=None" ---------------------------------------------------------------

IMAGE_FORGE = """
project: demo
providers:
  hf:
    type: higgsfield
kinds:
  affiche-img:
    asset: image
    prompts: prompts/affiche.yaml
    generate: {with: hf}
"""

AFFICHE_PROMPTS = """
prompts:
  cover: "A castle at dusk."
"""


def test_image_card_omits_none_valued_settings(tmp_path):
    # Arrange — higgsfield n'a pas de default_size et le kind n'a pas d'art_size :
    # settings={"size": None} côté Target, qui ne doit pas fuiter tel quel.
    (tmp_path / "forge.yaml").write_text(IMAGE_FORGE, encoding="utf-8")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "affiche.yaml").write_text(AFFICHE_PROMPTS, encoding="utf-8")
    project = load_project(tmp_path)

    # Act
    cards = studio_cards(project, "affiche-img")

    # Assert
    assert cards[0].settings == {}
