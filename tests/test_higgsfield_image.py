"""Tests P3b — images via Higgsfield : capacités, options, plan, execute."""
from pathlib import Path

import pytest
from pydantic import ValidationError

from tableforge.config import HiggsfieldProviderConfig
from tableforge.providers.base import SUPPORTED_ASSETS, options_model
from tableforge.providers.higgsfield import (IMAGE_REF_FIELD, HiggsfieldProvider,
                                             build_image_body)
from tableforge.targets import KindSpec, Target


def test_supported_assets_higgsfield_includes_image():
    # Arrange / Act
    supported = SUPPORTED_ASSETS["higgsfield"]

    # Assert
    assert "image" in supported
    assert "video" in supported


def test_options_model_higgsfield_image_accepts_contract_keys():
    # Arrange
    model = options_model("higgsfield", "image")

    # Act
    opts = model(model="bytedance/seedream/v4/text-to-image", aspect_ratio="3:4",
                 resolution="2k", style_id="9b68b243", style_strength=0.7, seed=42)

    # Assert
    assert opts.model == "bytedance/seedream/v4/text-to-image"
    assert opts.aspect_ratio == "3:4"
    assert opts.style_strength == 0.7
    assert opts.seed == 42


def test_options_model_higgsfield_image_rejects_unknown_key():
    # Arrange
    model = options_model("higgsfield", "image")

    # Act / Assert
    with pytest.raises(ValidationError):
        model(sise="2k")


def _provider() -> HiggsfieldProvider:
    return HiggsfieldProvider.from_config(HiggsfieldProviderConfig(type="higgsfield"))


def _image_spec(root, *, options=None, refs=(), notes=(),
                text="A footman. Dark fantasy.") -> KindSpec:
    target = Target(id="lame", text=text, refs=tuple(refs), notes=tuple(notes))
    return KindSpec(kind="cards-soul", asset="image", provider_name="higgsfield",
                    options=dict(options or {}), targets=(target,),
                    output_format=None, root=Path(root))


def test_build_image_body_keeps_only_contract_options():
    # Arrange
    options = {"model": "x/y/z", "aspect_ratio": "3:4", "style_strength": 0.7}

    # Act
    body = build_image_body("A footman.", options=options)

    # Assert
    assert body == {"prompt": "A footman.", "aspect_ratio": "3:4",
                    "style_strength": 0.7}   # "model" est le slug, pas le body


def test_plan_image_uses_default_soul_slug_and_art_dest(tmp_path):
    # Arrange
    spec = _image_spec(tmp_path)

    # Act
    jobs = _provider().plan(spec)

    # Assert
    assert len(jobs) == 1
    job = jobs[0]
    assert job.id == "lame"
    assert job.payload["path"] == "/higgsfield-ai/soul/standard"
    assert job.payload["json"] == {"prompt": "A footman. Dark fantasy."}
    assert job.dest == tmp_path / "out" / "art" / "cards-soul" / "lame.png"


def test_plan_image_honours_model_and_style_options(tmp_path):
    # Arrange
    spec = _image_spec(tmp_path, options={
        "model": "bytedance/seedream/v4/text-to-image", "aspect_ratio": "3:4",
        "resolution": "2k", "style_id": "9b68b243", "style_strength": 0.7, "seed": 42})

    # Act
    job = _provider().plan(spec)[0]

    # Assert
    assert job.payload["path"] == "/bytedance/seedream/v4/text-to-image"
    assert job.payload["json"]["aspect_ratio"] == "3:4"
    assert job.payload["json"]["resolution"] == "2k"
    assert job.payload["json"]["style_id"] == "9b68b243"
    assert job.payload["json"]["style_strength"] == 0.7
    assert job.payload["json"]["seed"] == 42
    assert "model" not in job.payload["json"]


def test_plan_image_hides_reference_data_urls_in_request(tmp_path):
    # Arrange
    refs = ("data:image/jpeg;base64,AAA", "data:image/jpeg;base64,BBB")
    spec = _image_spec(tmp_path, refs=refs)

    # Act
    job = _provider().plan(spec)[0]

    # Assert
    assert job.payload["json"][IMAGE_REF_FIELD] == list(refs)
    assert job.request["json"][IMAGE_REF_FIELD] == "[2 référence(s), data-URLs omises]"
    assert "data:image" not in str(job.request)


def test_plan_image_propagates_target_notes(tmp_path):
    # Arrange
    spec = _image_spec(tmp_path, notes=("avertissement",))

    # Act
    job = _provider().plan(spec)[0]

    # Assert
    assert job.notes == ("avertissement",)
