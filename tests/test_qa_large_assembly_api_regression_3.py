"""End-to-end API regression coverage for 6, 8, and 10 instance assemblies.

Regression: ISSUE-002 — large recommendations previously produced incomplete
manifests. Found by gstack QA on 2026-08-04.
Report: .gstack/qa-reports/qa-report-large-assembly-2026-08-04.md
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from scripts.large_assembly_prompt_suite import build_cases


CASES_BY_COUNT = {
    count: next(
        case
        for case in build_cases()
        if case["expected_instance_count"] == count and case["prompt_form"] == 1 and f"l{20:04d}" in case["expected_component_ids"][0]
    )
    for count in (6, 8, 10)
}


@pytest.mark.asyncio
@pytest.mark.parametrize("count", (6, 8, 10))
async def test_generate_api_preserves_large_assembly_semantics(count):
    case = CASES_BY_COUNT[count]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=120) as client:
        response = await client.post(
            "/api/generate",
            json={
                "description": case["prompt"],
                "part_type": "screw",
                "component_ids": case["expected_component_ids"],
                "use_ai": False,
            },
        )
        assert response.status_code == 200, response.text
        result = response.json()
        step_response = await client.get(result["step_url"])

    report = result["assembly_report"]
    assert len(report["instances"]) == count
    assert [item["component_id"] for item in report["instances"]] == case["expected_component_ids"]
    assert report["quality"]["valid_brep"]
    assert report["quality"]["interference_free"]
    assert report["quality"]["measured"]["topology"]["solids"] == count
    assert result["semantic_assembly"]["definitions"] == 3
    assert result["semantic_assembly"]["instances"] == count
    assert step_response.status_code == 200
    assert len(step_response.content) > 1_000
    assert "ISO-10303-21" in step_response.text[:100]
