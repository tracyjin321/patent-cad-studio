"""Regression coverage for ISO standard numbers adjacent to quantities.

Regression: ISSUE-002 — ISO 4032/4762 were parsed as instance quantities.
Found by /qa on 2026-08-04.
Report: .gstack/qa-reports/qa-report-127-0-0-1-2026-08-04.md
"""

from app.component_library import recommend_component_instances


def test_iso_standard_numbers_are_not_component_quantities():
    result = recommend_component_instances(
        "生成一套6图元M4紧固组件：1个ISO 4762 M4×8内六角圆柱头螺钉、"
        "4个M4平垫圈和1个ISO 4032 M4六角螺母，按轴向顺序装配。",
        limit=32,
    )

    assert result["component_ids"] == [
        "gbt70-1-shcs-m4-l0008",
        *(["flat-washer-normal-m4-simple"] * 4),
        "iso4032-hex-nut-m4",
    ]


def test_total_assembly_count_is_not_screw_quantity():
    result = recommend_component_instances(
        "生成10图元M4紧固栈：ISO 4762 M4×20螺钉1个、"
        "M4平垫圈8个、ISO 4032 M4螺母1个。",
        limit=32,
    )

    assert len(result["component_ids"]) == 10
    assert result["component_ids"].count("gbt70-1-shcs-m4-l0020") == 1
    assert result["component_ids"].count("iso4032-hex-nut-m4") == 1
