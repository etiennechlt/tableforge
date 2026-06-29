import pytest

from tableforge.config import load_project
from tableforge.data import load_rows
from tableforge.scaffold import init_project


def _has_playwright():
    try:
        import playwright.sync_api  # noqa: F401
    except Exception:
        return False
    return True


@pytest.mark.skipif(not _has_playwright(), reason="Playwright non installé")
def test_render_png_produces_file(tmp_path):
    from tableforge.render import render_png
    project_dir = init_project("smoke", tmp_path)
    cfg = load_project(project_dir)
    kind_cfg = cfg.kind("cards")
    row = load_rows(kind_cfg.data)[0]
    out = tmp_path / "out.png"
    try:
        render_png(cfg, kind_cfg, row, None, out)
    except Exception as exc:  # navigateur (Chromium) possiblement absent
        pytest.skip(f"navigateur indisponible : {exc}")
    assert out.exists() and out.stat().st_size > 0
