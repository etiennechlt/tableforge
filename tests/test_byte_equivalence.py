"""Verrou P0 : les requêtes dry-run v1 restent strictement identiques après refactor.

Constantes calculées avec l'implémentation d'AVANT le refactor (commit 199f667).
Ne JAMAIS les régénérer depuis le code refactoré.
"""
import hashlib
import json
from pathlib import Path

from PIL import Image

from tableforge.config import load_project
from tableforge.generate import generate_kind

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "couronnes"

FORGE_V1 = """
project: demo
provider:
  base_url: https://ark.x/api/v3
  api_key_env: ARK_API_KEY
  model: seedream-5-0-260128
  default_size: "64x64"
defaults: {max_refs: 2, ref_max_px: 32}
kinds:
  cards:
    prompts: prompts/cards.yaml
    template: templates/card
    render_size: {width: 10, height: 10}
    art_size: "32x32"
"""

PROMPTS_V1 = """
art_direction: "Dark fantasy."
negative: "Avoid: text."
style_refs: [reference/a.png, reference/b.png, reference/c.png]
prompts:
  lame: "A footman."
  emissaire: "A hooded envoy"
overrides:
  lame: {suffix: "Corrupted.", style_refs: [reference/x.png]}
"""

EXPECTED_LAME = {
    "model": "seedream-5-0-260128",
    "prompt": "A footman. Dark fantasy. Corrupted. Avoid: text.",
    "size": "32x32",
    "response_format": "url",
    "extra_body": {
        "watermark": False,
        "sequential_image_generation": "auto",
        "output_format": "png",
        "image": "[3 référence(s), data-URLs omises]",
    },
}

EXPECTED_EMISSAIRE = {
    "model": "seedream-5-0-260128",
    "prompt": "A hooded envoy. Dark fantasy. Avoid: text.",
    "size": "32x32",
    "response_format": "url",
    "extra_body": {
        "watermark": False,
        "sequential_image_generation": "auto",
        "output_format": "png",
        "image": "[2 référence(s), data-URLs omises]",
    },
}

COURONNES_COUNT = 18
COURONNES_IDS = [
    "plaidoyer", "lame", "emissaire", "marchandage", "glanage", "patrouille",
    "anneau-du-sceau", "edit-royal", "recruteur", "caravane-marchande",
    "chevalier-errant", "maitre-de-guilde", "pretresse", "banneret",
    "pacte-d-ether", "legion-damnee", "couronne-maudite", "cendres-vivantes",
]
COURONNES_DIGEST = "4914073c56812daf2f2300366ca1d55d1a63aedd76dac4144d207079f0e84d17"

EXPECTED_COURONNE_MAUDITE = {
    "model": "seedream-5-0-260128",
    "prompt": (
        "A blackened, thorn-wrought crown levitating above an empty throne, wreathed in cold "
        "violet ether flames, ash spiralling up into darkness, hairline cracks leaking pale "
        "light. Cursed majesty, the heart of corruption. Dark medieval fantasy trading-card "
        "illustration, painterly digital gouache with the weathered texture of an aged "
        "illuminated manuscript. A single centered subject, medium shot, strong cinematic "
        "chiaroscuro: one warm candle-gold key light against deep cold shadow. Muted grim "
        "palette — ash grey, weathered stone, oxblood red, candle gold; desaturated, somber. "
        "Visible hand-painted brushwork, fine detail, subtle parchment grain, slightly hazy "
        "atmospheric background that only suggests the setting. Cohesive concept-art look. "
        "No text, no letters, no card frame, no border, no UI — illustration only, full-bleed. "
        "Corrupted variant: introduce a sickly ether glow of violet and teal as the only "
        "saturated color, drifting grey ash and orange embers, hairline cracks leaking faint "
        "pale light, an oppressive cursed atmosphere — darker and colder than the base style. "
        "Avoid: any text, letters, captions, watermark, logo, signature; card frame, border "
        "or UI; modern objects, photographic realism, bright cheerful colors; multiple "
        "disconnected subjects, cluttered composition; deformed hands or anatomy."
    ),
    "size": "4704x3520",
    "response_format": "url",
    "extra_body": {
        "watermark": False,
        "sequential_image_generation": "auto",
        "output_format": "png",
        "image": "[3 référence(s), data-URLs omises]",
    },
}


def _project(tmp_path: Path):
    # Arrange : projet v1 complet (bloc provider: anonyme, refs de style réelles)
    (tmp_path / "forge.yaml").write_text(FORGE_V1, encoding="utf-8")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "cards.yaml").write_text(PROMPTS_V1, encoding="utf-8")
    for name in ("a", "b", "c", "x"):
        ref = tmp_path / "reference" / f"{name}.png"
        ref.parent.mkdir(exist_ok=True)
        Image.new("RGB", (8, 8), "gray").save(ref)
    return load_project(tmp_path)


def test_inline_v1_dry_run_requests_are_frozen(tmp_path):
    # Act
    results = generate_kind(_project(tmp_path), "cards", dry_run=True)
    # Assert
    assert [r.id for r in results] == ["lame", "emissaire"]
    assert all(r.dest is None for r in results)
    by_id = {r.id: r.request for r in results}
    assert by_id["lame"] == EXPECTED_LAME
    assert by_id["emissaire"] == EXPECTED_EMISSAIRE


def test_couronnes_dry_run_requests_are_frozen():
    # Act
    results = generate_kind(load_project(EXAMPLE), "cards", dry_run=True)
    # Assert
    assert len(results) == COURONNES_COUNT
    assert [r.id for r in results] == COURONNES_IDS
    by_id = {r.id: r.request for r in results}
    assert by_id["couronne-maudite"] == EXPECTED_COURONNE_MAUDITE
    payload = [{"id": r.id, "request": r.request} for r in results]
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    assert digest == COURONNES_DIGEST
