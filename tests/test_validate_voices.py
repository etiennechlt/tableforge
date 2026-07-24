from pathlib import Path

from tableforge.config import load_project
from tableforge.providers.base import validate_project

FORGE = """
project: demo
providers:
  eleven:
    type: elevenlabs
voices:
  narrateur: id-narrateur
kinds:
  regles:
    asset: tts
    prompts: prompts/regles.yaml
    generate: { with: eleven, voice: fantome }
  dialogues:
    asset: dialogue
    prompts: prompts/dialogues.yaml
    generate: { with: eleven }
"""

REGLES = 'entries:\n  x: { text: "Bonjour." }\n'
DIALOGUES = 'entries:\n  intro:\n    lines:\n      - { voice: spectre, text: "Bouh." }\n'


def _project(tmp_path: Path, forge: str):
    (tmp_path / "forge.yaml").write_text(forge, encoding="utf-8")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "regles.yaml").write_text(REGLES, encoding="utf-8")
    (tmp_path / "prompts" / "dialogues.yaml").write_text(DIALOGUES, encoding="utf-8")
    return load_project(tmp_path)


def test_validate_flags_unknown_voice_in_generate(tmp_path):
    issues = validate_project(_project(tmp_path, FORGE))

    assert any("fantome" in issue for issue in issues)
    assert any("narrateur" in issue for issue in issues)


def test_validate_flags_unknown_voice_in_dialogue_lines(tmp_path):
    issues = validate_project(_project(tmp_path, FORGE))

    assert any("spectre" in issue for issue in issues)


def test_validate_accepts_known_voices(tmp_path):
    forge_ok = FORGE.replace("voice: fantome", "voice: narrateur")
    dialogues_ok = DIALOGUES.replace("voice: spectre", "voice: narrateur")
    project = _project(tmp_path, forge_ok)
    (project.root / "prompts" / "dialogues.yaml").write_text(dialogues_ok, encoding="utf-8")

    issues = validate_project(project)

    assert issues == []
