from pathlib import Path

from tableforge.config import load_project
from tableforge.data import Row
from tableforge.render import render_html

FORGE = """
project: demo
provider: {base_url: x, api_key_env: K, model: m}
kinds:
  cards:
    template: templates/card
    render_size: {width: 10, height: 10}
"""


def _project(tmp_path: Path):
    (tmp_path / "forge.yaml").write_text(FORGE, encoding="utf-8")
    tdir = tmp_path / "templates" / "card"
    tdir.mkdir(parents=True)
    (tmp_path / "templates" / "tokens.css").write_text(":root{--ink:#000}", encoding="utf-8")
    (tdir / "style.css").write_text(
        "@import url('../tokens.css');\n.forge-asset{color:var(--ink)}", encoding="utf-8")
    (tdir / "template.html.j2").write_text(
        "<style>{{ css }}</style><div class='forge-asset'>{{ name }}|{{ row['cost'] }}|"
        "{% if art_url %}ART{% else %}NOART{% endif %}</div>", encoding="utf-8")
    return load_project(tmp_path)


def test_render_html_injects_fields_and_css(tmp_path):
    project = _project(tmp_path)
    row = Row(id="lame", data={"id": "lame", "name": "Lame", "cost": 2})
    html = render_html(project, project.kind("cards"), row, None)
    assert "Lame|2|NOART" in html
    assert "--ink:#000" in html          # tokens inlined
    assert "@import" not in html          # local import stripped


def test_render_html_with_art(tmp_path):
    project = _project(tmp_path)
    art = tmp_path / "a.png"
    from PIL import Image
    Image.new("RGB", (4, 4), "gray").save(art)
    row = Row(id="lame", data={"id": "lame", "name": "Lame", "cost": 2})
    html = render_html(project, project.kind("cards"), row, art)
    assert "ART" in html
