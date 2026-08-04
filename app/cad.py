import html
import math
from typing import Any, Iterable


VIEW_DIRECTION = (1.0, -1.0, 1.0)
VIEW_X_DIRECTION = (1.0, 1.0, 0.0)


def _projector(view_direction=VIEW_DIRECTION, view_x_direction=VIEW_X_DIRECTION):
    from OCP.HLRAlgo import HLRAlgo_Projector
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    return HLRAlgo_Projector(
        gp_Ax2(
            gp_Pnt(0, 0, 0),
            gp_Dir(*view_direction),
            gp_Dir(*view_x_direction),
        )
    )


def _edge_points(compound: object) -> list[list[tuple[float, float]]]:
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GeomAbs import GeomAbs_BezierCurve, GeomAbs_BSplineCurve, GeomAbs_Circle, GeomAbs_Ellipse, GeomAbs_Line
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    if compound.IsNull():
        return []
    paths: list[list[tuple[float, float]]] = []
    explorer = TopExp_Explorer(compound, TopAbs_EDGE)
    while explorer.More():
        curve = BRepAdaptor_Curve(TopoDS.Edge_s(explorer.Current()))
        first, last = curve.FirstParameter(), curve.LastParameter()
        curve_type = curve.GetType()
        if not math.isfinite(first) or not math.isfinite(last) or first == last:
            explorer.Next()
            continue
        if curve_type == GeomAbs_Line:
            samples = 2
        elif curve_type in (GeomAbs_Circle, GeomAbs_Ellipse):
            samples = max(12, min(72, int(abs(last - first) * 12) + 1))
        elif curve_type in (GeomAbs_BezierCurve, GeomAbs_BSplineCurve):
            samples = 42
        else:
            samples = 28
        points: list[tuple[float, float]] = []
        for index in range(samples):
            parameter = first + (last - first) * index / (samples - 1)
            point = curve.Value(parameter)
            coordinates = (float(point.X()), float(point.Y()))
            if not points or math.dist(points[-1], coordinates) > 1e-7:
                points.append(coordinates)
        if len(points) >= 2:
            paths.append(points)
        explorer.Next()
    return paths


def _path_key(points: list[tuple[float, float]]) -> tuple[tuple[float, float], ...]:
    indexes = sorted({0, len(points) // 4, len(points) // 2, 3 * len(points) // 4, len(points) - 1})
    key = tuple((round(points[index][0], 3), round(points[index][1], 3)) for index in indexes)
    reverse = tuple(reversed(key))
    return min(key, reverse)


def _unique_paths(groups: Iterable[list[list[tuple[float, float]]]]) -> list[list[tuple[float, float]]]:
    unique: dict[tuple[tuple[float, float], ...], list[tuple[float, float]]] = {}
    for paths in groups:
        for points in paths:
            unique.setdefault(_path_key(points), points)
    return list(unique.values())


def _project_edges(shape: object, view_direction=VIEW_DIRECTION, view_x_direction=VIEW_X_DIRECTION) -> tuple[list[list[tuple[float, float]]], list[list[tuple[float, float]]], object]:
    from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape

    projector = _projector(view_direction, view_x_direction)
    algorithm = HLRBRep_Algo()
    algorithm.Add(shape)
    algorithm.Projector(projector)
    algorithm.Update()
    algorithm.Hide()
    result = HLRBRep_HLRToShape(algorithm)
    visible = _unique_paths([
        _edge_points(result.VCompound()),
        _edge_points(result.OutLineVCompound()),
    ])
    hidden = _unique_paths([
        _edge_points(result.HCompound()),
        _edge_points(result.OutLineHCompound()),
    ])
    visible_keys = {_path_key(points) for points in visible}
    hidden = [points for points in hidden if _path_key(points) not in visible_keys]
    if not visible:
        raise RuntimeError("OpenCascade hidden-line projection returned no visible edges")
    return visible, hidden, projector


def _edge_count(shape: object) -> int:
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer

    count = 0
    explorer = TopExp_Explorer(shape, TopAbs_EDGE)
    while explorer.More():
        count += 1
        explorer.Next()
    return count


def _project_poly_edges(shape: object, view_direction=VIEW_DIRECTION, view_x_direction=VIEW_X_DIRECTION) -> tuple[list[list[tuple[float, float]]], list[list[tuple[float, float]]], object]:
    """Stable HLR for very complex B-Reps using the preview mesh tolerance."""
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.HLRBRep import HLRBRep_PolyAlgo, HLRBRep_PolyHLRToShape

    projector = _projector(view_direction, view_x_direction)
    BRepMesh_IncrementalMesh(shape, 0.35, False, 0.22, True)
    algorithm = HLRBRep_PolyAlgo()
    algorithm.Load(shape)
    algorithm.Projector(projector)
    algorithm.Update()
    result = HLRBRep_PolyHLRToShape()
    result.Update(algorithm)
    visible = _unique_paths([
        _edge_points(result.VCompound()),
        _edge_points(result.OutLineVCompound()),
    ])
    hidden = _unique_paths([
        _edge_points(result.HCompound()),
        _edge_points(result.OutLineHCompound()),
    ])
    visible_keys = {_path_key(points) for points in visible}
    hidden = [points for points in hidden if _path_key(points) not in visible_keys]
    if not visible:
        raise RuntimeError("OpenCascade polygonal hidden-line projection returned no visible edges")
    return visible, hidden, projector


def _fit_transform(paths: Iterable[list[tuple[float, float]]]):
    points = [point for path in paths for point in path]
    min_x = min(point[0] for point in points)
    max_x = max(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_y = max(point[1] for point in points)
    width = max(max_x - min_x, 1e-6)
    height = max(max_y - min_y, 1e-6)
    scale = min(600 / width, 700 / height)
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2

    def transform(point: tuple[float, float]) -> tuple[float, float]:
        return 397 + (point[0] - center_x) * scale, 500 - (point[1] - center_y) * scale

    return transform, scale


def _svg_path(points: list[tuple[float, float]], transform, css: str) -> str:
    projected = [transform(point) for point in points]
    data = "M" + "L".join(f"{x:.2f} {y:.2f}" for x, y in projected)
    return f'<path class="{css}" d="{data}"/>'


def _long_screw_svg(title: str, parameters: dict[str, Any]) -> str:
    """Draw a stable engineering projection for long, highly periodic screws.

    The 3D model and STEP still use the exact B-Rep.  OCCT's Exact/Poly HLR can
    segfault while classifying hundreds of intersecting helical edges, so the
    patent figure is constructed from the same nominal dimensions instead.
    """
    length = max(1.0, float(parameters.get("length", 1)))
    diameter = max(1.0, float(parameters.get("diameter", 1)))
    lead = max(0.1, float(parameters.get("lead", diameter / 4)))
    starts = max(1, int(parameters.get("starts", 1)))
    left, right = 100.0, 694.0
    center_y = 520.0
    body_height = min(180.0, max(42.0, 630.0 * diameter / length))
    top, bottom = center_y - body_height / 2, center_y + body_height / 2
    journal_length = min(length * .12, max(diameter * 1.35, length * .08))
    journal_px = 630.0 * journal_length / length
    journal_height = body_height * .64
    jt, jb = center_y - journal_height / 2, center_y + journal_height / 2
    thread_left, thread_right = left + journal_px, right - journal_px
    pitch_px = max(5.0, 630.0 * lead / length)

    paths = [
        f'<path class="o" d="M{thread_left:.2f} {top:.2f}H{thread_right:.2f}V{bottom:.2f}H{thread_left:.2f}Z"/>',
        f'<path class="o" d="M{left:.2f} {jt:.2f}H{thread_left:.2f}V{top:.2f}M{left:.2f} {jb:.2f}H{thread_left:.2f}V{bottom:.2f}"/>',
        f'<path class="o" d="M{thread_right:.2f} {top:.2f}V{jt:.2f}H{right:.2f}M{thread_right:.2f} {bottom:.2f}V{jb:.2f}H{right:.2f}"/>',
        f'<path class="o" d="M{left:.2f} {jt:.2f}V{jb:.2f}M{right:.2f} {jt:.2f}V{jb:.2f}"/>',
    ]
    # Rising strokes from left to right are the conventional visible cue for a
    # right-hand thread.  Multiple starts are represented by phase offsets.
    for start in range(starts):
        x = thread_left - start * pitch_px / starts
        while x <= thread_right:
            x0 = max(thread_left, x)
            x1 = min(thread_right, x + pitch_px * .72)
            if x1 > x0:
                fraction0 = (x0 - x) / (pitch_px * .72)
                fraction1 = (x1 - x) / (pitch_px * .72)
                y0 = bottom - body_height * .82 * fraction0
                y1 = bottom - body_height * .82 * fraction1
                paths.append(f'<path class="o" d="M{x0:.2f} {y0:.2f}L{x1:.2f} {y1:.2f}"/>')
            x += pitch_px
    safe_title = html.escape(title)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 794 1123" role="img" aria-label="{safe_title}主视图">
<defs><style>.o{{fill:none;stroke:#000;stroke-width:2.15;stroke-linejoin:round;stroke-linecap:round}}.h{{fill:none;stroke:#000;stroke-width:1.05;stroke-dasharray:6 5}}.f{{font:16px "SimSun","Songti SC",serif;fill:#000}}.p{{font:14px "SimSun","Songti SC",serif;fill:#000}}</style></defs>
<rect width="794" height="1123" fill="#fff"/>{''.join(paths)}<text class="f" x="397" y="660" text-anchor="middle">图1</text><text class="p" x="397" y="1080" text-anchor="middle">1</text></svg>'''


def generate_svg(shape: object, title: str, part_type: str, parameters: dict[str, Any]) -> str:
    # Exact HLR in OCCT 7.x can segfault on long swept helices. PolyHLR still
    # projects the same B-Rep and preserves the established preview tolerance.
    # Fused valve bodies contain sphere/cylinder/torus intersection curves that
    # also trigger native Exact-HLR failures despite a modest edge count.
    if part_type == "screw" and float(parameters.get("length", 0)) >= 400:
        return _long_screw_svg(title, parameters)
    return generate_view_svg(shape, title, part_type, "isometric", parameters)


VIEW_CONFIGS = {
    "front": ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0)),
    "top": ((0.0, 0.0, 1.0), (1.0, 0.0, 0.0)),
    "side": ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    "isometric": (VIEW_DIRECTION, VIEW_X_DIRECTION),
}


def generate_view_svg(shape: object, title: str, part_type: str, view: str, parameters: dict[str, Any] | None = None) -> str:
    if view not in VIEW_CONFIGS:
        raise ValueError(f"不支持的视图: {view}")
    direction, x_direction = VIEW_CONFIGS[view]
    projector = _project_poly_edges if part_type in {"valve", "rocket"} or _edge_count(shape) > 400 else _project_edges
    # Keep the original one-argument isometric projector contract so callers
    # and safety tests can replace the HLR implementation independently.
    if view == "isometric":
        visible, hidden, _ = projector(shape)
    else:
        visible, hidden, _ = projector(shape, direction, x_direction)
    transform, scale = _fit_transform([*visible, *hidden])
    visible_svg = "".join(_svg_path(points, transform, "o") for points in visible)
    hidden_svg = "".join(_svg_path(points, transform, "h") for points in hidden)
    all_screen = [transform(point) for path in [*visible, *hidden] for point in path]
    figure_label_y = min(1035.0, max(point[1] for point in all_screen) + 42.0)
    safe_title = html.escape(title)
    labels = {"front": "主视图", "top": "俯视图", "side": "侧视图", "isometric": "轴测图"}
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 794 1123" role="img" aria-label="{safe_title}{labels[view]}">
<defs><style>.o{{fill:none;stroke:#000;stroke-width:2.15;stroke-linejoin:round;stroke-linecap:round}}.h{{fill:none;stroke:#000;stroke-width:1.05;stroke-dasharray:6 5;stroke-linejoin:round;stroke-linecap:round}}.f{{font:16px "SimSun","Songti SC",serif;fill:#000}}.p{{font:14px "SimSun","Songti SC",serif;fill:#000}}</style></defs>
<rect width="794" height="1123" fill="#fff"/>{hidden_svg}{visible_svg}<text class="f" x="397" y="{figure_label_y:.2f}" text-anchor="middle">图1</text><text class="p" x="397" y="1080" text-anchor="middle">1</text></svg>'''


def generate_multiview_svgs(shape: object, title: str, part_type: str, parameters: dict[str, Any]) -> dict[str, str]:
    if part_type == "screw" and float(parameters.get("length", 0)) >= 400:
        stable = _long_screw_svg(title, parameters)
        return {view: stable for view in VIEW_CONFIGS}
    # The isometric patent view uses exact/poly HLR. Orthographic companion
    # views use the same adaptive OCCT triangulation, avoiding four expensive
    # hidden-line classifications for complex assemblies.
    from .model3d import _shape_mesh

    mesh = _shape_mesh(shape)
    result = {"isometric": generate_view_svg(shape, title, part_type, "isometric", parameters)}
    for view in ("front", "top", "side"):
        result[view] = _mesh_view_svg(mesh, title, view)
    return result


def _mesh_view_svg(mesh: dict[str, Any], title: str, view: str) -> str:
    values = mesh["positions"]
    points = [tuple(values[index:index + 3]) for index in range(0, len(values), 3)]
    projectors = {
        "front": lambda point: (point[0], point[2]),
        "top": lambda point: (point[0], point[1]),
        "side": lambda point: (point[1], point[2]),
    }
    project = projectors[view]
    edges: dict[tuple[tuple[float, float], tuple[float, float]], tuple[tuple[float, float], tuple[float, float]]] = {}
    indices = mesh["indices"]
    for offset in range(0, len(indices), 3):
        triangle = indices[offset:offset + 3]
        for left, right in ((triangle[0], triangle[1]), (triangle[1], triangle[2]), (triangle[2], triangle[0])):
            a, b = project(points[left]), project(points[right])
            key = tuple(sorted(((round(a[0], 3), round(a[1], 3)), (round(b[0], 3), round(b[1], 3)))))
            if key[0] != key[1]: edges.setdefault(key, (a, b))
    lines = list(edges.values())
    if len(lines) > 3000:
        stride = math.ceil(len(lines) / 3000)
        lines = lines[::stride]
    paths = [[a, b] for a, b in lines]
    transform, _ = _fit_transform(paths)
    rendered = "".join(_svg_path(path, transform, "o") for path in paths)
    safe_title = html.escape(title)
    label = {"front": "主视图", "top": "俯视图", "side": "侧视图"}[view]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 794 1123" role="img" aria-label="{safe_title}{label}"><defs><style>.o{{fill:none;stroke:#000;stroke-width:1.45;stroke-linejoin:round;stroke-linecap:round}}.f{{font:16px "SimSun","Songti SC",serif;fill:#000}}.p{{font:14px "SimSun","Songti SC",serif;fill:#000}}</style></defs><rect width="794" height="1123" fill="#fff"/>{rendered}<text class="f" x="397" y="1040" text-anchor="middle">图1</text><text class="p" x="397" y="1080" text-anchor="middle">1</text></svg>'''
