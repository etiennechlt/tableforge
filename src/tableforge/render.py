"""Composition d'un design : Jinja2 (données + art) → HTML, puis PNG via Playwright."""
from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Optional

from jinja2 import Template

from .config import KindConfig, ProjectConfig
from .data import Row


def combined_css(template_dir: Path) -> str:
    tokens_file = template_dir.parent / "tokens.css"
    tokens = tokens_file.read_text(encoding="utf-8") if tokens_file.exists() else ""
    style_file = template_dir / "style.css"
    style = style_file.read_text(encoding="utf-8") if style_file.exists() else ""
    style = re.sub(r"@import\s+url\([^)]*tokens\.css[^)]*\);", "", style)
    return f"{tokens}\n{style}"


def art_data_url(path: Path) -> str:
    raw = Path(path).read_bytes()
    ext = Path(path).suffix.lower().lstrip(".")
    mime = "jpeg" if ext in ("jpg", "jpeg") else (ext or "png")
    return f"data:image/{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def render_html(project: ProjectConfig, kind_cfg: KindConfig, row: Row,
                art_path: Optional[Path]) -> str:
    template = Template((kind_cfg.template / "template.html.j2").read_text(encoding="utf-8"))
    context = {
        **row.data,
        "row": row.data,
        "art_url": art_data_url(art_path) if art_path else None,
        "css": combined_css(kind_cfg.template),
        "meta": {"project": project.project, "kind": kind_cfg.name},
    }
    return template.render(**context)


def render_png(project: ProjectConfig, kind_cfg: KindConfig, row: Row,
               art_path: Optional[Path], out_path: Path) -> Path:  # pragma: no cover
    from playwright.sync_api import sync_playwright

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    html = render_html(project, kind_cfg, row, art_path)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(
            viewport={"width": kind_cfg.render_size.width, "height": kind_cfg.render_size.height},
            device_scale_factor=kind_cfg.scale)
        page.set_content(html, wait_until="networkidle")
        page.locator(kind_cfg.capture_selector).screenshot(path=str(out_path))
        browser.close()
    return out_path
