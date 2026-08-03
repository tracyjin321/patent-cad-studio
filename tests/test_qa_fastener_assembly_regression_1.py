"""Regression coverage for the M4 fastener stack assembly.

Regression: ISSUE-002 — fastener prompt generated a single lead screw.
Found by /qa on 2026-08-03.
Report: .gstack/qa-reports/qa-report-120-27-150-136-2026-08-03.md
"""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.assembly import automatic_manifest, build_assembly
from app.main import app


LIBRARY = Path(__file__).parents[1] / "component_library"
IDS = [
    "gbt70-1-shcs-m4-l0020",
    "flat-washer-normal-m4-simple",
    "flat-washer-normal-m4-simple",
    "iso4032-hex-nut-m4",
]


def test_m4_screw_two_washers_and_nut_form_valid_non_interfering_stack():
    manifest = automatic_manifest(IDS, LIBRARY)
    shape, report = build_assembly(manifest)

    assert [item["component_id"] for item in report["instances"]] == IDS
    assert report["quality"]["valid_brep"]
    assert report["quality"]["interference_free"]
    assert report["quality"]["measured"]["topology"]["solids"] == 4
    assert not shape.IsNull()
    assert [round(item["transform"][2][3], 6) for item in report["instances"]] == [0.0, -0.9, -2.7, -6.801328]


@pytest.mark.asyncio
async def test_generate_api_exports_all_four_fastener_instances():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=60) as client:
        response = await client.post("/api/generate", json={
            "description": "装配 M4×20 内六角螺钉、两个 M4 平垫圈和 M4 六角螺母。",
            "part_type": "screw",
            "component_ids": IDS,
            "use_ai": False,
        })

    assert response.status_code == 200, response.text
    result = response.json()
    assert [item["component_id"] for item in result["assembly_report"]["instances"]] == IDS
    assert result["assembly_report"]["quality"]["interference_free"]
    assert result["semantic_assembly"]["definitions"] == 3
    assert result["semantic_assembly"]["instances"] == 4
