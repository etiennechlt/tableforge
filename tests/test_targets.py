from pathlib import Path

import pytest

from tableforge.config import load_project
from tableforge.targets import build_kind_spec

FORGE = """
project: demo
providers:
  ark:
    type: seedream
    base_url: https://ark.x/api/v3
    api_key_env: ARK_API_KEY
    model: seedream-5-0-260128
    default_size: "64x64"
  eleven:
    type: elevenlabs
kinds:
  cards:
    prompts: prompts/cards.yaml
    art_size: "32x32"
    generate: {with: ark}
  sans-prompts:
    template: templates/card
    render_size: {width: 10, height: 10}
    generate: {with: ark}
  nappes:
    asset: sfx
    prompts: prompts/nappes.yaml
"""

PROMPTS = """
art_direction: "Dark fantasy."
negative: "Avoid: text."
prompts:
  lame: "A footman."
  emissaire: "A hooded envoy."
"""


def _project(tmp_path: Path):
    (tmp_path / "forge.yaml").write_text(FORGE, encoding="utf-8")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "cards.yaml").write_text(PROMPTS, encoding="utf-8")
    return load_project(tmp_path)


def test_image_spec_resolves_targets_and_settings(tmp_path):
    project = _project(tmp_path)
    spec = build_kind_spec(project, "cards")
    assert (spec.kind, spec.asset, spec.provider_name) == ("cards", "image", "ark")
    assert spec.root == project.root
    assert spec.output_format == "png"
    assert [t.id for t in spec.targets] == ["lame", "emissaire"]
    lame = spec.targets[0]
    assert lame.text == "A footman. Dark fantasy. Avoid: text."
    assert lame.settings == {"size": "32x32"}   # art_size prime sur default_size
    assert lame.refs == ()                       # pas de style_refs déclarées


def test_image_spec_falls_back_to_provider_default_size(tmp_path):
    project = _project(tmp_path)
    kind = project.kind("cards").model_copy(update={"art_size": None})
    project = project.model_copy(update={"kinds": {**project.kinds, "cards": kind}})
    spec = build_kind_spec(project, "cards")
    assert spec.targets[0].settings == {"size": "64x64"}


def test_ids_filter_preserves_order(tmp_path):
    spec = build_kind_spec(_project(tmp_path), "cards", ids=["emissaire"])
    assert [t.id for t in spec.targets] == ["emissaire"]


def test_image_kind_without_prompts_raises(tmp_path):
    with pytest.raises(ValueError, match="prompts"):
        build_kind_spec(_project(tmp_path), "sans-prompts")


def test_non_image_asset_not_implemented_in_p0(tmp_path):
    with pytest.raises(NotImplementedError, match="sfx"):
        build_kind_spec(_project(tmp_path), "nappes")


def test_options_come_from_generate_extras(tmp_path):
    from tableforge.config import GenerateConfig
    project = _project(tmp_path)
    kind = project.kind("cards").model_copy(
        update={"generate": GenerateConfig(**{"with": "ark", "style": "sombre"})})
    project = project.model_copy(update={"kinds": {**project.kinds, "cards": kind}})
    spec = build_kind_spec(project, "cards")
    assert spec.options == {"style": "sombre"}
