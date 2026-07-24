import pytest

from tableforge.config import load_project
from tableforge.providers.base import provider_for, validate_project
from tableforge.providers.elevenlabs import ElevenLabsProvider
from tableforge.providers.manual import ManualProvider

FORGE_ISSUES = """
project: demo
providers:
  eleven: { type: elevenlabs }
kinds:
  musiques:
    asset: music
    prompts: prompts/musiques.yaml
    generate: { with: eleven, length_ms: 60000 }
  bancale:
    asset: music
    prompts: prompts/musiques.yaml
    generate: { with: eleven, voice: narrateur }
  fantome:
    asset: sfx
    prompts: prompts/sfx.yaml
    generate: { with: inconnu }
  planche:
    asset: music
    prompts: prompts/musiques.yaml
    generate: { with: eleven }
    sheet: {page: A4, cols: 3, rows: 3, card_w_mm: 63, card_h_mm: 88}
  anim:
    asset: video
    from: nulle-part
    generate: { with: manual }
  lecture:
    asset: tts
    data: data/pnj.yaml
    generate: { with: eleven, voice: absente }
  dessins:
    prompts: prompts/dessins.yaml
    template: templates/card
    render_size: {width: 10, height: 10}
    generate: { with: eleven }
"""

FORGE_CLEAN = """
project: demo
providers:
  eleven: { type: elevenlabs }
voices:
  narrateur: JBFqnCBsd6RMkjVDRZzb
kinds:
  musiques:
    asset: music
    prompts: prompts/musiques.yaml
    generate: { with: eleven, length_ms: 60000 }
  atelier:
    asset: sfx
    prompts: prompts/sfx.yaml
    generate: { with: manual }
"""


def _project(tmp_path, text):
    (tmp_path / "forge.yaml").write_text(text, encoding="utf-8")
    return load_project(tmp_path)


def test_validate_flags_all_issue_families(tmp_path):
    issues = validate_project(_project(tmp_path, FORGE_ISSUES))
    text = "\n".join(issues)
    assert "clés acceptées" in text                # bancale : voice interdite pour music
    assert "provider 'inconnu' inconnu" in text    # fantome
    assert "sheet" in text                         # planche : sheet sur non-image
    assert "nulle-part" in text                    # anim : from vers kind inexistant
    assert "voix 'absente' inconnue" in text       # lecture : voix hors map voices:
    assert "ne sait pas générer" in text           # dessins : eleven ne fait pas d'image
    assert len(issues) >= 6


def test_validate_from_must_target_image_kind(tmp_path):
    forge = FORGE_CLEAN + """
  anim:
    asset: video
    from: musiques
    generate: { with: manual }
"""
    issues = validate_project(_project(tmp_path, forge))
    assert any("from" in issue and "image" in issue for issue in issues)


def test_validate_clean_project_returns_empty(tmp_path):
    assert validate_project(_project(tmp_path, FORGE_CLEAN)) == []


def test_validate_kind_without_generate_still_flags_sheet_and_from(tmp_path):
    # Un kind sans bloc generate: (ex. purement manuel/hors-scope génération)
    # doit quand même être passé au crible pour sheet/from — _kind_issues
    # retourne tôt après ces contrôles quand generate est absent, sans jamais
    # tenter de résoudre un provider.
    forge = FORGE_CLEAN + """
  affichette:
    asset: music
    from: nulle-part
    sheet: {page: A4, cols: 1, rows: 1, card_w_mm: 10, card_h_mm: 10}
"""
    issues = validate_project(_project(tmp_path, forge))
    text = "\n".join(issues)
    assert "sheet" in text
    assert "nulle-part" in text


def test_provider_for_routes_elevenlabs_and_manual(tmp_path):
    project = _project(tmp_path, FORGE_CLEAN)
    assert isinstance(provider_for(project, project.kind("musiques")), ElevenLabsProvider)
    assert isinstance(provider_for(project, project.kind("atelier")), ManualProvider)
