"""Deterministic visual signatures, reference-image similarity, and assembly scoring."""

from __future__ import annotations

import hashlib
import io
import json
import math
from pathlib import Path
import re
from typing import Any


NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def svg_signature(svg: str) -> dict[str, Any]:
    path_tags = re.findall(r"<path\b[^>]*>", svg)
    values = [float(value) for tag in path_tags for value in NUMBER.findall(re.search(r' d="([^"]*)"', tag).group(1) if ' d="' in tag else "")]
    normalized = re.sub(r"\s+", " ", svg).strip()
    return {
        "sha256": hashlib.sha256(normalized.encode()).hexdigest(),
        "paths": len(path_tags),
        "visible_paths": svg.count('class="o"'),
        "hidden_paths": svg.count('class="h"'),
        "coordinate_span": round(max(values) - min(values), 3) if values else 0.0,
    }


def visual_regression(component_id: str, views: dict[str, str], baseline_root: Path) -> dict[str, Any]:
    baseline_root.mkdir(parents=True, exist_ok=True)
    current = {name: svg_signature(svg) for name, svg in views.items()}
    path = baseline_root / f"{component_id}.json"
    if not path.is_file():
        path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"passed": True, "status": "baseline_created", "views": current, "baseline_url": str(path)}
    baseline = json.loads(path.read_text(encoding="utf-8"))
    comparisons = {}
    for name, signature in current.items():
        expected = baseline.get(name, {})
        path_delta = abs(signature["paths"] - int(expected.get("paths", signature["paths"])))
        limit = max(2, math.ceil(int(expected.get("paths", 0)) * .03))
        comparisons[name] = {"passed": path_delta <= limit and signature["coordinate_span"] > 0, "path_delta": path_delta, "limit": limit}
    return {"passed": all(item["passed"] for item in comparisons.values()), "status": "compared", "comparisons": comparisons, "views": current, "baseline_url": str(path)}


def assembly_quality_score(report: dict[str, Any] | None, views: dict[str, str], regression: dict[str, Any]) -> dict[str, Any]:
    quality = (report or {}).get("quality", {})
    instances = (report or {}).get("instances", [])
    connected = sum(1 for item in instances if item.get("target") is not None)
    expected_connections = max(0, len(instances) - 1)
    breakdown = {
        "brep": 25 if not report or quality.get("valid_brep") else 0,
        "interference": 25 if not report or quality.get("interference_free") else 0,
        "port_connectivity": 15 if not report or connected == expected_connections else round(15 * connected / max(1, expected_connections), 2),
        "resolved_transforms": 10 if not report or all(len(item.get("transform", [])) == 4 for item in instances) else 0,
        "multiview_completeness": round(15 * len(set(views) & {"front", "top", "side", "isometric"}) / 4, 2),
        "visual_regression": 10 if regression.get("passed") else 0,
    }
    score = round(sum(breakdown.values()), 2)
    return {"score": score, "grade": "A" if score >= 90 else "B" if score >= 80 else "C" if score >= 70 else "D", "breakdown": breakdown,
            "review_required": score < 90 or not regression.get("passed"), "threshold": 90}


def reference_image_score(image_bytes: bytes, svg: str) -> dict[str, Any]:
    try:
        from PIL import Image, ImageFilter
    except ImportError as exc:
        raise RuntimeError("参考图评分需要 Pillow") from exc
    image = Image.open(io.BytesIO(image_bytes)).convert("L")
    image.thumbnail((1024, 1024))
    edges = image.filter(ImageFilter.FIND_EDGES)
    pixels = list(edges.getdata())
    active = [index for index, value in enumerate(pixels) if value >= 32]
    if not active:
        raise ValueError("参考图未检测到有效轮廓")
    width, height = image.size
    xs, ys = [index % width for index in active], [index // width for index in active]
    reference_aspect = max(xs) - min(xs) + 1
    reference_aspect /= max(1, max(ys) - min(ys) + 1)
    coordinates = [float(value) for tag in re.findall(r'<path\b[^>]* d="([^"]*)"', svg) for value in NUMBER.findall(tag)]
    generated_aspect = 1.0
    if coordinates:
        pairs = list(zip(coordinates[::2], coordinates[1::2]))
        if pairs:
            generated_aspect = (max(x for x, _ in pairs) - min(x for x, _ in pairs)) / max(1e-6, max(y for _, y in pairs) - min(y for _, y in pairs))
    aspect_score = max(0.0, 1.0 - abs(math.log(max(reference_aspect, 1e-6) / max(generated_aspect, 1e-6))))
    reference_density = len(active) / max(1, width * height)
    generated_density = min(1.0, svg.count("<path") / 250)
    density_score = max(0.0, 1.0 - abs(reference_density - generated_density) * 2)
    contour = round(aspect_score * 100, 2)
    features = round(density_score * 100, 2)
    return {"score": round(contour * .7 + features * .3, 2), "contour_score": contour, "key_feature_score": features,
            "metrics": {"reference_aspect": round(reference_aspect, 4), "generated_aspect": round(generated_aspect, 4), "reference_edge_density": round(reference_density, 6), "generated_path_density": round(generated_density, 6)}}
