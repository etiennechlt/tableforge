import json
from pathlib import Path

import httpx
import respx

from tableforge.config import load_project
from tableforge.providers.elevenlabs import (
    DIALOGUE_SOFT_LIMIT,
    ElevenLabsProvider,
    build_dialogue_request,
    build_tts_request,
)
from tableforge.targets import DialogueLine, build_kind_spec


def test_build_tts_request_shapes_path_body_and_params():
    req = build_tts_request("Bonjour.", voice_id="V1", model="eleven_multilingual_v2",
                            language="fr", seed=7, output_format="mp3_44100_128")

    assert req["path"] == "/v1/text-to-speech/V1"
    assert req["json"] == {"text": "Bonjour.", "model_id": "eleven_multilingual_v2",
                           "language_code": "fr", "seed": 7}
    assert req["params"] == {"output_format": "mp3_44100_128"}


def test_build_tts_request_omits_optional_fields():
    req = build_tts_request("Salut", voice_id="V1", model="m", output_format="mp3_44100_128")

    assert "language_code" not in req["json"]
    assert "seed" not in req["json"]


def test_build_dialogue_request_maps_lines_in_order():
    lines = (DialogueLine(voice_id="V1", text="Oyez !"),
             DialogueLine(voice_id="V2", text="Silence."))

    req = build_dialogue_request(lines, model="eleven_v3", output_format="mp3_44100_128")

    assert req["path"] == "/v1/text-to-dialogue"
    assert req["json"] == {"inputs": [{"text": "Oyez !", "voice_id": "V1"},
                                      {"text": "Silence.", "voice_id": "V2"}],
                           "model_id": "eleven_v3"}
    assert req["params"] == {"output_format": "mp3_44100_128"}


def test_dialogue_soft_limit_is_two_thousand_chars():
    assert DIALOGUE_SOFT_LIMIT == 2000


FORGE = """
project: demo
providers:
  eleven:
    type: elevenlabs
voices:
  narrateur: id-narrateur
  heraut: id-heraut
kinds:
  narration:
    asset: tts
    data: data/cards.yaml
    generate: { with: eleven, voice: narrateur, text: "{{ name }}. {{ eff }}", language: fr }
  dialogues:
    asset: dialogue
    prompts: prompts/dialogues.yaml
    generate: { with: eleven }
"""

CARDS = """
rows:
  - { id: lame, name: "Lame", eff: "Gagner 1 Fer." }
"""

DIALOGUES = """
entries:
  intro:
    lines:
      - { voice: heraut, text: "Oyez !" }
      - { voice: narrateur, text: "Silence." }
"""


def _project(tmp_path: Path, dialogues: str = DIALOGUES):
    (tmp_path / "forge.yaml").write_text(FORGE, encoding="utf-8")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "cards.yaml").write_text(CARDS, encoding="utf-8")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "dialogues.yaml").write_text(dialogues, encoding="utf-8")
    return load_project(tmp_path)


def test_plan_tts_builds_jobs_with_audio_dest(tmp_path):
    project = _project(tmp_path)
    spec = build_kind_spec(project, "narration", ids=["lame"])
    provider = ElevenLabsProvider.from_config(project.providers["eleven"])

    jobs = provider.plan(spec)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.id == "lame"
    assert job.dest == project.root / "out" / "audio" / "narration" / "lame.mp3"
    assert job.payload["path"] == "/v1/text-to-speech/id-narrateur"
    assert job.payload["json"]["text"] == "Lame. Gagner 1 Fer."
    assert job.payload["json"]["model_id"] == "eleven_multilingual_v2"
    assert job.payload["json"]["language_code"] == "fr"
    assert job.payload["params"] == {"output_format": "mp3_44100_128"}


def test_plan_dialogue_builds_jobs_with_default_model(tmp_path):
    project = _project(tmp_path)
    spec = build_kind_spec(project, "dialogues")
    provider = ElevenLabsProvider.from_config(project.providers["eleven"])

    jobs = provider.plan(spec)

    job = jobs[0]
    assert job.dest == project.root / "out" / "audio" / "dialogues" / "intro.mp3"
    assert job.payload["path"] == "/v1/text-to-dialogue"
    assert job.payload["json"]["model_id"] == "eleven_v3"
    assert job.payload["json"]["inputs"][0] == {"text": "Oyez !", "voice_id": "id-heraut"}


def test_plan_dialogue_flags_text_longer_than_soft_limit(tmp_path):
    long_text = "x" * (DIALOGUE_SOFT_LIMIT + 100)
    dialogues = ('entries:\n  long:\n    lines:\n'
                 f'      - {{ voice: heraut, text: "{long_text}" }}\n')
    project = _project(tmp_path, dialogues=dialogues)
    spec = build_kind_spec(project, "dialogues")
    provider = ElevenLabsProvider.from_config(project.providers["eleven"])

    jobs = provider.plan(spec)

    assert any("2000" in note for note in jobs[0].notes)


@respx.mock
def test_execute_tts_posts_key_header_and_writes_file(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test")
    project = _project(tmp_path)
    spec = build_kind_spec(project, "narration", ids=["lame"])
    provider = ElevenLabsProvider.from_config(project.providers["eleven"])
    job = provider.plan(spec)[0]
    route = respx.post("https://api.elevenlabs.io/v1/text-to-speech/id-narrateur").mock(
        return_value=httpx.Response(200, content=b"MP3DATA"))

    saved = provider.execute(job)

    assert saved == [job.dest]
    assert job.dest.read_bytes() == b"MP3DATA"
    request = route.calls.last.request
    assert request.headers["xi-api-key"] == "sk-test"
    assert request.url.params["output_format"] == "mp3_44100_128"
    body = json.loads(request.content)
    assert body["text"] == "Lame. Gagner 1 Fer."
    assert body["model_id"] == "eleven_multilingual_v2"


@respx.mock
def test_execute_dialogue_posts_inputs_and_writes_file(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test")
    project = _project(tmp_path)
    spec = build_kind_spec(project, "dialogues")
    provider = ElevenLabsProvider.from_config(project.providers["eleven"])
    job = provider.plan(spec)[0]
    route = respx.post("https://api.elevenlabs.io/v1/text-to-dialogue").mock(
        return_value=httpx.Response(200, content=b"AUDIO"))

    saved = provider.execute(job)

    assert saved == [job.dest]
    assert job.dest.read_bytes() == b"AUDIO"
    body = json.loads(route.calls.last.request.content)
    assert body["inputs"] == [{"text": "Oyez !", "voice_id": "id-heraut"},
                              {"text": "Silence.", "voice_id": "id-narrateur"}]
    assert body["model_id"] == "eleven_v3"


def test_generate_kind_tts_dry_run_goes_through_provider_plan(tmp_path):
    from tableforge.generate import generate_kind

    project = _project(tmp_path)

    results = generate_kind(project, "narration", dry_run=True)

    assert [r.id for r in results] == ["lame"]
    assert results[0].dest is None
    assert results[0].request["path"] == "/v1/text-to-speech/id-narrateur"
