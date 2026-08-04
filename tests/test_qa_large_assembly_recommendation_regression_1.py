"""Regression coverage for description-driven assemblies larger than five instances.

Regression: ISSUE-001 — an eight-instance prompt was silently clipped to five.
Found by gstack QA on 2026-08-04.
Report: .gstack/qa-reports/qa-report-large-assembly-2026-08-04.md
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


PROMPT = (
    "生成一套 8 图元 M4 紧固组件：1 个 ISO 4762 M4×20 内六角圆柱头螺钉、"
    "6 个 M4 平垫圈和 1 个 M4 六角螺母，按轴向顺序装配。"
)


@pytest.mark.asyncio
async def test_eight_instance_prompt_is_not_silently_clipped_to_five():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/component-recommendations",
            json={"description": PROMPT, "limit": 32},
        )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["component_ids"] == [
        "gbt70-1-shcs-m4-l0020",
        *(["flat-washer-normal-m4-simple"] * 6),
        "iso4032-hex-nut-m4",
    ]
    assert [item["quantity"] for item in data["items"]] == [1, 6, 1]
