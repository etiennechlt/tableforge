from pathlib import Path

import pytest

from tableforge.config import load_project

FORGE_YAML = """
project: demo
provider:
  base_url: https://ark.example/api/v3
  api_key_env: ARK_API_KEY
  model: seedream-5-0-260128
kinds:
  cards:
    data: data/cards.yaml
    prompts: prompts/cards.yaml
    template: templates/card
    render_size: {width: 744, height: 1039}
    scale: 3
    sheet: {page: A4, cols: 3, rows: 3, card_w_mm: 63, card_h_mm: 88}
"""


def _project(tmp_path: Path) -> Path:
    (tmp_path / "forge.yaml").write_text(FORGE_YAML, encoding="utf-8")
    return tmp_path


def test_load_project_resolves_paths_and_defaults(tmp_path):
    cfg = load_project(_project(tmp_path))
    assert cfg.project == "demo"
    assert cfg.root == tmp_path
    cards = cfg.kind("cards")
    assert cards.name == "cards"
    assert cards.template == tmp_path / "templates" / "card"
    assert cards.data == tmp_path / "data" / "cards.yaml"
    assert cards.capture_selector == ".forge-asset"
    assert cfg.defaults.max_refs == 3
    assert cfg.provider.default_size == "4704x3520"
    assert cards.sheet.cols == 3


def test_load_project_accepts_forge_yaml_path(tmp_path):
    cfg = load_project(_project(tmp_path) / "forge.yaml")
    assert cfg.root == tmp_path


def test_unknown_kind_raises(tmp_path):
    cfg = load_project(_project(tmp_path))
    with pytest.raises(KeyError, match="board"):
        cfg.kind("board")


def test_invalid_page_rejected(tmp_path):
    bad = FORGE_YAML.replace("page: A4", "page: A3")
    (tmp_path / "forge.yaml").write_text(bad, encoding="utf-8")
    with pytest.raises(Exception):
        load_project(tmp_path)
