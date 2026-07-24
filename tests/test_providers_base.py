from pathlib import Path
from types import SimpleNamespace

import pytest

from tableforge.config import load_project
from tableforge.providers.base import (AssetJob, ensure_provider,
                                       resolve_provider_name)

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
    from tableforge.providers.base import provider_for
    project = _project(tmp_path)
    provider = provider_for(project, project.kind("cards"))
    assert provider.api_key is None and provider.api_key_env == "ARK_API_KEY"


def test_provider_for_other_types_not_implemented_in_p0(tmp_path):
    from tableforge.providers.base import provider_for
    project = _project(tmp_path)
    with pytest.raises(NotImplementedError):
        provider_for(project, project.kind("nappes"))       # elevenlabs -> P1
    with pytest.raises(NotImplementedError):
        provider_for(project, project.kind("affiche"))      # manual -> P1
