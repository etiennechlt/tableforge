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
    assert len(expanded) == 20   # plaidoyer & lame ont qty 2 (16×1 + 2×2)


def test_example_dry_run_builds_all_prompts():
    cfg = load_project(EXAMPLE)
    results = generate_kind(cfg, "cards", dry_run=True)
    assert len(results) == 18
    crown = next(r for r in results if r.id == "couronne-maudite")
    assert "Corrupted variant" in crown.request["prompt"]


def test_example_music_dry_run_builds_requests():
    cfg = load_project(EXAMPLE)
    results = generate_kind(cfg, "musiques", dry_run=True)
    assert len(results) == 7
    menu = next(r for r in results if r.id == "menu")
    assert menu.request["path"] == "/v1/music"
    assert menu.request["json"]["music_length_ms"] == 90000
    assert "Dark medieval fantasy orchestral score" in menu.request["json"]["prompt"]
    assert "No lead vocals" in menu.request["json"]["prompt"]
    assert menu.request["params"]["output_format"] == "mp3_44100_128"


def test_example_soundscapes_loop_and_duration():
    cfg = load_project(EXAMPLE)
    results = generate_kind(cfg, "nappes", dry_run=True)
    assert len(results) == 6
    fleau = next(r for r in results if r.id == "fleau")
    assert fleau.request["json"]["loop"] is True
    assert fleau.request["json"]["duration_seconds"] == 30.0
    assert fleau.request["json"]["model_id"] == "eleven_text_to_sound_v2"


def test_example_sfx_catalog_complete():
    cfg = load_project(EXAMPLE)
    results = generate_kind(cfg, "sfx", dry_run=True)
    assert len(results) == 15
    draw = next(r for r in results if r.id == "sfx-draw")
    assert draw.request["json"]["duration_seconds"] == 0.8
    assert draw.request["json"]["loop"] is False


def test_example_validates_clean():
    from tableforge.providers.base import validate_project
    cfg = load_project(EXAMPLE)
    assert validate_project(cfg) == []


def test_example_narration_reads_name_and_eff():
    from tableforge.targets import build_kind_spec

    cfg = load_project(EXAMPLE)

    spec = build_kind_spec(cfg, "narration", ids=["lame"])

    assert spec.asset == "tts"
    target = spec.targets[0]
    assert target.text == "Lame. Gagner 1 Fer."
    assert target.voice_id == cfg.voices["narrateur"]


def test_example_pnj_rows_pick_their_own_voice():
    from tableforge.targets import build_kind_spec

    cfg = load_project(EXAMPLE)

    spec = build_kind_spec(cfg, "voix-pnj")

    reine = next(t for t in spec.targets if t.id == "reine")
    assert reine.voice_id == cfg.voices["vieille-reine"]
    assert "cendres" in reine.text


def test_example_dialogues_resolve_all_lines():
    from tableforge.targets import build_kind_spec

    cfg = load_project(EXAMPLE)

    spec = build_kind_spec(cfg, "dialogues")

    intro = next(t for t in spec.targets if t.id == "intro")
    assert [line.voice_id for line in intro.lines] == [
        cfg.voices["heraut"], cfg.voices["vieille-reine"]]


def test_example_cartes_animees_dry_run_builds_i2v_requests():
    # Arrange
    cfg = load_project(EXAMPLE)

    # Act — aucun art généré dans le dépôt : cibles = entrées du catalogue de mouvement
    results = generate_kind(cfg, "cartes-animees", dry_run=True)

    # Assert
    assert {r.id for r in results} == {"lame", "couronne-maudite", "pacte-d-ether"}
    lame = next(r for r in results if r.id == "lame")
    assert lame.request["path"] == "/bytedance/seedance/v1/image-to-video"
    assert lame.request["json"]["image"].startswith("[image source :")
    assert "data:" not in str(lame.request)
    assert all(r.dest is None for r in results)


def test_example_teaser_dry_run_builds_t2v_request():
    # Arrange
    cfg = load_project(EXAMPLE)

    # Act
    results = generate_kind(cfg, "teaser", dry_run=True)

    # Assert
    assert [r.id for r in results] == ["intro"]
    request = results[0].request
    assert request["path"] == "/kling-video/v2.1/standard/text-to-video"
    assert request["json"]["aspect_ratio"] == "16:9"
    assert "image" not in request["json"]
