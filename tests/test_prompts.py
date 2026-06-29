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
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (2048, 1536), "gray").save(path)


def test_reference_data_urls_caps_and_adds_override(tmp_path):
    for n in ("a", "b", "c", "d", "x"):
        _png(tmp_path / "reference" / f"{n}.png")
    urls = reference_data_urls(CFG, tmp_path, "couronne-maudite", max_refs=3, max_px=64)
    # 3 base refs (capped) + 1 override ref = 4
    assert len(urls) == 4
    assert all(u.startswith("data:image/jpeg;base64,") for u in urls)


def test_reference_data_urls_no_id(tmp_path):
    for n in ("a", "b", "c", "d"):
        _png(tmp_path / "reference" / f"{n}.png")
    urls = reference_data_urls(CFG, tmp_path, None, max_refs=2, max_px=64)
    assert len(urls) == 2


def test_encode_downscales(tmp_path):
    p = tmp_path / "ref.png"
    _png(p)
    url = encode_image_data_url(p, max_px=32)
    assert url.startswith("data:image/jpeg;base64,")
