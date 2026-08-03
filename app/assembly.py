"""Validated ComponentSpec assembly planning, execution, and quality gates."""

from __future__ import annotations

import hashlib
import json
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


class AssemblyManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    application_protocol: Literal["AP214", "AP242"] = "AP242"
    length_unit: Literal["mm"] = "mm"
    components: list[AssemblyComponent] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_graph(self):
        occupied: set[tuple[int, str]] = set()
        for index, item in enumerate(self.components):
            mating = any(value is not None for value in (item.port, item.target, item.mate_to))
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
        if item.target is not None:
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
    if not quality["valid_brep"]:
        raise ValueError("装配 B-Rep 无效")
    if reject_interference and not quality["interference_free"]:
        pairs = [f"{p['left']}-{p['right']}" for p in quality["pair_checks"] if p["interfering"]]
        raise ValueError("装配存在实体干涉: " + ", ".join(pairs))
    payload = manifest.model_dump(mode="json")
    report = {
        "schema_version": "1.0",
        "fingerprint": hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
        "instances": report_instances,
        "quality": quality,
    }
    return compound, report


def automatic_manifest(component_ids: list[str], library: Path, protocol: str = "AP242") -> AssemblyManifest:
    specs = [load_spec(library / component_id / "component.yaml") for component_id in component_ids]
    subtypes = [str(spec.get("identity", {}).get("subtype") or "") for spec in specs]
    fastener_stack = bool(
        subtypes
        and subtypes[0] == "socket_head_cap_screw"
        and all(subtype == "flat_washer" for subtype in subtypes[1:-1])
        and len(subtypes) >= 3
        and subtypes[-1] == "hex_nut"
    )
    components = []
    for index, component_id in enumerate(component_ids):
        spec = library / component_id / "component.yaml"
        item: dict[str, Any] = {"spec": str(spec), "component_id": component_id}
        if index:
            if fastener_stack:
                item.update({"port": "face_a", "target": index - 1, "mate_to": "head_bearing_face" if index == 1 else "face_b"})
            else:
                item.update({"port": "end_a", "target": index - 1, "mate_to": "end_b"})
        components.append(item)
    return AssemblyManifest(application_protocol=protocol, components=components)
