"""Regression coverage for description-driven concrete component selection.

Regression: ISSUE-001 — M4 fastener prompt kept component_ids empty.
Found by /qa on 2026-08-03.
Report: .gstack/qa-reports/qa-report-120-27-150-136-2026-08-03.md
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


PROMPT = (
    "生成一套 M4 紧固组件，包含 1 个 GB/T 70.1 / ISO 4762 M4×20 "
    "内六角圆柱头螺钉、2 个 M4 平垫圈和 1 个 M4 六角螺母。"
)


@pytest.mark.asyncio
async def test_description_recommends_exact_fastener_instances_with_quantity():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/component-recommendations", json={"description": PROMPT, "limit": 5})

    assert response.status_code == 200
    data = response.json()
    assert data["component_ids"] == [
        "gbt70-1-shcs-m4-l0020",
        "flat-washer-normal-m4-simple",
        "flat-washer-normal-m4-simple",
        "iso4032-hex-nut-m4",
    ]
    assert [item["quantity"] for item in data["items"]] == [1, 2, 1]
