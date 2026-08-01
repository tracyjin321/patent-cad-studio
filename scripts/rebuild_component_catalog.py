#!/usr/bin/env python3
"""Rebuild component_library/catalog.yaml from component directories."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.component_spec import load_spec, validate_spec  # noqa: E402


def build_catalog(library: Path) -> dict:
    components = []
    seen: set[str] = set()
    for spec_path in sorted(library.glob("*/component.yaml")):
        spec = load_spec(spec_path)
        validation = validate_spec(spec, spec_path=spec_path)
        if validation["errors"]:
            raise ValueError(f"{spec_path}: " + "; ".join(validation["errors"]))
        identity = spec["identity"]
        component_id = identity["id"]
        if component_id in seen:
            raise ValueError(f"图元 ID 重复: {component_id}")
        if spec_path.parent.name != component_id:
            raise ValueError(f"目录名必须等于 identity.id: {spec_path.parent.name} != {component_id}")
        seen.add(component_id)
        components.append({
            "id": component_id,
            "name": identity["name"],
            "type": identity["type"],
            "subtype": identity.get("subtype"),
            "version": identity["version"],
            "status": identity["status"],
            "spec": f"{component_id}/component.yaml",
            "reference_step": f"{component_id}/{spec['artifacts']['reference_step']['file']}",
            "source_material_directory": spec.get("provenance", {}).get("source_material_directory"),
        })
    return {"schema_version": "1.0", "components": components}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", type=Path, default=ROOT / "component_library")
    args = parser.parse_args()
    catalog = build_catalog(args.library)
    output = args.library / "catalog.yaml"
    output.write_text(yaml.safe_dump(catalog, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"components={len(catalog['components'])}")
    print(output)


if __name__ == "__main__":
    main()
