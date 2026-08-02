from pathlib import Path
from contextlib import contextmanager
import fcntl
import os
import re
import time
from threading import Lock
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import Body, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from .cad import generate_svg
from .documents import extract_document_text
from .llm import DEFAULTS, LABELS, parse_parameters, recommend_core_elements
from .component_spec import load_spec, spec_to_step, step_to_spec, validate_spec
from .component_library import components_by_id, query_components
from .models import GenerateRequest, GenerateResponse, RecommendRequest, RecommendResponse, YamlToStepRequest
from .model3d import write_step
from .parametric_spec import resolve_parametric_component


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
GENERATED = ROOT / "generated"
GENERATED.mkdir(exist_ok=True)
GENERATED_LIBRARY = GENERATED / "component_library"
GENERATED_LIBRARY.mkdir(exist_ok=True)
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
MAX_DESCRIPTION_CHARS = 5000
# OCP/OpenCascade is not reliably thread-safe inside one Python interpreter.
# Keep one CAD job per worker, and scale with isolated uvicorn worker processes.
CAD_KERNEL_LOCK = Lock()
CAD_WORKERS = max(1, int(os.getenv("CAD_WORKERS", "5")))
HEAVY_CAD_SLOTS = max(2, int(os.getenv("HEAVY_CAD_SLOTS", "2")))
app = FastAPI(title="专图灵境 API", version="1.0.0")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
app.mount("/vendor/three", StaticFiles(directory=ROOT / "node_modules" / "three"), name="three")


@contextmanager
def cad_resource_slot(part_type: str):
    """Bound memory-heavy jobs across workers while normal jobs stay 5-way parallel."""
    if part_type not in {"gear", "screw"}:
        yield
        return
    slot_dir = GENERATED / ".heavy-slots"
    slot_dir.mkdir(exist_ok=True)
    stream = None
    while stream is None:
        for index in range(HEAVY_CAD_SLOTS):
            candidate = (slot_dir / f"slot-{index}.lock").open("a+b")
            try:
                fcntl.flock(candidate.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                stream = candidate
                break
            except BlockingIOError:
                candidate.close()
        if stream is None:
            time.sleep(0.1)
    try:
        yield
    finally:
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "generation": "available",
        "worker_busy": CAD_KERNEL_LOCK.locked(),
        "worker_pid": os.getpid(),
        "configured_workers": CAD_WORKERS,
    }


@app.post("/api/documents/extract")
async def extract_document(file: UploadFile = File(...)) -> dict[str, str | bool]:
    filename = file.filename or ""
    content = await file.read(MAX_DOCUMENT_BYTES + 1)
    await file.close()
    if len(content) > MAX_DOCUMENT_BYTES:
        raise HTTPException(status_code=413, detail="文档不能超过 10MB")
    try:
        text = extract_document_text(filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    truncated = len(text) > MAX_DESCRIPTION_CHARS
    return {"text": text[:MAX_DESCRIPTION_CHARS], "truncated": truncated}


@app.post("/api/recommend", response_model=RecommendResponse)
async def recommend(request: RecommendRequest) -> RecommendResponse:
    elements, parser, detail = await recommend_core_elements(request.description, request.use_ai)
    return RecommendResponse(elements=elements, parser=parser, parser_detail=detail)


@app.get("/api/components")
def list_components(
    q: str = Query(default="", max_length=100),
    category: str = Query(default="", max_length=50),
) -> dict[str, object]:
    """Search the local component library used by the assembly constraint picker."""
    return query_components(q, category)


@app.post("/api/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest) -> GenerateResponse:
    try:
        selected_components = components_by_id(request.component_ids)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=f"未知 component_library 图元: {exc.args[0]}") from exc
    parameters, parser, parser_detail = await parse_parameters(request.description, request.part_type, request.use_ai)
    title = f"{LABELS[request.part_type]}技术附图"

    def build_artifacts():
        # One OpenCascade job per interpreter; separate uvicorn processes provide
        # safe multi-user parallelism without changing geometry or meshing quality.
        with CAD_KERNEL_LOCK, cad_resource_slot(request.part_type):
            resolved = resolve_parametric_component(
                request.part_type,
                parameters,
                request.description,
                formal_library=ROOT / "component_library",
                generated_library=GENERATED_LIBRARY,
            )
            shape = resolved.shape
            svg = generate_svg(shape, title, request.part_type, parameters)
            result_id = str(uuid4())
            model = write_step(GENERATED / f"{result_id}.step", f"{request.part_type} 3D model", shape)
            checks = [
                {"name": "结构轮廓清晰", "passed": svg.count('class="o"') >= 2},
                {"name": "法兰连接孔轮廓", "passed": request.part_type != "flange" or svg.count('class="o"') >= int(parameters["bolt_holes"]) * 2},
                {"name": "无多余中心线/尺寸线", "passed": 'class="c"' not in svg and 'class="d"' not in svg},
                {"name": "黑白线稿规范", "passed": "stroke:#000" in svg and 'fill="#fff"' in svg},
                {"name": "附图编号", "passed": ">图1</text>" in svg},
                {"name": "参数完整", "passed": all(value is not None for value in parameters.values())},
                {"name": "参数化 YAML 规范", "passed": not validate_spec(resolved.spec, spec_path=resolved.spec_path)["errors"]},
            ]
            if request.part_type == "valve":
                measured = resolved.spec.get("validation", {}).get("geometry", {}).get("measured") or {}
                size = measured.get("bounding_box", {}).get("size", [0, 0, 0])
                topology = measured.get("topology", {})
                checks.extend([
                    {
                        "name": "阀体长度与总高度",
                        "passed": len(size) == 3
                        and size[0] >= float(parameters["body_length"])
                        and abs(size[2] - float(parameters["height"])) <= 0.1,
                    },
                    {
                        "name": "双端法兰与整体结构",
                        "passed": int(parameters["ports"]) == 2
                        and len(resolved.spec.get("ports", [])) == 2
                        and topology.get("solids") == 1,
                    },
                ])
            return resolved, svg, result_id, model, checks

    resolved, svg, result_id, model, checks = await run_in_threadpool(build_artifacts)
    return GenerateResponse(
        id=result_id,
        title=title,
        part_type=request.part_type,
        svg=svg,
        parameters={key: parameters[key] for key in DEFAULTS[request.part_type]},
        structural_parameters={key: value for key, value in parameters.items() if key not in DEFAULTS[request.part_type]},
        compliance=checks,
        parser=parser,
        parser_detail=parser_detail,
        model=model,
        step_url=f"/api/models/{result_id}/step",
        spec_id=resolved.component_id,
        spec_url=f"/api/components/{resolved.component_id}/yaml",
        generation_source=resolved.source,
        spec_fingerprint=resolved.fingerprint,
        core_elements=request.core_elements or [request.part_type],
        selected_components=[{
            "id": component["id"], "name": component["name"], "type": component["type"],
            "category": component["category"],
        } for component in selected_components],
    )


@app.get("/api/models/{model_id}/step")
def download_step(model_id: str) -> Response:
    if not model_id.replace("-", "").isalnum():
        return Response(status_code=404)
    path = GENERATED / f"{model_id}.step"
    if not path.exists():
        return Response(status_code=404)
    return FileResponse(path, media_type="application/step", filename=f"part-{model_id[:8]}.step")


@app.get("/api/components/{component_id}/yaml")
def download_component_yaml(component_id: str) -> Response:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,127}", component_id):
        return Response(status_code=404)
    candidates = [
        ROOT / "component_library" / component_id / "component.yaml",
        GENERATED_LIBRARY / component_id / "component.yaml",
    ]
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        return Response(status_code=404)
    return FileResponse(path, media_type="application/yaml", filename=f"{component_id}.yaml")


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
    return FileResponse(
        ROOT / "static" / "index.html",
        headers={"Cache-Control": "no-store, must-revalidate"},
    )


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)
