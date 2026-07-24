from pathlib import Path

import pytest

from tableforge.config import GenerateConfig, load_project

LEGACY = """
project: demo
provider:
  base_url: https://ark.x/api/v3
  api_key_env: ARK_API_KEY
  model: seedream-5-0-260128
kinds:
  cards:
    prompts: prompts/cards.yaml
    template: templates/card
    render_size: {width: 10, height: 10}
  board:
    data: data/board.yaml
    template: templates/board
    render_size: {width: 10, height: 10}
"""

NAMED = """
project: demo
providers:
  ark:
    type: seedream
    base_url: https://ark.x/api/v3
    api_key_env: ARK_API_KEY
    model: seedream-5-0-260128
  eleven:
    type: elevenlabs
voices:
  narrateur: JBFqnCBsd6RMkjVDRZzb
kinds:
  cards:
    prompts: prompts/cards.yaml
    generate: {with: ark}
  narration:
    asset: tts
    data: data/cards.yaml
    generate: {with: eleven, voice: narrateur, text: "{{ name }}"}
  affiche:
    prompts: prompts/affiche.yaml
    generate: {with: manual}
    studio_url: https://example.test/app
"""


def _write(tmp_path: Path, text: str) -> Path:
    (tmp_path / "forge.yaml").write_text(text, encoding="utf-8")
    return tmp_path


def test_legacy_provider_is_normalized_to_default(tmp_path):
    cfg = load_project(_write(tmp_path, LEGACY))
    assert set(cfg.providers) == {"default"}
    assert cfg.providers["default"].type == "seedream"
    assert cfg.provider.model == "seedream-5-0-260128"  # propriété dépréciée


def test_legacy_image_kind_with_prompts_gets_default_generate(tmp_path):
    cfg = load_project(_write(tmp_path, LEGACY))
    assert cfg.kind("cards").generate.with_ == "default"
    assert cfg.kind("board").generate is None  # pas de prompts -> pas d'injection


def test_both_provider_forms_rejected(tmp_path):
    both = LEGACY + "\nproviders:\n  ark:\n    type: seedream\n    base_url: x\n    api_key_env: K\n    model: m\n"
    with pytest.raises(ValueError, match="pas les deux"):
        load_project(_write(tmp_path, both))


def test_named_providers_parse_with_defaults(tmp_path):
    cfg = load_project(_write(tmp_path, NAMED))
    assert cfg.providers["eleven"].base_url == "https://api.elevenlabs.io"
    assert cfg.providers["eleven"].output_format == "mp3_44100_128"
    assert cfg.providers["eleven"].api_key_env == "ELEVENLABS_API_KEY"
    assert cfg.voices == {"narrateur": "JBFqnCBsd6RMkjVDRZzb"}


def test_named_provider_requires_explicit_type(tmp_path):
    text = NAMED.replace("    type: elevenlabs\n", "")
    with pytest.raises(ValueError, match="type"):
        load_project(_write(tmp_path, text))


def test_kind_multimodal_fields(tmp_path):
    cfg = load_project(_write(tmp_path, NAMED))
    narration = cfg.kind("narration")
    assert narration.asset == "tts"
    assert narration.template is None and narration.render_size is None
    assert narration.generate.with_ == "eleven"
    assert narration.generate.extras() == {"voice": "narrateur", "text": "{{ name }}"}
    affiche = cfg.kind("affiche")
    assert affiche.asset == "image"
    assert affiche.studio_url == "https://example.test/app"


def test_from_alias_parses(tmp_path):
    text = NAMED + "  anim:\n    asset: video\n    from: cards\n    prompts: prompts/anim.yaml\n    generate: {with: manual}\n"
    cfg = load_project(_write(tmp_path, text))
    assert cfg.kind("anim").from_ == "cards"


def test_project_without_any_provider_rejected(tmp_path):
    with pytest.raises(ValueError, match="provider"):
        load_project(_write(tmp_path, "project: demo\nkinds: {}\n"))


def test_deprecated_provider_property_without_default_raises(tmp_path):
    cfg = load_project(_write(tmp_path, NAMED))
    with pytest.raises(KeyError, match="default"):
        cfg.provider


def test_generate_config_alias_and_extras():
    gc = GenerateConfig(**{"with": "ark", "voice": "narrateur"})
    assert gc.with_ == "ark"
    assert gc.extras() == {"voice": "narrateur"}


def test_reserved_provider_names_rejected(tmp_path):
    for reserved in ("manual", "default"):
        text = NAMED.replace("  ark:", f"  {reserved}:", 1)
        with pytest.raises(ValueError, match="réservé"):
            load_project(_write(tmp_path, text))


def test_unknown_provider_type_gets_french_error(tmp_path):
    text = NAMED.replace("type: elevenlabs", "type: bogus")
    with pytest.raises(ValueError, match="bogus"):
        load_project(_write(tmp_path, text))
