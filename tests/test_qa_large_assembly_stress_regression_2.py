"""High-load regression suite for 6–10 instance description-driven assemblies.

Regression: ISSUE-002 — recommendation and assembly behavior was not stress-tested
past five instances. Found by gstack QA on 2026-08-04.
Report: .gstack/qa-reports/qa-report-large-assembly-2026-08-04.md
"""

from pathlib import Path

import pytest

from app.assembly import automatic_manifest, build_assembly
from app.component_library import recommend_component_instances
from scripts.large_assembly_prompt_suite import build_cases


LIBRARY = Path(__file__).parents[1] / "component_library"


@pytest.mark.parametrize("case", build_cases(), ids=lambda case: case["id"])
def test_all_large_prompts_match_every_requested_instance_in_order(case):
    result = recommend_component_instances(case["prompt"], limit=32)

    assert result["component_ids"] == case["expected_component_ids"]
    assert len(result["component_ids"]) == case["expected_instance_count"]


@pytest.mark.parametrize(
    "case",
    [case for case in build_cases() if case["prompt_form"] == 1],
    ids=lambda case: case["id"],
)
def test_each_unique_large_stack_has_valid_ports_brep_and_instance_count(case):
    manifest = automatic_manifest(case["expected_component_ids"], LIBRARY)
    shape, report = build_assembly(manifest)

    assert not shape.IsNull()
    assert [item["component_id"] for item in report["instances"]] == case["expected_component_ids"]
    assert len(report["instances"]) == case["expected_instance_count"]
    assert report["quality"]["valid_brep"]
    assert report["quality"]["interference_free"]
    assert report["quality"]["measured"]["topology"]["solids"] == case["expected_instance_count"]
    assert manifest.components[1].port == "face_a"
    assert manifest.components[1].mate_to == "head_bearing_face"
    assert all(item.port == "face_a" and item.mate_to == "face_b" for item in manifest.components[2:])
