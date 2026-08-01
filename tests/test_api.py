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
    assert response.json() == {"status": "ok"}


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
