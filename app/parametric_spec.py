"""YAML-first parametric component generation and exact-spec reuse."""

from __future__ import annotations

import hashlib
import json
import fcntl
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

from .component_spec import dump_spec, inspect_shape, load_spec, read_step, validate_spec, write_shape_step
from .llm import COUNT_LIMITS, DEFAULTS, LABELS, normalize_parameters
from .model3d import GENERATOR_VERSIONS, build_shape


@dataclass(frozen=True)
class ResolvedParametricComponent:
    spec: dict[str, Any]
    spec_path: Path
    reference_step: Path
    shape: object
    source: Literal["library", "cache", "generated"]
    fingerprint: str

    @property
    def component_id(self) -> str:
        return str(self.spec["identity"]["id"])


def _canonical_parameters(part_type: str, parameters: dict[str, Any]) -> dict[str, Any]:
    return normalize_parameters(part_type, parameters)


def parametric_fingerprint(part_type: str, parameters: dict[str, Any]) -> str:
    if part_type not in GENERATOR_VERSIONS:
        raise ValueError(f"未注册的参数化生成器: {part_type}")
    payload = {
        "schema": "component-spec-parametric-v2",
        "generator_id": part_type,
        "generator_version": GENERATOR_VERSIONS[part_type],
        "parameters": _canonical_parameters(part_type, parameters),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def spec_fingerprint(spec: dict[str, Any]) -> str:
    generator = spec.get("geometry", {}).get("generator", {})
    parameters = {item["name"]: item.get("default") for item in spec.get("parameters", []) if isinstance(item, dict) and item.get("name")}
    part_type = str(generator.get("generator_id", ""))
    return parametric_fingerprint(part_type, parameters)


def create_parametric_spec(part_type: str, parameters: dict[str, Any], description: str) -> dict[str, Any]:
    normalized = _canonical_parameters(part_type, parameters)
    fingerprint = parametric_fingerprint(part_type, normalized)
    component_id = f"generated-{part_type}-{fingerprint[:16]}"
    today = date.today().isoformat()
    parameter_specs = []
    for name, value in normalized.items():
        parameter_specs.append({
            "name": name,
            "type": "integer" if isinstance(value, int) and not isinstance(value, bool) else "number",
            "unit": "count" if name in COUNT_LIMITS else "mm",
            "required": True,
            "default": value,
        })
    return {
        "schema_version": "1.3",
        "spec_type": "component",
        "identity": {
            "id": component_id,
            "name": f"{LABELS[part_type]}参数化图元",
            "name_en": None,
            "type": part_type,
            "subtype": "prompt_generated",
            "family": "parametric",
            "standard": None,
            "description": f"由结构化参数生成的{LABELS[part_type]}图元。",
            "license": "project-generated",
            "version": "1.0.0",
            "created_at": today,
            "updated_at": today,
            "status": "draft",
            "tags": [part_type, "parametric", "prompt-generated"],
            "default_preset": "parsed",
            "default_color": "#8D9BAB",
        },
        "coordinate_system": {
            "length_unit": "mm",
            "angle_unit": "deg",
            "handedness": "right_handed",
            "origin": [0.0, 0.0, 0.0],
            "x_axis": [1.0, 0.0, 0.0],
            "y_axis": [0.0, 1.0, 0.0],
            "z_axis": [0.0, 0.0, 1.0],
            "origin_definition": "parametric generator origin",
            "z_axis_definition": "parametric generator +Z",
            "zero_rotation_definition": "parametric generator +X",
        },
        "parameters": parameter_specs,
        "derived_parameters": [],
        "constraints": {"expression_language": "CEL", "rules": []},
        "ports": [],
        "geometry": {
            "representation": "parametric_brep",
            "modeling_kernel": "OpenCascade",
            "generator": {
                "mode": "parametric",
                "generator_id": part_type,
                "generator_version": GENERATOR_VERSIONS[part_type],
                "preferred_engine": "OpenCascade",
                "parameters_source": "parameters[].default",
            },
            "construction": [{
                "id": "build_parametric_shape",
                "operation": "invoke_allowlisted_generator",
                "generator_id": part_type,
            }],
            "output": {
                "format": "STEP",
                "application_protocol": "AP242",
                "preserve_names": True,
                "preserve_colors": True,
                "filename_template": f"{component_id}.step",
            },
        },
        "presets": [{"name": "parsed", "source_ref": "prompt", "verification_status": "pending", "params": normalized}],
        "validation": {
            "parameter_validation": {
                "required_parameters_complete": True,
                "enum_validation": True,
                "constraint_validation": True,
            },
            "topology": {
                "expected_body_count": None,
                "solid_required": True,
                "closed_shell_required": True,
                "manifold_required": True,
                "self_intersection_allowed": False,
            },
            "geometry": {
                "dimensional_tolerance": 0.01,
                "angular_tolerance": 0.1,
                "positive_volume_required": True,
                "measured": None,
            },
            "ports": {
                "validate_frame_orthogonality": True,
                "validate_axis_normalized": True,
                "validate_origin_on_interface": True,
            },
            "step_roundtrip": {
                "required": True,
                "application_protocol": "AP242",
                "preserve_product_name": True,
                "preserve_color": True,
                "preserve_units": True,
            },
        },
        "artifacts": {
            "reference_step": {
                "file": "reference.step",
                "role": "由参数化 YAML 物化的几何基准",
                "format": "STEP",
                "application_protocol": "AP242",
                "length_unit": "mm",
                "sha256": None,
            },
            "generator_source": {"file": None, "required": False, "sha256": None},
            "preview_model": {"file": None, "required": False, "sha256": None},
            "thumbnail": {"file": None, "required": False, "sha256": None},
        },
        "provenance": {
            "source_type": "prompt_generated",
            "spec_fingerprint": fingerprint,
            "prompt_sha256": hashlib.sha256(description.encode()).hexdigest(),
            "standard_refs": [],
            "data_entry_method": "moonshot_or_local_parser",
            "verified_by": "deterministic-generator",
            "verified_at": None,
        },
    }


def build_shape_from_spec(spec: dict[str, Any]) -> object:
    validation = validate_spec(spec)
    if validation["errors"]:
        raise ValueError("参数化 YAML 校验失败: " + "; ".join(validation["errors"]))
    generator = spec["geometry"]["generator"]
    parameters = {item["name"]: item["default"] for item in spec["parameters"]}
    normalized = _canonical_parameters(generator["generator_id"], parameters)
    return build_shape(generator["generator_id"], normalized)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _default_ports(measured: dict[str, Any], part_type: str) -> list[dict[str, Any]]:
    bbox = measured["bounding_box"]
    axis_index = 0 if part_type in {"valve", "shaft", "screw"} else 2
    axis = [0.0, 0.0, 0.0]
    axis[axis_index] = 1.0
    up = [1.0, 0.0, 0.0] if axis_index != 0 else [0.0, 1.0, 0.0]
    center = [(bbox["min"][i] + bbox["max"][i]) / 2 for i in range(3)]
    low, high = center.copy(), center.copy()
    low[axis_index], high[axis_index] = bbox["min"][axis_index], bbox["max"][axis_index]
    return [
        {"id": "end_a", "name": "轴向端口 A", "type": "mechanical_interface", "role": "mechanical_connection",
         "frame": {"origin": [round(v, 6) for v in low], "axis": [-v if v else 0.0 for v in axis], "up": up.copy()},
         "interface": {}, "compatible_with": {"port_types": ["mechanical_interface"], "rules": []},
         "allowed_mates": ["coincident_concentric"]},
        {"id": "end_b", "name": "轴向端口 B", "type": "mechanical_interface", "role": "mechanical_connection",
         "frame": {"origin": [round(v, 6) for v in high], "axis": axis.copy(), "up": up.copy()},
         "interface": {}, "compatible_with": {"port_types": ["mechanical_interface"], "rules": []},
         "allowed_mates": ["coincident_concentric"]},
    ]


def _validated_hit(spec_path: Path, fingerprint: str, source: Literal["library", "cache"]) -> ResolvedParametricComponent | None:
    try:
        spec = load_spec(spec_path)
        if spec.get("geometry", {}).get("generator", {}).get("mode") != "parametric":
            return None
        if spec.get("provenance", {}).get("spec_fingerprint") != fingerprint or spec_fingerprint(spec) != fingerprint:
            return None
        validation = validate_spec(spec, spec_path=spec_path)
        if validation["errors"]:
            return None
        reference = spec_path.parent / spec["artifacts"]["reference_step"]["file"]
        return ResolvedParametricComponent(spec, spec_path, reference, read_step(reference), source, fingerprint)
    except (KeyError, OSError, TypeError, ValueError):
        return None


def _find_library_hit(library: Path, fingerprint: str) -> ResolvedParametricComponent | None:
    if not library.is_dir():
        return None
    for spec_path in library.glob("*/component.yaml"):
        try:
            if "mode: parametric" not in spec_path.read_text(encoding="utf-8"):
                continue
        except OSError:
            continue
        if resolved := _validated_hit(spec_path, fingerprint, "library"):
            return resolved
    return None


@contextmanager
def _fingerprint_lock(generated_library: Path, fingerprint: str):
    """Serialize only identical cache materializations across worker processes."""
    lock_dir = generated_library / ".locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    with (lock_dir / f"{fingerprint}.lock").open("a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def resolve_parametric_component(
    part_type: str,
    parameters: dict[str, Any],
    description: str,
    *,
    formal_library: Path,
    generated_library: Path,
) -> ResolvedParametricComponent:
    """Resolve an exact parametric spec, or write YAML first and materialize it."""
    draft = create_parametric_spec(part_type, parameters, description)
    fingerprint = draft["provenance"]["spec_fingerprint"]
    if resolved := _find_library_hit(formal_library, fingerprint):
        return resolved

    component_id = draft["identity"]["id"]
    component_dir = generated_library / component_id
    spec_path = component_dir / "component.yaml"
    if resolved := _validated_hit(spec_path, fingerprint, "cache"):
        return resolved

    with _fingerprint_lock(generated_library, fingerprint):
        # Another worker may have completed the same component while we waited.
        if resolved := _validated_hit(spec_path, fingerprint, "cache"):
            return resolved
        component_dir.mkdir(parents=True, exist_ok=True)
        dump_spec(draft, spec_path)
        persisted = load_spec(spec_path)
        shape = build_shape_from_spec(persisted)
        reference = component_dir / persisted["artifacts"]["reference_step"]["file"]
        write_shape_step(shape, reference)
        measured = inspect_shape(shape)
        persisted["identity"]["status"] = "generated"
        persisted["identity"]["updated_at"] = date.today().isoformat()
        persisted["ports"] = _default_ports(measured, part_type)
        persisted["presets"][0]["verification_status"] = "geometry_measured"
        persisted["validation"]["topology"]["expected_body_count"] = measured["topology"]["solids"]
        persisted["validation"]["geometry"]["measured"] = measured
        persisted["artifacts"]["reference_step"]["sha256"] = _file_sha256(reference)
        persisted["provenance"]["verified_at"] = date.today().isoformat()
        dump_spec(persisted, spec_path)
        final_validation = validate_spec(persisted, spec_path=spec_path)
        if final_validation["errors"]:
            raise ValueError("参数化图元物化后校验失败: " + "; ".join(final_validation["errors"]))
        # Use the AP242 round-tripped shape on the first request as well as on
        # cache hits.  Complex boolean compounds (notably long swept screws)
        # are geometrically valid but can crash OCCT when exported/meshed a
        # second time in the same worker; STEP import canonicalizes them to the
        # stable solid that every subsequent request already receives.
        canonical_shape = read_step(reference)
        return ResolvedParametricComponent(persisted, spec_path, reference, canonical_shape, "generated", fingerprint)
