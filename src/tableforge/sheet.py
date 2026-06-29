"""Planche d'impression : calcul de grille (pur) + rendu HTML→PDF (Playwright)."""
from __future__ import annotations

import base64
import math
from dataclasses import dataclass
from pathlib import Path

from .config import SheetConfig

PAGE_SIZES_MM: dict[str, tuple[float, float]] = {
    "A4": (210.0, 297.0),
    "Letter": (215.9, 279.4),
}


@dataclass(frozen=True)
class Slot:
    page: int
    col: int
    row: int
    x_mm: float
    y_mm: float
    w_mm: float
    h_mm: float
    id: str


@dataclass(frozen=True)
class SheetPlan:
    page: str
    page_w_mm: float
    page_h_mm: float
    pages: int
    gap_mm: float
    bleed_mm: float
    cut_marks: bool
    slots: list[Slot]


def plan_sheet(item_ids: list[str], cfg: SheetConfig) -> SheetPlan:
    page_w, page_h = PAGE_SIZES_MM[cfg.page]
    grid_w = cfg.cols * cfg.card_w_mm + (cfg.cols - 1) * cfg.gap_mm
    grid_h = cfg.rows * cfg.card_h_mm + (cfg.rows - 1) * cfg.gap_mm
    margin_x = (page_w - grid_w) / 2
    margin_y = (page_h - grid_h) / 2
    per_page = cfg.cols * cfg.rows
    pages = max(1, math.ceil(len(item_ids) / per_page)) if item_ids else 0

    slots: list[Slot] = []
    for index, asset_id in enumerate(item_ids):
        page = index // per_page
        within = index % per_page
        row = within // cfg.cols
        col = within % cfg.cols
        x = margin_x + col * (cfg.card_w_mm + cfg.gap_mm)
        y = margin_y + row * (cfg.card_h_mm + cfg.gap_mm)
        slots.append(Slot(page, col, row, x, y, cfg.card_w_mm, cfg.card_h_mm, asset_id))

    return SheetPlan(cfg.page, page_w, page_h, pages, cfg.gap_mm, cfg.bleed_mm,
                     cfg.cut_marks, slots)


def _img_data_url(path: Path) -> str:
    raw = Path(path).read_bytes()
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


def render_sheet_html(plan: SheetPlan, art_by_id: dict[str, Path]) -> str:
    pages_html = []
    for page in range(plan.pages):
        cells = []
        for slot in plan.slots:
            if slot.page != page:
                continue
            src = art_by_id.get(slot.id)
            img = f'<img src="{_img_data_url(src)}">' if src else ""
            cells.append(
                f'<div class="cell" style="left:{slot.x_mm}mm;top:{slot.y_mm}mm;'
                f'width:{slot.w_mm}mm;height:{slot.h_mm}mm">{img}</div>')
        pages_html.append(f'<section class="page">{"".join(cells)}</section>')
    marks = ".cell{outline:0.2mm dashed #999}" if plan.cut_marks else ""
    css = (
        f"@page{{size:{plan.page_w_mm}mm {plan.page_h_mm}mm;margin:0}}"
        "*{margin:0;box-sizing:border-box}"
        f".page{{position:relative;width:{plan.page_w_mm}mm;height:{plan.page_h_mm}mm;"
        "page-break-after:always;overflow:hidden}"
        ".cell{position:absolute}.cell img{width:100%;height:100%;object-fit:cover}"
        + marks
    )
    return ("<!doctype html><html><head><meta charset='utf-8'><style>" + css
            + "</style></head><body>" + "".join(pages_html) + "</body></html>")


def build_sheet_pdf(plan: SheetPlan, art_by_id: dict[str, Path], out_path: Path) -> Path:  # pragma: no cover
    from playwright.sync_api import sync_playwright

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    html = render_sheet_html(plan, art_by_id)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.pdf(path=str(out_path), prefer_css_page_size=True, print_background=True)
        browser.close()
    return out_path
