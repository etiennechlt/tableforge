import pytest
from pydantic import ValidationError

from tableforge.config import load_project
from tableforge.providers.base import (
    SUPPORTED_ASSETS,
    options_model,
    resolve_provider_name,
)

FORGE_TWO = """
project: demo
providers:
  ark:
    type: seedream
    base_url: https://ark.x/api/v3
    api_key_env: ARK_API_KEY
    model: seedream-5-0-260128
  eleven: { type: elevenlabs }
kinds:
  musiques:
    asset: music
    prompts: prompts/musiques.yaml
    generate: { with: eleven }
  nappes:
    asset: sfx
    prompts: prompts/nappes.yaml
  fantome:
    asset: music
    prompts: prompts/musiques.yaml
    generate: { with: nexiste }
  mauvais:
    asset: music
    prompts: prompts/musiques.yaml
    generate: { with: ark }
  atelier:
    asset: sfx
    prompts: prompts/sfx.yaml
    generate: { with: manual }
"""

FORGE_NO_CANDIDATE = """
project: demo
providers:
  ark:
    type: seedream
    base_url: https://ark.x/api/v3
    api_key_env: ARK_API_KEY
    model: seedream-5-0-260128
kinds:
  musiques: { asset: music, prompts: prompts/m.yaml }
"""

FORGE_AMBIGUOUS = """
project: demo
providers:
  a: { type: elevenlabs }
  b: { type: elevenlabs }
kinds:
  musiques: { asset: music, prompts: prompts/m.yaml }
"""


def _project(tmp_path, text=FORGE_TWO):
    (tmp_path / "forge.yaml").write_text(text, encoding="utf-8")
    return load_project(tmp_path)


def test_supported_assets_table():
    assert SUPPORTED_ASSETS["seedream"] == frozenset({"image"})
    assert SUPPORTED_ASSETS["elevenlabs"] == frozenset({"music", "sfx", "tts", "dialogue"})
    assert SUPPORTED_ASSETS["higgsfield"] == frozenset({"image", "video"})
    assert SUPPORTED_ASSETS["manual"] == frozenset(
        {"image", "music", "sfx", "tts", "dialogue", "video"})


def test_resolve_explicit_provider(tmp_path):
    project = _project(tmp_path)
    assert resolve_provider_name(project, project.kind("musiques")) == "eleven"


def test_resolve_auto_single_candidate(tmp_path):
    project = _project(tmp_path)
    assert resolve_provider_name(project, project.kind("nappes")) == "eleven"


def test_resolve_manual_is_reserved(tmp_path):
    project = _project(tmp_path)
    assert resolve_provider_name(project, project.kind("atelier")) == "manual"


def test_resolve_unknown_provider_raises(tmp_path):
    project = _project(tmp_path)
    with pytest.raises(ValueError, match="provider 'nexiste' inconnu"):
        resolve_provider_name(project, project.kind("fantome"))


def test_resolve_incapable_provider_raises(tmp_path):
    project = _project(tmp_path)
    with pytest.raises(ValueError, match="ne sait pas générer"):
        resolve_provider_name(project, project.kind("mauvais"))


def test_resolve_no_candidate_raises(tmp_path):
    project = _project(tmp_path, FORGE_NO_CANDIDATE)
    with pytest.raises(ValueError, match="aucun provider"):
        resolve_provider_name(project, project.kind("musiques"))


def test_resolve_ambiguous_lists_candidates(tmp_path):
    project = _project(tmp_path, FORGE_AMBIGUOUS)
    with pytest.raises(ValueError, match="a, b"):
        resolve_provider_name(project, project.kind("musiques"))


def test_options_model_music_forbids_unknown_keys():
    model = options_model("elevenlabs", "music")
    assert model(length_ms=60000).length_ms == 60000
    with pytest.raises(ValidationError):
        model(voice="narrateur")


def test_options_model_sfx_and_unknown_pairs():
    model = options_model("elevenlabs", "sfx")
    opts = model(duration_s=2.0, loop=True)
    assert opts.duration_s == 2.0
    assert opts.loop is True
    assert options_model("elevenlabs", "video") is None
