"""Regression for assembly geometry, drawing, parameters, and semantic counts.

Regression: ISSUE-004 — an assembly could retain lead-screw presentation
semantics even when its STEP contained the selected fastener instances.
Found by gstack QA on 2026-08-04.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


IDS = [
    "gbt70-1-shcs-m4-l0020",
    *(["flat-washer-normal-m4-simple"] * 6),
    "iso4032-hex-nut-m4",
]


@pytest.mark.asyncio
async def test_eight_component_assembly_has_consistent_presentation_and_counts():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=120) as client:
        response = await client.post(
            "/api/generate",
            json={
                "description": "1 个 M4×20 内六角螺钉、6 个 M4 平垫圈和 1 个 M4 六角螺母。",
                "part_type": "screw",
                "component_ids": IDS,
                "use_ai": False,
            },
        )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["title"] == "紧固组件技术附图"
    assert 'aria-label="紧固组件技术附图轴测图"' in result["svg"]
    assert "丝杠" not in result["title"]
    assert result["parameters"] == {
        "assembly_kind": "fastener_stack",
        "component_instances": 8,
        "unique_components": 3,
    }
    assert result["structural_parameters"] == {
        "solid_count": 8,
        "valid_brep": True,
        "interference_free": True,
    }
    assert len(result["assembly_report"]["instances"]) == 8
    assert result["semantic_assembly"]["instances"] == 8
    checks = {item["name"]: item["passed"] for item in result["compliance"]}
    assert checks["图元、实例与实体数量一致"]
    assert checks["XCAF 语义实例数量一致"]
