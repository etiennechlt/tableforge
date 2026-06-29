"""Chargement des lignes de données (rows) d'un kind, indépendant du schéma métier."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


def slugify(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_only = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")


@dataclass(frozen=True)
class Row:
    id: str
    data: dict

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    @property
    def qty(self) -> int:
        return int(self.data.get("qty", 1))


def _row_id(entry: dict) -> str:
    if entry.get("id"):
        return str(entry["id"])
    if entry.get("name"):
        return slugify(str(entry["name"]))
    raise ValueError("chaque row doit avoir un champ 'id' ou 'name'")


def load_rows(path: Path) -> list[Row]:
    with open(path, encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    entries = raw.get("rows")
    if not isinstance(entries, list):
        raise ValueError(f"{path} : clé 'rows' (liste) manquante")
    rows: list[Row] = []
    for entry in entries:
        asset_id = _row_id(entry)
        rows.append(Row(id=asset_id, data={**entry, "id": asset_id}))
    return rows


def expand(rows: list[Row]) -> list[Row]:
    result: list[Row] = []
    for row in rows:
        result.extend([row] * row.qty)
    return result
