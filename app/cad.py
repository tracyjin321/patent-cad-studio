import html
import math
from typing import Any, Iterable


VIEW_DIRECTION = (1.0, -1.0, 1.0)
VIEW_X_DIRECTION = (1.0, 1.0, 0.0)
AXES = {
    "bearing": "z",
    "flange": "z",
    "valve": "x",
    "shaft": "x",
    "gear": "z",
    "screw": "x",
    "coupling": "z",
    "seal": "z",
}


def _projector():
    from OCP.HLRAlgo import HLRAlgo_Projector
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    return HLRAlgo_Projector(
        gp_Ax2(
            gp_Pnt(0, 0, 0),
            gp_Dir(*VIEW_DIRECTION),
            gp_Dir(*VIEW_X_DIRECTION),
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


def _project_edges(shape: object) -> tuple[list[list[tuple[float, float]]], list[list[tuple[float, float]]], object]:
    from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape

    projector = _projector()
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


def _fit_transform(paths: Iterable[list[tuple[float, float]]]):
    points = [point for path in paths for point in path]
    min_x = min(point[0] for point in points)
    max_x = max(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_y = max(point[1] for point in points)
    width = max(max_x - min_x, 1e-6)
    height = max(max_y - min_y, 1e-6)
    scale = min(620 / width, 375 / height)
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2

    def transform(point: tuple[float, float]) -> tuple[float, float]:
        return 450 + (point[0] - center_x) * scale, 286 - (point[1] - center_y) * scale

    return transform, scale


def _svg_path(points: list[tuple[float, float]], transform, css: str) -> str:
    projected = [transform(point) for point in points]
    data = "M" + "L".join(f"{x:.2f} {y:.2f}" for x, y in projected)
    return f'<path class="{css}" d="{data}"/>'


def _dimension_label(part_type: str, p: dict[str, Any]) -> str:
    if part_type == "bearing":
        return f'⌀{p["outer_diameter"]} · B {p["width"]}'
    if part_type == "flange":
        return f'⌀{p["outer_diameter"]} · {p["bolt_holes"]}孔 · T {p["thickness"]}'
    if part_type == "valve":
        return f'L {p["body_length"]} · DN {p["nominal_diameter"]}'
    if part_type == "shaft":
        return f'L {p["total_length"]} · ⌀max {p["max_diameter"]}'
    if part_type == "gear":
        return f'm={p["module"]} · z={p["teeth"]} · B {p["face_width"]}'
    if part_type == "screw":
        return f'L {p["length"]} · 导程 {p["lead"]}'
    if part_type == "coupling":
        return f'L {p["length"]} · ⌀{p["outer_diameter"]}'
    return f'⌀{p["outer_diameter"]} / ⌀{p["inner_diameter"]} · B {p["width"]}'


def _centerline(projector: object, part_type: str, transform, scale: float) -> str:
    from OCP.gp import gp_Pnt

    direction = {"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1)}[AXES[part_type]]
    origin = projector.Project(gp_Pnt(0, 0, 0))
    endpoint = projector.Project(gp_Pnt(*direction))
    start_screen = transform((float(origin[0]), float(origin[1])))
    end_screen = transform((float(endpoint[0]), float(endpoint[1])))
    dx, dy = end_screen[0] - start_screen[0], end_screen[1] - start_screen[1]
    length = max(math.hypot(dx, dy), scale * .5)
    dx, dy = dx / length, dy / length
    half = 350.0
    x1, y1 = start_screen[0] - dx * half, start_screen[1] - dy * half
    x2, y2 = start_screen[0] + dx * half, start_screen[1] + dy * half
    return f'<path class="c" d="M{x1:.2f} {y1:.2f}L{x2:.2f} {y2:.2f}"/>'


def generate_svg(shape: object, title: str, part_type: str, parameters: dict[str, Any]) -> str:
    visible, hidden, projector = _project_edges(shape)
    transform, scale = _fit_transform([*visible, *hidden])
    visible_svg = "".join(_svg_path(points, transform, "o") for points in visible)
    hidden_svg = "".join(_svg_path(points, transform, "h") for points in hidden)
    all_screen = [transform(point) for path in [*visible, *hidden] for point in path]
    min_x = max(95.0, min(point[0] for point in all_screen))
    max_x = min(805.0, max(point[0] for point in all_screen))
    label = html.escape(_dimension_label(part_type, parameters))
    safe_title = html.escape(title)
    centerline = _centerline(projector, part_type, transform, scale)
    dimension = f'<path class="d" d="M{min_x:.2f} 525L{max_x:.2f} 525"/><text class="t" x="{(min_x + max_x) / 2:.2f}" y="513" text-anchor="middle">{label}</text>'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 620" role="img" aria-label="{safe_title}轴侧图">
<defs><marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#667085"/></marker><style>.o{{fill:none;stroke:#17202a;stroke-width:2.15;stroke-linejoin:round;stroke-linecap:round}}.h{{fill:none;stroke:#98a2b3;stroke-width:1.05;stroke-dasharray:6 5}}.c{{fill:none;stroke:#667085;stroke-width:1.1;stroke-dasharray:11 4 2 4}}.d{{fill:none;stroke:#667085;stroke-width:1.1;marker-start:url(#arrow);marker-end:url(#arrow)}}.t{{font:14px sans-serif;fill:#344054}}.n{{font:13px sans-serif;fill:#7b2d8e}}</style></defs>
<rect width="900" height="620" fill="#fff"/><text x="36" y="40" class="t">{safe_title}</text><text x="864" y="40" class="n" text-anchor="end">轴侧图（实体投影）</text>{hidden_svg}{visible_svg}{centerline}{dimension}
<text x="36" y="590" class="t">同源技术附图 · OpenCascade HLR · 单位 mm</text></svg>'''
