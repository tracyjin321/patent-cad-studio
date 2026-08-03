#!/usr/bin/env python3
"""Import the high-frequency ISO 4762 / GB/T 70.1 nominal-compatible subset.

The script consumes the public step.parts API, verifies the advertised SHA,
checks a single valid B-Rep, materializes ComponentSpec v1.3, validates a
STEP -> YAML -> STEP round trip, and only then writes the formal library.
"""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import tempfile
from typing import Any

import httpx
import yaml

from app.assembly import automatic_manifest, build_assembly
from app.component_spec import inspect_step, roundtrip_report, step_to_spec, validate_spec
from scripts.rebuild_component_catalog import build_catalog


ROOT = Path(__file__).resolve().parents[1]
API = "https://api.step.parts/v1/parts"
STANDARD_URL = "https://std.samr.gov.cn/gb/search/gbDetailed?id=71F772D7F825D3A7E05397BE0A0AB82A"
LICENSE_URL = "https://github.com/earthtojake/step.parts/blob/main/LICENSE"
NOTICE_URL = "https://github.com/earthtojake/step.parts/blob/main/THIRD_PARTY_NOTICES.md"
HIGH_FREQUENCY = {
    "M2": {4, 6, 8, 10, 12}, "M2.5": {5, 6, 8, 10, 12},
    "M3": {6, 8, 10, 12, 16}, "M4": {8, 10, 12, 16, 20},
    "M5": {10, 12, 16, 20, 25}, "M6": {12, 16, 20, 25, 30},
    "M8": {16, 20, 25, 30, 40}, "M10": {20, 25, 30, 40, 50},
    "M12": {25, 30, 40, 50, 60},
}
PITCH = {"M2": .4, "M2.5": .45, "M3": .5, "M4": .7, "M5": .8, "M6": 1.0, "M8": 1.25, "M10": 1.5, "M12": 1.75}


def _slug(thread: str, length: int) -> str:
    size = thread[1:].replace(".", "p")
    return f"gbt70-1-shcs-m{size}-l{length:04d}"


def fetch_catalog(client: httpx.Client) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page = 1
    while True:
        response = client.get(API, params={"category": "fastener", "family": "socket-head-cap-screw", "standard": "ISO 4762", "pageSize": 100, "page": page})
        response.raise_for_status()
        payload = response.json()
        items.extend(payload["items"])
        if not payload["hasNextPage"]:
            return items
        page += 1


def select_candidates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = []
    for item in items:
        attrs = item.get("attributes", {})
        thread, length = attrs.get("thread"), attrs.get("lengthMm")
        if thread in HIGH_FREQUENCY and length in HIGH_FREQUENCY[thread]:
            selected.append(item)
    return sorted(selected, key=lambda item: (float(item["attributes"]["thread"][1:]), item["attributes"]["lengthMm"]))


def _port(port_id: str, name: str, origin_z: float, axis_z: float, thread: str, role: str) -> dict[str, Any]:
    return {
        "id": port_id, "name": name, "type": "threaded_connection", "role": role,
        "frame": {"origin": [0.0, 0.0, origin_z], "axis": [0.0, 0.0, axis_z], "up": [1.0, 0.0, 0.0]},
        "interface": {"thread": thread, "pitch_mm": PITCH[thread], "gender": "male"},
        "compatible_with": {"port_types": ["threaded_connection"], "rules": ["same_thread", "opposite_gender"]},
        "allowed_mates": ["coincident_concentric"],
    }


def import_one(item: dict[str, Any], library: Path, client: httpx.Client) -> dict[str, Any]:
    attrs = item["attributes"]
    thread, length = attrs["thread"], int(attrs["lengthMm"])
    diameter = float(thread[1:])
    component_id = _slug(thread, length)
    target = library / component_id
    if target.exists():
        return {"id": component_id, "status": "existing"}
    response = client.get(item["stepUrl"])
    response.raise_for_status()
    content = response.content
    actual_sha = hashlib.sha256(content).hexdigest()
    if actual_sha != item["sha256"] or not content.lstrip().startswith(b"ISO-10303-21;"):
        raise ValueError(f"{item['id']}: download checksum or STEP header mismatch")
    with tempfile.TemporaryDirectory(prefix="iso4762-import-") as temp_name:
        temp = Path(temp_name)
        source = temp / "source.step"
        source.write_bytes(content)
        measured = inspect_step(source)
        if not measured["valid_solid"] or measured["topology"]["solids"] != 1:
            raise ValueError(f"{item['id']}: expected one valid solid")
        axial = measured["bounding_box"]["size"][2]
        if abs(axial - (length + diameter)) > max(.05, diameter * .02):
            raise ValueError(f"{item['id']}: axial envelope {axial} does not match L+k={length + diameter}")
        work = temp / component_id
        work.mkdir()
        spec_path = work / "component.yaml"
        spec = step_to_spec(source, spec_path, identity={
            "id": component_id, "name": f"内六角圆柱头螺钉 {thread}×{length}",
            "name_en": item["name"], "type": "fastener", "subtype": "socket_head_cap_screw",
            "family": "gbt70-1-socket-head-cap-screw", "standard": "GB/T 70.1-2008 / ISO 4762:2004 (MOD)",
            "license": "MIT", "version": "1.0.0",
        }, reference_filename="reference.step")
        zmin, zmax = measured["bounding_box"]["min"][2], measured["bounding_box"]["max"][2]
        spec["identity"].update({
            "status": "approved", "updated_at": date.today().isoformat(),
            "description": f"step.parts ISO 4762 {thread}×{length} 几何；按 GB/T 70.1-2008 修改采用关系登记为公称兼容图元。",
            "tags": ["GB/T 70.1", "ISO 4762", thread, f"L{length}", "socket-head", "step.parts"],
        })
        spec["parameters"] = [
            {"name": "nominal_diameter", "type": "number", "unit": "mm", "default": diameter, "editable": False},
            {"name": "nominal_length", "type": "number", "unit": "mm", "default": length, "editable": False},
            {"name": "thread_pitch", "type": "number", "unit": "mm", "default": PITCH[thread], "editable": False},
        ]
        spec["ports"] = [
            _port("thread_tip", "螺纹端装配口", zmin, -1.0, thread, "thread_male"),
            _port("head_bearing_face", "头部支承面", min(0.0, zmax), 1.0, thread, "bearing_face"),
        ]
        spec["provenance"].update({
            "source_type": "step_parts_mit_original", "source_url": item["pageUrl"], "source_step_url": item["stepUrl"],
            "source_sha256": item["sha256"], "source_catalog_id": item["id"], "source_license": "MIT",
            "license_reference": LICENSE_URL, "third_party_notice_checked": NOTICE_URL,
            "license_decision": "MIT: no file-level attribution and no matching family entry in THIRD_PARTY_NOTICES",
            "standard_refs": ["ISO 4762:2004", "GB/T 70.1-2008"], "standard_adoption": "MOD",
            "standard_reference": STANDARD_URL, "qualification": "nominal geometry compatible; tolerance/material/property class not certified",
            "verified_by": "iso4762-gbt70-1-import-gate", "verified_at": date.today().isoformat(),
        })
        spec_path.write_text(yaml.safe_dump(spec, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
        validation, roundtrip = validate_spec(spec, spec_path=spec_path), roundtrip_report(spec_path)
        if validation["errors"] or not roundtrip["passed"]:
            raise ValueError(f"{item['id']}: ComponentSpec or round-trip validation failed")
        work.rename(target)
    manifest = automatic_manifest([component_id], library)
    _, assembly_report = build_assembly(manifest)
    if not assembly_report["quality"]["valid_brep"] or assembly_report["instances"][0]["component_id"] != component_id:
        raise ValueError(f"{item['id']}: assembly execution validation failed")
    return {"id": component_id, "status": "imported", "source_id": item["id"], "sha256": actual_sha, "roundtrip": True,
            "assembly_ports": True, "assembly_brep": True}


def run(library: Path) -> dict[str, Any]:
    library.mkdir(parents=True, exist_ok=True)
    with httpx.Client(follow_redirects=True, timeout=45, headers={"User-Agent": "patent-cad-studio-component-governance/1.0"}) as client:
        catalog = fetch_catalog(client)
        selected = select_candidates(catalog)
        results = [import_one(item, library, client) for item in selected]
    rebuilt = build_catalog(library)
    (library / "catalog.yaml").write_text(yaml.safe_dump(rebuilt, allow_unicode=True, sort_keys=False), encoding="utf-8")
    report = {"source_candidates": len(catalog), "selected": len(selected), "imported": sum(x["status"] == "imported" for x in results),
              "existing": sum(x["status"] == "existing" for x in results), "catalog_count": len(rebuilt["components"]), "results": results}
    report_path = ROOT / "docs" / "iso4762-gbt70-1-import-report-2026-08-03.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", type=Path, default=ROOT / "component_library")
    args = parser.parse_args()
    print(json.dumps(run(args.library.resolve()), ensure_ascii=False, indent=2))
