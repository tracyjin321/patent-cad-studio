"""Deterministic Falcon 9 Block 5 B-Rep primitives and assembly rules.

The model intentionally stays on the project's existing OpenCascade pipeline:
simple analytic solids are composed into independently addressable subassemblies,
then collected into one STEP-compatible compound.  Coordinates are millimetres;
the lowest engine-nozzle plane is Z=0 and the vehicle axis is +Z.
"""

from __future__ import annotations

import math
from typing import Any


FALCON9_DEFAULTS: dict[str, float | int] = {
    "total_height": 70000.0,
    "body_diameter": 3660.0,
    "fairing_diameter": 5200.0,
    "fairing_height": 13100.0,
    "engine_count": 9,
    "engine_nozzle_diameter": 920.0,
    "grid_fin_count": 4,
    "landing_leg_count": 4,
    "ring_count": 4,
}


def build_falcon9_components(parameters: dict[str, Any]) -> dict[str, object]:
    """Build named Falcon 9 subassemblies using stable analytic primitives."""
    from OCP.BRep import BRep_Builder
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCone, BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax1, gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
    from OCP.TopoDS import TopoDS_Compound

    p = {**FALCON9_DEFAULTS, **parameters}
    total = float(p["total_height"])
    body_r = float(p["body_diameter"]) / 2
    fairing_r = float(p["fairing_diameter"]) / 2
    fairing_h = float(p["fairing_height"])
    nozzle_r = float(p["engine_nozzle_diameter"]) / 2

    # Fixed assembly stations.  Engine bells occupy the first 2.5 m; the
    # 13.1 m fairing terminates at the official 70 m vehicle envelope.
    engine_h = 2500.0
    first_top = 45500.0
    interstage_top = 50000.0
    fairing_base = total - fairing_h
    second_top = fairing_base

    def cylinder(radius: float, height: float, z0: float, x: float = 0, y: float = 0):
        return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, z0), gp_Dir(0, 0, 1)), radius, height).Shape()

    def cone(r0: float, r1: float, height: float, z0: float, x: float = 0, y: float = 0):
        return BRepPrimAPI_MakeCone(gp_Ax2(gp_Pnt(x, y, z0), gp_Dir(0, 0, 1)), r0, r1, height).Shape()

    def compound(shapes: list[object]):
        result, builder = TopoDS_Compound(), BRep_Builder()
        builder.MakeCompound(result)
        for shape in shapes:
            builder.Add(result, shape)
        return result

    def rotate_z(shape: object, angle: float):
        transform = gp_Trsf()
        transform.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), angle)
        return BRepBuilderAPI_Transform(shape, transform, True).Shape()

    def beam_between(start: tuple[float, float, float], end: tuple[float, float, float], radius: float):
        vector = gp_Vec(gp_Pnt(*start), gp_Pnt(*end))
        length = vector.Magnitude()
        return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(*start), gp_Dir(vector)), radius, length).Shape()

    # Nine Merlin 1D sea-level bells: eight around one centre engine.
    engines: list[object] = []
    engine_centres = [(0.0, 0.0)] + [
        (1180.0 * math.cos(index * math.pi / 4), 1180.0 * math.sin(index * math.pi / 4))
        for index in range(8)
    ]
    for x, y in engine_centres[: int(p["engine_count"])]:
        engines.extend([
            cone(nozzle_r, nozzle_r * .38, engine_h * .82, 0, x, y),
            cylinder(nozzle_r * .4, engine_h * .18, engine_h * .82, x, y),
        ])

    # First stage, octaweb skirt, and external reinforcement rings.
    first_stage: list[object] = [
        cylinder(body_r, first_top - engine_h, engine_h),
        cone(body_r * 1.04, body_r, 700.0, engine_h),
    ]
    for index in range(int(p["ring_count"])):
        z = engine_h + 7000.0 + index * 8500.0
        first_stage.append(cylinder(body_r + 5.0, 50.0, z))

    # Folded landing legs: two longitudinal spars and diagonal braces per leg.
    legs: list[object] = []
    for index in range(int(p["landing_leg_count"])):
        angle = index * math.pi / 2
        radial = (math.cos(angle), math.sin(angle))
        tangent = (-math.sin(angle), math.cos(angle))
        lower = (radial[0] * (body_r + 95), radial[1] * (body_r + 95), 3600.0)
        upper = (radial[0] * (body_r + 70), radial[1] * (body_r + 70), 7600.0)
        for side in (-1, 1):
            offset = 115.0 * side
            a = (lower[0] + tangent[0] * offset, lower[1] + tangent[1] * offset, lower[2])
            b = (upper[0] + tangent[0] * offset, upper[1] + tangent[1] * offset, upper[2])
            legs.append(beam_between(a, b, 55.0))
        legs.extend([
            beam_between(lower, upper, 42.0),
            beam_between((lower[0] + tangent[0] * 115, lower[1] + tangent[1] * 115, lower[2]),
                         (upper[0] - tangent[0] * 115, upper[1] - tangent[1] * 115, upper[2]), 30.0),
        ])

    # Four grid fins with a visible frame and orthogonal lattice.
    grid_fins: list[object] = []
    fin_z, fin_span, fin_height, fin_t = 43800.0, 1800.0, 1450.0, 80.0
    for index in range(int(p["grid_fin_count"])):
        local: list[object] = []
        x0 = body_r - 30.0
        local.extend([
            BRepPrimAPI_MakeBox(gp_Pnt(x0, -fin_t / 2, fin_z), fin_span, fin_t, 90.0).Shape(),
            BRepPrimAPI_MakeBox(gp_Pnt(x0, -fin_t / 2, fin_z + fin_height - 90), fin_span, fin_t, 90.0).Shape(),
            BRepPrimAPI_MakeBox(gp_Pnt(x0, -fin_t / 2, fin_z), 90.0, fin_t, fin_height).Shape(),
            BRepPrimAPI_MakeBox(gp_Pnt(x0 + fin_span - 90, -fin_t / 2, fin_z), 90.0, fin_t, fin_height).Shape(),
        ])
        for slat in range(1, 6):
            local.append(BRepPrimAPI_MakeBox(
                gp_Pnt(x0 + slat * fin_span / 6 - 18, -fin_t / 2, fin_z + 80),
                36.0, fin_t, fin_height - 160,
            ).Shape())
        for slat in range(1, 5):
            local.append(BRepPrimAPI_MakeBox(
                gp_Pnt(x0 + 80, -fin_t / 2, fin_z + slat * fin_height / 5 - 18),
                fin_span - 160, fin_t, 36.0,
            ).Shape())
        grid_fins.append(rotate_z(compound(local), index * math.pi / 2))

    interstage: list[object] = [cylinder(body_r, interstage_top - first_top, first_top)]
    # Four trapezoidal separation-actuator fairings represented by tapered pods.
    for index in range(4):
        pod = cone(210.0, 120.0, 900.0, 47200.0, body_r + 70.0, 0.0)
        interstage.append(rotate_z(pod, index * math.pi / 2))

    second_stage: list[object] = [cylinder(body_r, second_top - interstage_top, interstage_top)]
    # Vacuum nozzle sits inside the interstage and opens downward.
    second_stage.extend([
        cone(1350.0, 260.0, 4000.0, interstage_top - 4000.0),
        cylinder(120.0, second_top - interstage_top - 700.0, interstage_top + 350.0, body_r + 135.0, 0.0),
    ])

    # 3.66 m to 5.2 m adapter plus a continuous B-spline von Karman ogive.
    fairing: list[object] = [cone(body_r, fairing_r, 3000.0, fairing_base)]
    ogive_base = fairing_base + 3000.0
    ogive_height = total - ogive_base
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeWire
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeRevol
    from OCP.GeomAPI import GeomAPI_PointsToBSpline
    from OCP.TColgp import TColgp_Array1OfPnt

    samples = 25
    points = TColgp_Array1OfPnt(1, samples)
    for index in range(samples):
        u = index / (samples - 1)
        theta = math.pi * (1 - u)
        radius = fairing_r / math.sqrt(math.pi) * math.sqrt(max(0.0, theta - math.sin(2 * theta) / 2))
        points.SetValue(index + 1, gp_Pnt(radius, 0.0, ogive_base + u * ogive_height))
    meridian = BRepBuilderAPI_MakeEdge(GeomAPI_PointsToBSpline(points).Curve()).Edge()
    top_axis = gp_Pnt(0.0, 0.0, total)
    bottom_axis = gp_Pnt(0.0, 0.0, ogive_base)
    wire_builder = BRepBuilderAPI_MakeWire()
    wire_builder.Add(meridian)
    wire_builder.Add(BRepBuilderAPI_MakeEdge(top_axis, bottom_axis).Edge())
    wire_builder.Add(BRepBuilderAPI_MakeEdge(bottom_axis, gp_Pnt(fairing_r, 0.0, ogive_base)).Edge())
    profile = BRepBuilderAPI_MakeFace(wire_builder.Wire()).Face()
    fairing.append(BRepPrimAPI_MakeRevol(profile, gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 2 * math.pi, True).Shape())
    # Longitudinal clam-shell seam rails make the split topology legible.
    seam_w = 20.0
    fairing.extend([
        BRepPrimAPI_MakeBox(gp_Pnt(-seam_w / 2, fairing_r - 14.0, fairing_base), seam_w, 28.0, 3000.0).Shape(),
        BRepPrimAPI_MakeBox(gp_Pnt(-seam_w / 2, -fairing_r - 14.0, fairing_base), seam_w, 28.0, 3000.0).Shape(),
    ])

    return {
        "first_stage": compound([*engines, *first_stage, *legs]),
        "grid_fins": compound(grid_fins),
        "interstage": compound(interstage),
        "second_stage": compound(second_stage),
        "payload_fairing": compound(fairing),
    }


def build_falcon9_shape(parameters: dict[str, Any]):
    """Return the full vehicle as one STEP-exportable compound assembly."""
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound

    result, builder = TopoDS_Compound(), BRep_Builder()
    builder.MakeCompound(result)
    for shape in build_falcon9_components(parameters).values():
        builder.Add(result, shape)
    return result
