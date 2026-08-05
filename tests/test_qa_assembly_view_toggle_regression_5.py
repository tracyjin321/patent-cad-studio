"""Regression: 3D preview could not switch between assembled and exploded states.

Found by /qa on 2026-08-05.
Report: .gstack/qa-reports/qa-report-127-0-0-1-2026-08-05-advanced-constraints.md
"""

from pathlib import Path

import pytest

from app.assembly import automatic_manifest, build_assembly
from app.component_library import recommend_component_instances


ROOT = Path(__file__).parents[1]
PROMPT = "生成齿轮轴组合：阶梯齿轮轴、6004轴承、弹性挡圈、定位套筒、平键与直齿轮同轴装配。"


def test_gear_shaft_uses_coaxial_assembled_placements_and_declared_contacts():
    ids = recommend_component_instances(PROMPT, 32)["component_ids"]
    manifest = automatic_manifest(ids, ROOT / "component_library", description=PROMPT)
    _, report = build_assembly(manifest)
    assert report["solved_constraints"][0]["type"] == "coaxial_shaft_stack"
    assert len({str(instance["transform"]) for instance in report["instances"]}) == 9
    expected = [pair for pair in report["quality"]["pair_checks"] if pair.get("expected_contact")]
    assert len(expected) == 9
    assert report["quality"]["interference_free"] is True
    assert report["solved_constraints"][0]["exploded_offsets_mm"] == [0.0, -110.0, -80.0, -50.0, -25.0, 35.0, 60.0, 82.0, 112.0]
    assert ids.count("bearing-6004-2z-gbt276") == 2
    assert ids.count("circlip-external-gbt894-1-d20") == 2
    size = report["quality"]["measured"]["bounding_box"]["size"]
    reference_size = [48.016108, 88.216108, 47.741082]
    assert sorted(size) == pytest.approx(sorted(reference_size), abs=0.3)


def test_3d_preview_exposes_reversible_assembly_explosion_toggle():
    html = (ROOT / "static/index.html").read_text(encoding="utf-8")
    app_js = (ROOT / "static/app.js").read_text(encoding="utf-8")
    viewer_js = (ROOT / "static/model-viewer.js").read_text(encoding="utf-8")
    assert 'id="assembly-view-toggle"' in html
    assert "查看展开关系" in html and "查看装配关系" in app_js
    assert 'setAssemblyMode("assembled")' in app_js
    assert 'mode==="exploded"' in viewer_js
    assert "object.userData.explodeVector" in viewer_js
    assert "rank*16" not in viewer_js
