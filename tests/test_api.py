import importlib
from io import BytesIO

import pytest
import yaml
from docx import Document
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
    received: dict[str, object] = {}
    svg = '<svg><style>.o{stroke:#000}</style><rect fill="#fff"/><path class="o"/><path class="o"/><path class="h"/><text class="f">图1</text></svg>'

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
    assert received["svg"] is received["step"]


@pytest.mark.asyncio
async def test_generate_writes_yaml_before_step_and_reuses_exact_spec(monkeypatch, tmp_path):
    generated = tmp_path / "generated"
    generated_library = generated / "component_library"
    generated.mkdir()
    generated_library.mkdir()
    monkeypatch.setattr(main_module, "GENERATED", generated)
    monkeypatch.setattr(main_module, "GENERATED_LIBRARY", generated_library)
    payload = {
        "description": "法兰外径160mm，内径76mm，厚度18mm，8个连接孔。",
        "part_type": "flange",
        "use_ai": False,
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/api/generate", json=payload)
        second = await client.post("/api/generate", json=payload)
        yaml_response = await client.get(first.json()["spec_url"])
    assert first.status_code == second.status_code == 200
    first_data, second_data = first.json(), second.json()
    assert first_data["generation_source"] == "generated"
    assert second_data["generation_source"] == "cache"
    assert first_data["spec_id"] == second_data["spec_id"]
    assert first_data["spec_fingerprint"] == second_data["spec_fingerprint"]
    assert yaml_response.status_code == 200
    spec = yaml.safe_load(yaml_response.text)
    assert spec["geometry"]["representation"] == "parametric_brep"
    assert spec["geometry"]["generator"]["mode"] == "parametric"
    assert spec["geometry"]["generator"]["generator_id"] == "flange"
    assert spec["artifacts"]["reference_step"]["sha256"]
    assert next(item for item in first_data["compliance"] if item["name"] == "参数化 YAML 规范")["passed"]


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
    assert 'viewBox="0 0 794 1123"' in svg
    assert ">图1</text>" in svg
    assert 'class="c"' not in svg
    assert 'class="d"' not in svg
    assert "⌀50 · 8孔 · T 70" not in svg
    assert "轴侧图（实体投影）" not in svg
    assert "OpenCascade" not in svg
    assert svg.count('class="o"') >= 8


def test_valve_body_stem_and_handwheel_form_one_connected_solid():
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    from app.model3d import build_shape

    shape = build_shape("valve", {
        "nominal_diameter": 50, "body_length": 230, "height": 310, "ports": 2,
    })
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    solids = 0
    while explorer.More():
        solids += 1
        explorer.Next()
    assert solids == 1


def test_valve_prompt_binds_dn_length_height_and_ports_semantically():
    from app.llm import local_parse

    parameters = local_parse(
        "生成DN50截止阀，阀体长度230mm，总高度310mm，双端法兰连接并包含手轮。",
        "valve",
    )
    assert parameters == {
        "nominal_diameter": 50,
        "body_length": 230,
        "height": 310,
        "ports": 2,
    }


def test_valve_geometry_honors_requested_overall_dimensions():
    from app.component_spec import inspect_shape
    from app.model3d import build_shape

    measured = inspect_shape(build_shape("valve", {
        "nominal_diameter": 50, "body_length": 230, "height": 310, "ports": 2,
    }))
    size = measured["bounding_box"]["size"]
    assert size[0] >= 230
    assert size[2] == pytest.approx(310, abs=0.1)


@pytest.mark.asyncio
async def test_valve_api_validates_semantic_dimensions_and_structure():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/generate", json={
            "description": "生成DN50截止阀，阀体长度230mm，总高度310mm，双端法兰连接并包含手轮。",
            "part_type": "valve",
            "use_ai": False,
        })
    assert response.status_code == 200
    data = response.json()
    assert data["parameters"] == {
        "nominal_diameter": 50, "body_length": 230, "height": 310, "ports": 2,
    }
    checks = {item["name"]: item["passed"] for item in data["compliance"]}
    assert checks["阀体长度与总高度"]
    assert checks["双端法兰与整体结构"]


def test_screw_component_assembly_generation_path_preserves_right_hand_thread(tmp_path):
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    from app.component_spec import load_spec, step_to_spec, validate_spec
    from app.llm import local_parse
    from app.model3d import primitives
    from app.parametric_spec import resolve_parametric_component

    description = "设计梯形传动丝杠，长度420mm，直径28mm，导程6mm，单头右旋螺纹。"
    parameters = local_parse(description, "screw")
    assert parameters == {"length": 420.0, "diameter": 28.0, "lead": 6.0, "starts": 1}
    parts = primitives("screw", parameters)
    journals = [item for item in parts if item["type"] == "cylinder" and item["r"] == 28 * .32]
    thread = next(item for item in parts if item["type"] == "helix")
    assert len(journals) == 2
    assert all(item["depth"] > 0 and item["r"] < 14 for item in journals)
    assert thread["depth"] < parameters["length"]
    assert {key: thread[key] for key in ("pitch", "starts", "handedness", "profile")} == {
        "pitch": 6.0, "starts": 1, "handedness": "right", "profile": "trapezoidal",
    }

    resolved = resolve_parametric_component(
        "screw", parameters, description,
        formal_library=tmp_path / "formal", generated_library=tmp_path / "generated",
    )
    explorer = TopExp_Explorer(resolved.shape, TopAbs_SOLID)
    solids = 0
    while explorer.More():
        solids += 1
        explorer.Next()
    assert solids == 1
    spec = load_spec(resolved.spec_path)
    assert {item["name"]: item["default"] for item in spec["parameters"]} == parameters
    assert [port["id"] for port in spec["ports"]] == ["end_a", "end_b"]
    assert spec["validation"]["topology"]["expected_body_count"] == 1
    recovered_path = resolved.spec_path.parent / "recovered.yaml"
    recovered = step_to_spec(
        resolved.reference_step, recovered_path, copy_reference=False,
        source_spec_path=resolved.spec_path,
    )
    assert recovered["parameters"] == spec["parameters"]
    assert recovered["ports"] == spec["ports"]
    assert validate_spec(recovered, spec_path=recovered_path)["errors"] == []


@pytest.mark.asyncio
async def test_weld_neck_flange_prompt_preserves_dn_neck_and_connection_holes():
    description = "设计高压对焊法兰，公称直径DN100，外径220mm，带颈结构，配置8个连接孔。"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/generate", json={
            "description": description,
            "part_type": "flange",
            "use_ai": False,
        })
    assert response.status_code == 200
    data = response.json()
    assert data["parameters"]["outer_diameter"] == 220
    assert data["parameters"]["inner_diameter"] == 100
    assert data["parameters"]["bolt_holes"] == 8
    assert data["parameters"]["neck_height"] > 0
    assert data["svg"].count('class="o"') >= 20
    assert len(data["model"][0]["positions"]) > 1000
    assert next(item for item in data["compliance"] if item["name"] == "法兰连接孔轮廓")["passed"]


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/health")
    data = response.json()
    assert data["status"] == "ok"
    assert data["generation"] == "available"
    assert data["worker_busy"] is False
    assert data["configured_workers"] >= 1
    assert isinstance(data["worker_pid"], int)


@pytest.mark.asyncio
async def test_health_remains_responsive_while_cad_generation_is_busy(monkeypatch):
    import asyncio
    import threading
    import time
    from pathlib import Path
    from types import SimpleNamespace

    started, release = threading.Event(), threading.Event()

    def slow_resolve(*args, **kwargs):
        started.set()
        assert release.wait(15)
        return SimpleNamespace(
            shape=object(), spec={}, spec_path=Path("component.yaml"),
            component_id="generated-bearing-test", source="generated", fingerprint="test",
        )

    monkeypatch.setattr(main_module, "resolve_parametric_component", slow_resolve)
    monkeypatch.setattr(main_module, "generate_svg", lambda *args: '<svg><style>.o{stroke:#000}</style><rect fill="#fff"/><path class="o"/><path class="o"/><text>图1</text></svg>')
    monkeypatch.setattr(main_module, "write_step", lambda *args: [])
    monkeypatch.setattr(main_module, "validate_spec", lambda *args, **kwargs: {"errors": [], "warnings": []})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        generation = asyncio.create_task(client.post("/api/generate", json={
            "description": "生成测试轴承", "part_type": "bearing", "use_ai": False,
        }))
        assert await asyncio.to_thread(started.wait, 10)
        before = time.perf_counter()
        health_response = await client.get("/api/health")
        elapsed = time.perf_counter() - before
        release.set()
        generated = await generation
    assert health_response.json()["status"] == "ok"
    assert health_response.json()["generation"] == "available"
    assert health_response.json()["worker_busy"] is True
    assert elapsed < 1
    assert generated.status_code == 200


def test_complex_brep_uses_stable_polygonal_hlr(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(main_module, "generate_svg", main_module.generate_svg)
    from app import cad
    monkeypatch.setattr(cad, "_edge_count", lambda shape: 401)
    monkeypatch.setattr(cad, "_project_poly_edges", lambda shape: ([[(0.0, 0.0), (1.0, 1.0)]], [], None))
    monkeypatch.setattr(cad, "_project_edges", lambda shape: calls.append("exact"))
    svg = cad.generate_svg(object(), "复杂丝杠", "screw", {})
    assert svg.startswith("<svg")
    assert calls == []


def test_valve_uses_stable_polygonal_hlr_for_fused_curved_surfaces(monkeypatch):
    from app import cad
    calls: list[str] = []
    monkeypatch.setattr(cad, "_edge_count", lambda shape: 105)
    monkeypatch.setattr(cad, "_project_poly_edges", lambda shape: ([[(0.0, 0.0), (1.0, 1.0)]], [], None))
    monkeypatch.setattr(cad, "_project_edges", lambda shape: calls.append("exact"))
    svg = cad.generate_svg(object(), "截止阀", "valve", {})
    assert svg.startswith("<svg")
    assert calls == []


@pytest.mark.asyncio
async def test_extract_txt_patent_document():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/documents/extract",
            files={"file": ("patent.txt", "一种法兰连接结构。".encode(), "text/plain")},
        )
    assert response.status_code == 200
    assert response.json() == {"text": "一种法兰连接结构。", "truncated": False}


@pytest.mark.asyncio
async def test_extract_docx_patent_document():
    stream = BytesIO()
    document = Document()
    document.add_paragraph("一种轴承支撑结构。")
    document.save(stream)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/documents/extract",
            files={"file": ("patent.docx", stream.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
    assert response.status_code == 200
    assert response.json()["text"] == "一种轴承支撑结构。"


@pytest.mark.asyncio
async def test_extract_document_rejects_unsupported_format():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/documents/extract",
            files={"file": ("patent.md", b"unsupported", "text/markdown")},
        )
    assert response.status_code == 422
    assert response.json()["detail"] == "仅支持 PDF、DOCX 和 TXT 文档"


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
async def test_component_library_can_be_searched_and_filtered():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        catalog = await client.get("/api/components")
        bearing = await client.get("/api/components", params={"q": "BAU6201Z", "category": "shaft_support"})
    assert catalog.status_code == 200
    assert catalog.json()["total"] == 88
    assert len(catalog.json()["categories"]) >= 6
    assert bearing.status_code == 200
    assert [item["id"] for item in bearing.json()["items"]] == ["deep-groove-ball-bau6201z"]


@pytest.mark.asyncio
async def test_generate_returns_selected_component_constraints(monkeypatch):
    monkeypatch.setattr(main_module, "write_step", lambda *args: [])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/generate", json={
            "description": "生成一个深沟球轴承。",
            "part_type": "bearing",
            "component_ids": ["deep-groove-ball-bau6201z"],
            "use_ai": False,
        })
        invalid = await client.post("/api/generate", json={
            "description": "生成一个轴承。", "part_type": "bearing",
            "component_ids": ["not-in-library"], "use_ai": False,
        })
    assert response.status_code == 200
    assert response.json()["selected_components"][0]["name"] == "深沟球轴承"
    assert invalid.status_code == 422
    assert "not-in-library" in invalid.json()["detail"]


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
    assert detail == "智能解析响应超时，已自动回退"


@pytest.mark.asyncio
async def test_parameter_extraction_uses_strict_structured_output(monkeypatch):
    captured: dict[str, object] = {}

    class SuccessfulResponse:
        def raise_for_status(self): return None
        def json(self):
            return {
                "choices": [{
                    "finish_reason": "stop",
                    "message": {"content": '{"outer_diameter":90,"inner_diameter":45,"width":23,"rolling_elements":12}'},
                }],
            }

    class SuccessfulClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, *args, **kwargs):
            captured.update(kwargs["json"])
            return SuccessfulResponse()

    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda **kwargs: SuccessfulClient())
    monkeypatch.setenv("MOONSHOT_API_KEY", "test-key")
    parameters, parser, detail = await llm.parse_parameters("轴承外径90内径45宽23，12个滚珠", "bearing", True)
    response_format = captured["response_format"]
    assert parser == "moonshot"
    assert detail is None
    assert parameters["rolling_elements"] == 12
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    assert response_format["json_schema"]["schema"]["additionalProperties"] is False
    assert captured["thinking"] == {"type": "disabled"}
    assert captured["max_completion_tokens"] == 256


@pytest.mark.asyncio
async def test_remote_protocol_error_is_hidden_from_user_and_logged(monkeypatch, caplog):
    class BrokenClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, *args, **kwargs):
            raise llm.httpx.RemoteProtocolError("Server disconnected without sending a response")

    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda **kwargs: BrokenClient())
    monkeypatch.setenv("MOONSHOT_API_KEY", "test-key")
    _, parser, detail = await llm.parse_parameters("生成一个密封件", "seal", True)
    assert parser == "local-fallback"
    assert detail == "智能解析服务通信异常，已自动回退"
    assert "RemoteProtocolError" not in detail
    assert "Server disconnected without sending a response" in caplog.text


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
