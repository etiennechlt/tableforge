from typer.testing import CliRunner

from tableforge.cli import app

runner = CliRunner()


def test_init_then_list_then_dry_run(tmp_path):
    res = runner.invoke(app, ["init", "mon-jeu", "--dest", str(tmp_path)])
    assert res.exit_code == 0, res.output
    project = tmp_path / "mon-jeu"

    res = runner.invoke(app, ["list", "--project", str(project)])
    assert res.exit_code == 0
    assert "cards" in res.output

    res = runner.invoke(app, ["generate", "cards", "--project", str(project), "--dry-run"])
    assert res.exit_code == 0
    assert "heros" in res.output


def test_unknown_kind_errors(tmp_path):
    runner.invoke(app, ["init", "g", "--dest", str(tmp_path)])
    res = runner.invoke(app, ["render", "nope", "--project", str(tmp_path / "g")])
    assert res.exit_code != 0
