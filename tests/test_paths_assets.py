from pathlib import Path

from tableforge.paths import art_path, asset_dir, asset_path, extension_for

ROOT = Path("/proj")


def test_extension_for_image_defaults_to_png():
    assert extension_for("image", None) == ".png"
    assert extension_for("image", "webp") == ".webp"


def test_extension_for_audio_follows_output_format_prefix():
    assert extension_for("music", "mp3_44100_128") == ".mp3"
    assert extension_for("sfx", "opus_48000_128") == ".ogg"
    assert extension_for("tts", "pcm_44100") == ".wav"
    assert extension_for("dialogue", "ulaw_8000") == ".wav"
    assert extension_for("music", None) == ".mp3"


def test_extension_for_video_is_mp4():
    assert extension_for("video", None) == ".mp4"


def test_asset_dir_maps_modalities():
    assert asset_dir(ROOT, "image", "cards") == ROOT / "out" / "art" / "cards"
    assert asset_dir(ROOT, "music", "musiques") == ROOT / "out" / "audio" / "musiques"
    assert asset_dir(ROOT, "sfx", "nappes") == ROOT / "out" / "audio" / "nappes"
    assert asset_dir(ROOT, "video", "teaser") == ROOT / "out" / "video" / "teaser"


def test_asset_path_image_matches_art_path():
    assert asset_path(ROOT, "image", "cards", "lame", "png") == art_path(ROOT, "cards", "lame")


def test_asset_path_audio_uses_format_extension():
    expected = ROOT / "out" / "audio" / "nappes" / "cite.mp3"
    assert asset_path(ROOT, "sfx", "nappes", "cite", "mp3_44100_128") == expected
