"""Contract coverage for the 70-prompt mechanical patent QA corpus.

Found by /qa on 2026-08-04.
Report: .gstack/qa-reports/qa-report-127-0-0-1-2026-08-04.md
"""

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


ROOT = Path(__file__).parents[1]
CASES = json.loads((ROOT / "docs" / "mechanical-patent-prompts-70-2026-08-04.json").read_text(encoding="utf-8"))


def test_prompt_corpus_has_50_base_and_20_assembly_cases():
    assert len(CASES) == 70
    assert [case["id"] for case in CASES] == [f"MP-{index:03d}" for index in range(1, 71)]
    assert sum("装配" in case["category"] for case in CASES[50:]) >= 15


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
async def test_every_patent_prompt_has_a_valid_component_resolution_contract(case):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/component-recommendations", json={
            "description": case["prompt"], "limit": 32, "use_ai": False,
        })

    assert response.status_code == 200
    data = response.json()
    assert data["capability"] in {"ready", "parametric_generation", "manual_rules_required"}
    assert len(data["component_ids"]) <= 32
    assert len(data["assembly_relations"]) == max(0, len(data["component_ids"]) - 1)


@pytest.mark.parametrize("case_id,expected", [
    ("MP-041", 6), ("MP-042", 8), ("MP-043", 7), ("MP-044", 9), ("MP-045", 10),
])
def test_supported_m4_patent_assemblies_preserve_instance_count(case_id, expected):
    from app.component_library import recommend_component_instances

    case = next(item for item in CASES if item["id"] == case_id)
    result = recommend_component_instances(case["prompt"], limit=32)
    assert len(result["component_ids"]) == expected
