from typer.testing import CliRunner

from tableforge.cli import app

runner = CliRunner()

FORGE = """
project: demo
providers:
  ark:
    type: seedream
    base_url: https://ark.x/api/v3
    api_key_env: ARK_API_KEY
    model: seedream-5-0-260128
kinds:
  libre:
    prompts: prompts/libre.yaml
    generate: {with: ark}
"""


def _project(tmp_path):
    (tmp_path / "forge.yaml").write_text(FORGE, encoding="utf-8")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "libre.yaml").write_text(
        "art_direction: 'X.'\nprompts:\n  a: 'A.'\n", encoding="utf-8")
    return tmp_path


def test_render_refuses_template_less_kind(tmp_path):
    res = runner.invoke(app, ["render", "libre", "--project", str(_project(tmp_path))])
    assert res.exit_code != 0
    assert "template" in res.output


def test_list_tolerates_template_less_kind(tmp_path):
    res = runner.invoke(app, ["list", "--project", str(_project(tmp_path))])
    assert res.exit_code == 0
    assert "libre" in res.output


def test_dry_run_works_on_template_less_kind(tmp_path):
    res = runner.invoke(app, ["generate", "libre", "--project",
                              str(_project(tmp_path)), "--dry-run"])
    assert res.exit_code == 0
    assert "a" in res.output
