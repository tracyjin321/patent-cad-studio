from pathlib import Path
from contextlib import asynccontextmanager, contextmanager
import asyncio
import fcntl
import hashlib
import json
import os
import re
import time
from threading import Lock
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from fastapi import Body, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from .cad import generate_multiview_svgs, generate_svg
from .documents import extract_document_text
from .llm import DEFAULTS, LABELS, parse_parameters, recommend_core_elements
from .component_spec import load_spec, read_step, spec_to_step, step_to_spec, validate_spec, write_shape_step
from .component_library import components_by_id, recommend_component_instances, structured_query_components
from .component_governance import create_backlog, discovery_links, ingest_step_url, review_component
from .quality import assembly_quality_score, reference_image_score, visual_regression
from .semantic_assembly import write_xcaf_assembly
from .standard_families import FAMILIES, materialize_family
from .assembly import automatic_manifest, build_assembly
from .models import ComponentIngestRequest, ComponentRecommendationRequest, ComponentRecommendationResponse, FamilyMaterializeRequest, GenerateRequest, GenerateResponse, RecommendRequest, RecommendResponse, ReviewRequest, YamlToStepRequest
from .model3d import write_step
from .parametric_spec import resolve_parametric_component


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
GENERATED = ROOT / "generated"
GENERATED.mkdir(exist_ok=True)
GENERATED_LIBRARY = GENERATED / "component_library"
GENERATED_LIBRARY.mkdir(exist_ok=True)
ASSEMBLY_CACHE = GENERATED / "assemblies"
ASSEMBLY_CACHE.mkdir(exist_ok=True)
TASKS_DIR = GENERATED / "tasks"
TASKS_DIR.mkdir(exist_ok=True)
VISUAL_BASELINES = GENERATED / "visual-baselines"
GENERATION_REVIEWS = GENERATED / "generation-reviews"
GENERATION_REVIEWS.mkdir(exist_ok=True)
GENERATION_TASKS: dict[str, dict[str, object]] = {}
RUNNING_TASKS: dict[str, asyncio.Task] = {}
GENERATION_TIMEOUT_SECONDS = max(30, int(os.getenv("GENERATION_TIMEOUT_SECONDS", "300")))
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


def _persist_task(task_id: str) -> None:
    record = {key: value for key, value in GENERATION_TASKS[task_id].items() if key != "runtime_task"}
    (TASKS_DIR / f"{task_id}.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")


def recover_generation_tasks() -> None:
    for path in TASKS_DIR.glob("*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("status") in {"queued", "running"}:
                record.update({"status": "failed", "error": "生成 worker 曾中断，请重新提交任务", "recoverable": True})
                path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            GENERATION_TASKS[str(record["id"])] = record
        except (OSError, ValueError, KeyError):
            continue


@asynccontextmanager
async def app_lifespan(_app):
    recover_generation_tasks()
    yield


app.router.lifespan_context = app_lifespan


@contextmanager
def cad_resource_slot(part_type: str, parameters: dict[str, object] | None = None):
    """Bound memory-heavy jobs across workers while normal jobs stay 5-way parallel."""
    if part_type not in {"gear", "screw", "rocket"}:
        yield
        return
    slot_dir = GENERATED / ".heavy-slots"
    slot_dir.mkdir(exist_ok=True)
    values = parameters or {}
    exclusive = part_type == "rocket" or (
        part_type == "gear" and float(values.get("helix_angle", 0)) > 0
    ) or (
        part_type == "screw" and float(values.get("length", 0)) >= 400
    )
    required = HEAVY_CAD_SLOTS if exclusive else 1
    streams = []
    while len(streams) < required:
        streams = []
        for index in range(HEAVY_CAD_SLOTS):
            candidate = (slot_dir / f"slot-{index}.lock").open("a+b")
            try:
                fcntl.flock(candidate.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                streams.append(candidate)
                if len(streams) == required: break
            except BlockingIOError:
                candidate.close()
        if len(streams) < required:
            for candidate in streams:
                fcntl.flock(candidate.fileno(), fcntl.LOCK_UN);candidate.close()
            streams = []
            time.sleep(0.1)
    try:
        yield
    finally:
        for stream in streams:
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


@app.post("/api/component-recommendations", response_model=ComponentRecommendationResponse)
def recommend_components(request: ComponentRecommendationRequest) -> dict[str, object]:
    return recommend_component_instances(request.description, request.limit)


@app.get("/api/components")
def list_components(
    q: str = Query(default="", max_length=100),
    category: str = Query(default="", max_length=50),
    component_type: str = Query(default="", max_length=50),
    subtype: str = Query(default="", max_length=100),
    status: str = Query(default="", max_length=30),
    standard: str = Query(default="", max_length=100),
    port_type: str = Query(default="", max_length=100),
    limit: int = Query(default=100, ge=1, le=200),
) -> dict[str, object]:
    """Search the local component library used by the assembly constraint picker."""
    return structured_query_components(q, category, component_type=component_type, subtype=subtype, status=status, standard=standard, port_type=port_type, limit=limit)


@app.get("/api/components/discovery")
def component_discovery(q: str = Query(min_length=2, max_length=100)) -> dict[str, object]:
    local = structured_query_components(q, limit=10)
    return {"query": q, "local": local, "providers": discovery_links(q), "next_action": local["disposition"]}


@app.post("/api/component-backlog", status_code=201)
def component_backlog(requirement: dict[str, object]) -> dict[str, object]:
    if len(str(requirement.get("description", "")).strip()) < 2:
        raise HTTPException(status_code=422, detail="待补图元必须包含 description")
    return create_backlog(requirement)


@app.get("/api/component-families")
def component_families() -> dict[str, object]:
    return {"items": [{"id": key, **value} for key, value in FAMILIES.items()]}


@app.post("/api/component-families/materialize", status_code=201)
def materialize_component_family(request: FamilyMaterializeRequest) -> dict[str, object]:
    try:
        return materialize_family(request.family_id, request.parameters, GENERATED_LIBRARY)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/component-ingestion", status_code=201)
def component_ingestion(request: ComponentIngestRequest) -> dict[str, object]:
    try:
        return ingest_step_url(request.url, request.identity)
    except (ValueError, httpx.HTTPError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/component-ingestion/{review_id}/review")
def component_ingestion_review(review_id: str, request: ReviewRequest) -> dict[str, object]:
    try:
        return review_component(review_id, request.decision, request.reviewer, request.note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="入库审核任务不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


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
        with CAD_KERNEL_LOCK, cad_resource_slot(request.part_type, parameters):
            assembly_report = None
            if request.component_ids:
                manifest = automatic_manifest(request.component_ids, ROOT / "component_library")
                cache_key = hashlib.sha256(manifest.model_dump_json().encode()).hexdigest()
                cache_step, cache_report = ASSEMBLY_CACHE / f"{cache_key}.step", ASSEMBLY_CACHE / f"{cache_key}.json"
                if cache_step.is_file() and cache_report.is_file():
                    shape = read_step(cache_step)
                    assembly_report = json.loads(cache_report.read_text(encoding="utf-8"))
                    generation_source = "cache"
                else:
                    shape, assembly_report = build_assembly(manifest)
                    write_shape_step(shape, cache_step, manifest.application_protocol)
                    cache_report.write_text(json.dumps(assembly_report, ensure_ascii=False, indent=2), encoding="utf-8")
                    generation_source = "generated"
                spec_id = request.component_ids[0]
                spec_url = f"/api/components/{spec_id}/yaml"
                fingerprint = assembly_report["fingerprint"]
                spec_check = {"name": "装配清单与端口规则", "passed": True}
            else:
                resolved = resolve_parametric_component(
                    request.part_type,
                    parameters,
                    request.description,
                    formal_library=ROOT / "component_library",
                    generated_library=GENERATED_LIBRARY,
                )
                shape = resolved.shape
                generation_source = resolved.source
                spec_id = resolved.component_id
                spec_url = f"/api/components/{resolved.component_id}/yaml"
                fingerprint = resolved.fingerprint
                spec_check = {"name": "参数化 YAML 规范", "passed": not validate_spec(resolved.spec, spec_path=resolved.spec_path)["errors"]}
            svg = generate_svg(shape, title, request.part_type, parameters)
            multiviews = generate_multiview_svgs(shape, title, request.part_type, parameters) if hasattr(shape, "ShapeType") else {view: svg for view in ("front", "top", "side", "isometric")}
            multiviews["isometric"] = svg
            result_id = str(uuid4())
            result_step = GENERATED / f"{result_id}.step"
            model = write_step(result_step, f"{request.part_type} 3D model", shape)
            semantic_assembly = None
            if request.component_ids:
                semantic_assembly = write_xcaf_assembly(manifest, result_step)
                assembly_report["semantic_assembly"] = semantic_assembly
            regression = visual_regression(spec_id, multiviews, VISUAL_BASELINES)
            quality_score = assembly_quality_score(assembly_report, multiviews, regression)
            (GENERATED / f"{result_id}.svg").write_text(svg, encoding="utf-8")
            checks = [
                {"name": "结构轮廓清晰", "passed": svg.count('class="o"') >= 2},
                {"name": "法兰连接孔轮廓", "passed": request.part_type != "flange" or svg.count('class="o"') >= int(parameters["bolt_holes"]) * 2},
                {"name": "无多余中心线/尺寸线", "passed": 'class="c"' not in svg and 'class="d"' not in svg},
                {"name": "黑白线稿规范", "passed": "stroke:#000" in svg and 'fill="#fff"' in svg},
                {"name": "附图编号", "passed": ">图1</text>" in svg},
                {"name": "参数完整", "passed": all(value is not None for value in parameters.values())},
                spec_check,
            ]
            if request.component_ids:
                checks.extend([
                    {"name": "装配 B-Rep 有效", "passed": bool(assembly_report["quality"]["valid_brep"])},
                    {"name": "装配无实体干涉", "passed": bool(assembly_report["quality"]["interference_free"])},
                ])
            if request.part_type == "valve" and not request.component_ids:
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
            return svg, multiviews, result_id, model, checks, assembly_report, generation_source, spec_id, spec_url, fingerprint, regression, quality_score, semantic_assembly

    svg, multiviews, result_id, model, checks, assembly_report, generation_source, spec_id, spec_url, fingerprint, regression, quality_score, semantic_assembly = await run_in_threadpool(build_artifacts)
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
        spec_id=spec_id,
        spec_url=spec_url,
        generation_source=generation_source,
        spec_fingerprint=fingerprint,
        core_elements=request.core_elements or [request.part_type],
        selected_components=[{
            "id": component["id"], "name": component["name"], "type": component["type"],
            "category": component["category"],
        } for component in selected_components],
        assembly_report=assembly_report,
        quality_report=assembly_report["quality"] if assembly_report else None,
        multiviews=multiviews,
        visual_regression=regression,
        quality_score=quality_score,
        semantic_assembly=semantic_assembly,
    )


async def _run_generation_task(task_id: str, request: GenerateRequest) -> None:
    record = GENERATION_TASKS[task_id]
    record.update({"status": "running", "progress": 10})
    _persist_task(task_id)
    try:
        result = await asyncio.wait_for(generate(request), timeout=GENERATION_TIMEOUT_SECONDS)
        record.update({"status": "completed", "progress": 100, "result": result.model_dump(mode="json"), "error": None})
    except asyncio.CancelledError:
        record.update({"status": "cancelled", "error": "任务已取消", "progress": 0})
    except asyncio.TimeoutError:
        record.update({"status": "failed", "error": f"生成超时（{GENERATION_TIMEOUT_SECONDS} 秒），可重试", "recoverable": True})
    except HTTPException as exc:
        record.update({"status": "failed", "error": str(exc.detail), "recoverable": False})
    except Exception as exc:
        record.update({"status": "failed", "error": f"CAD 生成失败：{exc}", "recoverable": True})
    finally:
        _persist_task(task_id)
        RUNNING_TASKS.pop(task_id, None)


@app.post("/api/generation-tasks", status_code=202)
async def create_generation_task(request: GenerateRequest) -> dict[str, object]:
    task_id = str(uuid4())
    GENERATION_TASKS[task_id] = {"id": task_id, "status": "queued", "progress": 0, "request": request.model_dump(mode="json"), "result": None, "error": None}
    _persist_task(task_id)
    RUNNING_TASKS[task_id] = asyncio.create_task(_run_generation_task(task_id, request))
    return {"id": task_id, "status": "queued", "status_url": f"/api/generation-tasks/{task_id}"}


@app.get("/api/generation-tasks/{task_id}")
def get_generation_task(task_id: str) -> dict[str, object]:
    record = GENERATION_TASKS.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="生成任务不存在")
    return record


@app.delete("/api/generation-tasks/{task_id}")
async def cancel_generation_task(task_id: str) -> dict[str, object]:
    record = GENERATION_TASKS.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="生成任务不存在")
    if record.get("status") in {"completed", "failed", "cancelled"}:
        return {"id": task_id, "status": record["status"]}
    runtime = RUNNING_TASKS.get(task_id)
    if runtime:
        runtime.cancel()
    record.update({"status": "cancelled", "error": "任务已取消"})
    _persist_task(task_id)
    return {"id": task_id, "status": "cancelled"}


@app.get("/api/models/{model_id}/step")
def download_step(model_id: str) -> Response:
    if not model_id.replace("-", "").isalnum():
        return Response(status_code=404)
    path = GENERATED / f"{model_id}.step"
    if not path.exists():
        return Response(status_code=404)
    return FileResponse(path, media_type="application/step", filename=f"part-{model_id[:8]}.step")


@app.post("/api/models/{model_id}/reference-score")
async def compare_reference_image(model_id: str, file: UploadFile = File(...)) -> dict[str, object]:
    svg_path = GENERATED / f"{model_id}.svg"
    if not svg_path.is_file():
        raise HTTPException(status_code=404, detail="模型不存在")
    content = await file.read(10 * 1024 * 1024 + 1)
    await file.close()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="参考图不能超过 10MB")
    try:
        return reference_image_score(content, svg_path.read_text(encoding="utf-8"))
    except (ValueError, RuntimeError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/generation-reviews/{model_id}")
def get_generation_review(model_id: str) -> dict[str, object]:
    path = GENERATION_REVIEWS / f"{model_id}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"model_id": model_id, "status": "pending"}


@app.post("/api/generation-reviews/{model_id}")
def set_generation_review(model_id: str, request: ReviewRequest) -> dict[str, object]:
    if not (GENERATED / f"{model_id}.step").is_file():
        raise HTTPException(status_code=404, detail="模型不存在")
    record = {"model_id": model_id, "status": "approved" if request.decision == "approve" else "rejected", "reviewer": request.reviewer, "note": request.note, "reviewed_at": time.time()}
    (GENERATION_REVIEWS / f"{model_id}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


@app.get("/api/generated-components/{component_id}/step")
def generated_component_step(component_id: str) -> Response:
    path = GENERATED_LIBRARY / component_id / "reference.step"
    return FileResponse(path, media_type="application/step", filename=f"{component_id}.step") if path.is_file() else Response(status_code=404)


@app.get("/api/generated-components/{component_id}/yaml")
def generated_component_yaml(component_id: str) -> Response:
    path = GENERATED_LIBRARY / component_id / "component.yaml"
    return FileResponse(path, media_type="application/yaml", filename=f"{component_id}.yaml") if path.is_file() else Response(status_code=404)


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
