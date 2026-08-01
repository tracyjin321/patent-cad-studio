import html
import math
from typing import Any, Iterable


VIEW_DIRECTION = (1.0, -1.0, 1.0)
VIEW_X_DIRECTION = (1.0, 1.0, 0.0)


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


def generate_svg(shape: object, title: str, part_type: str, parameters: dict[str, Any]) -> str:
    visible, hidden, _ = _project_edges(shape)
    transform, scale = _fit_transform([*visible, *hidden])
    visible_svg = "".join(_svg_path(points, transform, "o") for points in visible)
    hidden_svg = "".join(_svg_path(points, transform, "h") for points in hidden)
    all_screen = [transform(point) for path in [*visible, *hidden] for point in path]
    figure_label_y = min(1035.0, max(point[1] for point in all_screen) + 42.0)
    safe_title = html.escape(title)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 794 1123" role="img" aria-label="{safe_title}轴侧图">
<defs><style>.o{{fill:none;stroke:#000;stroke-width:2.15;stroke-linejoin:round;stroke-linecap:round}}.h{{fill:none;stroke:#000;stroke-width:1.05;stroke-dasharray:6 5;stroke-linejoin:round;stroke-linecap:round}}.f{{font:16px "SimSun","Songti SC",serif;fill:#000}}</style></defs>
<rect width="794" height="1123" fill="#fff"/>{hidden_svg}{visible_svg}<text class="f" x="397" y="{figure_label_y:.2f}" text-anchor="middle">图1</text></svg>'''
