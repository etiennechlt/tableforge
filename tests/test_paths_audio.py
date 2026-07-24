from pathlib import Path

from tableforge import paths


def test_extension_for_audio_formats():
    assert paths.extension_for("music", "mp3_44100_128") == ".mp3"
    assert paths.extension_for("sfx", None) == ".mp3"
    assert paths.extension_for("tts", "opus_48000_64") == ".ogg"
    assert paths.extension_for("dialogue", "pcm_16000") == ".wav"
    assert paths.extension_for("music", "ulaw_8000") == ".wav"
    assert paths.extension_for("music", "alaw_8000") == ".wav"


def test_extension_for_image_and_video():
    assert paths.extension_for("image", None) == ".png"
    assert paths.extension_for("image", "jpeg") == ".jpeg"
    assert paths.extension_for("video", None) == ".mp4"


def test_asset_path_audio():
    root = Path("/proj")
    assert paths.asset_dir(root, "music", "musiques") == root / "out" / "audio" / "musiques"
    assert (paths.asset_path(root, "sfx", "nappes", "fleau", "mp3_44100_128")
            == root / "out" / "audio" / "nappes" / "fleau.mp3")
