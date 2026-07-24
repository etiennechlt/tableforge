from pathlib import Path

import pytest

from tableforge.config import load_project
from tableforge.targets import build_kind_spec

FORGE = """
project: demo
providers:
  eleven:
    type: elevenlabs
voices:
  narrateur: id-narrateur
  heraut: id-heraut
  vieille-reine: id-vieille-reine
kinds:
  regles:
    asset: tts
    prompts: prompts/regles.yaml
    generate: { with: eleven, voice: narrateur }
  narration:
    asset: tts
    data: data/cards.yaml
    generate: { with: eleven, voice: narrateur, text: "{{ name }}. {{ eff }}", language: fr }
  pnj:
    asset: tts
    data: data/pnj.yaml
    generate: { with: eleven, text: "{{ replique }}", voice_field: voice, voice: narrateur }
  dialogues:
    asset: dialogue
    prompts: prompts/dialogues.yaml
    generate: { with: eleven }
  sans-source:
    asset: tts
    generate: { with: eleven, voice: narrateur }
"""

REGLES = """
output_format: mp3_22050_32
entries:
  mise-en-place: { text: "Placez le plateau." }
  rappel: { text: "Un sceau par lieu.", voice: heraut }
  annonce: "Bienvenue à la table."
"""


def _write(tmp_path: Path, rel: str, content: str) -> None:
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _project(tmp_path: Path, files: dict[str, str] | None = None):
    _write(tmp_path, "forge.yaml", FORGE)
    for rel, content in (files or {}).items():
        _write(tmp_path, rel, content)
    return load_project(tmp_path)


def test_tts_catalog_targets_use_default_voice(tmp_path):
    project = _project(tmp_path, {"prompts/regles.yaml": REGLES})

    spec = build_kind_spec(project, "regles")

    assert spec.asset == "tts"
    target = next(t for t in spec.targets if t.id == "mise-en-place")
    assert target.text == "Placez le plateau."
    assert target.voice_id == "id-narrateur"


def test_tts_catalog_entry_voice_overrides_default(tmp_path):
    project = _project(tmp_path, {"prompts/regles.yaml": REGLES})

    spec = build_kind_spec(project, "regles")

    rappel = next(t for t in spec.targets if t.id == "rappel")
    assert rappel.voice_id == "id-heraut"


def test_tts_catalog_accepts_bare_string_entries(tmp_path):
    project = _project(tmp_path, {"prompts/regles.yaml": REGLES})

    spec = build_kind_spec(project, "regles")

    annonce = next(t for t in spec.targets if t.id == "annonce")
    assert annonce.text == "Bienvenue à la table."
    assert annonce.voice_id == "id-narrateur"


def test_tts_catalog_output_format_flows_to_spec(tmp_path):
    project = _project(tmp_path, {"prompts/regles.yaml": REGLES})

    spec = build_kind_spec(project, "regles")

    assert spec.output_format == "mp3_22050_32"


def test_tts_unknown_voice_lists_declared_voices(tmp_path):
    catalog = 'entries:\n  x: { text: "Bonjour.", voice: fantome }\n'
    project = _project(tmp_path, {"prompts/regles.yaml": catalog})

    with pytest.raises(KeyError, match="voix inconnue") as excinfo:
        build_kind_spec(project, "regles")

    assert "narrateur" in str(excinfo.value)


def test_tts_catalog_entry_without_voice_anywhere_raises(tmp_path):
    forge_no_default = FORGE.replace(
        "generate: { with: eleven, voice: narrateur }\n  narration",
        "generate: { with: eleven }\n  narration")
    _write(tmp_path, "forge.yaml", forge_no_default)
    _write(tmp_path, "prompts/regles.yaml", 'entries:\n  x: { text: "Bonjour." }\n')
    project = load_project(tmp_path)

    with pytest.raises(ValueError, match="aucune voix"):
        build_kind_spec(project, "regles")


def test_tts_kind_without_text_or_prompts_raises(tmp_path):
    project = _project(tmp_path)

    with pytest.raises(ValueError, match="prompts"):
        build_kind_spec(project, "sans-source")


CARDS = """
rows:
  - { id: lame, name: "Lame", eff: "Gagner 1 Fer.", qty: 2 }
  - { id: emissaire, name: "Émissaire", eff: "+1 influence." }
"""

PNJ = """
rows:
  - { id: reine, voice: vieille-reine, replique: "Les couronnes passent." }
  - { id: garde, replique: "Halte." }
"""


def test_tts_rows_render_jinja_template(tmp_path):
    project = _project(tmp_path, {"data/cards.yaml": CARDS})

    spec = build_kind_spec(project, "narration")

    assert [t.id for t in spec.targets] == ["lame", "emissaire"]  # qty ignoré : 1 audio par id
    lame = spec.targets[0]
    assert lame.text == "Lame. Gagner 1 Fer."
    assert lame.voice_id == "id-narrateur"


def test_tts_rows_missing_template_field_raises_french_error(tmp_path):
    cards = 'rows:\n  - { id: lame, name: "Lame" }\n'
    project = _project(tmp_path, {"data/cards.yaml": cards})

    with pytest.raises(ValueError, match="champ manquant") as excinfo:
        build_kind_spec(project, "narration")

    assert "lame" in str(excinfo.value)


def test_tts_voice_field_beats_default_voice(tmp_path):
    project = _project(tmp_path, {"data/pnj.yaml": PNJ})

    spec = build_kind_spec(project, "pnj")

    reine = next(t for t in spec.targets if t.id == "reine")
    assert reine.voice_id == "id-vieille-reine"
    assert reine.text == "Les couronnes passent."


def test_tts_voice_field_falls_back_to_default_when_row_has_no_voice(tmp_path):
    project = _project(tmp_path, {"data/pnj.yaml": PNJ})

    spec = build_kind_spec(project, "pnj")

    garde = next(t for t in spec.targets if t.id == "garde")
    assert garde.voice_id == "id-narrateur"


def test_tts_rows_unknown_id_raises(tmp_path):
    project = _project(tmp_path, {"data/cards.yaml": CARDS})

    with pytest.raises(KeyError, match="inconnu"):
        build_kind_spec(project, "narration", ids=["absent"])


def test_tts_rows_filter_by_ids(tmp_path):
    project = _project(tmp_path, {"data/cards.yaml": CARDS})

    spec = build_kind_spec(project, "narration", ids=["emissaire"])

    assert [t.id for t in spec.targets] == ["emissaire"]
