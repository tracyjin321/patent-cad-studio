"""Regression coverage for re-recognition after an M4 length change.

Regression: ISSUE-004 — changed descriptions could retain stale component instances.
Found by /qa on 2026-08-03.
Report: .gstack/qa-reports/qa-report-120-27-150-136-2026-08-03.md
"""

from pathlib import Path

from app.assembly import automatic_manifest, build_assembly
from app.component_library import recommend_component_instances


LIBRARY = Path(__file__).parents[1] / "component_library"


def test_changed_m4_length_replaces_screw_and_keeps_valid_stack():
    prompt = "生成 1 个 ISO 4762 M4×16 内六角圆柱头螺钉、2 个 M4 平垫圈和 1 个 M4 六角螺母。"
    component_ids = recommend_component_instances(prompt)["component_ids"]

    assert component_ids == [
        "gbt70-1-shcs-m4-l0016",
        "flat-washer-normal-m4-simple",
        "flat-washer-normal-m4-simple",
        "iso4032-hex-nut-m4",
    ]
    _, report = build_assembly(automatic_manifest(component_ids, LIBRARY))
    assert report["quality"]["valid_brep"]
    assert report["quality"]["interference_free"]
