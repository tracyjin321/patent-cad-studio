"""Coverage for the curated technical-description recommendation pool."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_prompt_examples_exposes_all_70_mechanical_patent_prompts():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/prompt-examples")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 70
    assert len(data["items"]) == 70
    assert data["items"][0]["id"] == "MP-001"
    assert data["items"][-1]["id"] == "MP-070"
    assert all(item["prompt"].strip() for item in data["items"])


def test_frontend_loads_the_prompt_pool_into_the_top_example_control():
    from pathlib import Path

    source = (Path(__file__).parents[1] / "static" / "app.js").read_text(encoding="utf-8")
    assert 'fetch("/api/prompt-examples"' in source
    assert "refreshExamples=prompts" in source
    assert "换一条推荐 · ${prompts.length}条" in source
