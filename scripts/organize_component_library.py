#!/usr/bin/env python3
"""Migrate mixed graphic-element STEP/YAML pairs into the component library."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.component_spec import dump_spec, validate_spec  # noqa: E402


def find_step(yaml_path: Path, spec: dict) -> Path:
    filename = spec.get("artifacts", {}).get("reference_step", {}).get("file")
    if not filename:
        raise ValueError(f"{yaml_path}: 缺少 reference_step.file")
    result = yaml_path.parent / filename
    if not result.is_file():
        raise FileNotFoundError(result)
    return result


def migrate(source_root: Path, library_root: Path) -> list[dict]:
    catalog = []
    for yaml_path in sorted(source_root.rglob("*.yaml")):
        spec = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        component_id = spec["identity"]["id"]
        target_dir = library_root / component_id
        target_yaml = target_dir / "component.yaml"
        target_step = target_dir / "reference.step"
        if target_yaml.exists() or target_step.exists():
            raise FileExistsError(f"目标图元目录已有文件: {target_dir}")
        source_step = find_step(yaml_path, spec)
        target_dir.mkdir(parents=True, exist_ok=False)
        shutil.move(str(source_step), target_step)
        spec["artifacts"]["reference_step"]["file"] = "reference.step"
        for operation in spec.get("geometry", {}).get("construction", []):
            if operation.get("operation") == "import_step":
                operation["source"] = "reference.step"
        provenance = spec.setdefault("provenance", {})
        provenance["source_material_directory"] = str(yaml_path.parent.relative_to(ROOT))
        dump_spec(spec, target_yaml)
        yaml_path.unlink()
        result = validate_spec(spec, spec_path=target_yaml)
        if result["errors"]:
            raise ValueError(f"{component_id}: " + "; ".join(result["errors"]))
        catalog.append({
            "id": component_id,
            "name": spec["identity"]["name"],
            "type": spec["identity"]["type"],
            "subtype": spec["identity"].get("subtype"),
            "version": spec["identity"]["version"],
            "status": spec["identity"]["status"],
            "spec": f"{component_id}/component.yaml",
            "reference_step": f"{component_id}/reference.step",
            "source_material_directory": provenance["source_material_directory"],
        })
    return catalog


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=ROOT / "component_library")
    parser.add_argument("--output", type=Path, default=ROOT / "component_library")
    args = parser.parse_args()
    catalog_path = args.output / "catalog.yaml"
    if catalog_path.exists():
        parser.error(f"目录已经整理过：{catalog_path}")
    catalog = migrate(args.source.resolve(), args.output.resolve())
    catalog_path.write_text(
        yaml.safe_dump({"schema_version": "1.0", "components": catalog}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"migrated={len(catalog)}")
    print(catalog_path)


if __name__ == "__main__":
    main()
