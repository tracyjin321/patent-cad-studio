import json
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.assembly import automatic_manifest
from app.component_library import structured_query_components
from app.component_spec import inspect_step, roundtrip_report
from app.main import app
from app.quality import assembly_quality_score, reference_image_score, visual_regression
from app.semantic_assembly import write_xcaf_assembly
from app.standard_families import materialize_family
from app.component_governance import validate_version_transition


ROOT = Path(__file__).parents[1]
IDS = ["precision-shaft-d03-l0050-chamfered", "bearing-608-open-simple", "shaft-coupler-rigid-clamp-d03-d03-simple"]


def test_structured_search_explains_ranking_and_no_hit_routing():
    bearing = structured_query_components("6201 深沟球轴承", limit=3)
    missing = structured_query_components("完全不存在的冷门部件")
    metric = structured_query_components("M5x20 六角螺栓")
    assert bearing["items"][0]["matched"] and bearing["recommendation"]["reason"]
    assert missing["disposition"] == "backlog_required"
    assert metric["disposition"] == "parametric_generation"
    assert metric["parsed_query"]["diameter_mm"] == 5


def test_standard_family_materialization_roundtrips(tmp_path):
    result = materialize_family("iso4017-hex-bolt", {"diameter_mm": 5, "length_mm": 20}, tmp_path)
    report = roundtrip_report(Path(result["spec_path"]))
    assert report["passed"]


def test_xcaf_export_preserves_instances_and_reuses_definitions(tmp_path):
    manifest = automatic_manifest([IDS[0], IDS[0]], ROOT / "component_library")
    # Reuse is tested without mating because the same target port cannot be occupied twice.
    payload = manifest.model_dump(mode="json")
    payload["components"][1].update({"port": None, "target": None, "mate_to": None})
    from app.assembly import AssemblyManifest
    report = write_xcaf_assembly(AssemblyManifest.model_validate(payload), tmp_path / "assembly.step")
    assert report["definitions"] == 1 and report["instances"] == 2
    assert report["tree"][1]["reused_definition"] is True
    assert inspect_step(tmp_path / "assembly.step")["topology"]["solids"] == 2


def test_visual_regression_and_quality_scoring(tmp_path):
    svg = '<svg><path class="o" d="M0 0L10 10"/><path class="h" d="M0 10L10 0"/></svg>'
    views = {name: svg for name in ("front", "top", "side", "isometric")}
    first = visual_regression("sample", views, tmp_path)
    second = visual_regression("sample", views, tmp_path)
    score = assembly_quality_score(None, views, second)
    assert first["status"] == "baseline_created" and second["passed"]
    assert score["score"] == 100 and score["grade"] == "A"


def test_reference_image_contour_and_feature_score():
    from PIL import Image, ImageDraw
    from io import BytesIO
    image = Image.new("RGB", (100, 50), "white")
    ImageDraw.Draw(image).rectangle((10, 10, 90, 40), outline="black", width=3)
    stream = BytesIO(); image.save(stream, format="PNG")
    score = reference_image_score(stream.getvalue(), '<svg><path class="o" d="M0 0L80 0L80 30L0 30Z"/></svg>')
    assert 0 <= score["score"] <= 100
    assert "contour_score" in score and "key_feature_score" in score


def test_version_governance_rejects_silent_geometry_change():
    existing = {"identity": {"version": "1.2.3"}, "artifacts": {"reference_step": {"sha256": "old"}}}
    patch_only = {"identity": {"version": "1.2.4"}, "artifacts": {"reference_step": {"sha256": "new"}}}
    minor = {"identity": {"version": "1.3.0"}, "artifacts": {"reference_step": {"sha256": "new"}}}
    with pytest.raises(ValueError, match="major 或 minor"):
        validate_version_transition(existing, patch_only)
    validate_version_transition(existing, minor)


def test_online_step_ingestion_runs_bidirectional_validation(monkeypatch, tmp_path):
    from app import component_governance as governance
    step_bytes = (ROOT / "component_library" / "bearing-608-open-simple" / "reference.step").read_bytes()
    client = httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(200, content=step_bytes)))
    monkeypatch.setattr(governance, "REVIEW_ROOT", tmp_path / "review")
    monkeypatch.setattr(governance, "AUDIT_LOG", tmp_path / "audit.jsonl")
    monkeypatch.setattr(governance, "_validate_download_url", lambda _url: None)
    result = governance.ingest_step_url(
        "https://www.step.parts/download/sample.step",
        {"id": "review-bearing-608", "name": "审核轴承", "type": "bearing", "license": "CC-BY-4.0"},
        client=client,
    )
    assert result["validation"]["errors"] == []
    assert result["roundtrip"]["passed"] is True
    assert result["status"] == "pending_approval"


@pytest.mark.asyncio
async def test_phase3_discovery_family_and_backlog_api():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        discovery = await client.get("/api/components/discovery", params={"q": "NEMA23 电机"})
        families = await client.get("/api/component-families")
        backlog = await client.post("/api/component-backlog", json={"description": "需要特殊花键轴图元", "standard": "GB/T TBD"})
    assert discovery.status_code == 200 and len(discovery.json()["providers"]) == 3
    assert any(item["id"] == "nema-motor" for item in families.json()["items"])
    assert backlog.status_code == 201 and backlog.json()["status"] == "open"


@pytest.mark.asyncio
async def test_generate_returns_multiview_xcaf_and_quality_score():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/generate", json={"description": "装配轴轴承和联轴器", "part_type": "shaft", "component_ids": IDS, "use_ai": False})
        step = await client.get(response.json()["step_url"])
    data = response.json()
    assert response.status_code == 200, response.text
    assert set(data["multiviews"]) == {"front", "top", "side", "isometric"}
    assert data["semantic_assembly"]["format"] == "XCAF/AP242"
    assert data["quality_score"]["score"] >= 90
    assert step.content.startswith(b"ISO-10303-21;")
