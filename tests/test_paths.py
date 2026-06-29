from pathlib import Path

from tableforge import paths


def test_path_conventions():
    root = Path("/proj")
    assert paths.art_dir(root, "cards") == root / "out" / "art" / "cards"
    assert paths.render_dir(root, "cards") == root / "out" / "render" / "cards"
    assert paths.art_path(root, "cards", "lame") == root / "out" / "art" / "cards" / "lame.png"
    assert paths.render_path(root, "cards", "lame") == root / "out" / "render" / "cards" / "lame.png"
    assert paths.sheet_path(root, "cards") == root / "out" / "sheet" / "cards.pdf"
