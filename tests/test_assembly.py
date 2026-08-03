from pathlib import Path

import pytest
from pydantic import ValidationError

from app.assembly import AssemblyManifest, automatic_manifest, build_assembly


ROOT = Path(__file__).parents[1]
IDS = ["precision-shaft-d03-l0050-chamfered", "bearing-608-open-simple", "shaft-coupler-rigid-clamp-d03-d03-simple"]


def test_manifest_rejects_future_target_and_duplicate_port():
    with pytest.raises(ValidationError, match="此前组件"):
        AssemblyManifest(components=[{"spec": "a"}, {"spec": "b", "port": "end_a", "target": 1, "mate_to": "end_b"}])
    with pytest.raises(ValidationError, match="目标端口已占用"):
        AssemblyManifest(components=[{"spec": "a"}, {"spec": "b", "port": "end_a", "target": 0, "mate_to": "end_b"}, {"spec": "c", "port": "end_a", "target": 0, "mate_to": "end_b"}])


def test_shaft_bearing_coupling_assembly_has_transforms_and_quality():
    _, report = build_assembly(automatic_manifest(IDS, ROOT / "component_library"))
    assert [item["component_id"] for item in report["instances"]] == IDS
    assert report["instances"][1]["transform"] != report["instances"][0]["transform"]
    assert report["quality"]["valid_brep"] and report["quality"]["interference_free"]
    assert report["quality"]["measured"]["topology"]["solids"] >= 3
    assert len(report["quality"]["pair_checks"]) == 3


def test_overlapping_components_are_rejected_before_export():
    spec = str(ROOT / "component_library" / IDS[0] / "component.yaml")
    manifest = AssemblyManifest(components=[{"spec": spec, "fixed": True}, {"spec": spec}])
    with pytest.raises(ValueError, match="干涉"):
        build_assembly(manifest)
