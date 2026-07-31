from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .cad import generate_svg
from .llm import LABELS, parse_parameters
from .models import GenerateRequest, GenerateResponse
from .model3d import write_step


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


@app.post("/api/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest) -> GenerateResponse:
    parameters, parser, parser_detail = await parse_parameters(request.description, request.part_type, request.use_ai)
    svg = generate_svg(request.part_type, parameters)
    result_id = str(uuid4())
    model = write_step(GENERATED / f"{result_id}.step", f"{request.part_type} 3D model", request.part_type, parameters)
    checks = [
        {"name": "封闭轮廓", "passed": svg.count('class="o"') >= 2},
        {"name": "中心线/尺寸标注", "passed": 'class="h"' in svg and 'class="d"' in svg},
        {"name": "黑白线稿规范", "passed": "stroke:#17202a" in svg and 'fill="#fff"' in svg},
        {"name": "参数完整", "passed": all(value is not None for value in parameters.values())},
    ]
    return GenerateResponse(
        id=result_id,
        title=f"{LABELS[request.part_type]}技术附图",
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


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)
