import pytest

from tableforge.scaffold import init_project


def test_init_creates_project(tmp_path):
    target = init_project("mon-jeu", tmp_path)
    assert target == tmp_path / "mon-jeu"
    forge = (target / "forge.yaml").read_text(encoding="utf-8")
    assert "project: mon-jeu" in forge
    assert "__PROJECT_NAME__" not in forge
    assert (target / "data" / "cards.yaml").exists()
    assert (target / "templates" / "card" / "style.css").exists()
    assert (target / "templates" / "tokens.css").exists()
    readme = (target / "README.md").read_text(encoding="utf-8")
    assert "# mon-jeu" in readme


def test_init_refuses_non_empty(tmp_path):
    (tmp_path / "mon-jeu").mkdir()
    (tmp_path / "mon-jeu" / "x").write_text("busy", encoding="utf-8")
    with pytest.raises(FileExistsError):
        init_project("mon-jeu", tmp_path)
