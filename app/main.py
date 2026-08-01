from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .cad import generate_svg
from .llm import LABELS, parse_parameters, recommend_core_elements
from .component_spec import load_spec, spec_to_step, step_to_spec, validate_spec
from .models import GenerateRequest, GenerateResponse, RecommendRequest, RecommendResponse, YamlToStepRequest
from .model3d import build_shape, write_step


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
GENERATED = ROOT / "generated"
GENERATED.mkdir(exist_ok=True)
app = FastAPI(title="专图灵境 API", version="1.0.0")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
app.mount("/vendor/three", StaticFiles(directory=ROOT / "node_modules" / "three"), name="three")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/recommend", response_model=RecommendResponse)
async def recommend(request: RecommendRequest) -> RecommendResponse:
    elements, parser, detail = await recommend_core_elements(request.description, request.use_ai)
    return RecommendResponse(elements=elements, parser=parser, parser_detail=detail)


@app.post("/api/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest) -> GenerateResponse:
    parameters, parser, parser_detail = await parse_parameters(request.description, request.part_type, request.use_ai)
    title = f"{LABELS[request.part_type]}技术附图"
    shape = build_shape(request.part_type, parameters)
    svg = generate_svg(shape, title, request.part_type, parameters)
    result_id = str(uuid4())
    model = write_step(GENERATED / f"{result_id}.step", f"{request.part_type} 3D model", shape)
    checks = [
        {"name": "封闭轮廓", "passed": svg.count('class="o"') >= 2},
        {"name": "中心线/尺寸标注", "passed": 'class="h"' in svg and 'class="d"' in svg},
        {"name": "黑白线稿规范", "passed": "stroke:#17202a" in svg and 'fill="#fff"' in svg},
        {"name": "参数完整", "passed": all(value is not None for value in parameters.values())},
    ]
    return GenerateResponse(
        id=result_id,
        title=title,
        part_type=request.part_type,
        svg=svg,
        parameters=parameters,
        compliance=checks,
        parser=parser,
        parser_detail=parser_detail,
        model=model,
        step_url=f"/api/models/{result_id}/step",
        core_elements=request.core_elements or [request.part_type],
    )


@app.get("/api/models/{model_id}/step")
def download_step(model_id: str) -> Response:
    if not model_id.replace("-", "").isalnum():
        return Response(status_code=404)
    path = GENERATED / f"{model_id}.step"
    if not path.exists():
        return Response(status_code=404)
    return FileResponse(path, media_type="application/step", filename=f"part-{model_id[:8]}.step")


def _safe_spec_path(relative: str) -> Path:
    candidate = (ROOT / relative).resolve()
    allowed = (ROOT / "component_library").resolve(), GENERATED.resolve()
    if candidate.suffix.lower() not in {".yaml", ".yml"} or not any(candidate.is_relative_to(root) for root in allowed):
        raise HTTPException(status_code=400, detail="spec_path 只能指向 component_library 或 generated 下的 YAML")
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="YAML 不存在")
    return candidate


@app.post("/api/convert/step-to-yaml")
def convert_step_to_yaml(
    content: bytes = Body(media_type="application/step"),
    filename: str = Query(default="component.step", max_length=200),
) -> dict[str, object]:
    suffix = Path(filename).suffix.lower()
    if suffix not in {".step", ".stp"}:
        raise HTTPException(status_code=400, detail="filename 必须以 .step 或 .stp 结尾")
    if not content or len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="STEP 必须非空且不超过 50 MiB")
    conversion_id = str(uuid4())
    source = GENERATED / f"{conversion_id}-source{suffix}"
    yaml_path = GENERATED / f"{conversion_id}.yaml"
    source.write_bytes(content)
    try:
        spec = step_to_spec(source, yaml_path, identity={"name": Path(filename).stem})
    except (ValueError, RuntimeError) as exc:
        source.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"id": conversion_id, "identity": spec["identity"], "geometry": spec["validation"]["geometry"]["measured"],
            "yaml_url": f"/api/conversions/{conversion_id}/yaml",
            "reference_step_url": f"/api/conversions/{conversion_id}/reference-step"}


@app.post("/api/convert/yaml-to-step")
def convert_yaml_to_step(request: YamlToStepRequest) -> dict[str, object]:
    spec_path = _safe_spec_path(request.spec_path)
    conversion_id = str(uuid4())
    output = GENERATED / f"{conversion_id}.step"
    try:
        measured = spec_to_step(spec_path, output, force_reexport=request.reexport)
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"id": conversion_id, "geometry": measured, "step_url": f"/api/models/{conversion_id}/step"}


@app.get("/api/conversions/{conversion_id}/yaml")
def download_yaml(conversion_id: str) -> Response:
    if not conversion_id.replace("-", "").isalnum():
        return Response(status_code=404)
    path = GENERATED / f"{conversion_id}.yaml"
    if not path.exists():
        return Response(status_code=404)
    return FileResponse(path, media_type="application/yaml", filename=f"component-{conversion_id[:8]}.yaml")


@app.get("/api/conversions/{conversion_id}/reference-step")
def download_conversion_reference(conversion_id: str) -> Response:
    if not conversion_id.replace("-", "").isalnum():
        return Response(status_code=404)
    candidates = [GENERATED / f"{conversion_id}.step", GENERATED / f"{conversion_id}.stp"]
    path = next((item for item in candidates if item.exists()), None)
    if path is None:
        return Response(status_code=404)
    return FileResponse(path, media_type="application/step", filename=f"component-{conversion_id[:8]}{path.suffix}")


@app.get("/api/component-spec/validate")
def validate_component_spec(spec_path: str) -> dict[str, object]:
    path = _safe_spec_path(spec_path)
    result = validate_spec(load_spec(path), spec_path=path)
    return {**result, "valid": not result["errors"]}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)
