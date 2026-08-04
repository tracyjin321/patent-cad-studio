import pytest
from httpx import ASGITransport, AsyncClient

from app import main as main_module
from app.main import app
from app.model3d import assembly_to_model


@pytest.mark.asyncio
async def test_recommendation_exposes_relations_and_fallback_contract(monkeypatch):
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
    prompt = "1 个 ISO 4762 M4x8 内六角螺钉、2 个 M4 平垫圈和 1 个 M4 六角螺母，按轴向装配"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/component-recommendations", json={"description": prompt, "limit": 32})
    assert response.status_code == 200
    data = response.json()
    assert len(data["component_ids"]) == 4
    assert len(data["assembly_relations"]) == 3
    assert data["missing_components"] == []
    assert data["capability"] == "ready"


def test_assembly_preview_has_one_colored_mesh_per_instance():
    from app.assembly import automatic_manifest, build_assembly
    manifest = automatic_manifest([
        "gbt70-1-shcs-m4-l0008", "flat-washer-normal-m4-simple", "iso4032-hex-nut-m4",
    ], main_module.ROOT / "component_library")
    _, report = build_assembly(manifest)
    model = assembly_to_model(report)
    assert len(model) == 3
    assert [item["component_id"] for item in model] == [item["component_id"] for item in report["instances"]]
    assert len({item["color"] for item in model}) == 3
