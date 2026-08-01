import importlib

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app import llm


main_module = importlib.import_module("app.main")


PARTS = ["bearing", "flange", "valve", "shaft", "gear", "screw", "coupling", "seal"]


@pytest.mark.asyncio
@pytest.mark.parametrize("part_type", PARTS)
async def test_all_part_types_generate_valid_svg(part_type: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/generate", json={
            "description": "生成一个用于专利附图的标准机械零件，外径100，内径45，长度200。",
            "part_type": part_type,
            "core_elements": [part_type],
            "use_ai": False,
        })
        step = await client.get(response.json()["step_url"])
    assert response.status_code == 200
    data = response.json()
    assert data["svg"].startswith("<svg")
    assert data["svg"].endswith("</svg>")
    assert data["parameters"]
    assert data["model"]
    assert data["core_elements"] == [part_type]
    assert data["step_url"].endswith("/step")
    assert all(item["passed"] for item in data["compliance"])
    assert step.status_code == 200
    assert step.content.startswith(b"ISO-10303-21;")


@pytest.mark.asyncio
async def test_svg_and_step_share_the_same_brep_shape(monkeypatch):
    shape = object()
    received: dict[str, object] = {}
    svg = '<svg><style>.o{stroke:#17202a}</style><rect fill="#fff"/><path class="o"/><path class="o"/><path class="h"/><path class="d"/></svg>'

    monkeypatch.setattr(main_module, "build_shape", lambda part, parameters: shape)

    def fake_svg(candidate, title, part, parameters):
        received["svg"] = candidate
        return svg

    def fake_step(path, title, candidate):
        received["step"] = candidate
        return [{"type": "mesh", "positions": [], "indices": []}]

    monkeypatch.setattr(main_module, "generate_svg", fake_svg)
    monkeypatch.setattr(main_module, "write_step", fake_step)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/generate", json={
            "description": "生成外径100、内径45的法兰。",
            "part_type": "flange",
            "use_ai": False,
        })
    assert response.status_code == 200
    assert received == {"svg": shape, "step": shape}


@pytest.mark.asyncio
async def test_flange_svg_is_an_occ_entity_projection():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/generate", json={
            "description": "法兰外径50，内径16，厚度70，8个螺栓孔。",
            "part_type": "flange",
            "use_ai": False,
        })
    assert response.status_code == 200
    svg = response.json()["svg"]
    assert "轴侧图（实体投影）" in svg
    assert "⌀50 · 8孔 · T 70" in svg
    assert svg.count('class="o"') >= 8


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/health")
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_core_element_recommendation_local_fallback():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/recommend", json={
            "description": "主轴由滚动轴承支撑，并通过联轴器与齿轮传动机构连接。",
            "use_ai": False,
        })
    assert response.status_code == 200
    assert response.json()["elements"] == ["bearing", "shaft", "gear", "coupling"]
    assert response.json()["parser"] == "local"


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


def test_invalid_dimensions_are_normalized_before_geometry_generation():
    flange = llm.normalize_parameters("flange", {
        "outer_diameter": 0,
        "inner_diameter": 999,
        "thickness": -1,
        "bolt_holes": 100,
    })
    assert flange["outer_diameter"] == llm.DEFAULTS["flange"]["outer_diameter"]
    assert flange["inner_diameter"] < flange["outer_diameter"]
    assert flange["thickness"] == llm.DEFAULTS["flange"]["thickness"]
    assert flange["bolt_holes"] == 16


@pytest.mark.asyncio
async def test_step_to_yaml_and_yaml_to_step_api():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    source = root / "component_library" / "deep-groove-ball-bau6201z" / "reference.step"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        converted = await client.post(
            "/api/convert/step-to-yaml?filename=bearing.stp",
            content=source.read_bytes(),
            headers={"content-type": "application/step"},
        )
        assert converted.status_code == 200, converted.text
        yaml_response = await client.get(converted.json()["yaml_url"])
        assert yaml_response.status_code == 200
        reference_response = await client.get(converted.json()["reference_step_url"])
        assert reference_response.status_code == 200
        assert reference_response.content == source.read_bytes()
        conversion_id = converted.json()["id"]
        rebuilt = await client.post("/api/convert/yaml-to-step", json={"spec_path": f"generated/{conversion_id}.yaml", "reexport": True})
        assert rebuilt.status_code == 200, rebuilt.text
        step_response = await client.get(rebuilt.json()["step_url"])
        assert step_response.status_code == 200
        assert step_response.content.startswith(b"ISO-10303-21;")
