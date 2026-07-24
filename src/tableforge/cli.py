"""CLI tableforge (commande `forge`)."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import typer

from . import paths
from .config import load_project
from .data import expand, load_rows
from .generate import generate_kind

app = typer.Typer(add_completion=False,
                  help="Générateur d'assets de jeu piloté par configuration.")

ProjectOpt = typer.Option(Path("."), "--project", "-p",
                          help="Dossier du projet (contient forge.yaml).")


@app.command()
def init(name: str, dest: Path = typer.Option(Path("."), "--dest", help="Dossier parent.")):
    """Crée un nouveau projet vierge."""
    from .scaffold import init_project
    target = init_project(name, dest)
    typer.echo(f"Projet créé : {target}")


@app.command("list")
def list_kinds(project: Path = ProjectOpt):
    """Liste les kinds déclarés + diagnostics de configuration."""
    from .providers.base import validate_project
    cfg = load_project(project)
    for name, kind in cfg.kinds.items():
        flags = []
        if kind.data:
            flags.append("data" if kind.data.exists() else "data?")
        if kind.prompts:
            flags.append("prompts" if kind.prompts.exists() else "prompts?")
        if kind.template is not None:
            flags.append("template" if kind.template.exists() else "template?")
        sheet = " +sheet" if kind.sheet else ""
        provider = kind.generate.with_ if kind.generate and kind.generate.with_ else "auto"
        typer.echo(f"- {name} [{kind.asset} via {provider}]: {', '.join(flags)}{sheet}")
    issues = validate_project(cfg)
    if issues:
        typer.echo("problèmes de configuration :")
        for issue in issues:
            typer.echo(f"  ! {issue}")
        raise typer.Exit(code=1)


@app.command()
def generate(kind: str, project: Path = ProjectOpt,
             id: Optional[List[str]] = typer.Option(None, "--id", help="Limiter à ces ids."),
             dry_run: bool = typer.Option(False, "--dry-run"),
             force: bool = typer.Option(False, "--force")):
    """Génère l'art IA d'un kind."""
    cfg = load_project(project)
    results = generate_kind(cfg, kind, ids=id or None, dry_run=dry_run, force=force)
    for res in results:
        where = "(dry-run)" if res.dest is None else str(res.dest)
        typer.echo(f"{res.id}: {where}")


@app.command()
def studio(kind: str, project: Path = ProjectOpt,
           id: Optional[List[str]] = typer.Option(None, "--id", help="Limiter à ces ids.")):
    """Fiches studio : texte, réglages, destination, URL de l'écran web."""
    from .studio import studio_cards
    cfg = load_project(project)
    for card in studio_cards(cfg, kind, ids=id or None):
        typer.echo(f"=== {card.kind}/{card.id}")
        if card.url:
            typer.echo(f"    écran   : {card.url}")
        typer.echo(f"    texte   : {card.text}")
        if card.settings:
            settings = ", ".join(f"{k}={v}" for k, v in sorted(card.settings.items()))
            typer.echo(f"    réglages: {settings}")
        for note in card.notes:
            typer.echo(f"    note    : {note}")
        typer.echo(f"    déposer : {card.dest}")


def _require_image_kind(kind_cfg, kind: str) -> None:
    if kind_cfg.asset != "image":
        from .paths import MODALITY_BY_ASSET
        modality = MODALITY_BY_ASSET.get(kind_cfg.asset, kind_cfg.asset)
        raise typer.BadParameter(
            f"le kind '{kind}' est {modality} ({kind_cfg.asset}) — rien à rendre ; "
            "utilise forge generate")


def _render_kind(cfg, kind: str, only: Optional[List[str]]):
    from .render import render_png
    kind_cfg = cfg.kind(kind)
    _require_image_kind(kind_cfg, kind)
    if kind_cfg.template is None or kind_cfg.render_size is None:
        raise typer.BadParameter(
            f"le kind '{kind}' n'a pas de template — rien à rendre")
    if kind_cfg.data is None:
        raise typer.BadParameter(f"le kind '{kind}' n'a pas de fichier data")
    rows = load_rows(kind_cfg.data)
    if only:
        rows = [r for r in rows if r.id in set(only)]
    out = []
    for row in rows:
        art = paths.find_art(cfg.root, kind, row.id)
        out_path = paths.render_path(cfg.root, kind, row.id)
        render_png(cfg, kind_cfg, row, art, out_path)
        out.append(out_path)
        typer.echo(f"{row.id}: {out_path}")
    return out


@app.command()
def render(kind: str, project: Path = ProjectOpt,
           id: Optional[List[str]] = typer.Option(None, "--id")):
    """Compose les designs PNG d'un kind."""
    _render_kind(load_project(project), kind, id)


@app.command()
def board(kind: str, project: Path = ProjectOpt):
    """Rendu d'un kind pleine page (plateau / map)."""
    _render_kind(load_project(project), kind, None)


@app.command()
def sheet(kind: str, project: Path = ProjectOpt):
    """Assemble la planche d'impression PDF d'un kind."""
    from .sheet import build_sheet_pdf, plan_sheet
    cfg = load_project(project)
    kind_cfg = cfg.kind(kind)
    _require_image_kind(kind_cfg, kind)
    if kind_cfg.sheet is None or kind_cfg.data is None:
        raise typer.BadParameter(f"le kind '{kind}' n'a pas de bloc 'sheet'/'data'")
    rows = expand(load_rows(kind_cfg.data))
    art_by_id = {}
    for row in rows:
        rp = paths.render_path(cfg.root, kind, row.id)
        if rp.exists():
            art_by_id[row.id] = rp
    plan = plan_sheet([r.id for r in rows], kind_cfg.sheet)
    out = build_sheet_pdf(plan, art_by_id, paths.sheet_path(cfg.root, kind))
    typer.echo(f"planche : {out}")


@app.command("all")
def run_all(kind: str, project: Path = ProjectOpt):
    """generate (si clé) → render → sheet."""
    cfg = load_project(project)
    try:
        generate_kind(cfg, kind)
    except RuntimeError as exc:
        typer.echo(f"(génération ignorée : {exc})")
    _render_kind(cfg, kind, None)
    if cfg.kind(kind).sheet:
        sheet(kind, project)
