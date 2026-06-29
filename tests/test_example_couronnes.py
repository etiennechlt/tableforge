from pathlib import Path

from tableforge.config import load_project
from tableforge.data import expand, load_rows
from tableforge.generate import generate_kind

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "couronnes"


def test_example_loads_and_has_18_cards():
    cfg = load_project(EXAMPLE)
    rows = load_rows(cfg.kind("cards").data)
    assert len(rows) == 18
    assert {r.id for r in rows} >= {"lame", "couronne-maudite", "pacte-d-ether"}


def test_example_expands_to_print_count():
    cfg = load_project(EXAMPLE)
    expanded = expand(load_rows(cfg.kind("cards").data))
    assert len(expanded) == 20   # plaidoyer & lame ont qty 2 (16×1 + 2×2)


def test_example_dry_run_builds_all_prompts():
    cfg = load_project(EXAMPLE)
    results = generate_kind(cfg, "cards", dry_run=True)
    assert len(results) == 18
    crown = next(r for r in results if r.id == "couronne-maudite")
    assert "Corrupted variant" in crown.request["prompt"]
