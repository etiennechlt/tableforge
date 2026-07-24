from pathlib import Path

import pytest

from tableforge.catalog import (
    MUSIC_MAX_MS,
    MUSIC_MIN_MS,
    SFX_MAX_S,
    SFX_MIN_S,
    build_media_prompt,
    catalog_entries,
    clamp_music_length_ms,
    clamp_sfx_duration_s,
    get_entry,
    load_catalog,
    prompt_for_entry,
)

CATALOG = {
    "direction": "Epic orchestral score.",
    "negative": "No vocals.",
    "defaults": {"length_ms": 60000},
    "entries": {
        "menu": {"prompt": "Main theme", "length_ms": 90000},
        "raw": "Just a bare prompt",
    },
}


def test_load_catalog_reads_yaml(tmp_path: Path):
    path = tmp_path / "music.yaml"
    path.write_text("direction: Epic.\nentries:\n  menu: {prompt: Theme}\n", encoding="utf-8")
    cfg = load_catalog(path)
    assert cfg["direction"] == "Epic."
    assert cfg["entries"]["menu"]["prompt"] == "Theme"


def test_catalog_entries_requires_entries_key():
    with pytest.raises(KeyError, match="entries"):
        catalog_entries({"tracks": {}})
    assert catalog_entries(CATALOG)["menu"]["length_ms"] == 90000


def test_get_entry_wraps_bare_string():
    assert get_entry(CATALOG, "raw") == {"prompt": "Just a bare prompt"}


def test_get_entry_unknown_id_raises_french():
    with pytest.raises(KeyError, match="aucune entrée"):
        get_entry(CATALOG, "nope")


def test_build_media_prompt_joins_subject_and_direction():
    assert build_media_prompt("A theme.", "Epic score.") == "A theme. Epic score."
    assert build_media_prompt("A theme", "") == "A theme."


def test_prompt_for_entry_folds_negative():
    text = prompt_for_entry("menu", CATALOG)
    assert text == "Main theme. Epic orchestral score. No vocals."


def test_prompt_for_entry_without_negative():
    text = prompt_for_entry("menu", CATALOG, with_negative=False)
    assert text == "Main theme. Epic orchestral score."


def test_clamp_music_length_bounds():
    assert clamp_music_length_ms(1000) == MUSIC_MIN_MS
    assert clamp_music_length_ms(700000) == MUSIC_MAX_MS
    assert clamp_music_length_ms(90000) == 90000


def test_clamp_sfx_duration_bounds():
    assert clamp_sfx_duration_s(0.1) == SFX_MIN_S
    assert clamp_sfx_duration_s(60) == SFX_MAX_S
    assert clamp_sfx_duration_s(2.5) == 2.5
