from pathlib import Path

import pytest

from tableforge.data import Row, expand, load_rows, slugify


def test_slugify_strips_accents_and_punctuation():
    assert slugify("Pacte d'Éther") == "pacte-d-ether"
    assert slugify("Couronne Maudite") == "couronne-maudite"


def test_load_rows_derives_id_from_name(tmp_path):
    f = tmp_path / "cards.yaml"
    f.write_text("rows:\n  - {name: 'Lame', force: 1}\n", encoding="utf-8")
    rows = load_rows(f)
    assert rows[0].id == "lame"
    assert rows[0]["force"] == 1
    assert rows[0]["id"] == "lame"


def test_load_rows_explicit_id_wins(tmp_path):
    f = tmp_path / "cards.yaml"
    f.write_text("rows:\n  - {id: x1, name: 'Whatever'}\n", encoding="utf-8")
    assert load_rows(f)[0].id == "x1"


def test_load_rows_requires_id_or_name(tmp_path):
    f = tmp_path / "cards.yaml"
    f.write_text("rows:\n  - {force: 1}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="id"):
        load_rows(f)


def test_load_rows_missing_rows_key(tmp_path):
    f = tmp_path / "cards.yaml"
    f.write_text("nope: 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="rows"):
        load_rows(f)


def test_expand_repeats_by_qty(tmp_path):
    f = tmp_path / "cards.yaml"
    f.write_text("rows:\n  - {id: a, qty: 2}\n  - {id: b}\n", encoding="utf-8")
    expanded = expand(load_rows(f))
    assert [r.id for r in expanded] == ["a", "a", "b"]


def test_row_get_default():
    row = Row(id="a", data={"id": "a"})
    assert row.get("missing", 7) == 7
