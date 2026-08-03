#!/usr/bin/env python3
"""Re-verify imported GB/T 70.1 nominal-compatible components and report it."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from app.assembly import automatic_manifest, build_assembly
from app.component_spec import roundtrip_report, validate_spec


ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "component_library"
REPORT = ROOT / "docs" / "iso4762-gbt70-1-import-report-2026-08-03.json"


def run() -> dict:
    results = []
    for spec_path in sorted(LIBRARY.glob("gbt70-1-shcs-*/component.yaml")):
        spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
        component_id = spec["identity"]["id"]
        validation = validate_spec(spec, spec_path=spec_path)
        roundtrip = roundtrip_report(spec_path)
        shape, assembly = build_assembly(automatic_manifest([component_id], LIBRARY))
        result = {
            "id": component_id,
            "schema_valid": not validation["errors"],
            "roundtrip": roundtrip["passed"],
            "assembly_brep": assembly["quality"]["valid_brep"] and not shape.IsNull(),
            "instance_transform_resolved": len(assembly["instances"]) == 1,
        }
        if not all(value for key, value in result.items() if key != "id"):
            raise ValueError(f"verification failed: {result}")
        results.append(result)

    report = json.loads(REPORT.read_text(encoding="utf-8"))
    report["verification"] = {
        "component_count": len(results),
        "all_schema_valid": all(item["schema_valid"] for item in results),
        "all_roundtrip_valid": all(item["roundtrip"] for item in results),
        "all_assembly_brep_valid": all(item["assembly_brep"] for item in results),
        "all_instance_transforms_resolved": all(item["instance_transform_resolved"] for item in results),
        "results": results,
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report["verification"]


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
