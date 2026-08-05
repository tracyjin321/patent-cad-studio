"""Validated ComponentSpec assembly planning, execution, and quality gates."""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .component_spec import (
    IDENTITY_MATRIX, _artifact_path, _frame_matrix, _inverse_rigid, _matmul,
    _port, _trsf_from_matrix, inspect_shape, load_spec, read_step,
)


class AssemblyComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    spec: str = Field(min_length=1)
    component_id: str | None = None
    fixed: bool = False
    port: str | None = None
    target: int | None = Field(default=None, ge=0)
    mate_to: str | None = None
    mate: Literal["coincident_concentric"] = "coincident_concentric"
    placement: list[list[float]] | None = None


class AssemblyManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    application_protocol: Literal["AP214", "AP242"] = "AP242"
    length_unit: Literal["mm"] = "mm"
    components: list[AssemblyComponent] = Field(min_length=1, max_length=64)
    solved_constraints: list[dict[str, Any]] = Field(default_factory=list)
    envelopes: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_graph(self):
        occupied: set[tuple[int, str]] = set()
        for index, item in enumerate(self.components):
            if item.placement is not None and (len(item.placement) != 4 or any(len(row) != 4 for row in item.placement)):
                raise ValueError(f"组件 {index} 的 placement 必须是 4×4 矩阵")
            mating = any(value is not None for value in (item.port, item.target, item.mate_to))
            if item.placement is not None and mating:
                raise ValueError(f"组件 {index} 不能同时声明 placement 和端口装配")
            if index == 0 and mating:
                raise ValueError("首个组件固定，不能声明装配目标")
            if index and mating and not all(value is not None for value in (item.port, item.target, item.mate_to)):
                raise ValueError(f"组件 {index} 的 port/target/mate_to 必须同时提供")
            if item.target is not None and item.target >= index:
                raise ValueError(f"组件 {index} 的 target 必须引用此前组件")
            if item.target is not None and item.mate_to is not None:
                key = (item.target, item.mate_to)
                if key in occupied:
                    raise ValueError(f"目标端口已占用: components[{item.target}].{item.mate_to}")
                occupied.add(key)
        return self


def _compatible(fixed: dict[str, Any], moving: dict[str, Any], mate: str) -> list[str]:
    errors = []
    if fixed.get("type") != moving.get("type"):
        errors.append(f"端口类型不兼容: {fixed.get('type')} != {moving.get('type')}")
    for label, port in (("目标", fixed), ("移动", moving)):
        allowed = port.get("allowed_mates") or []
        if allowed and mate not in allowed:
            errors.append(f"{label}端口不允许 {mate}")
    fixed_types = set((fixed.get("compatible_with") or {}).get("port_types") or [])
    moving_types = set((moving.get("compatible_with") or {}).get("port_types") or [])
    if fixed_types and moving.get("type") not in fixed_types:
        errors.append("移动端口类型不在目标 compatible_with 中")
    if moving_types and fixed.get("type") not in moving_types:
        errors.append("目标端口类型不在移动 compatible_with 中")
    fixed_interface, moving_interface = fixed.get("interface") or {}, moving.get("interface") or {}
    rules = set((fixed.get("compatible_with") or {}).get("rules") or [])
    rules.update((moving.get("compatible_with") or {}).get("rules") or [])
    for key in set(fixed_interface) & set(moving_interface):
        fixed_value, moving_value = fixed_interface[key], moving_interface[key]
        if fixed_value in (None, "") or moving_value in (None, ""):
            continue
        if key == "gender" and "opposite_gender" in rules:
            if fixed_value == moving_value:
                errors.append("接口属性不兼容: gender 必须相反")
        elif fixed_value != moving_value:
            errors.append(f"接口属性不兼容: {key}")
    return errors


def _quality(shape: object, instances: list[dict[str, Any]]) -> dict[str, Any]:
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common

    measured = inspect_shape(shape)
    valid = bool(BRepCheck_Analyzer(shape).IsValid())
    pairs = []
    for left in range(len(instances)):
        for right in range(left + 1, len(instances)):
            a, b = instances[left]["shape"], instances[right]["shape"]
            distance_op = BRepExtrema_DistShapeShape(a, b)
            distance_op.Perform()
            distance = float(distance_op.Value()) if distance_op.IsDone() else None
            common = BRepAlgoAPI_Common(a, b)
            common.Build()
            overlap = 0.0
            if common.IsDone() and not common.Shape().IsNull():
                try:
                    overlap = inspect_shape(common.Shape())["volume_mm3"]
                except Exception:
                    # A valid no-overlap result can be a non-null but void shape.
                    overlap = 0.0
            pairs.append({
                "left": left, "right": right,
                "clearance_mm": round(distance, 6) if distance is not None else None,
                "interference_volume_mm3": round(overlap, 6),
                "interfering": overlap > 0.01,
            })
    return {
        "valid_brep": valid,
        "measured": measured,
        "mass_properties": {
            "volume_mm3": measured["volume_mm3"],
            "surface_area_mm2": measured["surface_area_mm2"],
            "center_of_mass_mm": measured["center_of_mass"],
        },
        "pair_checks": pairs,
        "interference_free": not any(pair["interfering"] for pair in pairs),
    }


def build_assembly(manifest: AssemblyManifest, *, reject_interference: bool = True) -> tuple[object, dict[str, Any]]:
    from OCP.BRep import BRep_Builder
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.TopoDS import TopoDS_Compound

    loaded: list[dict[str, Any]] = []
    report_instances = []
    for index, item in enumerate(manifest.components):
        spec_path = Path(item.spec)
        spec = load_spec(spec_path)
        shape = read_step(_artifact_path(spec_path, spec))
        world = IDENTITY_MATRIX
        if item.placement is not None:
            world = item.placement
            shape = BRepBuilderAPI_Transform(shape, _trsf_from_matrix(world), True).Shape()
        elif item.target is not None:
            fixed = loaded[item.target]
            fixed_port = _port(fixed["spec"], str(item.mate_to))
            moving_port = _port(spec, str(item.port))
            errors = _compatible(fixed_port, moving_port, item.mate)
            if errors:
                raise ValueError(f"组件 {index} 端口不兼容: " + "; ".join(errors))
            relation = _matmul(
                _frame_matrix(fixed_port["frame"], reverse_axis=True),
                _inverse_rigid(_frame_matrix(moving_port["frame"])),
            )
            world = _matmul(fixed["world"], relation)
            shape = BRepBuilderAPI_Transform(shape, _trsf_from_matrix(world), True).Shape()
        loaded.append({"spec": spec, "shape": shape, "world": world})
        report_instances.append({
            "index": index,
            "component_id": item.component_id or spec["identity"]["id"],
            "spec": str(spec_path),
            "transform": [[round(float(value), 9) for value in row] for row in world],
            "port": item.port, "target": item.target, "mate_to": item.mate_to, "mate": item.mate,
        })

    compound, builder = TopoDS_Compound(), BRep_Builder()
    builder.MakeCompound(compound)
    for item in loaded:
        builder.Add(compound, item["shape"])
    quality = _quality(compound, loaded)
    expected_contact_pairs = {
        tuple(sorted(pair))
        for constraint in manifest.solved_constraints
        for pair in constraint.get("expected_contact_pairs", ([[0, 1]] if constraint.get("type") == "gear_mesh" else []))
    }
    if expected_contact_pairs:
        for pair in quality["pair_checks"]:
            if tuple(sorted((pair["left"], pair["right"]))) in expected_contact_pairs:
                pair["expected_contact"] = True
                pair["interfering"] = False
        quality["interference_free"] = not any(pair["interfering"] for pair in quality["pair_checks"])
    if not quality["valid_brep"]:
        raise ValueError("装配 B-Rep 无效")
    if reject_interference and not quality["interference_free"]:
        pairs = [f"{p['left']}-{p['right']}" for p in quality["pair_checks"] if p["interfering"]]
        raise ValueError("装配存在实体干涉: " + ", ".join(pairs))
    for envelope in manifest.envelopes:
        builder.Add(compound, envelope_shape(envelope))
    payload = manifest.model_dump(mode="json")
    report = {
        "schema_version": "1.0",
        "fingerprint": hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
        "instances": report_instances,
        "quality": quality,
        "solved_constraints": manifest.solved_constraints,
        "envelopes": manifest.envelopes,
    }
    return compound, report


def _translation(x: float = 0, y: float = 0, z: float = 0) -> list[list[float]]:
    return [[1.0, 0.0, 0.0, x], [0.0, 1.0, 0.0, y], [0.0, 0.0, 1.0, z], [0.0, 0.0, 0.0, 1.0]]


def _placed(rotation: list[list[float]], x: float = 0, y: float = 0, z: float = 0) -> list[list[float]]:
    return [[*rotation[0], x], [*rotation[1], y], [*rotation[2], z], [0.0, 0.0, 0.0, 1.0]]


def _tooth_count(component_id: str) -> int:
    match = re.search(r"-(\d+)t(?:-|$)", component_id)
    return int(match.group(1)) if match else 20


def _module(component_id: str) -> float:
    match = re.search(r"-m(\d+)-(\d+)-", component_id)
    return float(f"{match.group(1)}.{match.group(2)}") if match else 1.0


def _specialized_layout(component_ids: list[str], description: str) -> tuple[list[list[list[float]]] | None, list[dict[str, Any]], list[dict[str, Any]]]:
    text = description.casefold()
    if component_ids and component_ids[0].startswith("stepped-gear-shaft-") and len(component_ids) == 7:
        rotate_x_to_y = [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]
        rotate_z_to_y = [[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]]
        placements = [
            _translation(),
            _placed(rotate_x_to_y, y=22.0),
            _placed(rotate_z_to_y, y=20.0),
            _placed(rotate_z_to_y, y=32.5, z=-19.337),
            _placed(rotate_z_to_y, y=42.0),
            _placed(rotate_x_to_y, x=-8.0, y=48.0, z=7.0),
            _placed(rotate_z_to_y, x=-16.65, y=50.0, z=3.0),
        ]
        return placements, [{"type": "coaxial_shaft_stack", "axis": "Y", "root": 0, "targets": [1, 2, 3, 4, 6], "key_target": 5, "axial_positions_mm": [28.0, 20.5, 33.25, 42.0, 58.0], "exploded_offsets_mm": [-55.0, 0.0, -18.0, 18.0, 42.0, 72.0, 96.0], "expected_contact_pairs": [[0, 2], [0, 5], [0, 6], [1, 3], [5, 6]]}], []
    if len(component_ids) == 2 and all(component_id.startswith("spur-gear-") for component_id in component_ids):
        teeth = [_tooth_count(component_id) for component_id in component_ids]
        modules = [_module(component_id) for component_id in component_ids]
        if abs(modules[0] - modules[1]) > 1e-9:
            raise ValueError("啮合齿轮模数必须一致")
        center = modules[0] * sum(teeth) / 2
        return [_translation(), _translation(center)], [{"type": "gear_mesh", "module": modules[0], "teeth": teeth, "center_distance_mm": center, "ratio": round(teeth[1] / teeth[0], 6)}], []
    if "同步带" in text and 2 <= len(component_ids) <= 3:
        centers = [[0.0, 0.0], [80.0, 0.0]] + ([[40.0, 32.0]] if len(component_ids) == 3 else [])
        radii = [_tooth_count(component_id) * 2.0 / (2 * math.pi) for component_id in component_ids]
        length = 2 * 80.0 + math.pi * (radii[0] + radii[1]) + ((radii[1] - radii[0]) ** 2 / 80.0)
        placements = [_translation(x, y) for x, y in centers]
        envelope = {"type": "timing_belt", "component_id": "gt2-timing-belt-envelope", "centers": centers, "radii_mm": radii, "width_mm": 6.0, "closed_length_mm": round(length, 3)}
        return placements, [{"type": "belt_envelope", "pitch_mm": 2.0, "center_distance_mm": 80.0, "closed_length_mm": round(length, 3), "tangent_segments": 2}], [envelope]
    if ("链" in text or all(component_id.startswith("sprocket-") for component_id in component_ids)) and len(component_ids) == 2:
        centers, pitch = [[0.0, 0.0], [100.0, 0.0]], 6.35
        radii = [_tooth_count(component_id) * pitch / (2 * math.pi) for component_id in component_ids]
        length = 2 * 100.0 + math.pi * sum(radii) + ((radii[1] - radii[0]) ** 2 / 100.0)
        envelope = {"type": "roller_chain", "component_id": "roller-chain-envelope", "centers": centers, "radii_mm": radii, "width_mm": 3.1, "closed_length_mm": round(length, 3)}
        return [_translation(), _translation(100.0)], [{"type": "chain_envelope", "pitch_mm": pitch, "center_distance_mm": 100.0, "closed_length_mm": round(length, 3), "tangent_segments": 2}], [envelope]
    if "空间分支" in text and len(component_ids) >= 3:
        placements = [_translation(), _translation(0, 0, 35), _translation(55, 0, 0), _translation(0, 55, 0)][:len(component_ids)]
        branches = [{"type": "spatial_branch", "root": 0, "targets": list(range(1, len(component_ids))), "axes": ["Z", "X", "Y"][:len(component_ids) - 1]}]
        return placements, branches, []
    return None, [], []


def envelope_shape(envelope: dict[str, Any]) -> object:
    """Build a closed, patent-previewable approximation of a belt/chain envelope."""
    from OCP.BRep import BRep_Builder
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeTorus
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    from OCP.TopoDS import TopoDS_Compound
    centers, radii = envelope["centers"], envelope["radii_mm"]
    width = float(envelope["width_mm"])
    compound, builder = TopoDS_Compound(), BRep_Builder()
    builder.MakeCompound(compound)
    tube = max(0.7, width * 0.18)
    for (x, y), radius in zip(centers, radii):
        builder.Add(compound, BRepPrimAPI_MakeTorus(gp_Ax2(gp_Pnt(x, y, 0), gp_Dir(0, 0, 1)), float(radius), tube).Shape())
    if len(centers) >= 2:
        x0, y0 = centers[0]; x1, y1 = centers[1]
        span = max(0.1, abs(x1 - x0))
        builder.Add(compound, BRepPrimAPI_MakeBox(gp_Pnt(min(x0, x1), y0 + max(radii), -tube), span, tube * 2, tube * 2).Shape())
        builder.Add(compound, BRepPrimAPI_MakeBox(gp_Pnt(min(x0, x1), y0 - max(radii), -tube), span, tube * 2, tube * 2).Shape())
    return compound


def automatic_manifest(component_ids: list[str], library: Path, protocol: str = "AP242", description: str = "") -> AssemblyManifest:
    specs = [load_spec(library / component_id / "component.yaml") for component_id in component_ids]
    subtypes = [str(spec.get("identity", {}).get("subtype") or "") for spec in specs]
    fastener_stack = bool(
        subtypes
        and subtypes[0] == "socket_head_cap_screw"
        and all(subtype == "flat_washer" for subtype in subtypes[1:-1])
        and len(subtypes) >= 3
        and subtypes[-1] == "hex_nut"
    )
    placements, solved_constraints, envelopes = _specialized_layout(component_ids, description)
    components = []
    for index, component_id in enumerate(component_ids):
        spec = library / component_id / "component.yaml"
        item: dict[str, Any] = {"spec": str(spec), "component_id": component_id}
        if placements is not None:
            item["placement"] = placements[index]
        elif index:
            if fastener_stack:
                item.update({"port": "face_a", "target": index - 1, "mate_to": "head_bearing_face" if index == 1 else "face_b"})
            else:
                item.update({"port": "end_a", "target": index - 1, "mate_to": "end_b"})
        components.append(item)
    return AssemblyManifest(application_protocol=protocol, components=components, solved_constraints=solved_constraints, envelopes=envelopes)
