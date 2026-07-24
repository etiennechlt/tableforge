from pathlib import Path

from tableforge import paths


def test_path_conventions():
    root = Path("/proj")
    assert paths.art_dir(root, "cards") == root / "out" / "art" / "cards"
    assert paths.render_dir(root, "cards") == root / "out" / "render" / "cards"
    assert paths.art_path(root, "cards", "lame") == root / "out" / "art" / "cards" / "lame.png"
    assert paths.render_path(root, "cards", "lame") == root / "out" / "render" / "cards" / "lame.png"
    assert paths.sheet_path(root, "cards") == root / "out" / "sheet" / "cards.pdf"


def test_video_paths_use_mp4_under_out_video():
    # Arrange
    root = Path("/proj")

    # Act / Assert
    assert paths.MODALITY_BY_ASSET["video"] == "video"
    assert paths.extension_for("video", None) == ".mp4"
    assert paths.extension_for("video", "whatever") == ".mp4"
    assert paths.asset_dir(root, "video", "teaser") == root / "out" / "video" / "teaser"
    assert (paths.asset_path(root, "video", "teaser", "intro")
            == root / "out" / "video" / "teaser" / "intro.mp4")
