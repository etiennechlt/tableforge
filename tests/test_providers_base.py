from pathlib import Path
from types import SimpleNamespace

import pytest

from tableforge.config import load_project
from tableforge.providers.base import (AssetJob, SUPPORTED_ASSETS,
                                       ensure_provider, options_model,
                                       provider_for, resolve_provider_name,
                                       validate_project)

FORGE = """
project: demo
providers:
  ark:
    type: seedream
    base_url: https://ark.x/api/v3
    api_key_env: ARK_API_KEY
    model: seedream-5-0-260128
  eleven:
    type: elevenlabs
kinds:
  cards:
    prompts: prompts/cards.yaml
    generate: {with: ark}
  libre:
    prompts: prompts/libre.yaml
  nappes:
    asset: sfx
    prompts: prompts/nappes.yaml
  affiche:
    prompts: prompts/affiche.yaml
    generate: {with: manual}
"""


def _project(tmp_path: Path):
    (tmp_path / "forge.yaml").write_text(FORGE, encoding="utf-8")
    return load_project(tmp_path)


def test_explicit_with_wins(tmp_path):
    project = _project(tmp_path)
    assert resolve_provider_name(project, project.kind("cards")) == "ark"


def test_manual_is_reserved(tmp_path):
    project = _project(tmp_path)
    assert resolve_provider_name(project, project.kind("affiche")) == "manual"


def test_unknown_with_lists_declared(tmp_path):
    project = _project(tmp_path)
    kind = project.kind("cards").model_copy(deep=True)
    kind.generate.with_ = "typo"
    with pytest.raises(ValueError, match="ark, eleven"):
        resolve_provider_name(project, kind)


def test_auto_resolution_single_candidate(tmp_path):
    project = _project(tmp_path)
    # asset image : seul 'ark' (seedream) sait faire -> auto-résolution
    assert resolve_provider_name(project, project.kind("libre")) == "ark"
    # asset sfx : seul 'eleven' (elevenlabs) sait faire
    assert resolve_provider_name(project, project.kind("nappes")) == "eleven"


def test_auto_resolution_ambiguous_lists_candidates(tmp_path):
    text = FORGE.replace("  eleven:\n    type: elevenlabs\n",
                         "  ark2:\n    type: seedream\n    base_url: https://b.x\n"
                         "    api_key_env: K2\n    model: m2\n")
    (tmp_path / "forge.yaml").write_text(text, encoding="utf-8")
    project = load_project(tmp_path)
    with pytest.raises(ValueError, match="ark, ark2"):
        resolve_provider_name(project, project.kind("libre"))


def test_auto_resolution_no_candidate(tmp_path):
    project = _project(tmp_path)
    kind = project.kind("libre").model_copy(update={"asset": "video"})
    with pytest.raises(ValueError, match="aucun provider"):
        resolve_provider_name(project, kind)


def test_ensure_provider_passthrough_and_wrap(tmp_path):
    class Modern:
        def plan(self, spec):
            return []

        def execute(self, job):
            return []

    modern = Modern()
    assert ensure_provider(modern) is modern

    class Legacy:
        def build(self, prompt, size=None, refs=None):
            return {"prompt": prompt, "size": size}

        def generate(self, prompt, dest, size=None, refs=None):
            return [dest]

    adapter = ensure_provider(Legacy())
    spec = SimpleNamespace(kind="cards", asset="image", root=Path("/proj"),
                           output_format="png",
                           targets=(SimpleNamespace(id="lame", text="A footman.",
                                                    refs=("data:x",),
                                                    settings={"size": "32x32"},
                                                    notes=()),))
    jobs = adapter.plan(spec)
    assert [j.id for j in jobs] == ["lame"]
    assert jobs[0].dest == Path("/proj/out/art/cards/lame.png")
    assert jobs[0].payload == {"prompt": "A footman.", "size": "32x32",
                               "refs": ["data:x"]}
    assert adapter.execute(jobs[0]) == [jobs[0].dest]


def test_asset_job_is_frozen():
    job = AssetJob(id="x", dest=Path("/tmp/x.png"), request={})
    with pytest.raises(Exception):
        job.id = "y"


def test_from_provider_config_is_keyless(tmp_path, monkeypatch):
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    from tableforge.providers.seedream import SeedreamProvider
    project = _project(tmp_path)
    provider = SeedreamProvider.from_provider_config(project.providers["ark"])
    assert provider.api_key is None
    assert provider.api_key_env == "ARK_API_KEY"
    assert provider.model == "seedream-5-0-260128"


def test_require_key_reads_env_at_execute_time(tmp_path, monkeypatch):
    from tableforge.providers.seedream import SeedreamProvider
    project = _project(tmp_path)
    provider = SeedreamProvider.from_provider_config(project.providers["ark"])
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ARK_API_KEY"):
        provider._require_key()
    monkeypatch.setenv("ARK_API_KEY", "secret")
    assert provider._require_key() == "secret"


def test_seedream_plan_matches_build_summary(tmp_path, monkeypatch):
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    from tableforge.providers.seedream import (SeedreamProvider,
                                               summarize_request)
    project = _project(tmp_path)
    provider = SeedreamProvider.from_provider_config(project.providers["ark"])
    spec = SimpleNamespace(kind="cards", asset="image", root=Path("/proj"),
                           output_format="png",
                           targets=(SimpleNamespace(id="lame", text="A footman. Dark.",
                                                    refs=("data:x",),
                                                    settings={"size": "32x32"},
                                                    notes=()),))
    jobs = provider.plan(spec)
    assert jobs[0].dest == Path("/proj/out/art/cards/lame.png")
    assert jobs[0].request == summarize_request(
        provider.build("A footman. Dark.", size="32x32", refs=["data:x"]))
    assert jobs[0].payload == {"prompt": "A footman. Dark.", "size": "32x32",
                               "refs": ["data:x"]}


def test_provider_for_builds_keyless_seedream(tmp_path, monkeypatch):
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    project = _project(tmp_path)
    provider = provider_for(project, project.kind("cards"))
    assert provider.api_key is None and provider.api_key_env == "ARK_API_KEY"


def test_provider_for_routes_elevenlabs_and_manual_in_p1(tmp_path):
    # P1 (task 9) : provider_for route désormais elevenlabs et manual au lieu de
    # lever NotImplementedError (P0 stub). Higgsfield est branché en P3a (task 6,
    # cf. test_provider_for_returns_higgsfield_provider plus bas).
    from tableforge.providers.elevenlabs import ElevenLabsProvider
    from tableforge.providers.manual import ManualProvider
    project = _project(tmp_path)
    assert isinstance(provider_for(project, project.kind("nappes")), ElevenLabsProvider)
    assert isinstance(provider_for(project, project.kind("affiche")), ManualProvider)


# --- P3a Task 6 : branchement registre higgsfield (provider_for/options_model) --

VIDEO_FORGE = """
project: demo
providers:
  hf:
    type: higgsfield
kinds:
  teaser:
    asset: video
    prompts: prompts/teaser.yaml
    generate: {with: hf, model: kling-video/v2.1/standard/text-to-video}
"""

VIDEO_CATALOG = """
direction: "Cinematic."
entries:
  intro: {prompt: "A ruined throne room"}
"""


def _video_project(tmp_path, forge=VIDEO_FORGE):
    (tmp_path / "forge.yaml").write_text(forge, encoding="utf-8")
    (tmp_path / "prompts").mkdir(exist_ok=True)
    (tmp_path / "prompts" / "teaser.yaml").write_text(VIDEO_CATALOG, encoding="utf-8")
    return load_project(tmp_path)


def test_supported_assets_declare_higgsfield_video():
    assert "video" in SUPPORTED_ASSETS["higgsfield"]


def test_provider_for_returns_higgsfield_provider(tmp_path):
    # Arrange
    project = _video_project(tmp_path)

    # Act
    provider = provider_for(project, project.kind("teaser"))

    # Assert
    from tableforge.providers.higgsfield import HiggsfieldProvider
    assert isinstance(provider, HiggsfieldProvider)
    assert provider.base_url == "https://platform.higgsfield.ai"


def test_options_model_higgsfield_video():
    from tableforge.providers.higgsfield import HiggsfieldVideoOptions
    assert options_model("higgsfield", "video") is HiggsfieldVideoOptions


def test_validate_project_flags_unknown_video_option(tmp_path):
    # Arrange — fps n'est pas une option (higgsfield, video)
    forge = VIDEO_FORGE.replace(
        "generate: {with: hf, model: kling-video/v2.1/standard/text-to-video}",
        "generate: {with: hf, model: kling-video/v2.1/standard/text-to-video, fps: 24}")
    project = _video_project(tmp_path, forge=forge)

    # Act
    issues = validate_project(project)

    # Assert
    assert any("fps" in issue for issue in issues)


def test_validate_project_flags_from_to_unknown_kind(tmp_path):
    # Arrange — from: vers un kind inexistant (contrôle posé en P1, verrouillé ici)
    forge = VIDEO_FORGE.replace("    prompts: prompts/teaser.yaml\n",
                                "    prompts: prompts/teaser.yaml\n    from: nope\n")
    project = _video_project(tmp_path, forge=forge)

    # Act
    issues = validate_project(project)

    # Assert
    assert any("nope" in issue for issue in issues)


# --- watch-item revue P2 : le replay du linter (ex-_voice_resolution_issues,
# renommé _target_resolution_issues) doit couvrir les kinds video, pas
# seulement tts/dialogue — sinon les erreurs de build_kind_spec propres à la
# vidéo (catalogue de mouvement avec un id hors des cartes source) ne
# remontent jamais dans `forge list`, seulement à l'exécution. -------------

I2V_FORGE = """
project: demo
providers:
  hf:
    type: higgsfield
kinds:
  cartes:
    prompts: prompts/cartes.yaml
  cartes-animees:
    asset: video
    from: cartes
    prompts: prompts/cartes-animees.yaml
    generate: {with: hf, model: bytedance/seedance/v1/image-to-video}
"""

CARTES_PROMPTS = """
art_direction: "Dark fantasy."
prompts:
  lame: "A footman."
"""

ORPHAN_MOTION_CATALOG = """
direction: "Slow atmospheric motion."
entries:
  fantome: {prompt: "A ghost stirs"}
"""


def test_validate_project_surfaces_i2v_catalog_entry_outside_source_ids(tmp_path):
    # Arrange
    (tmp_path / "forge.yaml").write_text(I2V_FORGE, encoding="utf-8")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "cartes.yaml").write_text(CARTES_PROMPTS, encoding="utf-8")
    (tmp_path / "prompts" / "cartes-animees.yaml").write_text(ORPHAN_MOTION_CATALOG,
                                                              encoding="utf-8")
    project = load_project(tmp_path)

    # Act
    issues = validate_project(project)

    # Assert
    assert any("fantome" in issue for issue in issues)
