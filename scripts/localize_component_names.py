#!/usr/bin/env python3
"""Normalize component identity names to Chinese while preserving English names."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.component_library import SUBTYPE_LABELS  # noqa: E402
from app.component_spec import geometry_signatures, inspect_step, validate_spec  # noqa: E402
from scripts.rebuild_component_catalog import build_catalog  # noqa: E402


def contains_chinese(value: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", value))


def localize_library(library: Path) -> list[Path]:
    updated: list[Path] = []
    for spec_path in sorted(library.glob("*/component.yaml")):
        spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
        identity = spec["identity"]
        current_name = str(identity["name"])
        changed = False
        if not contains_chinese(current_name):
            subtype = str(identity.get("subtype") or "")
            identity["name_en"] = identity.get("name_en") or current_name
            identity["name"] = SUBTYPE_LABELS.get(subtype, "机械图元")
            changed = True
        reference = spec_path.parent / spec["artifacts"]["reference_step"]["file"]
        signatures = geometry_signatures(inspect_step(reference))
        geometry_validation = spec.setdefault("validation", {}).setdefault("geometry", {})
        if geometry_validation.get("signatures") != signatures:
            geometry_validation["signatures"] = signatures
            changed = True
        provenance = spec.setdefault("provenance", {})
        if provenance.get("semantic_recovery") != "authoritative_sidecar":
            provenance["semantic_recovery"] = "authoritative_sidecar"
            changed = True
        if not changed:
            continue
        validation = validate_spec(spec, spec_path=spec_path)
        if validation["errors"]:
            raise ValueError(f"{spec_path}: " + "; ".join(validation["errors"]))
        spec_path.write_text(
            yaml.safe_dump(spec, allow_unicode=True, sort_keys=False, width=120),
            encoding="utf-8",
        )
        updated.append(spec_path)
    return updated


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", type=Path, default=ROOT / "component_library")
    args = parser.parse_args()
    updated = localize_library(args.library)
    catalog = build_catalog(args.library)
    catalog_path = args.library / "catalog.yaml"
    catalog_path.write_text(
        yaml.safe_dump(catalog, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"updated={len(updated)} components={len(catalog['components'])}")
    print(catalog_path)


if __name__ == "__main__":
    main()
