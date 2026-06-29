from pathlib import Path

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
