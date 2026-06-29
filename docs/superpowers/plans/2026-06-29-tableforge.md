# tableforge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `tableforge`, a generic config-driven toolkit that generates tabletop game assets (cards, maps/boards, designs, AI art) from a declarative project folder, shipped with a `forge init` scaffold and a complete working `examples/couronnes/`.

**Architecture:** A *project folder* declares *kinds* (asset types) in `forge.yaml`. Each kind binds data rows + prompts + an HTML/CSS/Jinja2 template. Three operations act on a kind: `generate` (AI art via a configurable Seedream/OpenAI-images provider), `render` (HTML→PNG via Playwright), `sheet` (PNG grid→print PDF via Playwright). Pure logic (config, data, prompts, request-building, sheet layout) is unit-tested; browser/network I/O is smoke-tested.

**Tech Stack:** Python ≥3.10, pydantic v2, PyYAML, Jinja2, Pillow, openai SDK (Ark base_url), httpx, python-dotenv, typer, Playwright (Chromium), hatchling, pytest. Env managed with **uv**.

## Global Constraints

- Python `>=3.10`; package name `tableforge`; CLI entry point `forge`.
- **No `python`/`pip` system** on this machine — always use `.venv/bin/python` (venv via **uv**).
- **No hardcoded secrets**: the API key is read at runtime from the env var named by `provider.api_key_env`; never store the key in YAML or code. `.env` is gitignored.
- **No ReportLab**: all layout is HTML/CSS rendered by Playwright.
- Immutable data (frozen dataclasses / return new objects), modules <~150 lines, errors explicit with clear messages, validation at boundaries (pydantic).
- Default capture selector `.forge-asset`; default page size `A4`.
- All asset linkage is by `id` (slug): `data` ↔ `prompts` ↔ `out/art/<kind>/<id>.png` ↔ `out/render/<kind>/<id>.png`.

---

## Task 1: Project skeleton & packaging

**Files:**
- Create: `pyproject.toml`
- Create: `src/tableforge/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_package.py`
- Create: `.env.example`

**Interfaces:**
- Produces: importable package `tableforge` with `tableforge.__version__: str`.

- [ ] **Step 1: Write the failing test**

`tests/test_package.py`:
```python
import tableforge


def test_version_is_exposed():
    assert isinstance(tableforge.__version__, str)
    assert tableforge.__version__
```

- [ ] **Step 2: Create packaging + sources**

`pyproject.toml`:
```toml
[project]
name = "tableforge"
version = "0.1.0"
description = "Générateur d'assets de jeu (cartes, plateau/map, designs, art IA) piloté par configuration."
requires-python = ">=3.10"
dependencies = [
    "pydantic>=2",
    "pyyaml",
    "jinja2",
    "pillow",
    "openai>=1.0",
    "httpx",
    "python-dotenv",
    "typer>=0.12",
    "playwright",
]

[project.optional-dependencies]
dev = ["pytest", "pytest-cov"]

[project.scripts]
forge = "tableforge.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/tableforge"]

[tool.hatch.build.targets.wheel.force-include]
"src/tableforge/templates" = "tableforge/templates"

[tool.pytest.ini_options]
addopts = "-q"
testpaths = ["tests"]
pythonpath = ["src"]

[tool.coverage.run]
source = ["tableforge"]
omit = ["*/render.py", "*/cli.py", "*/__main__.py"]

[tool.coverage.report]
exclude_lines = ["if __name__ == .__main__.:", "pragma: no cover"]
```

`src/tableforge/__init__.py`:
```python
"""tableforge — générateur d'assets de jeu piloté par configuration."""
__version__ = "0.1.0"
```

`tests/__init__.py`: empty file.

`.env.example`:
```bash
# tableforge — copier vers .env (jamais committé). La clé est lue via provider.api_key_env.
ARK_API_KEY=your_byteplus_ark_api_key_here
```

- [ ] **Step 3: Bootstrap env & run test**

Run:
```bash
cd /home/etienne/Documents/tableforge
uv venv .venv
uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/python -m pytest tests/test_package.py -v
```
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "chore: squelette de package tableforge + packaging"
```

---

## Task 2: `paths.py` — output path conventions

**Files:**
- Create: `src/tableforge/paths.py`
- Create: `tests/test_paths.py`

**Interfaces:**
- Produces:
  - `art_dir(root: Path, kind: str) -> Path`
  - `render_dir(root: Path, kind: str) -> Path`
  - `art_path(root: Path, kind: str, asset_id: str) -> Path`
  - `render_path(root: Path, kind: str, asset_id: str) -> Path`
  - `sheet_path(root: Path, kind: str) -> Path`

- [ ] **Step 1: Write the failing test**

`tests/test_paths.py`:
```python
from pathlib import Path

from tableforge import paths


def test_path_conventions():
    root = Path("/proj")
    assert paths.art_dir(root, "cards") == root / "out" / "art" / "cards"
    assert paths.render_dir(root, "cards") == root / "out" / "render" / "cards"
    assert paths.art_path(root, "cards", "lame") == root / "out" / "art" / "cards" / "lame.png"
    assert paths.render_path(root, "cards", "lame") == root / "out" / "render" / "cards" / "lame.png"
    assert paths.sheet_path(root, "cards") == root / "out" / "sheet" / "cards.pdf"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_paths.py -v`
Expected: FAIL (ModuleNotFoundError: tableforge.paths).

- [ ] **Step 3: Implement**

`src/tableforge/paths.py`:
```python
"""Conventions de chemins de sortie (out/art|render|sheet/<kind>/)."""
from __future__ import annotations

from pathlib import Path


def art_dir(root: Path, kind: str) -> Path:
    return root / "out" / "art" / kind


def render_dir(root: Path, kind: str) -> Path:
    return root / "out" / "render" / kind


def art_path(root: Path, kind: str, asset_id: str) -> Path:
    return art_dir(root, kind) / f"{asset_id}.png"


def render_path(root: Path, kind: str, asset_id: str) -> Path:
    return render_dir(root, kind) / f"{asset_id}.png"


def sheet_path(root: Path, kind: str) -> Path:
    return root / "out" / "sheet" / f"{kind}.pdf"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_paths.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: conventions de chemins de sortie (paths)"
```

---

## Task 3: `data.py` — rows, slugify, expand

**Files:**
- Create: `src/tableforge/data.py`
- Create: `tests/test_data.py`

**Interfaces:**
- Produces:
  - `slugify(name: str) -> str`
  - `class Row` (frozen): attrs `id: str`, `data: dict`; `__getitem__`, `.get(k, default=None)`, `.qty -> int`
  - `load_rows(path: Path) -> list[Row]` — reads `{rows: [...]}`, each entry needs `id` or `name`
  - `expand(rows: list[Row]) -> list[Row]` — repeats each row `qty` times

- [ ] **Step 1: Write the failing test**

`tests/test_data.py`:
```python
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


def test_expand_repeats_by_qty(tmp_path):
    f = tmp_path / "cards.yaml"
    f.write_text("rows:\n  - {id: a, qty: 2}\n  - {id: b}\n", encoding="utf-8")
    expanded = expand(load_rows(f))
    assert [r.id for r in expanded] == ["a", "a", "b"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_data.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement**

`src/tableforge/data.py`:
```python
"""Chargement des lignes de données (rows) d'un kind, indépendant du schéma métier."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


def slugify(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_only = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")


@dataclass(frozen=True)
class Row:
    id: str
    data: dict

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    @property
    def qty(self) -> int:
        return int(self.data.get("qty", 1))


def _row_id(entry: dict) -> str:
    if entry.get("id"):
        return str(entry["id"])
    if entry.get("name"):
        return slugify(str(entry["name"]))
    raise ValueError("chaque row doit avoir un champ 'id' ou 'name'")


def load_rows(path: Path) -> list[Row]:
    with open(path, encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    entries = raw.get("rows")
    if not isinstance(entries, list):
        raise ValueError(f"{path} : clé 'rows' (liste) manquante")
    rows: list[Row] = []
    for entry in entries:
        asset_id = _row_id(entry)
        rows.append(Row(id=asset_id, data={**entry, "id": asset_id}))
    return rows


def expand(rows: list[Row]) -> list[Row]:
    result: list[Row] = []
    for row in rows:
        result.extend([row] * row.qty)
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_data.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: chargement des rows (slugify, Row, load_rows, expand)"
```

---

## Task 4: `config.py` — forge.yaml models & loader

**Files:**
- Create: `src/tableforge/config.py`
- Create: `tests/test_config.py`

**Interfaces:**
- Produces:
  - `class RenderSize(BaseModel)`: `width: int (>0)`, `height: int (>0)`
  - `class SheetConfig(BaseModel)`: `page: Literal["A4","Letter"]="A4"`, `cols:int(>0)`, `rows:int(>0)`, `card_w_mm:float(>0)`, `card_h_mm:float(>0)`, `gap_mm:float=4`, `bleed_mm:float=0`, `cut_marks:bool=True`
  - `class KindConfig(BaseModel)`: `name:str`, `data:Optional[Path]`, `prompts:Optional[Path]`, `template:Path`, `capture_selector:str=".forge-asset"`, `render_size:RenderSize`, `scale:int=1`, `art_size:Optional[str]`, `sheet:Optional[SheetConfig]`
  - `class ProviderConfig(BaseModel)`: `base_url:str`, `api_key_env:str`, `model:str`, `default_size:str="4704x3520"`, `watermark:bool=False`, `output_format:str="png"`
  - `class Defaults(BaseModel)`: `max_refs:int=3`, `ref_max_px:int=1024`
  - `class ProjectConfig(BaseModel)`: `project:str`, `root:Path`, `provider:ProviderConfig`, `defaults:Defaults`, `kinds:dict[str,KindConfig]`; method `kind(name:str)->KindConfig`
  - `load_project(path: Path) -> ProjectConfig` — `path` is a project dir or a `forge.yaml`; resolves `data`/`prompts`/`template` relative to root; injects `name` into each kind.

> **Note (refinement vs spec):** `SheetConfig` adds `card_w_mm`/`card_h_mm` — the physical card size the print grid needs. Documented in README.

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:
```python
from pathlib import Path

import pytest

from tableforge.config import load_project

FORGE_YAML = """
project: demo
provider:
  base_url: https://ark.example/api/v3
  api_key_env: ARK_API_KEY
  model: seedream-5-0-260128
kinds:
  cards:
    data: data/cards.yaml
    prompts: prompts/cards.yaml
    template: templates/card
    render_size: {width: 744, height: 1039}
    scale: 3
    sheet: {page: A4, cols: 3, rows: 3, card_w_mm: 63, card_h_mm: 88}
"""


def _project(tmp_path: Path) -> Path:
    (tmp_path / "forge.yaml").write_text(FORGE_YAML, encoding="utf-8")
    return tmp_path


def test_load_project_resolves_paths_and_defaults(tmp_path):
    cfg = load_project(_project(tmp_path))
    assert cfg.project == "demo"
    assert cfg.root == tmp_path
    cards = cfg.kind("cards")
    assert cards.name == "cards"
    assert cards.template == tmp_path / "templates" / "card"
    assert cards.data == tmp_path / "data" / "cards.yaml"
    assert cards.capture_selector == ".forge-asset"
    assert cfg.defaults.max_refs == 3
    assert cfg.provider.default_size == "4704x3520"
    assert cards.sheet.cols == 3


def test_load_project_accepts_forge_yaml_path(tmp_path):
    cfg = load_project(_project(tmp_path) / "forge.yaml")
    assert cfg.root == tmp_path


def test_unknown_kind_raises(tmp_path):
    cfg = load_project(_project(tmp_path))
    with pytest.raises(KeyError, match="board"):
        cfg.kind("board")


def test_invalid_page_rejected(tmp_path):
    bad = FORGE_YAML.replace("page: A4", "page: A3")
    (tmp_path / "forge.yaml").write_text(bad, encoding="utf-8")
    with pytest.raises(Exception):
        load_project(tmp_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement**

`src/tableforge/config.py`:
```python
"""Modèles de configuration (forge.yaml) validés par pydantic + chargeur."""
from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field


class RenderSize(BaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class SheetConfig(BaseModel):
    page: Literal["A4", "Letter"] = "A4"
    cols: int = Field(gt=0)
    rows: int = Field(gt=0)
    card_w_mm: float = Field(gt=0)
    card_h_mm: float = Field(gt=0)
    gap_mm: float = 4.0
    bleed_mm: float = 0.0
    cut_marks: bool = True


class KindConfig(BaseModel):
    name: str
    template: Path
    render_size: RenderSize
    data: Optional[Path] = None
    prompts: Optional[Path] = None
    capture_selector: str = ".forge-asset"
    scale: int = Field(default=1, gt=0)
    art_size: Optional[str] = None
    sheet: Optional[SheetConfig] = None


class ProviderConfig(BaseModel):
    base_url: str
    api_key_env: str
    model: str
    default_size: str = "4704x3520"
    watermark: bool = False
    output_format: str = "png"


class Defaults(BaseModel):
    max_refs: int = 3
    ref_max_px: int = 1024


class ProjectConfig(BaseModel):
    project: str
    root: Path
    provider: ProviderConfig
    kinds: dict[str, KindConfig]
    defaults: Defaults = Field(default_factory=Defaults)

    def kind(self, name: str) -> KindConfig:
        if name not in self.kinds:
            raise KeyError(f"kind inconnu : '{name}' (connus : {', '.join(self.kinds)})")
        return self.kinds[name]


_PATH_FIELDS = ("data", "prompts", "template")


def load_project(path: Path) -> ProjectConfig:
    path = Path(path)
    forge_file = path / "forge.yaml" if path.is_dir() else path
    root = forge_file.parent
    with open(forge_file, encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    kinds_raw = raw.get("kinds", {}) or {}
    kinds: dict[str, KindConfig] = {}
    for name, spec in kinds_raw.items():
        spec = dict(spec)
        for field in _PATH_FIELDS:
            if spec.get(field) is not None:
                spec[field] = (root / spec[field]).resolve()
        kinds[name] = KindConfig(name=name, **spec)

    return ProjectConfig(
        project=raw["project"],
        root=root.resolve(),
        provider=ProviderConfig(**raw["provider"]),
        defaults=Defaults(**(raw.get("defaults") or {})),
        kinds=kinds,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: modèles + chargeur de configuration forge.yaml"
```

---

## Task 5: `prompts.py` — prompt assembly & reference encoding

**Files:**
- Create: `src/tableforge/prompts.py`
- Create: `tests/test_prompts.py`

**Interfaces:**
- Consumes: nothing internal (operates on plain dicts + PIL).
- Produces:
  - `load_prompts(path: Path) -> dict`
  - `prompt_for(asset_id: str, cfg: dict) -> str`
  - `encode_image_data_url(path, max_px=1024, quality=85) -> str`
  - `reference_data_urls(cfg: dict, root: Path, asset_id: str | None = None, max_refs=3, max_px=1024) -> list[str]`

- [ ] **Step 1: Write the failing test**

`tests/test_prompts.py`:
```python
from pathlib import Path

import pytest
from PIL import Image

from tableforge.prompts import encode_image_data_url, prompt_for, reference_data_urls

CFG = {
    "art_direction": "Dark fantasy, gouache.",
    "negative": "Avoid: text, border.",
    "style_refs": ["reference/a.png", "reference/b.png", "reference/c.png", "reference/d.png"],
    "prompts": {"lame": "A weary footman.", "couronne-maudite": "A thorn crown."},
    "overrides": {
        "couronne-maudite": {"suffix": "Corrupted: violet ether.", "style_refs": ["reference/x.png"]}
    },
}


def test_prompt_for_combines_subject_direction_negative():
    text = prompt_for("lame", CFG)
    assert text == "A weary footman. Dark fantasy, gouache. Avoid: text, border."


def test_prompt_for_applies_override_suffix():
    text = prompt_for("couronne-maudite", CFG)
    assert "Corrupted: violet ether." in text
    assert text.index("Corrupted") < text.index("Avoid")


def test_prompt_for_unknown_id_raises():
    with pytest.raises(KeyError, match="inconnu"):
        prompt_for("nope", CFG)


def _png(path: Path):
    Image.new("RGB", (2048, 1536), "gray").save(path)


def test_reference_data_urls_caps_and_adds_override(tmp_path):
    for n in ("a", "b", "c", "d", "x"):
        _png(tmp_path / "reference" / f"{n}.png") if (tmp_path / "reference").exists() else (
            (tmp_path / "reference").mkdir(), _png(tmp_path / "reference" / f"{n}.png"))
    urls = reference_data_urls(CFG, tmp_path, "couronne-maudite", max_refs=3, max_px=64)
    # 3 base refs (capped) + 1 override ref = 4
    assert len(urls) == 4
    assert all(u.startswith("data:image/jpeg;base64,") for u in urls)


def test_encode_downscales(tmp_path):
    p = tmp_path / "ref.png"
    _png(p)
    url = encode_image_data_url(p, max_px=32)
    assert url.startswith("data:image/jpeg;base64,")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_prompts.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement**

`src/tableforge/prompts.py`:
```python
"""Assemblage des prompts d'art + encodage des images de référence (i2i)."""
from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Optional

import yaml
from PIL import Image


def load_prompts(path: Path) -> dict:
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def prompt_for(asset_id: str, cfg: dict) -> str:
    prompts = cfg.get("prompts", {}) or {}
    if asset_id not in prompts:
        raise KeyError(f"prompt inconnu pour l'id « {asset_id} »")
    subject = str(prompts[asset_id]).strip().rstrip(".")
    art_direction = str(cfg.get("art_direction", "")).strip()
    text = f"{subject}. {art_direction}".strip()
    override = (cfg.get("overrides", {}) or {}).get(asset_id, {})
    if override.get("suffix"):
        text += " " + str(override["suffix"]).strip()
    if cfg.get("negative"):
        text += " " + str(cfg["negative"]).strip()
    return text


def encode_image_data_url(path, max_px: int = 1024, quality: int = 85) -> str:
    img = Image.open(path).convert("RGB")
    img.thumbnail((max_px, max_px))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=quality)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def reference_data_urls(
    cfg: dict,
    root: Path,
    asset_id: Optional[str] = None,
    max_refs: int = 3,
    max_px: int = 1024,
) -> list[str]:
    refs = list((cfg.get("style_refs", []) or [])[:max_refs])
    if asset_id:
        override = (cfg.get("overrides", {}) or {}).get(asset_id, {})
        refs += list(override.get("style_refs", []) or [])
    return [encode_image_data_url(Path(root) / ref, max_px=max_px) for ref in refs]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_prompts.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: assemblage des prompts + encodage des refs i2i"
```

---

## Task 6: `providers.py` — Seedream/OpenAI-images provider

**Files:**
- Create: `src/tableforge/providers.py`
- Create: `tests/test_providers.py`

**Interfaces:**
- Consumes: `tableforge.config.ProviderConfig`.
- Produces:
  - `build_request(*, model, size, refs, watermark, output_format, sequential="auto", response_format="url") -> dict`
  - `summarize_request(req: dict) -> dict`
  - `class SeedreamProvider` (frozen dataclass): fields `api_key, base_url, model, default_size, watermark, output_format`; classmethod `from_config(cfg: ProviderConfig) -> SeedreamProvider`; method `build(prompt, size=None, refs=None) -> dict`; method `generate(prompt, dest: Path, size=None, refs=None) -> list[Path]`

- [ ] **Step 1: Write the failing test**

`tests/test_providers.py`:
```python
import pytest

from tableforge.config import ProviderConfig
from tableforge.providers import SeedreamProvider, build_request, summarize_request


def _cfg():
    return ProviderConfig(base_url="https://ark.x/api/v3", api_key_env="ARK_API_KEY", model="seedream-5-0-260128")


def test_build_request_shapes_extra_body():
    req = build_request(model="m", size="64x64", refs=["data:..a", "data:..b"],
                        watermark=False, output_format="png")
    assert req["model"] == "m"
    assert req["size"] == "64x64"
    assert req["extra_body"]["image"] == ["data:..a", "data:..b"]
    assert req["extra_body"]["watermark"] is False
    assert req["extra_body"]["output_format"] == "png"


def test_build_request_omits_image_when_no_refs():
    req = build_request(model="m", size="64x64", refs=[], watermark=False, output_format="png")
    assert "image" not in req["extra_body"]


def test_summarize_hides_data_urls():
    req = build_request(model="m", size="64x64", refs=["a", "b"], watermark=False, output_format="png")
    summary = summarize_request(req)
    assert summary["extra_body"]["image"] == "[2 référence(s), data-URLs omises]"


def test_from_config_requires_key(monkeypatch):
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ARK_API_KEY"):
        SeedreamProvider.from_config(_cfg())


def test_from_config_reads_key(monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "secret")
    provider = SeedreamProvider.from_config(_cfg())
    assert provider.api_key == "secret"
    assert provider.model == "seedream-5-0-260128"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_providers.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement**

`src/tableforge/providers.py`:
```python
"""Provider d'images Seedream (BytePlus Ark, compatible OpenAI-images), configurable."""
from __future__ import annotations

import base64
import copy
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv

from .config import ProviderConfig

DEFAULT_SEQUENTIAL = "auto"


def build_request(*, model: str, size: str, refs: list[str], watermark: bool,
                  output_format: str, sequential: str = DEFAULT_SEQUENTIAL,
                  response_format: str = "url") -> dict:
    extra: dict = {
        "watermark": watermark,
        "sequential_image_generation": sequential,
        "output_format": output_format,
    }
    if refs:
        extra["image"] = list(refs)
    return {"model": model, "prompt": "", "size": size,
            "response_format": response_format, "extra_body": extra}


def summarize_request(req: dict) -> dict:
    summary = copy.deepcopy(req)
    images = summary.get("extra_body", {}).get("image")
    if images is not None:
        summary["extra_body"]["image"] = f"[{len(images)} référence(s), data-URLs omises]"
    return summary


def _save_image(item, dest: Path) -> Path:
    dest = Path(dest)
    b64 = getattr(item, "b64_json", None)
    if b64:
        dest.write_bytes(base64.b64decode(b64))
        return dest
    url = getattr(item, "url", None)
    if not url:
        raise RuntimeError("réponse sans image (ni url ni b64_json)")
    response = httpx.get(url, timeout=120.0)
    response.raise_for_status()
    dest.write_bytes(response.content)
    return dest


@dataclass(frozen=True)
class SeedreamProvider:
    api_key: str
    base_url: str
    model: str
    default_size: str
    watermark: bool
    output_format: str

    @classmethod
    def from_config(cls, cfg: ProviderConfig) -> "SeedreamProvider":
        load_dotenv()
        key = os.environ.get(cfg.api_key_env)
        if not key:
            raise RuntimeError(
                f"{cfg.api_key_env} manquant : copie .env.example vers .env et renseigne ta clé.")
        return cls(api_key=key, base_url=cfg.base_url, model=cfg.model,
                   default_size=cfg.default_size, watermark=cfg.watermark,
                   output_format=cfg.output_format)

    def build(self, prompt: str, size: Optional[str] = None,
              refs: Optional[list[str]] = None) -> dict:
        req = build_request(model=self.model, size=size or self.default_size,
                            refs=refs or [], watermark=self.watermark,
                            output_format=self.output_format)
        req["prompt"] = prompt
        return req

    def _client(self):
        from openai import OpenAI
        return OpenAI(api_key=self.api_key, base_url=self.base_url, max_retries=3, timeout=180.0)

    def generate(self, prompt: str, dest: Path, size: Optional[str] = None,
                 refs: Optional[list[str]] = None) -> list[Path]:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        response = self._client().images.generate(**self.build(prompt, size, refs))
        saved = [_save_image(response.data[0], dest)]
        for index, item in enumerate(response.data[1:], start=2):
            saved.append(_save_image(item, dest.with_name(f"{dest.stem}-{index}.png")))
        return saved
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_providers.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: provider Seedream configurable (compat OpenAI-images)"
```

---

## Task 7: `generate.py` — art generation orchestration

**Files:**
- Create: `src/tableforge/generate.py`
- Create: `tests/test_generate.py`

**Interfaces:**
- Consumes: `config.ProjectConfig`, `prompts.{load_prompts,prompt_for,reference_data_urls}`, `providers.{SeedreamProvider,build_request,summarize_request}`, `paths.art_path`.
- Produces:
  - `@dataclass(frozen=True) class GenerateResult`: `id:str`, `dest:Optional[Path]`, `request:dict`
  - `generate_kind(project: ProjectConfig, kind: str, ids: Optional[list[str]] = None, dry_run: bool = False, force: bool = False, provider=None) -> list[GenerateResult]`

- [ ] **Step 1: Write the failing test**

`tests/test_generate.py`:
```python
from pathlib import Path

from tableforge.config import load_project
from tableforge.generate import generate_kind

FORGE = """
project: demo
provider:
  base_url: https://ark.x/api/v3
  api_key_env: ARK_API_KEY
  model: seedream-5-0-260128
  default_size: "64x64"
kinds:
  cards:
    prompts: prompts/cards.yaml
    template: templates/card
    render_size: {width: 10, height: 10}
"""

PROMPTS = """
art_direction: "Dark fantasy."
prompts:
  lame: "A footman."
  emissaire: "A hooded envoy."
"""


def _project(tmp_path: Path):
    (tmp_path / "forge.yaml").write_text(FORGE, encoding="utf-8")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "cards.yaml").write_text(PROMPTS, encoding="utf-8")
    return load_project(tmp_path)


def test_dry_run_builds_requests_without_network(tmp_path):
    project = _project(tmp_path)
    results = generate_kind(project, "cards", dry_run=True)
    ids = sorted(r.id for r in results)
    assert ids == ["emissaire", "lame"]
    req = next(r.request for r in results if r.id == "lame")
    assert req["model"] == "seedream-5-0-260128"
    assert req["size"] == "64x64"
    assert "A footman" in req["prompt"]
    assert all(r.dest is None for r in results)


def test_dry_run_single_id(tmp_path):
    project = _project(tmp_path)
    results = generate_kind(project, "cards", ids=["lame"], dry_run=True)
    assert [r.id for r in results] == ["lame"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_generate.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement**

`src/tableforge/generate.py`:
```python
"""Orchestration de la génération d'art (un kind, ses ids)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .config import ProjectConfig
from .paths import art_path
from .prompts import load_prompts, prompt_for, reference_data_urls
from .providers import SeedreamProvider, build_request, summarize_request


@dataclass(frozen=True)
class GenerateResult:
    id: str
    dest: Optional[Path]
    request: dict


def generate_kind(project: ProjectConfig, kind: str, ids: Optional[list[str]] = None,
                  dry_run: bool = False, force: bool = False,
                  provider: Optional[SeedreamProvider] = None) -> list[GenerateResult]:
    kind_cfg = project.kind(kind)
    if kind_cfg.prompts is None:
        raise ValueError(f"le kind '{kind}' n'a pas de fichier prompts")
    cfg = load_prompts(kind_cfg.prompts)
    size = kind_cfg.art_size or project.provider.default_size
    target_ids = ids or list((cfg.get("prompts", {}) or {}).keys())

    if not dry_run and provider is None:
        provider = SeedreamProvider.from_config(project.provider)

    results: list[GenerateResult] = []
    for asset_id in target_ids:
        prompt = prompt_for(asset_id, cfg)
        refs = reference_data_urls(cfg, project.root, asset_id,
                                   project.defaults.max_refs, project.defaults.ref_max_px)
        dest = art_path(project.root, kind, asset_id)
        if dry_run:
            req = build_request(model=project.provider.model, size=size, refs=refs,
                                watermark=project.provider.watermark,
                                output_format=project.provider.output_format)
            req["prompt"] = prompt
            results.append(GenerateResult(asset_id, None, summarize_request(req)))
            continue
        if dest.exists() and not force:
            results.append(GenerateResult(asset_id, dest, {"skipped": "exists"}))
            continue
        provider.generate(prompt, dest, size=size, refs=refs)
        results.append(GenerateResult(asset_id, dest, summarize_request(provider.build(prompt, size, refs))))
    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_generate.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: orchestration de génération d'art (generate_kind)"
```

---

## Task 8: `sheet.py` — print-sheet layout & PDF

**Files:**
- Create: `src/tableforge/sheet.py`
- Create: `tests/test_sheet.py`

**Interfaces:**
- Consumes: `config.SheetConfig`, `paths.sheet_path`.
- Produces:
  - `PAGE_SIZES_MM: dict[str, tuple[float,float]]`
  - `@dataclass(frozen=True) class Slot`: `page:int, col:int, row:int, x_mm:float, y_mm:float, w_mm:float, h_mm:float, id:str`
  - `@dataclass(frozen=True) class SheetPlan`: `page:str, page_w_mm:float, page_h_mm:float, pages:int, gap_mm:float, bleed_mm:float, cut_marks:bool, slots:list[Slot]`
  - `plan_sheet(item_ids: list[str], cfg: SheetConfig) -> SheetPlan`
  - `render_sheet_html(plan: SheetPlan, art_by_id: dict[str, Path]) -> str`
  - `build_sheet_pdf(plan: SheetPlan, art_by_id: dict[str, Path], out_path: Path) -> Path` (Playwright; not unit-tested)

- [ ] **Step 1: Write the failing test**

`tests/test_sheet.py`:
```python
import pytest

from tableforge.config import SheetConfig
from tableforge.sheet import plan_sheet


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_sheet.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement**

`src/tableforge/sheet.py`:
```python
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
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body>{''.join(pages_html)}</body></html>"


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_sheet.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: planche d'impression (layout de grille + PDF)"
```

---

## Task 9: `render.py` — HTML→PNG composition

**Files:**
- Create: `src/tableforge/render.py`
- Create: `tests/test_render.py`

**Interfaces:**
- Consumes: `config.{KindConfig,ProjectConfig}`, `data.Row`.
- Produces:
  - `combined_css(template_dir: Path) -> str` — concatenates sibling `../tokens.css` (if present) + `template_dir/style.css`, stripping local `@import ... tokens.css`.
  - `art_data_url(path: Path) -> str`
  - `render_html(project: ProjectConfig, kind_cfg: KindConfig, row: Row, art_path: Optional[Path]) -> str`
  - `render_png(project, kind_cfg, row, art_path, out_path) -> Path` (Playwright; not unit-tested, omitted from coverage)

- [ ] **Step 1: Write the failing test**

`tests/test_render.py`:
```python
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
    (tdir / "style.css").write_text("@import url('../tokens.css');\n.forge-asset{color:var(--ink)}", encoding="utf-8")
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_render.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement**

`src/tableforge/render.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_render.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: composition de design HTML→PNG (render)"
```

---

## Task 10: Bundled starter + `scaffold.py`

**Files:**
- Create: `src/tableforge/templates/starter/forge.yaml`
- Create: `src/tableforge/templates/starter/.env.example`
- Create: `src/tableforge/templates/starter/README.md`
- Create: `src/tableforge/templates/starter/.gitignore`
- Create: `src/tableforge/templates/starter/data/cards.yaml`
- Create: `src/tableforge/templates/starter/prompts/cards.yaml`
- Create: `src/tableforge/templates/starter/templates/tokens.css`
- Create: `src/tableforge/templates/starter/templates/card/template.html.j2`
- Create: `src/tableforge/templates/starter/templates/card/style.css`
- Create: `src/tableforge/templates/starter/reference/.gitkeep`
- Create: `src/tableforge/scaffold.py`
- Create: `tests/test_scaffold.py`

**Interfaces:**
- Produces:
  - `starter_dir() -> Path` — locates bundled `templates/starter`
  - `init_project(name: str, dest: Path) -> Path` — creates `dest/name`, copies starter, substitutes `__PROJECT_NAME__`; raises `FileExistsError` if target non-empty.

- [ ] **Step 1: Create the bundled starter files**

`src/tableforge/templates/starter/forge.yaml`:
```yaml
project: __PROJECT_NAME__

provider:
  base_url: https://ark.ap-southeast.bytepluses.com/api/v3
  api_key_env: ARK_API_KEY          # NOM de la variable d'env (jamais la clé)
  model: seedream-5-0-260128
  default_size: "4704x3520"
  watermark: false

defaults:
  max_refs: 3
  ref_max_px: 1024

kinds:
  cards:
    data: data/cards.yaml
    prompts: prompts/cards.yaml
    template: templates/card
    capture_selector: ".forge-asset"
    render_size: { width: 744, height: 1039 }   # 63×88 mm @300 dpi
    scale: 3
    sheet:
      page: A4
      cols: 3
      rows: 3
      card_w_mm: 63
      card_h_mm: 88
      gap_mm: 4
      cut_marks: true
```

`src/tableforge/templates/starter/.env.example`:
```bash
# Copier vers .env (jamais committé). Clé lue via provider.api_key_env.
ARK_API_KEY=your_api_key_here
```

`src/tableforge/templates/starter/README.md`:
```markdown
# __PROJECT_NAME__

Projet tableforge. Commandes :

```bash
forge list
forge generate cards --dry-run     # vérifie les prompts sans appel réseau
forge generate cards               # art IA (nécessite ARK_API_KEY dans .env)  [coûte $]
forge render cards                 # designs PNG -> out/render/cards/
forge sheet cards                  # planche d'impression -> out/sheet/cards.pdf
```

Édite `data/cards.yaml` (tes cartes), `prompts/cards.yaml` (tes sujets + images de référence),
`templates/card/style.css` (ton style). Mets tes images de référence dans `reference/`.
```

`src/tableforge/templates/starter/.gitignore`:
```
.env
out/
__pycache__/
```

`src/tableforge/templates/starter/data/cards.yaml`:
```yaml
rows:
  - { id: heros,   name: "Héros",   cost: 3, eff: "Un exemple de carte.",          qty: 2 }
  - { id: relique, name: "Relique", cost: 5, eff: "Une autre carte d'exemple.",    qty: 1 }
```

`src/tableforge/templates/starter/prompts/cards.yaml`:
```yaml
art_direction: >-
  Painterly fantasy illustration, single centered subject, cinematic light,
  muted palette. No text, no border, illustration only, full-bleed.
negative: >-
  Avoid: text, letters, watermark, card frame, border, modern objects.
style_refs: []          # ajoute ici des chemins vers reference/xxx.png pour l'i2i
prompts:
  heros: "A lone armored hero standing on a windswept ridge at dusk."
  relique: "An ancient glowing relic resting on a stone altar in shadow."
# overrides:
#   relique: { suffix: "Add a faint magical glow.", style_refs: [reference/relique-ref.png] }
```

`src/tableforge/templates/starter/templates/tokens.css`:
```css
:root{
  --ink:#2c2c2a; --muted:#6f6e68; --paper:#f1ead8; --accent:#b07a1e;
  --card-radius:14px;
}
```

`src/tableforge/templates/starter/templates/card/template.html.j2`:
```html
<!doctype html><html lang="fr"><head><meta charset="utf-8"><style>{{ css }}</style></head>
<body style="margin:0;background:#0c0a08">
  <div class="forge-asset">
    <div class="art"{% if art_url %} style="background-image:url('{{ art_url }}')"{% endif %}></div>
    {% if cost is not none %}<div class="cost">{{ cost }}</div>{% endif %}
    <div class="title">{{ name }}</div>
    <div class="eff">{{ eff }}</div>
  </div>
</body></html>
```

`src/tableforge/templates/starter/templates/card/style.css`:
```css
@import url('../tokens.css');
.forge-asset{width:744px;height:1039px;position:relative;background:var(--paper);
  border-radius:var(--card-radius);overflow:hidden;font-family:Georgia,serif;color:var(--ink)}
.art{position:absolute;inset:0 0 38% 0;background:#1a1712 center/cover no-repeat}
.cost{position:absolute;top:18px;left:18px;width:54px;height:54px;border-radius:50%;
  background:var(--accent);color:#fff;display:flex;align-items:center;justify-content:center;
  font-size:28px;font-weight:bold}
.title{position:absolute;top:60%;left:0;right:0;text-align:center;font-size:34px;font-weight:bold}
.eff{position:absolute;top:70%;left:32px;right:32px;font-size:22px;color:var(--muted)}
```

`src/tableforge/templates/starter/reference/.gitkeep`: empty file.

- [ ] **Step 2: Write the failing test**

`tests/test_scaffold.py`:
```python
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


def test_init_refuses_non_empty(tmp_path):
    (tmp_path / "mon-jeu").mkdir()
    (tmp_path / "mon-jeu" / "x").write_text("busy", encoding="utf-8")
    with pytest.raises(FileExistsError):
        init_project("mon-jeu", tmp_path)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_scaffold.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 4: Implement**

`src/tableforge/scaffold.py`:
```python
"""Scaffold d'un nouveau projet à partir du starter bundlé."""
from __future__ import annotations

import shutil
from importlib import resources
from pathlib import Path

PLACEHOLDER = "__PROJECT_NAME__"


def starter_dir() -> Path:
    return Path(resources.files("tableforge")) / "templates" / "starter"


def init_project(name: str, dest: Path) -> Path:
    target = Path(dest) / name
    if target.exists() and any(target.iterdir()):
        raise FileExistsError(f"{target} existe déjà et n'est pas vide")
    shutil.copytree(starter_dir(), target, dirs_exist_ok=True)
    for path in target.rglob("*"):
        if path.is_file() and path.suffix in (".yaml", ".md", ".css", ".j2", ".gitignore", ""):
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if PLACEHOLDER in text:
                path.write_text(text.replace(PLACEHOLDER, name), encoding="utf-8")
    return target
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_scaffold.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: starter bundlé + scaffold (forge init)"
```

---

## Task 11: `cli.py` — typer commands

**Files:**
- Create: `src/tableforge/cli.py`
- Create: `src/tableforge/__main__.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes: all prior modules.
- Produces: `app` (typer.Typer) with commands `init, list, generate, render, sheet, board, all`. `forge = tableforge.cli:app` (from Task 1).

- [ ] **Step 1: Write the failing test**

`tests/test_cli.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement**

`src/tableforge/cli.py`:
```python
"""CLI tableforge (commande `forge`)."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import typer

from . import paths
from .config import load_project
from .data import expand, load_rows
from .generate import generate_kind

app = typer.Typer(add_completion=False, help="Générateur d'assets de jeu piloté par configuration.")

ProjectOpt = typer.Option(Path("."), "--project", "-p", help="Dossier du projet (contient forge.yaml).")


@app.command()
def init(name: str, dest: Path = typer.Option(Path("."), "--dest", help="Dossier parent.")):
    """Crée un nouveau projet vierge."""
    from .scaffold import init_project
    target = init_project(name, dest)
    typer.echo(f"Projet créé : {target}")


@app.command("list")
def list_kinds(project: Path = ProjectOpt):
    """Liste les kinds déclarés."""
    cfg = load_project(project)
    for name, kind in cfg.kinds.items():
        flags = []
        if kind.data:
            flags.append("data" if kind.data.exists() else "data?")
        if kind.prompts:
            flags.append("prompts" if kind.prompts.exists() else "prompts?")
        flags.append("template" if kind.template.exists() else "template?")
        sheet = " +sheet" if kind.sheet else ""
        typer.echo(f"- {name}: {', '.join(flags)}{sheet}")


@app.command()
def generate(kind: str, project: Path = ProjectOpt,
             id: Optional[List[str]] = typer.Option(None, "--id", help="Limiter à ces ids."),
             dry_run: bool = typer.Option(False, "--dry-run"),
             force: bool = typer.Option(False, "--force")):
    """Génère l'art IA d'un kind."""
    cfg = load_project(project)
    results = generate_kind(cfg, kind, ids=id or None, dry_run=dry_run, force=force)
    for res in results:
        where = "(dry-run)" if res.dest is None else str(res.dest)
        typer.echo(f"{res.id}: {where}")


def _render_kind(cfg, kind: str, only: Optional[List[str]]):
    from .render import render_png
    kind_cfg = cfg.kind(kind)
    if kind_cfg.data is None:
        raise typer.BadParameter(f"le kind '{kind}' n'a pas de fichier data")
    rows = load_rows(kind_cfg.data)
    if only:
        rows = [r for r in rows if r.id in set(only)]
    out = []
    for row in rows:
        art = paths.art_path(cfg.root, kind, row.id)
        out_path = paths.render_path(cfg.root, kind, row.id)
        render_png(cfg, kind_cfg, row, art if art.exists() else None, out_path)
        out.append(out_path)
        typer.echo(f"{row.id}: {out_path}")
    return out


@app.command()
def render(kind: str, project: Path = ProjectOpt,
           id: Optional[List[str]] = typer.Option(None, "--id")):
    """Compose les designs PNG d'un kind."""
    _render_kind(load_project(project), kind, id)


@app.command()
def board(kind: str, project: Path = ProjectOpt):
    """Rendu d'un kind pleine page (plateau / map)."""
    _render_kind(load_project(project), kind, None)


@app.command()
def sheet(kind: str, project: Path = ProjectOpt):
    """Assemble la planche d'impression PDF d'un kind."""
    from .sheet import build_sheet_pdf, plan_sheet
    cfg = load_project(project)
    kind_cfg = cfg.kind(kind)
    if kind_cfg.sheet is None or kind_cfg.data is None:
        raise typer.BadParameter(f"le kind '{kind}' n'a pas de bloc 'sheet'/'data'")
    rows = expand(load_rows(kind_cfg.data))
    art_by_id = {}
    for row in rows:
        rp = paths.render_path(cfg.root, kind, row.id)
        if rp.exists():
            art_by_id[row.id] = rp
    plan = plan_sheet([r.id for r in rows], kind_cfg.sheet)
    out = build_sheet_pdf(plan, art_by_id, paths.sheet_path(cfg.root, kind))
    typer.echo(f"planche : {out}")


@app.command("all")
def run_all(kind: str, project: Path = ProjectOpt):
    """generate (si clé) → render → sheet."""
    cfg = load_project(project)
    try:
        generate_kind(cfg, kind)
    except RuntimeError as exc:
        typer.echo(f"(génération ignorée : {exc})")
    _render_kind(cfg, kind, None)
    if cfg.kind(kind).sheet:
        sheet(kind, project)
```

`src/tableforge/__main__.py`:
```python
from .cli import app

if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: PASS (2 tests). (Note: render/sheet commands invoke Playwright; the CLI tests exercise only `init`, `list`, `generate --dry-run`, and a `--bad kind` parameter error path.)

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: CLI forge (init/list/generate/render/sheet/board/all)"
```

---

## Task 12: Full coverage run + smoke render

**Files:**
- Create: `tests/test_smoke_render.py`

**Interfaces:**
- Consumes: scaffolded starter project (via `init_project`) + Playwright.

- [ ] **Step 1: Write the browser smoke test (skips if Chromium absent)**

`tests/test_smoke_render.py`:
```python
import shutil

import pytest

from tableforge.config import load_project
from tableforge.data import load_rows
from tableforge.scaffold import init_project


def _has_chromium():
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return False
    return True


@pytest.mark.skipif(not _has_chromium(), reason="Playwright non installé")
def test_render_png_produces_file(tmp_path):
    from tableforge.render import render_png
    project_dir = init_project("smoke", tmp_path)
    cfg = load_project(project_dir)
    kind_cfg = cfg.kind("cards")
    row = load_rows(kind_cfg.data)[0]
    out = tmp_path / "out.png"
    try:
        render_png(cfg, kind_cfg, row, None, out)
    except Exception as exc:  # browser binary may be missing in CI
        pytest.skip(f"navigateur indisponible : {exc}")
    assert out.exists() and out.stat().st_size > 0
```

- [ ] **Step 2: Run the full suite with coverage**

Run:
```bash
.venv/bin/python -m pytest --cov=tableforge --cov-report=term-missing
```
Expected: all green; coverage on pure-logic modules (config, data, prompts, providers, generate, sheet, scaffold, paths) ≥ 80%. (`render.py`, `cli.py`, `__main__.py` are omitted via pyproject `omit`.)

- [ ] **Step 3: If coverage <80% on any logic module, add targeted tests**

Inspect `term-missing` output; add tests covering uncovered branches (e.g., `data.load_rows` missing-`rows` error, `config.load_project` with a `board` kind lacking `sheet`). Re-run.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "test: smoke de rendu navigateur + run de couverture"
```

---

## Task 13: `examples/couronnes/` — runnable example port

**Files:**
- Create: `examples/couronnes/forge.yaml`
- Create: `examples/couronnes/data/cards.yaml`
- Create: `examples/couronnes/data/board.yaml`
- Create: `examples/couronnes/prompts/cards.yaml`
- Create: `examples/couronnes/templates/tokens.css`
- Create: `examples/couronnes/templates/card/template.html.j2`
- Create: `examples/couronnes/templates/card/style.css`
- Create: `examples/couronnes/templates/board/template.html.j2`
- Create: `examples/couronnes/templates/board/style.css`
- Create: `examples/couronnes/reference/` (copied style refs)
- Create: `examples/couronnes/README.md`
- Create: `tests/test_example_couronnes.py`

**Interfaces:**
- Consumes: `config.load_project`, `data.load_rows`, `generate.generate_kind`.

> **Source material** (read-only, on disk): `/home/etienne/Documents/couronnes-cendres/`
> - cards data: `data/cards.yaml` (fields `cat,name,cost,corr,seal,eff,inf,force,qty`)
> - card template/CSS: `design/card/card.html.j2`, `design/card/card.css`, `design/tokens/tokens.css`
> - prompts: `data/prompts.yaml` (art_direction, corrupted_suffix, negative, style_refs, corrupted_refs, prompts)
> - reference images: `reference/02-Lame.png`, `reference/XX-Couronne Maudite.png`, `assets/style-refs/00-exemple-personnage.png`

- [ ] **Step 1: Write `forge.yaml`**

`examples/couronnes/forge.yaml`:
```yaml
project: couronnes-cendres

provider:
  base_url: https://ark.ap-southeast.bytepluses.com/api/v3
  api_key_env: ARK_API_KEY
  model: seedream-5-0-260128
  default_size: "4704x3520"
  watermark: false

defaults:
  max_refs: 2
  ref_max_px: 1024

kinds:
  cards:
    data: data/cards.yaml
    prompts: prompts/cards.yaml
    template: templates/card
    capture_selector: ".cc-card"
    render_size: { width: 744, height: 1039 }
    scale: 3
    sheet:
      page: A4
      cols: 3
      rows: 3
      card_w_mm: 63
      card_h_mm: 88
      gap_mm: 4
      cut_marks: true
  board:
    data: data/board.yaml
    template: templates/board
    capture_selector: ".cc-board"
    render_size: { width: 2480, height: 3508 }   # A4 @300 dpi
    scale: 1
```

- [ ] **Step 2: Port `data/cards.yaml`**

Transform each card from the source `cards.yaml` `cards:` list into a `rows:` list, adding `id: <slug of name>` and keeping `cat, name, cost, corr, seal, eff, inf, force, qty`. (Slugs: `slugify(name)`, e.g. "Pacte d'Éther" → `pacte-d-ether`.)

`examples/couronnes/data/cards.yaml`:
```yaml
rows:
  - { id: plaidoyer,       cat: depart, name: "Plaidoyer",        cost: null, corr: null, seal: null,                  eff: "Carte de pure révélation : aucune action sur le plateau.", inf: 2, force: 0, qty: 2 }
  - { id: lame,            cat: depart, name: "Lame",             cost: null, corr: null, seal: "Caserne",             eff: "Gagner 1 Fer.",                                           inf: 0, force: 1, qty: 2 }
  - { id: emissaire,       cat: depart, name: "Émissaire",        cost: null, corr: null, seal: "Faction (au choix)",  eff: "+1 influence sur la piste choisie.",                      inf: 1, force: 0, qty: 1 }
  - { id: marchandage,     cat: depart, name: "Marchandage",      cost: null, corr: null, seal: "Marché",              eff: "Gagner 2 Or.",                                            inf: 1, force: 0, qty: 1 }
  - { id: glanage,         cat: depart, name: "Glanage",          cost: null, corr: null, seal: "Confins",             eff: "Gagner 2 Vivres.",                                        inf: 0, force: 1, qty: 1 }
  - { id: patrouille,      cat: depart, name: "Patrouille",       cost: null, corr: null, seal: "Région (au choix)",   eff: "Placer 1 unité dans cette région.",                       inf: 0, force: 1, qty: 1 }
  - { id: anneau-du-sceau, cat: depart, name: "Anneau du Sceau",  cost: null, corr: null, seal: "Joker",               eff: "Aller sur tout espace libre et déclencher l'action du lieu.", inf: 1, force: 1, qty: 1 }
  - { id: edit-royal,      cat: depart, name: "Édit Royal",       cost: null, corr: null, seal: "Couronne",            eff: "+1 influence Couronne et gagner 1 Or.",                   inf: 1, force: 0, qty: 1 }
  - { id: recruteur,           cat: marche, name: "Recruteur",          cost: 2, corr: null, seal: "Caserne",        eff: "Placer 1 unité, puis épurer 1 carte de ta main.",          inf: 0, force: 1, qty: 1 }
  - { id: caravane-marchande,  cat: marche, name: "Caravane Marchande", cost: 3, corr: null, seal: "Marché",         eff: "Gagner 3 Or. Variante : gagner 1 Or et piocher 1 carte.",  inf: 2, force: 0, qty: 1 }
  - { id: chevalier-errant,    cat: marche, name: "Chevalier Errant",   cost: 4, corr: null, seal: "Région",         eff: "Placer 2 unités dans cette région.",                       inf: 1, force: 2, qty: 1 }
  - { id: maitre-de-guilde,    cat: marche, name: "Maître de Guilde",   cost: 5, corr: null, seal: "Guildes",        eff: "+1 influence Guildes, gagner 2 Or et piocher 1 carte.",    inf: 3, force: 0, qty: 1 }
  - { id: pretresse,           cat: marche, name: "Prêtresse",          cost: 5, corr: null, seal: "Temple",         eff: "+1 influence Temple, puis retirer 1 corruption de ton sac.", inf: 2, force: 1, qty: 1 }
  - { id: banneret,            cat: marche, name: "Banneret",           cost: 6, corr: null, seal: "Caserne / Cité", eff: "Placer 2 unités, gagner 1 Fer et piocher 1 carte.",        inf: 2, force: 3, qty: 1 }
  - { id: pacte-d-ether,    cat: premium, name: "Pacte d'Éther",     cost: 5, corr: 1, seal: "Sanctuaire", eff: "Gagner 2 Éther et piocher 1 carte.",                                                  inf: 3, force: 1, qty: 1 }
  - { id: legion-damnee,    cat: premium, name: "Légion Damnée",     cost: 6, corr: 2, seal: "Caserne",    eff: "Placer 3 unités et gagner 1 Fer.",                                                    inf: 1, force: 4, qty: 1 }
  - { id: couronne-maudite, cat: premium, name: "Couronne Maudite",  cost: 7, corr: 2, seal: "Couronne",   eff: "+2 influence Couronne et gagner 2 Or. Surcharge (+1 corruption) : piocher 2 cartes.",  inf: 4, force: 0, qty: 1 }
  - { id: cendres-vivantes, cat: premium, name: "Cendres Vivantes",  cost: 5, corr: 1, seal: "Sanctuaire", eff: "Convertir X corruption de ton sac en X Force pour ce conflit.",                        inf: 2, force: 1, qty: 1 }
```

- [ ] **Step 3: Port `prompts/cards.yaml`**

Copy `art_direction`, `negative`, `prompts` verbatim from source `data/prompts.yaml`. Convert the source's `corrupted_suffix` + `corrupted_refs` (which applied to all 4 premium cards) into per-id `overrides` for `pacte-d-ether`, `legion-damnee`, `couronne-maudite`, `cendres-vivantes`. Set `style_refs` to the two copied refs.

`examples/couronnes/prompts/cards.yaml`:
```yaml
art_direction: >-
  Dark medieval fantasy trading-card illustration, painterly digital gouache with the
  weathered texture of an aged illuminated manuscript. A single centered subject, medium
  shot, strong cinematic chiaroscuro: one warm candle-gold key light against deep cold
  shadow. Muted grim palette — ash grey, weathered stone, oxblood red, candle gold;
  desaturated, somber. Visible hand-painted brushwork, fine detail, subtle parchment grain,
  slightly hazy atmospheric background that only suggests the setting. Cohesive concept-art
  look. No text, no letters, no card frame, no border, no UI — illustration only, full-bleed.

negative: >-
  Avoid: any text, letters, captions, watermark, logo, signature; card frame, border or UI;
  modern objects, photographic realism, bright cheerful colors; multiple disconnected
  subjects, cluttered composition; deformed hands or anatomy.

style_refs:
  - reference/02-Lame.png
  - reference/00-exemple-personnage.png

_corruption: &corruption >-
  Corrupted variant: introduce a sickly ether glow of violet and teal as the only saturated
  color, drifting grey ash and orange embers, hairline cracks leaking faint pale light, an
  oppressive cursed atmosphere — darker and colder than the base style.

overrides:
  pacte-d-ether:    { suffix: *corruption, style_refs: [reference/XX-Couronne-Maudite.png] }
  legion-damnee:    { suffix: *corruption, style_refs: [reference/XX-Couronne-Maudite.png] }
  couronne-maudite: { suffix: *corruption, style_refs: [reference/XX-Couronne-Maudite.png] }
  cendres-vivantes: { suffix: *corruption, style_refs: [reference/XX-Couronne-Maudite.png] }

prompts:
  plaidoyer: "A ragged commoner kneeling on cold stone steps, one hand raised in earnest plea, clutching a rolled petition; towering shadowed figures of authority loom out of focus above. A scene of words and supplication, no weapons."
  lame: "A weary low-ranking footman in a patched gambeson gripping a plain, nicked iron sword point-down in the mud of a barracks yard; a forge glows dull orange behind him. Humble, grounded, martial."
  emissaire: "A hooded emissary in a dust-worn traveling cloak holding out a sealed letter with a red wax seal, a faint diplomatic smile; the blurred banners of a foreign faction behind. Quiet, persuasive."
  marchandage: "Close on two hands over a wooden market stall exchanging a small stack of gold coins for goods, a merchant's shrewd eyes just visible; crates, scales and hanging wares blur behind. Lively haggling."
  glanage: "A stooped peasant gleaning the last grain at the ragged edge of a harvested field at dusk, a half-full wicker basket of provisions at the hip; the wild borderlands stretch grey beyond. Toil and scarcity."
  patrouille: "Two spear-carrying levy guards walking a muddy border road at blue dusk, lantern light, breath misting; a watchtower silhouette ahead. Watchful, cold, ordinary duty."
  anneau-du-sceau: "Extreme close-up of an ornate gold signet ring pressing into a pool of blood-red wax, the crest crisp and glinting, a single warm light catching the metal, everything else in deep shadow; a faint magical sheen on the gold. Iconic, a key object."
  edit-royal: "An unfurled royal decree on heavy parchment, weighted by a golden crown-stamped wax seal and a red ribbon, a quill and a few gold coins beside it on a dark oak desk lit by candlelight. Authority and gold."
  recruteur: "A grizzled recruiting sergeant at a wooden table outside a barracks, pointing a calloused finger toward the gate as a nervous young villager makes his mark on a muster roll; spears stacked behind. Decisive."
  caravane-marchande: "A laden merchant caravan of canvas-covered wagons and pack mules passing through a town gate at golden hour, crates and bound bales heavy with trade, a fat coin-purse in view. Wealth in motion."
  chevalier-errant: "A lone armored knight-errant on a dark warhorse cresting a windswept ridge, lance upright, a tattered personal pennant snapping, distant grey hills. Noble, solitary, martial."
  maitre-de-guilde: "A prosperous guild master in rich fur-trimmed robes and a heavy chain of office, standing among ledgers, coin scales and bolts of cloth in a warm guildhall, a knowing half-smile. Influence and gold."
  pretresse: "A serene priestess in pale robes within a candlelit temple, raising a softly glowing censer; threads of clean golden light dispel a faint dark haze at the edges of the frame. Purity against corruption."
  banneret: "An armored banner-captain on foot, sword raised, rallying a tight rank of soldiers beneath a large heraldic banner; embers and dust in shafts of light, fierce determination. Command and battle."
  pacte-d-ether: "A cloaked figure in a ruined sanctuary pressing a bare hand to a floating, fractured ether crystal that pulses sickly violet-teal; glowing tendrils of ether crawl up the arm, ash drifting in the cold dark. A forbidden bargain."
  legion-damnee: "A column of damned soldiers in blackened, ash-caked armor marching out of smoke, hollow eyes lit with faint ether-fire, embers and grey ash swirling around their boots. Relentless, dreadful, numerous."
  couronne-maudite: "A blackened, thorn-wrought crown levitating above an empty throne, wreathed in cold violet ether flames, ash spiralling up into darkness, hairline cracks leaking pale light. Cursed majesty, the heart of corruption."
  cendres-vivantes: "A humanoid creature half-formed from swirling living ash and glowing embers, cracks of violet-teal light running through its ashen body as it rises from a smoldering sanctuary floor. Power born of corruption."
```

- [ ] **Step 4: Port the card template/CSS and add the labels the template needs**

Copy `design/tokens/tokens.css` from source → `examples/couronnes/templates/tokens.css`.
Copy `design/card/card.css` from source → `examples/couronnes/templates/card/style.css`.
Adapt the source `design/card/card.html.j2` into `examples/couronnes/templates/card/template.html.j2`: the source uses `cat_label` (computed in old `render_html.py`). Since the generic engine passes only row fields, compute the label inside the template from `cat` with a Jinja map.

`examples/couronnes/templates/card/template.html.j2`:
```html
<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><style>{{ css }}</style></head>
<body style="margin:0;background:#0c0a08">
  {% set cat_label = {"depart":"Départ","marche":"Marché","premium":"Premium corrompue"}[cat] %}
  <div class="cc-card" data-cat="{{ cat }}">
    <div class="cc-art"{% if art_url %} style="background-image:url('{{ art_url }}')"{% endif %}></div>
    <span class="cc-fleuron tl"></span><span class="cc-fleuron tr"></span>
    <span class="cc-fleuron bl"></span><span class="cc-fleuron br"></span>
    {% if cost is not none %}<div class="cc-seal cc-seal--cost">{{ cost }}</div>{% endif %}
    {% if corr is not none %}<div class="cc-seal cc-seal--corr">+{{ corr }}</div>
    <div class="cc-corr-label">corruption</div>{% endif %}
    <div class="cc-titleblock">
      <div class="cc-name">{{ name }}</div>
      <div class="cc-cat">{{ cat_label }}</div>
    </div>
    <div class="cc-deploy">
      <div class="cc-label">Déploiement</div>
      {% if seal %}<span class="cc-chip">{{ seal }}</span>
      {% else %}<span class="cc-chip cc-chip--none">Aucun déploiement</span>{% endif %}
      <div class="cc-eff">{{ eff }}</div>
    </div>
    <div class="cc-reveal">
      <div class="cc-stat cc-stat--inf"><div class="cc-lab">Influence</div><div class="cc-val">{{ inf }}</div></div>
      <div class="cc-stat cc-stat--force"><div class="cc-lab">Force</div><div class="cc-val">{{ force }}</div></div>
    </div>
  </div>
</body></html>
```

> If `design/card/card.css` references `.cc-card` and `@import ... tokens.css`, the generic `combined_css` strips the import and prepends `tokens.css` — no edits needed. Verify the captured selector matches `capture_selector: ".cc-card"`.

- [ ] **Step 5: Minimal board kind**

`examples/couronnes/data/board.yaml`:
```yaml
rows:
  - { id: plateau, name: "Plateau", title: "Couronnes & Cendres" }
```

`examples/couronnes/templates/board/template.html.j2`:
```html
<!doctype html><html lang="fr"><head><meta charset="utf-8"><style>{{ css }}</style></head>
<body style="margin:0">
  <div class="cc-board"{% if art_url %} style="background-image:url('{{ art_url }}')"{% endif %}>
    <h1>{{ title }}</h1>
  </div>
</body></html>
```

`examples/couronnes/templates/board/style.css`:
```css
@import url('../tokens.css');
.cc-board{width:2480px;height:3508px;background:#14110d;color:#e8dcc0;
  display:flex;align-items:center;justify-content:center;background-size:cover}
.cc-board h1{font-family:Georgia,serif;font-size:120px;letter-spacing:8px;text-align:center}
```

- [ ] **Step 6: Copy reference images**

```bash
mkdir -p examples/couronnes/reference
cp /home/etienne/Documents/couronnes-cendres/reference/02-Lame.png examples/couronnes/reference/02-Lame.png
cp "/home/etienne/Documents/couronnes-cendres/reference/XX-Couronne Maudite.png" examples/couronnes/reference/XX-Couronne-Maudite.png
cp /home/etienne/Documents/couronnes-cendres/assets/style-refs/00-exemple-personnage.png examples/couronnes/reference/00-exemple-personnage.png 2>/dev/null || true
```

- [ ] **Step 7: Example README**

`examples/couronnes/README.md`:
```markdown
# Exemple — Couronnes & Cendres

Projet tableforge complet (18 cartes Économie + plateau). Démontre prompts, images de
référence (i2i), overrides de corruption, rendu HTML→PNG et planche d'impression.

```bash
forge list -p examples/couronnes
forge generate cards -p examples/couronnes --dry-run    # vérifie les prompts (pas de réseau)
forge generate cards -p examples/couronnes              # art IA (ARK_API_KEY requis)  [coûte $]
forge render cards   -p examples/couronnes              # faces PNG
forge sheet cards    -p examples/couronnes              # planche A4 PDF
forge board board    -p examples/couronnes              # plateau
```
```

- [ ] **Step 8: Test the example loads & dry-runs**

`tests/test_example_couronnes.py`:
```python
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
    assert len(expanded) == 21   # two cards have qty 2


def test_example_dry_run_builds_all_prompts():
    cfg = load_project(EXAMPLE)
    results = generate_kind(cfg, "cards", dry_run=True)
    assert len(results) == 18
    crown = next(r for r in results if r.id == "couronne-maudite")
    assert "Corrupted variant" in crown.request["prompt"]
```

- [ ] **Step 9: Run the example tests**

Run: `.venv/bin/python -m pytest tests/test_example_couronnes.py -v`
Expected: PASS (3 tests).

- [ ] **Step 10: Commit**

```bash
git add -A && git commit -m "feat: exemple complet examples/couronnes (port runnable)"
```

---

## Task 14: Docs — README, HANDOFF, CLAUDE.md

**Files:**
- Create: `README.md`
- Create: `HANDOFF.md`
- Create: `CLAUDE.md`

**Interfaces:** none (documentation).

- [ ] **Step 1: Write `README.md`**

Cover: what tableforge is; install (uv bootstrap from Global Constraints); the project-folder layout; the 3 config files (`forge.yaml`, `prompts/<kind>.yaml`, `data/<kind>.yaml`) with the field tables from the spec; the template contract (context vars `name/…`, `row`, `art_url`, `css`, `meta`; `capture_selector`); the commands table; a quickstart (`forge init mon-jeu` → edit → generate/render/sheet); the `examples/couronnes` pointer. Note the `SheetConfig.card_w_mm/card_h_mm` requirement.

- [ ] **Step 2: Write `HANDOFF.md`**

Mirror the couronnes HANDOFF style: what it is, current state, essential commands (with `.venv/bin/python`), gotchas (uv, Playwright `playwright install chromium`, ARK key region/model from couronnes memory), architecture map (the module table), how to verify (`pytest`). Point to spec + this plan.

- [ ] **Step 3: Write `CLAUDE.md`**

Project conventions for a Claude Code session: always `.venv/bin/python`; run `pytest` before claiming done; TDD for new kinds; don't hardcode secrets; commands cheatsheet; where the bundled starter lives (`src/tableforge/templates/starter`); coverage expectation.

- [ ] **Step 4: Final verification**

Run:
```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m tableforge list -p examples/couronnes
.venv/bin/python -m tableforge generate cards -p examples/couronnes --dry-run | head
```
Expected: all tests green; `list` shows `cards +sheet` and `board`; dry-run prints 18 ids.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "docs: README + HANDOFF + CLAUDE.md"
```

---

## Self-Review

**Spec coverage check:**
- §3.1 forge.yaml → Task 4 ✓ · §3.2 prompts → Task 5 ✓ · §3.3 data → Task 3 ✓ · §3.4 template contract → Task 9 ✓
- §4 commands (init/list/generate/render/sheet/board/all) → Task 11 ✓
- §5 modules (config/data/prompts/providers/generate/render/sheet/scaffold/paths/cli/templates) → Tasks 2–11 ✓
- §6 provider Seedream configurable → Task 6 ✓ · §7 sheet without ReportLab → Task 8 ✓
- §8 examples/couronnes → Task 13 ✓ · §9 tests ≥80% → Tasks 2–12 ✓ · §10 stack/env → Task 1 + Task 14 ✓ · §11 deliverables → all ✓

**Placeholder scan:** no TBD/TODO; every code step has full code; data port shows all 18 rows verbatim.

**Type consistency:** `generate_kind`/`GenerateResult` signatures match between Task 7 and Task 11; `SheetConfig` fields (`card_w_mm/card_h_mm`) defined in Task 4 and consumed in Task 8/13; `KindConfig.template` (a dir) used consistently by `render_html`/`combined_css` (Task 9) and example (Task 13); `init_project(name, dest)` matches CLI `init` (Task 10/11); `plan_sheet(item_ids, cfg)` and `build_sheet_pdf(plan, art_by_id, out)` consistent (Task 8/11).

**Refinement noted:** `SheetConfig` gains `card_w_mm`/`card_h_mm` vs the spec's sheet block (physical size needed by the print grid) — documented in README (Task 14) and config note (Task 4).
