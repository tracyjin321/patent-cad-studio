import html
import math
from typing import Any, Iterable


Point3 = tuple[float, float, float]
ORIGIN_X = 435.0
ORIGIN_Y = 335.0
ISO_COS = math.sqrt(3) / 2


def _svg(content: str, title: str) -> str:
    safe = html.escape(title)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 620" role="img" aria-label="{safe}轴侧图">
<defs><marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#667085"/></marker><style>.o{{fill:#fff;stroke:#17202a;stroke-width:2.25;stroke-linejoin:round;stroke-linecap:round}}.h{{fill:none;stroke:#667085;stroke-width:1.15;stroke-dasharray:7 5}}.d{{fill:none;stroke:#667085;stroke-width:1.1;marker-start:url(#arrow);marker-end:url(#arrow)}}.t{{font:14px sans-serif;fill:#344054}}.n{{font:13px sans-serif;fill:#7b2d8e}}</style></defs>
<rect width="900" height="620" fill="#fff"/><text x="36" y="40" class="t">{safe}</text><text x="864" y="40" class="n" text-anchor="end">轴侧图（等轴测）</text>{content}
<text x="36" y="590" class="t">轴测技术附图 · 比例示意 · 单位 mm</text></svg>'''


def _dimension(x1: float, y1: float, x2: float, y2: float, label: str) -> str:
    safe = html.escape(str(label))
    return f'<path class="d" d="M{x1} {y1}L{x2} {y2}"/><text class="t" x="{(x1+x2)/2}" y="{(y1+y2)/2-8}" text-anchor="middle">{safe}</text>'


def _project(point: Point3) -> tuple[float, float]:
    x, y, z = point
    return ORIGIN_X + (x - y) * ISO_COS, ORIGIN_Y + (x + y) * .5 - z


def _path(points: Iterable[Point3], css: str = "o", close: bool = False) -> str:
    projected = [_project(point) for point in points]
    if not projected:
        return ""
    data = "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in projected)
    return f'<path class="{css}" d="{data}{"Z" if close else ""}"/>'


def _circle_points(center: Point3, radius: float, plane: str = "yz", steps: int = 72) -> list[Point3]:
    cx, cy, cz = center
    points: list[Point3] = []
    for index in range(steps):
        angle = 2 * math.pi * index / steps
        a, b = radius * math.cos(angle), radius * math.sin(angle)
        if plane == "yz":
            points.append((cx, cy + a, cz + b))
        elif plane == "xy":
            points.append((cx + a, cy + b, cz))
        else:
            points.append((cx + a, cy, cz + b))
    return points


def _circle(center: Point3, radius: float, plane: str = "yz", css: str = "o", steps: int = 72) -> str:
    return _path(_circle_points(center, radius, plane, steps), css, True)


def _point_on_circle_x(x: float, radius: float, angle: float) -> Point3:
    return x, radius * math.cos(angle), radius * math.sin(angle)


def _cylinder_x(x0: float, x1: float, radius: float, inner: float | None = None) -> str:
    silhouette_angles = (-math.pi / 4, 3 * math.pi / 4)
    content = _circle((x0, 0, 0), radius)
    if inner:
        content += _circle((x0, 0, 0), inner, css="h")
    for angle in silhouette_angles:
        content += _path([_point_on_circle_x(x0, radius, angle), _point_on_circle_x(x1, radius, angle)])
    content += _circle((x1, 0, 0), radius)
    if inner:
        content += _circle((x1, 0, 0), inner)
    return content


def _cylinder_z(z0: float, z1: float, radius: float) -> str:
    content = _circle((0, 0, z0), radius, "xy")
    for angle in (-math.pi / 4, 3 * math.pi / 4):
        a, b = radius * math.cos(angle), radius * math.sin(angle)
        content += _path([(a, b, z0), (a, b, z1)])
    return content + _circle((0, 0, z1), radius, "xy")


def _axis(length: float = 700) -> str:
    return _path([(-length / 2, 0, 0), (length / 2, 0, 0)], "h")


def _front_circle(center_y: float, center_z: float, radius: float, css: str = "o") -> str:
    x, y = _project((0, center_y, center_z))
    return f'<circle class="{css}" cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}"/>'


def bearing(p: dict[str, Any]) -> str:
    outer = 178.0
    bore = max(62.0, min(112.0, outer * float(p["inner_diameter"]) / float(p["outer_diameter"])))
    width = max(62.0, min(118.0, float(p["width"]) * 3.5))
    x0, x1 = -width / 2, width / 2
    count = max(6, min(16, int(p["rolling_elements"])))
    pitch = (outer + bore) * .51
    ball_radius = max(10.0, min(18.0, (outer - bore) * .16))
    content = _cylinder_x(x0, x1, outer, bore)
    content += _circle((x1 + 1, 0, 0), outer * .81)
    content += _circle((x1 + 2, 0, 0), bore * 1.28)
    for index in range(count):
        angle = 2 * math.pi * index / count
        cy, cz = pitch * math.cos(angle), pitch * math.sin(angle)
        content += _front_circle(cy, cz, ball_radius)
    content += _circle((x1 + 4, 0, 0), bore * 1.12)
    content += _circle((x1 + 5, 0, 0), bore)
    content += _axis()
    content += _dimension(255, 545, 650, 545, f'⌀{p["outer_diameter"]} · B {p["width"]}')
    return _svg(content, "滚动轴承")


def flange(p: dict[str, Any]) -> str:
    outer = 178.0
    bore = max(55.0, min(105.0, outer * float(p["inner_diameter"]) / float(p["outer_diameter"])))
    thickness = max(52.0, min(105.0, float(p["thickness"]) * 3.2))
    x0, x1 = -thickness / 2, thickness / 2
    count = max(4, min(16, int(p["bolt_holes"])))
    content = _cylinder_x(x0, x1, outer, bore)
    pitch = outer * .70
    hole_radius = max(8.0, outer * .06)
    for index in range(count):
        angle = 2 * math.pi * index / count
        content += _circle((x1 + 2, pitch * math.cos(angle), pitch * math.sin(angle)), hole_radius)
    content += _circle((x1 + 3, 0, 0), pitch, css="h")
    content += _axis()
    content += _dimension(245, 545, 655, 545, f'⌀{p["outer_diameter"]} · {p["bolt_holes"]}孔')
    return _svg(content, "圆形法兰")


def valve(p: dict[str, Any]) -> str:
    content = _axis(760)
    content += _cylinder_x(-285, 285, 52, 30)
    content += _cylinder_x(-285, -250, 82, 31)
    content += _cylinder_x(250, 285, 82, 31)
    content += _cylinder_x(-105, 105, 108)
    content += _cylinder_z(70, 150, 38)
    content += _circle((0, 0, 150), 55, "xy")
    content += _cylinder_z(150, 225, 12)
    content += _circle((0, 0, 225), 92, "xy")
    content += _circle((0, 0, 225), 70, "xy")
    for angle in (0, math.pi / 2, math.pi, 3 * math.pi / 2):
        a, b = 80 * math.cos(angle), 80 * math.sin(angle)
        c, d = 12 * math.cos(angle), 12 * math.sin(angle)
        content += _path([(c, d, 225), (a, b, 225)])
    content += _dimension(205, 535, 690, 535, f'L {p["body_length"]} · DN {p["nominal_diameter"]}')
    return _svg(content, "截止阀")


def shaft(p: dict[str, Any]) -> str:
    steps = max(3, min(6, int(p["steps"])))
    bounds = [-295 + 590 * index / steps for index in range(steps + 1)]
    radii = [45 + 30 * math.sin(math.pi * (index + 1) / (steps + 1)) for index in range(steps)]
    content = _axis(730)
    for index, radius in enumerate(radii):
        content += _cylinder_x(bounds[index], bounds[index + 1], radius)
    key_start, key_end = bounds[steps // 2], bounds[min(steps, steps // 2 + 1)]
    key_y, key_z = -24.0, radii[steps // 2] * .78
    content += _path([(key_start + 10, key_y, key_z), (key_end - 10, key_y, key_z), (key_end - 10, key_y + 18, key_z), (key_start + 10, key_y + 18, key_z)], close=True)
    content += _dimension(170, 520, 705, 520, f'L {p["total_length"]} · ⌀max {p["max_diameter"]}')
    return _svg(content, "阶梯轴系")


def _gear_outline(x: float, teeth: int, outer: float, root: float, css: str = "o") -> str:
    points: list[Point3] = []
    for index in range(teeth * 2):
        radius = outer if index % 2 == 0 else root
        angle = 2 * math.pi * index / (teeth * 2)
        points.append((x, radius * math.cos(angle), radius * math.sin(angle)))
    return _path(points, css, True)


def gear(p: dict[str, Any]) -> str:
    teeth = max(10, min(40, int(p["teeth"])))
    outer, root = 178.0, 151.0
    depth = max(60.0, min(115.0, float(p["face_width"]) * 3.0))
    x0, x1 = -depth / 2, depth / 2
    bore = max(35.0, min(78.0, float(p["bore"]) * 1.55))
    content = _gear_outline(x0, teeth, outer, root)
    content += _circle((x0, 0, 0), bore, css="h")
    for angle in (-math.pi / 4, 3 * math.pi / 4):
        content += _path([_point_on_circle_x(x0, outer, angle), _point_on_circle_x(x1, outer, angle)])
    content += _gear_outline(x1, teeth, outer, root)
    content += _circle((x1, 0, 0), bore)
    content += _path([(x1 + 1, -11, bore), (x1 + 1, 11, bore), (x1 + 1, 11, bore + 30), (x1 + 1, -11, bore + 30)], close=True)
    content += _axis()
    content += _dimension(245, 548, 655, 548, f'm={p["module"]} · z={p["teeth"]}')
    return _svg(content, "直齿圆柱齿轮")


def screw(p: dict[str, Any]) -> str:
    x0, x1 = -300.0, 300.0
    radius = 48.0
    content = _axis(730)
    content += _cylinder_x(x0, x0 + 48, 32)
    content += _cylinder_x(x0 + 48, x1 - 48, radius)
    content += _cylinder_x(x1 - 48, x1, 32)
    turns = max(10, min(34, int(float(p["length"]) / max(1.0, float(p["lead"])))))
    for start in range(max(1, min(3, int(p["starts"])))):
        points: list[Point3] = []
        samples = turns * 18
        for index in range(samples + 1):
            ratio = index / samples
            angle = 2 * math.pi * (turns * ratio + start / max(1, int(p["starts"])))
            points.append((x0 + 48 + (x1 - x0 - 96) * ratio, radius * 1.06 * math.cos(angle), radius * 1.06 * math.sin(angle)))
        content += _path(points)
    content += _dimension(165, 500, 710, 500, f'L {p["length"]} · 导程 {p["lead"]}')
    return _svg(content, "精密丝杠")


def coupling(p: dict[str, Any]) -> str:
    flange_radius, hub_radius = 132.0, 78.0
    content = _axis(730)
    content += _cylinder_x(-245, -160, flange_radius, 38)
    content += _cylinder_x(-160, 160, hub_radius, 38)
    content += _cylinder_x(160, 245, flange_radius, 38)
    count = max(4, min(12, int(p["bolts"])))
    pitch = flange_radius * .72
    for index in range(count):
        angle = 2 * math.pi * index / count
        y, z = pitch * math.cos(angle), pitch * math.sin(angle)
        content += _circle((246, y, z), 10)
    content += _dimension(195, 530, 690, 530, f'L {p["length"]} · ⌀{p["outer_diameter"]}')
    return _svg(content, "法兰联轴器")


def seal(p: dict[str, Any]) -> str:
    outer = 172.0
    inner = max(72.0, min(122.0, outer * float(p["inner_diameter"]) / float(p["outer_diameter"])))
    width = max(58.0, min(105.0, float(p["width"]) * 5.0))
    x0, x1 = -width / 2, width / 2
    content = _cylinder_x(x0, x1, outer, inner)
    for index in range(max(1, min(3, int(p["lip_count"])))):
        lip = inner + 20 + index * 18
        content += _circle((x1 + 2 + index, 0, 0), min(outer - 8, lip))
    content += _axis()
    content += _dimension(245, 535, 655, 535, f'⌀{p["outer_diameter"]} / ⌀{p["inner_diameter"]} · B {p["width"]}')
    return _svg(content, "唇形密封件")


GENERATORS = {
    "bearing": bearing,
    "flange": flange,
    "valve": valve,
    "shaft": shaft,
    "gear": gear,
    "screw": screw,
    "coupling": coupling,
    "seal": seal,
}


def generate_svg(part_type: str, parameters: dict[str, Any]) -> str:
    return GENERATORS[part_type](parameters)
