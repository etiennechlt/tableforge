from tableforge.config import load_project
from tableforge.studio import STUDIO_URLS, studio_cards

FORGE = """
project: demo
providers:
  eleven:
    type: elevenlabs
voices:
  narrateur: id-narrateur
kinds:
  regles:
    asset: tts
    prompts: prompts/regles.yaml
    generate: { with: eleven, voice: narrateur }
"""

REGLES = 'entries:\n  mise-en-place: { text: "Placez le plateau." }\n'


def test_studio_urls_point_to_speech_synthesis():
    assert STUDIO_URLS[("elevenlabs", "tts")] == "https://elevenlabs.io/app/speech-synthesis"
    assert STUDIO_URLS[("elevenlabs", "dialogue")] == "https://elevenlabs.io/app/speech-synthesis"


def test_studio_cards_for_tts_kind(tmp_path):
    (tmp_path / "forge.yaml").write_text(FORGE, encoding="utf-8")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "regles.yaml").write_text(REGLES, encoding="utf-8")
    project = load_project(tmp_path)

    cards = studio_cards(project, "regles")

    assert len(cards) == 1
    card = cards[0]
    assert card.id == "mise-en-place"
    assert card.kind == "regles"
    assert card.url == "https://elevenlabs.io/app/speech-synthesis"
    assert card.dest.name == "mise-en-place.mp3"
