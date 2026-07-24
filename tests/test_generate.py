from pathlib import Path

import pytest

from tableforge.config import load_project
from tableforge.generate import generate_kind

FORGE = """
project: demo
provider:
  base_url: https://ark.x/api/v3
  api_key_env: ARK_API_KEY
  model: seedream-5-0-260128
  default_size: "64x64"
kinds:
  cards:
    prompts: prompts/cards.yaml
    template: templates/card
    render_size: {width: 10, height: 10}
"""

PROMPTS = """
art_direction: "Dark fantasy."
prompts:
  lame: "A footman."
  emissaire: "A hooded envoy."
"""


def _project(tmp_path: Path):
    (tmp_path / "forge.yaml").write_text(FORGE, encoding="utf-8")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "cards.yaml").write_text(PROMPTS, encoding="utf-8")
    return load_project(tmp_path)


def test_dry_run_builds_requests_without_network(tmp_path):
    project = _project(tmp_path)
    results = generate_kind(project, "cards", dry_run=True)
    ids = sorted(r.id for r in results)
    assert ids == ["emissaire", "lame"]
    req = next(r.request for r in results if r.id == "lame")
    assert req["model"] == "seedream-5-0-260128"
    assert req["size"] == "64x64"
    assert "A footman" in req["prompt"]
    assert all(r.dest is None for r in results)


def test_dry_run_single_id(tmp_path):
    project = _project(tmp_path)
    results = generate_kind(project, "cards", ids=["lame"], dry_run=True)
    assert [r.id for r in results] == ["lame"]


def test_kind_without_prompts_raises(tmp_path):
    forge = FORGE.replace("    prompts: prompts/cards.yaml\n", "")
    (tmp_path / "forge.yaml").write_text(forge, encoding="utf-8")
    project = load_project(tmp_path)
    with pytest.raises(ValueError, match="prompts"):
        generate_kind(project, "cards", dry_run=True)


def test_skips_existing_art_without_force(tmp_path):
    project = _project(tmp_path)
    art = project.root / "out" / "art" / "cards" / "lame.png"
    art.parent.mkdir(parents=True)
    art.write_bytes(b"x")

    class FakeProvider:
        def generate(self, *a, **k):  # pragma: no cover - must not be called
            raise AssertionError("ne doit pas régénérer")

        def build(self, *a, **k):
            return {}

    results = generate_kind(project, "cards", ids=["lame"], provider=FakeProvider())
    assert results[0].request == {"skipped": "exists"}


FORGE_MULTIMODAL = """
project: demo
providers:
  ark:
    type: seedream
    base_url: https://ark.x/api/v3
    api_key_env: ARK_API_KEY
    model: seedream-5-0-260128
  eleven:
    type: elevenlabs
  hf:
    type: higgsfield
kinds:
  teaser:
    asset: video
    prompts: prompts/teaser.yaml
    generate: {with: hf, model: kling-video/v2.1/standard/text-to-video}
  nappes:
    asset: sfx
    prompts: prompts/nappes.yaml
    generate: {with: eleven}
  cards:
    prompts: prompts/cards.yaml
    template: templates/card
    render_size: {width: 10, height: 10}
    generate: {with: ark}
  board:
    data: data/board.yaml
    template: templates/board
    render_size: {width: 10, height: 10}
"""


def test_kinds_in_order_image_then_audio_then_video(tmp_path):
    # Arrange — déclaration volontairement dans le désordre (video, audio, image, image)
    (tmp_path / "forge.yaml").write_text(FORGE_MULTIMODAL, encoding="utf-8")
    from tableforge.generate import kinds_in_order
    project = load_project(tmp_path)

    # Act
    order = kinds_in_order(project)

    # Assert — image d'abord (ordre de déclaration conservé), puis audio, puis vidéo
    assert order == ["cards", "board", "nappes", "teaser"]
