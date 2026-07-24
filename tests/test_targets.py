from pathlib import Path

import pytest

from tableforge.config import load_project
from tableforge.targets import build_kind_spec

FORGE = """
project: demo
providers:
  ark:
    type: seedream
    base_url: https://ark.x/api/v3
    api_key_env: ARK_API_KEY
    model: seedream-5-0-260128
    default_size: "64x64"
  eleven:
    type: elevenlabs
kinds:
  cards:
    prompts: prompts/cards.yaml
    art_size: "32x32"
    generate: {with: ark}
  sans-prompts:
    template: templates/card
    render_size: {width: 10, height: 10}
    generate: {with: ark}
  nappes:
    asset: video
    prompts: prompts/nappes.yaml
    generate: {with: manual}
"""

PROMPTS = """
art_direction: "Dark fantasy."
negative: "Avoid: text."
prompts:
  lame: "A footman."
  emissaire: "A hooded envoy."
"""

NAPPES_CATALOG = """
direction: "Ambient tablecloth motion, seamless loop."
entries:
  fond: {prompt: "The tablecloth ripples gently"}
"""


def _project(tmp_path: Path):
    (tmp_path / "forge.yaml").write_text(FORGE, encoding="utf-8")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "cards.yaml").write_text(PROMPTS, encoding="utf-8")
    (tmp_path / "prompts" / "nappes.yaml").write_text(NAPPES_CATALOG, encoding="utf-8")
    return load_project(tmp_path)


def test_image_spec_resolves_targets_and_settings(tmp_path):
    project = _project(tmp_path)
    spec = build_kind_spec(project, "cards")
    assert (spec.kind, spec.asset, spec.provider_name) == ("cards", "image", "ark")
    assert spec.root == project.root
    assert spec.output_format == "png"
    assert [t.id for t in spec.targets] == ["lame", "emissaire"]
    lame = spec.targets[0]
    assert lame.text == "A footman. Dark fantasy. Avoid: text."
    assert lame.settings == {"size": "32x32"}   # art_size prime sur default_size
    assert lame.refs == ()                       # pas de style_refs déclarées


def test_image_spec_falls_back_to_provider_default_size(tmp_path):
    project = _project(tmp_path)
    kind = project.kind("cards").model_copy(update={"art_size": None})
    project = project.model_copy(update={"kinds": {**project.kinds, "cards": kind}})
    spec = build_kind_spec(project, "cards")
    assert spec.targets[0].settings == {"size": "64x64"}


def test_ids_filter_preserves_order(tmp_path):
    spec = build_kind_spec(_project(tmp_path), "cards", ids=["emissaire"])
    assert [t.id for t in spec.targets] == ["emissaire"]


def test_image_kind_without_prompts_raises(tmp_path):
    with pytest.raises(ValueError, match="prompts"):
        build_kind_spec(_project(tmp_path), "sans-prompts")


def test_video_asset_now_builds_a_spec(tmp_path):
    # 'sfx' (P1) puis 'dialogue' (P2) et enfin 'video' (P3a, task-5-brief.md) sont
    # désormais implémentés — il ne reste plus d'asset NYI dans build_kind_spec :
    # ce test remplace l'ancien garde-fou NotImplementedError('video').
    spec = build_kind_spec(_project(tmp_path), "nappes")
    assert spec.asset == "video"
    assert spec.provider_name == "manual"
    assert [t.id for t in spec.targets] == ["fond"]


def test_options_come_from_generate_extras(tmp_path):
    from tableforge.config import GenerateConfig
    project = _project(tmp_path)
    kind = project.kind("cards").model_copy(
        update={"generate": GenerateConfig(**{"with": "ark", "style": "sombre"})})
    project = project.model_copy(update={"kinds": {**project.kinds, "cards": kind}})
    spec = build_kind_spec(project, "cards")
    assert spec.options == {"style": "sombre"}


# --- P3a Task 5 : cibles vidéo — i2v (from:) et t2v (catalogue) -------------

FORGE_VIDEO = """
project: demo
providers:
  ark:
    type: seedream
    base_url: https://ark.x/api/v3
    api_key_env: ARK_API_KEY
    model: seedream-5-0-260128
  hf:
    type: higgsfield
kinds:
  cards:
    prompts: prompts/cards.yaml
    template: templates/card
    render_size: {width: 10, height: 10}
    generate: {with: ark}
  cartes-animees:
    asset: video
    from: cards
    prompts: prompts/cartes-animees.yaml
    generate: {with: hf, model: bytedance/seedance/v1/image-to-video}
  teaser:
    asset: video
    prompts: prompts/teaser.yaml
    generate: {with: hf, model: kling-video/v2.1/standard/text-to-video, aspect_ratio: "16:9"}
"""

CARDS_PROMPTS = """
art_direction: "Dark fantasy."
prompts:
  lame: "A footman."
  emissaire: "A hooded envoy."
"""

MOTION_CATALOG = """
direction: "Slow atmospheric motion, seamless loop."
defaults:
  duration_s: 5
entries:
  lame: {prompt: "The cloak ripples in a cold wind"}
"""

TEASER_CATALOG = """
direction: "Cinematic dark fantasy trailer shot."
entries:
  intro: {prompt: "A ruined throne room, ash rising", duration_s: 8}
"""


def _video_project(tmp_path, motion=MOTION_CATALOG, art_ids=("lame", "emissaire")):
    (tmp_path / "forge.yaml").write_text(FORGE_VIDEO, encoding="utf-8")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "cards.yaml").write_text(CARDS_PROMPTS, encoding="utf-8")
    (tmp_path / "prompts" / "cartes-animees.yaml").write_text(motion, encoding="utf-8")
    (tmp_path / "prompts" / "teaser.yaml").write_text(TEASER_CATALOG, encoding="utf-8")
    art_dir = tmp_path / "out" / "art" / "cards"
    art_dir.mkdir(parents=True)
    for art_id in art_ids:
        (art_dir / f"{art_id}.png").write_bytes(b"png")
    return load_project(tmp_path)


def test_t2v_spec_uses_catalog_entries(tmp_path):
    # Arrange
    project = _video_project(tmp_path)

    # Act
    spec = build_kind_spec(project, "teaser")

    # Assert
    assert spec.asset == "video"
    assert spec.provider_name == "hf"
    assert spec.options == {"model": "kling-video/v2.1/standard/text-to-video",
                            "aspect_ratio": "16:9"}
    assert [t.id for t in spec.targets] == ["intro"]
    target = spec.targets[0]
    assert target.text == "A ruined throne room, ash rising. Cinematic dark fantasy trailer shot."
    assert target.settings == {"duration_s": 8}
    assert target.source_image is None


def test_t2v_without_catalog_raises(tmp_path):
    # Arrange — teaser sans fichier prompts
    forge = FORGE_VIDEO.replace("    prompts: prompts/teaser.yaml\n", "")
    (tmp_path / "forge.yaml").write_text(forge, encoding="utf-8")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "cards.yaml").write_text(CARDS_PROMPTS, encoding="utf-8")
    (tmp_path / "prompts" / "cartes-animees.yaml").write_text(MOTION_CATALOG, encoding="utf-8")
    project = load_project(tmp_path)

    # Act / Assert
    with pytest.raises(ValueError, match="prompts"):
        build_kind_spec(project, "teaser")


def test_i2v_targets_are_union_of_art_and_catalog(tmp_path):
    # Arrange — art pour lame + emissaire, catalogue pour lame seulement
    project = _video_project(tmp_path)

    # Act
    spec = build_kind_spec(project, "cartes-animees")

    # Assert
    assert [t.id for t in spec.targets] == ["emissaire", "lame"]
    lame = next(t for t in spec.targets if t.id == "lame")
    assert lame.text == "The cloak ripples in a cold wind. Slow atmospheric motion, seamless loop."
    assert lame.settings == {"duration_s": 5}
    assert lame.source_image == tmp_path / "out" / "art" / "cards" / "lame.png"
    assert lame.notes == ()
    emissaire = next(t for t in spec.targets if t.id == "emissaire")
    assert emissaire.text == "Slow atmospheric motion, seamless loop."
    assert emissaire.settings == {"duration_s": 5}


def test_i2v_missing_art_adds_warning_note(tmp_path):
    # Arrange — entrée catalogue 'lame' mais aucun art généré
    project = _video_project(tmp_path, art_ids=())

    # Act
    spec = build_kind_spec(project, "cartes-animees")

    # Assert — la cible existe (dry-run possible), avec note d'avertissement
    assert [t.id for t in spec.targets] == ["lame"]
    assert any("art source manquant" in note for note in spec.targets[0].notes)
    assert any("forge generate cards" in note for note in spec.targets[0].notes)


MOTION_CATALOG_NO_DIRECTION = """
entries:
  lame: {prompt: "The cloak ripples in a cold wind"}
"""


def test_i2v_art_only_target_without_direction_notes_empty_prompt(tmp_path):
    # Arrange — 'emissaire' a de l'art mais aucune entrée catalogue, et le
    # catalogue n'a pas de 'direction:' : le prompt assemblé serait "" (aucun
    # texte à envoyer au provider). Fold-in P3a (revue finale) : ça doit
    # produire une note, pas un envoi silencieux de prompt vide.
    project = _video_project(tmp_path, motion=MOTION_CATALOG_NO_DIRECTION)

    # Act
    spec = build_kind_spec(project, "cartes-animees")

    # Assert
    emissaire = next(t for t in spec.targets if t.id == "emissaire")
    assert emissaire.text == ""
    assert any("prompt vide" in note for note in emissaire.notes)


def test_i2v_catalog_entry_outside_source_ids_raises_naming_both_files(tmp_path):
    # Arrange
    bad_catalog = MOTION_CATALOG + "  fantome: {prompt: \"ghost\"}\n"

    # Act / Assert
    project = _video_project(tmp_path, motion=bad_catalog)
    with pytest.raises(ValueError) as excinfo:
        build_kind_spec(project, "cartes-animees")
    message = str(excinfo.value)
    assert "fantome" in message
    assert "cartes-animees.yaml" in message
    assert "cards.yaml" in message


def test_i2v_filters_ids_and_rejects_unknown(tmp_path):
    # Arrange
    project = _video_project(tmp_path)

    # Act
    spec = build_kind_spec(project, "cartes-animees", ids=["lame"])

    # Assert
    assert [t.id for t in spec.targets] == ["lame"]
    with pytest.raises(KeyError, match="inconnu"):
        build_kind_spec(project, "cartes-animees", ids=["nope"])
