import pytest

from tableforge.config import SheetConfig
from tableforge.sheet import plan_sheet, render_sheet_html


def _cfg(**kw):
    base = dict(page="A4", cols=3, rows=3, card_w_mm=63, card_h_mm=88, gap_mm=4)
    base.update(kw)
    return SheetConfig(**base)


def test_nine_items_one_page_centered():
    plan = plan_sheet([f"c{i}" for i in range(9)], _cfg())
    assert plan.pages == 1
    assert len(plan.slots) == 9
    # grid width = 3*63 + 2*4 = 197 ; margin_x = (210-197)/2 = 6.5
    first = plan.slots[0]
    assert first.page == 0 and first.col == 0 and first.row == 0
    assert first.x_mm == pytest.approx(6.5)
    assert first.w_mm == 63 and first.h_mm == 88
    # second column x = 6.5 + 63 + 4 = 73.5
    assert plan.slots[1].x_mm == pytest.approx(73.5)


def test_overflow_paginates():
    plan = plan_sheet([f"c{i}" for i in range(10)], _cfg())
    assert plan.pages == 2
    assert plan.slots[9].page == 1
    assert plan.slots[9].col == 0 and plan.slots[9].row == 0


def test_letter_page_size():
    plan = plan_sheet(["a"], _cfg(page="Letter"))
    assert plan.page_w_mm == pytest.approx(215.9)


def test_render_sheet_html_emits_pages_and_marks(tmp_path):
    plan = plan_sheet(["a", "b"], _cfg())
    html = render_sheet_html(plan, {})
    assert html.count("<section") == 1
    assert "dashed" in html  # cut marks on by default
