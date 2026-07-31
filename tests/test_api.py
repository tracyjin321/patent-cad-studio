import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app import llm


PARTS = ["bearing", "flange", "valve", "shaft", "gear", "screw", "coupling", "seal"]


@pytest.mark.asyncio
@pytest.mark.parametrize("part_type", PARTS)
async def test_all_part_types_generate_valid_svg(part_type: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/generate", json={
            "description": "生成一个用于专利附图的标准机械零件，外径100，内径45，长度200。",
            "part_type": part_type,
            "use_ai": False,
        })
        step = await client.get(response.json()["step_url"])
    assert response.status_code == 200
    data = response.json()
    assert data["svg"].startswith("<svg")
    assert data["svg"].endswith("</svg>")
    assert data["parameters"]
    assert data["model"]
    assert data["step_url"].endswith("/step")
    assert all(item["passed"] for item in data["compliance"])
    assert step.status_code == 200
    assert step.content.startswith(b"ISO-10303-21;")


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/health")
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_timeout_fallback_reports_reason(monkeypatch):
    class TimeoutClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, *args, **kwargs): raise llm.httpx.ReadTimeout("slow")
    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda **kwargs: TimeoutClient())
    monkeypatch.setenv("MOONSHOT_API_KEY", "test-key")
    _, parser, detail = await llm.parse_parameters("生成一个轴承", "bearing", True)
    assert parser == "local-fallback"
    assert detail == "Kimi 请求超时"
