"""Regression coverage for fastener assembly terminology.

Regression: ISSUE-003 — a concrete fastener assembly was labelled as a lead screw.
Found by /qa on 2026-08-03.
Report: .gstack/qa-reports/qa-report-120-27-150-136-2026-08-03.md
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_fastener_assembly_uses_fastener_title():
    component_ids = [
        "gbt70-1-shcs-m4-l0020",
        "flat-washer-normal-m4-simple",
        "flat-washer-normal-m4-simple",
        "iso4032-hex-nut-m4",
    ]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=60) as client:
        response = await client.post("/api/generate", json={
            "description": "M4 紧固组件",
            "part_type": "screw",
            "component_ids": component_ids,
            "use_ai": False,
        })

    assert response.status_code == 200
    assert response.json()["title"] == "紧固组件技术附图"
