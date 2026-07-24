from pathlib import Path

import pytest

from tableforge.providers.manual import ManualProvider
from tableforge.targets import KindSpec, Target


def _spec() -> KindSpec:
    return KindSpec(kind="affiche", asset="sfx", provider_name="manual", options={},
                    targets=(Target(id="poster", text="A whoosh. Punchy.",
                                    settings={"loop": False, "duration_s": 1.0}),),
                    output_format=None, root=Path("/proj"))


def test_plan_builds_manual_cards():
    jobs = ManualProvider().plan(_spec())
    assert len(jobs) == 1
    job = jobs[0]
    assert job.dest == Path("/proj/out/audio/affiche/poster.mp3")
    assert job.request == {"manual": True, "prompt": "A whoosh. Punchy.",
                           "settings": {"loop": False, "duration_s": 1.0}}
    assert job.payload["kind"] == "affiche"


def test_execute_refuses_pointing_to_studio():
    job = ManualProvider().plan(_spec())[0]
    with pytest.raises(RuntimeError) as exc:
        ManualProvider().execute(job)
    message = str(exc.value)
    assert "forge studio affiche" in message
    assert str(job.dest) in message
