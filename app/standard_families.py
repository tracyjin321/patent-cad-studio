"""Allowlisted parametric families for frequently requested standard components."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .component_spec import step_to_spec, write_shape_step


FAMILIES = {
    "iso4017-hex-bolt": {"label": "ISO 4017 六角头螺栓", "standard": "ISO 4017 / GB/T 5783", "type": "fastener", "parameters": {"diameter_mm": [2, 12], "length_mm": [4, 120]}},
    "iso4032-hex-nut": {"label": "ISO 4032 六角螺母", "standard": "ISO 4032 / GB/T 6170", "type": "nut", "parameters": {"diameter_mm": [2, 12]}},
    "iso7089-flat-washer": {"label": "ISO 7089 平垫圈", "standard": "ISO 7089 / GB/T 97.1", "type": "fastener", "parameters": {"diameter_mm": [2, 12]}},
    "deep-groove-60xx": {"label": "6000–6208 深沟球轴承", "standard": "GB/T 276", "type": "bearing", "parameters": {"bore_mm": [8, 40], "outer_mm": [22, 80], "width_mm": [7, 18]}},
    "nema-motor": {"label": "NEMA 步进电机", "standard": "NEMA ICS 16", "type": "actuator", "parameters": {"frame": [17, 34], "body_length_mm": [20, 80]}},
}


def family_shape(family_id: str, parameters: dict[str, Any]):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Vec
    from OCP.GC import GC_MakeCircle
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeFace

    diameter = float(parameters.get("diameter_mm", 3))
    if family_id == "iso4017-hex-bolt":
        length = float(parameters.get("length_mm", 10))
        shaft = BRepPrimAPI_MakeCylinder(diameter / 2, length).Shape()
        radius = diameter * .92
        points = [gp_Pnt(radius * __import__("math").cos(i * __import__("math").pi / 3), radius * __import__("math").sin(i * __import__("math").pi / 3), length) for i in range(6)]
        wire = BRepBuilderAPI_MakeWire()
        for i in range(6): wire.Add(BRepBuilderAPI_MakeEdge(points[i], points[(i + 1) % 6]).Edge())
        head = BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(wire.Wire()).Face(), gp_Vec(0, 0, diameter * .65)).Shape()
        from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
        return BRepAlgoAPI_Fuse(shaft, head).Shape()
    if family_id == "iso4032-hex-nut":
        outer = family_shape("iso4017-hex-bolt", {"diameter_mm": diameter, "length_mm": .001})
        hole = BRepPrimAPI_MakeCylinder(diameter / 2, diameter).Shape()
        return BRepAlgoAPI_Cut(outer, hole).Shape()
    if family_id == "iso7089-flat-washer":
        outer = BRepPrimAPI_MakeCylinder(diameter, diameter * .18).Shape()
        return BRepAlgoAPI_Cut(outer, BRepPrimAPI_MakeCylinder(diameter * .53, diameter * .18).Shape()).Shape()
    if family_id == "deep-groove-60xx":
        outer, bore, width = float(parameters.get("outer_mm", 22)), float(parameters.get("bore_mm", 8)), float(parameters.get("width_mm", 7))
        return BRepAlgoAPI_Cut(BRepPrimAPI_MakeCylinder(outer / 2, width).Shape(), BRepPrimAPI_MakeCylinder(bore / 2, width).Shape()).Shape()
    if family_id == "nema-motor":
        frame, length = float(parameters.get("frame", 17)), float(parameters.get("body_length_mm", 34))
        side = {17: 42.3, 23: 56.4, 34: 86}.get(int(frame), frame * 2.5)
        body = BRepPrimAPI_MakeBox(gp_Pnt(-side / 2, -side / 2, 0), side, side, length).Shape()
        shaft = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, length), gp_Dir(0, 0, 1)), max(2.5, side * .055), side * .35).Shape()
        from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
        return BRepAlgoAPI_Fuse(body, shaft).Shape()
    raise KeyError(family_id)


def materialize_family(family_id: str, parameters: dict[str, Any], output_root: Path) -> dict[str, Any]:
    if family_id not in FAMILIES:
        raise KeyError(family_id)
    normalized = {key: float(value) for key, value in sorted(parameters.items())}
    import hashlib, json
    fingerprint = hashlib.sha256(json.dumps({"family": family_id, "parameters": normalized}, sort_keys=True).encode()).hexdigest()
    component_id = f"family-{family_id}-{fingerprint[:12]}"
    directory = output_root / component_id
    spec_path = directory / "component.yaml"
    if not spec_path.is_file():
        directory.mkdir(parents=True, exist_ok=True)
        step = directory / "reference.step"
        write_shape_step(family_shape(family_id, normalized), step)
        family = FAMILIES[family_id]
        spec = step_to_spec(step, spec_path, identity={"id": component_id, "name": family["label"], "type": family["type"], "subtype": family_id, "family": family_id}, copy_reference=False)
        spec["identity"].update({"standard": family["standard"], "status": "reviewed", "tags": [family_id, "parametric-family"]})
        spec["parameters"] = [{"name": key, "type": "number", "unit": "mm", "required": True, "default": value} for key, value in normalized.items()]
        spec["provenance"].update({"source_type": "standard_parametric_family", "family_id": family_id, "spec_fingerprint": fingerprint})
        import yaml
        spec_path.write_text(yaml.safe_dump(spec, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
    return {"id": component_id, "family_id": family_id, "parameters": normalized, "spec_path": str(spec_path), "step_url": f"/api/generated-components/{component_id}/step", "yaml_url": f"/api/generated-components/{component_id}/yaml"}
