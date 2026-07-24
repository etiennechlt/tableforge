"""Tests P3b — images via Higgsfield : capacités, options, plan, execute."""
from pathlib import Path

import pytest
from pydantic import ValidationError

from tableforge.providers.base import SUPPORTED_ASSETS, options_model


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
