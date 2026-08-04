"""ComponentSpec v1.3 STEP/YAML conversion and assembly utilities.

Imported STEP files use a lossless ``reference_brep`` recipe: YAML records the
source artifact, checksum, measured geometry and assembly ports.  Rebuilding
without a transform copies the original bytes; transformed parts are imported
and exported by OpenCascade.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any, Iterable

import yaml


IDENTITY_MATRIX = [[1.0 if row == column else 0.0 for column in range(4)] for row in range(4)]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_step(path: Path):
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader

    reader = STEPControl_Reader()
    if reader.ReadFile(str(path)) != IFSelect_RetDone:
        raise ValueError(f"无法读取 STEP: {path}")
    if reader.TransferRoots() == 0:
        raise ValueError(f"STEP 中没有可转换的形状: {path}")
    return reader.OneShape()


def inspect_shape(shape: object) -> dict[str, Any]:
    from OCP.BRep import BRep_Tool
    from OCP.BRepGProp import BRepGProp
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_COMPOUND, TopAbs_EDGE, TopAbs_FACE, TopAbs_SHELL, TopAbs_SOLID, TopAbs_VERTEX
    from OCP.TopExp import TopExp_Explorer

    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    bounds = [round(float(value), 6) for value in box.Get()]
    counts = {}
    for name, kind in (("solids", TopAbs_SOLID), ("shells", TopAbs_SHELL), ("faces", TopAbs_FACE),
                       ("edges", TopAbs_EDGE), ("vertices", TopAbs_VERTEX), ("compounds", TopAbs_COMPOUND)):
        explorer, count = TopExp_Explorer(shape, kind), 0
        while explorer.More():
            count += 1
            explorer.Next()
        counts[name] = count
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    center = props.CentreOfMass()
    surface_props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(shape, surface_props)
    valid = not bool(BRep_Tool.IsClosed_s(shape)) if counts["solids"] == 0 else True
    return {
        "bounding_box": {
            "min": bounds[:3], "max": bounds[3:],
            "size": [round(bounds[i + 3] - bounds[i], 6) for i in range(3)],
        },
        "topology": counts,
        "volume_mm3": round(float(props.Mass()), 6),
        "surface_area_mm2": round(float(surface_props.Mass()), 6),
        "center_of_mass": [round(float(center.X()), 6), round(float(center.Y()), 6), round(float(center.Z()), 6)],
        "valid_solid": valid,
    }


def inspect_step(path: Path) -> dict[str, Any]:
    return inspect_shape(read_step(path))


def geometry_signatures(measured: dict[str, Any]) -> dict[str, str]:
    """Return strict-topology and engineering-stable SHA-256 signatures."""
    strict = {
        "topology": measured["topology"],
        "volume_mm3": measured["volume_mm3"],
        "surface_area_mm2": measured["surface_area_mm2"],
        "bounding_box": measured["bounding_box"],
        "center_of_mass": measured["center_of_mass"],
    }
    engineering = {
        "topology": {key: measured["topology"][key] for key in ("solids", "shells", "faces")},
        "volume_mm3": measured["volume_mm3"],
        "surface_area_mm2": measured["surface_area_mm2"],
        "bounding_box": measured["bounding_box"],
        "center_of_mass": measured["center_of_mass"],
    }
    encode = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return {"strict_topology_sha256": hashlib.sha256(encode(strict)).hexdigest(),
            "engineering_geometry_sha256": hashlib.sha256(encode(engineering)).hexdigest()}


def _relative_close(expected: float, actual: float, relative_tolerance: float) -> bool:
    tolerance = max(1e-6, abs(expected) * relative_tolerance)
    return abs(expected - actual) <= tolerance


def _engineering_geometry_errors(
    stored: dict[str, Any],
    actual: dict[str, Any],
    *,
    dimensional_tolerance: float,
    relative_tolerance: float,
) -> list[str]:
    """Compare stable engineering measurements without requiring identical hashes."""
    try:
        dimensional_tolerance = float(dimensional_tolerance)
        relative_tolerance = float(relative_tolerance)
        if dimensional_tolerance < 0 or relative_tolerance < 0:
            raise ValueError("tolerances must be non-negative")

        errors: list[str] = []
        stored_topology = stored["topology"]
        actual_topology = actual["topology"]
        if any(stored_topology[key] != actual_topology[key] for key in ("solids", "shells", "faces")):
            errors.append("reference STEP 工程拓扑与记录不一致")

        if not _relative_close(
            float(stored["volume_mm3"]),
            float(actual["volume_mm3"]),
            relative_tolerance,
        ):
            errors.append("reference STEP 工程几何体积超出声明公差")

        if "surface_area_mm2" in stored and not _relative_close(
            float(stored["surface_area_mm2"]),
            float(actual["surface_area_mm2"]),
            relative_tolerance,
        ):
            errors.append("reference STEP 工程几何表面积超出声明公差")

        stored_box = stored["bounding_box"]
        actual_box = actual["bounding_box"]
        box_pairs: list[tuple[Any, Any]] = []
        for section in ("min", "max", "size"):
            expected = stored_box[section]
            observed = actual_box[section]
            if len(expected) != 3 or len(observed) != 3:
                raise ValueError("bounding box coordinates must be three-dimensional")
            box_pairs.extend(zip(expected, observed))
        if any(abs(float(expected) - float(observed)) > dimensional_tolerance
               for expected, observed in box_pairs):
            errors.append("reference STEP 工程几何包围盒超出声明公差")

        stored_center = stored["center_of_mass"]
        actual_center = actual["center_of_mass"]
        if len(stored_center) != 3 or len(actual_center) != 3:
            raise ValueError("center of mass must be three-dimensional")
        if any(abs(float(expected) - float(observed)) > dimensional_tolerance
               for expected, observed in zip(stored_center, actual_center)):
            errors.append("reference STEP 工程几何重心超出声明公差")
        return errors
    except (KeyError, TypeError, ValueError):
        return ["reference STEP 工程几何测量基准无效"]


def load_spec(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        spec = yaml.safe_load(stream)
    if not isinstance(spec, dict) or spec.get("schema_version") != "1.3":
        raise ValueError(f"{path} 不是 ComponentSpec v1.3")
    return spec


def validate_spec(spec: dict[str, Any], *, spec_path: Path | None = None) -> dict[str, list[str]]:
    """Validate the interoperable subset of ComponentSpec v1.3."""
    errors: list[str] = []
    warnings: list[str] = []
    if spec.get("schema_version") != "1.3":
        errors.append("schema_version 必须为 1.3")
    if spec.get("spec_type") != "component":
        errors.append("spec_type 必须为 component")
    identity = spec.get("identity")
    if not isinstance(identity, dict) or not identity.get("id") or not identity.get("name") or not identity.get("type"):
        errors.append("identity.id/name/type 均为必填")
    parameters = spec.get("parameters", [])
    names = [item.get("name") for item in parameters if isinstance(item, dict)]
    if len(names) != len(set(names)) or any(not name for name in names):
        errors.append("parameters.name 必须非空且唯一")
    for item in parameters:
        if item.get("required") and item.get("default") is None:
            errors.append(f"必填参数 {item.get('name')} 缺少 default")
    port_ids: set[str] = set()
    for port in spec.get("ports", []):
        port_id = port.get("id")
        if not port_id or port_id in port_ids:
            errors.append("ports.id 必须非空且唯一")
        port_ids.add(port_id)
        frame = port.get("frame", {})
        try:
            axis, up = _normalize(frame["axis"]), _normalize(frame["up"])
            if len(frame["origin"]) != 3 or abs(sum(a*b for a, b in zip(axis, up))) > 1e-6:
                errors.append(f"端口 {port_id} 的 axis/up 必须正交且 origin 为三维坐标")
        except (KeyError, TypeError, ValueError):
            errors.append(f"端口 {port_id} 的 frame 无效")
    geometry = spec.get("geometry", {})
    generator = geometry.get("generator", {})
    generator_mode = generator.get("mode")
    placement = geometry.get("placement")
    if placement is not None:
        try:
            _validate_matrix(placement)
        except (TypeError, ValueError) as exc:
            errors.append(f"geometry.placement 无效: {exc}")
    artifact = spec.get("artifacts", {}).get("reference_step", {})
    if not artifact.get("file"):
        errors.append("artifacts.reference_step.file 为必填")
    elif spec_path is not None:
        source = _artifact_path(spec_path, spec)
        if not source.exists():
            errors.append(f"reference STEP 不存在: {source}")
        elif artifact.get("sha256") and _sha256(source) != artifact["sha256"]:
            errors.append("reference STEP SHA-256 不匹配")
        else:
            geometry_validation = spec.get("validation", {}).get("geometry", {})
            stored_measured = geometry_validation.get("measured")
            stored_signatures = geometry_validation.get("signatures")
            if stored_measured is not None:
                actual_measured = inspect_step(source)
                engineering_errors = _engineering_geometry_errors(
                    stored_measured,
                    actual_measured,
                    dimensional_tolerance=geometry_validation.get("dimensional_tolerance", 0.01),
                    relative_tolerance=geometry_validation.get("relative_tolerance", 1e-6),
                )
                errors.extend(engineering_errors)
                if (not engineering_errors and stored_signatures
                        and stored_signatures != geometry_signatures(actual_measured)):
                    warnings.append("reference STEP 精确几何签名不匹配；工程几何仍在声明公差内")
            elif stored_signatures:
                errors.append("reference STEP 工程几何测量基准无效")
    if generator_mode == "reference_step":
        if geometry.get("representation") != "reference_brep":
            errors.append("reference_step 模式必须使用 reference_brep")
    elif generator_mode == "parametric":
        if geometry.get("representation") != "parametric_brep":
            errors.append("parametric 模式必须使用 parametric_brep")
        try:
            from .llm import DEFAULTS, FEATURE_DEFAULTS, normalize_parameters
            from .model3d import GENERATOR_VERSIONS

            generator_id = generator["generator_id"]
            if generator_id not in GENERATOR_VERSIONS:
                errors.append(f"未注册的参数化生成器: {generator_id}")
            else:
                if generator.get("generator_version") != GENERATOR_VERSIONS[generator_id]:
                    errors.append(f"生成器版本不匹配: {generator_id}")
                values = {item["name"]: item.get("default") for item in parameters if isinstance(item, dict) and item.get("name")}
                base_keys = set(DEFAULTS[generator_id])
                allowed_keys = base_keys | set(FEATURE_DEFAULTS.get(generator_id, {}))
                if not base_keys.issubset(values) or not set(values).issubset(allowed_keys):
                    errors.append(f"参数集与生成器 {generator_id} 不匹配")
                elif normalize_parameters(generator_id, values) != values:
                    errors.append("参数未通过归一化约束")
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"参数化生成器定义无效: {exc}")
        filename = artifact.get("file")
        if filename and Path(filename).name != filename:
            errors.append("参数化 reference STEP 必须与 YAML 位于同一目录")
    else:
        errors.append("geometry.generator.mode 必须为 reference_step 或 parametric")
    return {"errors": errors, "warnings": warnings}


def dump_spec(spec: dict[str, Any], path: Path) -> None:
    result = validate_spec(spec)
    if result["errors"]:
        raise ValueError("YAML 规范校验失败: " + "; ".join(result["errors"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(spec, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")


def _slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return result or hashlib.sha1(value.encode()).hexdigest()[:12]


def step_to_spec(step_path: Path, output: Path, *, identity: dict[str, str] | None = None,
                 copy_reference: bool = True, reference_filename: str | None = None,
                 source_spec_path: Path | None = None) -> dict[str, Any]:
    """Create a portable ComponentSpec for any STEP file.

    By default the reference STEP is copied next to the YAML, making the pair
    relocatable. Existing same-path artifacts are never overwritten.
    """
    measured = inspect_step(step_path)
    info = identity or {}
    component_id = info.get("id", _slug(step_path.stem))
    if reference_filename and Path(reference_filename).name != reference_filename:
        raise ValueError("reference_filename 只能是文件名，不能包含目录")
    reference = (output.parent / reference_filename if reference_filename else output.with_suffix(step_path.suffix.lower())) if copy_reference else step_path.resolve()
    if copy_reference and reference.resolve() != step_path.resolve():
        if reference.exists() and _sha256(reference) != _sha256(step_path):
            raise FileExistsError(f"目标 reference STEP 已存在且内容不同: {reference}")
        reference.parent.mkdir(parents=True, exist_ok=True)
        if not reference.exists():
            shutil.copyfile(step_path, reference)
    artifact_file = reference.name if reference.parent.resolve() == output.parent.resolve() else str(reference)
    if source_spec_path is not None:
        spec = deepcopy(load_spec(source_spec_path))
        if spec.get("geometry", {}).get("placement") is not None:
            raise ValueError("带 placement 的 YAML 重导出后不能直接继承局部端口；请先固化坐标变换")
        if identity:
            spec["identity"].update(identity)
        spec["identity"]["updated_at"] = date.today().isoformat()
        spec["artifacts"]["reference_step"]["file"] = artifact_file
        spec["artifacts"]["reference_step"]["sha256"] = _sha256(reference)
        for operation in spec.get("geometry", {}).get("construction", []):
            if operation.get("operation") == "import_step":
                operation["source"] = artifact_file
        geometry_validation = spec.setdefault("validation", {}).setdefault("geometry", {})
        geometry_validation["measured"] = measured
        geometry_validation["signatures"] = geometry_signatures(measured)
        spec.setdefault("validation", {}).setdefault("topology", {})["expected_body_count"] = measured["topology"]["solids"]
        provenance = spec.setdefault("provenance", {})
        provenance["semantic_recovery"] = "authoritative_sidecar"
        provenance["source_spec_sha256"] = _sha256(source_spec_path)
        dump_spec(spec, output)
        return spec
    bbox, size = measured["bounding_box"], measured["bounding_box"]["size"]
    axis_index = size.index(max(size))
    axis = [0.0, 0.0, 0.0]
    axis[axis_index] = 1.0
    up = [1.0, 0.0, 0.0] if axis_index != 0 else [0.0, 1.0, 0.0]
    center = [(bbox["min"][i] + bbox["max"][i]) / 2 for i in range(3)]
    low, high = center.copy(), center.copy()
    low[axis_index], high[axis_index] = bbox["min"][axis_index], bbox["max"][axis_index]
    today = date.today().isoformat()
    spec = {
        "schema_version": "1.3", "spec_type": "component",
        "identity": {"id": component_id, "name": info.get("name", step_path.stem),
                     "name_en": info.get("name_en"), "type": info.get("type", "generic"),
                     "subtype": info.get("subtype", "imported_step"), "family": info.get("family", "generic"),
                     "standard": None, "description": f"由 {step_path.name} 转换的固定几何图元。",
                     "license": "源文件许可见 STEP 元数据", "version": "1.0.0", "created_at": today,
                     "updated_at": today, "status": "draft", "tags": [step_path.stem],
                     "default_preset": "reference", "default_color": "#8D9BAB"},
        "coordinate_system": {"length_unit": "mm", "angle_unit": "deg", "handedness": "right_handed",
                              "origin": [round(v, 6) for v in center], "x_axis": [1.0, 0.0, 0.0],
                              "y_axis": [0.0, 1.0, 0.0], "z_axis": [0.0, 0.0, 1.0],
                              "origin_definition": "STEP 包围盒中心", "z_axis_definition": "原始 STEP +Z",
                              "zero_rotation_definition": "原始 STEP +X"},
        "parameters": [], "derived_parameters": [], "constraints": {"expression_language": "CEL", "rules": []},
        "ports": [
            {"id": "end_a", "name": "轴向端口 A", "type": "mechanical_interface", "role": "mechanical_connection",
             "frame": {"origin": [round(v, 6) for v in low], "axis": [-v for v in axis], "up": up},
             "interface": {}, "compatible_with": {"port_types": ["mechanical_interface"], "rules": []},
             "allowed_mates": ["coincident_concentric"]},
            {"id": "end_b", "name": "轴向端口 B", "type": "mechanical_interface", "role": "mechanical_connection",
             "frame": {"origin": [round(v, 6) for v in high], "axis": axis, "up": up},
             "interface": {}, "compatible_with": {"port_types": ["mechanical_interface"], "rules": []},
             "allowed_mates": ["coincident_concentric"]},
        ],
        "geometry": {"representation": "reference_brep", "modeling_kernel": "OpenCascade",
                     "generator": {"mode": "reference_step", "preferred_engine": "OpenCascade",
                                   "engine_version": "7.8.x", "script_required_for_release": False},
                     "construction": [{"id": "import_reference", "operation": "import_step", "source": artifact_file}],
                     "output": {"format": "STEP", "application_protocol": "AP242", "preserve_names": True,
                                "preserve_colors": True, "filename_template": f"{component_id}.step"}},
        "presets": [{"name": "reference", "source_ref": step_path.name,
                     "verification_status": "geometry_measured", "params": {}}],
        "validation": {"parameter_validation": {"required_parameters_complete": True, "enum_validation": True,
                                                  "constraint_validation": True},
                       "topology": {"expected_body_count": measured["topology"]["solids"], "solid_required": True,
                                    "closed_shell_required": True, "manifold_required": True,
                                    "self_intersection_allowed": False},
                       "geometry": {"dimensional_tolerance": 0.01, "angular_tolerance": 0.1,
                                    "positive_volume_required": True, "measured": measured,
                                    "signatures": geometry_signatures(measured)},
                       "ports": {"validate_frame_orthogonality": True, "validate_axis_normalized": True,
                                 "validate_origin_on_interface": True},
                       "step_roundtrip": {"required": True, "application_protocol": "AP242",
                                          "preserve_product_name": True, "preserve_color": True,
                                          "preserve_units": True}},
        "artifacts": {"reference_step": {"file": artifact_file, "role": "固定规格几何与往返转换基准",
                                           "format": "STEP", "application_protocol": "source_preserved",
                                           "length_unit": "mm", "sha256": _sha256(reference)},
                      "generator_source": {"file": None, "required": False, "sha256": None},
                      "preview_model": {"file": None, "required": False, "sha256": None},
                      "thumbnail": {"file": None, "required": False, "sha256": None}},
        "provenance": {"source_type": "imported_step", "standard_refs": [], "data_entry_method": "imported",
                       "semantic_recovery": "inferred",
                       "verified_by": None, "verified_at": None},
    }
    dump_spec(spec, output)
    return spec


def _artifact_path(spec_path: Path, spec: dict[str, Any]) -> Path:
    filename = spec.get("artifacts", {}).get("reference_step", {}).get("file")
    if not filename:
        raise ValueError("YAML 缺少 artifacts.reference_step.file")
    result = Path(filename)
    return result if result.is_absolute() else spec_path.parent / result


def write_shape_step(shape: object, path: Path, application_protocol: str = "AP242") -> None:
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.Interface import Interface_Static
    from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer

    path.parent.mkdir(parents=True, exist_ok=True)
    # Imported specs use source_preserved when the original protocol is not
    # asserted. Re-exports use the project's canonical AP242 representation.
    schemas = {"AP214": "AP214IS", "AP242": "AP242DIS", "SOURCE_PRESERVED": "AP242DIS"}
    schema = schemas.get(application_protocol.upper())
    if schema is None:
        raise ValueError(f"不支持的 STEP 应用协议: {application_protocol}")
    Interface_Static.SetCVal_s("write.step.schema", schema)
    writer = STEPControl_Writer()
    if writer.Transfer(shape, STEPControl_AsIs) != IFSelect_RetDone or writer.Write(str(path)) != IFSelect_RetDone:
        raise RuntimeError(f"OpenCascade 无法写入 {path}")


def spec_to_step(spec_path: Path, output: Path, *, verify_checksum: bool = True,
                 force_reexport: bool = False) -> dict[str, Any]:
    spec = load_spec(spec_path)
    validation = validate_spec(spec, spec_path=spec_path)
    if validation["errors"]:
        raise ValueError("YAML 规范校验失败: " + "; ".join(validation["errors"]))
    source = _artifact_path(spec_path, spec)
    expected = spec["artifacts"]["reference_step"].get("sha256")
    if verify_checksum and expected and _sha256(source) != expected:
        raise ValueError(f"reference STEP 校验和不匹配: {source}")
    output.parent.mkdir(parents=True, exist_ok=True)
    placement = spec.get("geometry", {}).get("placement")
    generator_mode = spec.get("geometry", {}).get("generator", {}).get("mode")
    if generator_mode == "parametric":
        from .parametric_spec import build_shape_from_spec

        shape = build_shape_from_spec(spec)
        if placement is not None:
            from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform

            shape = BRepBuilderAPI_Transform(shape, _trsf_from_matrix(placement), True).Shape()
        protocol = str(spec.get("geometry", {}).get("output", {}).get("application_protocol", "AP242"))
        write_shape_step(shape, output, protocol)
    elif placement is not None or force_reexport:
        from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform

        shape = read_step(source)
        if placement is not None:
            shape = BRepBuilderAPI_Transform(shape, _trsf_from_matrix(placement), True).Shape()
        protocol = str(spec.get("geometry", {}).get("output", {}).get("application_protocol", "AP242"))
        write_shape_step(shape, output, protocol)
    elif source.resolve() != output.resolve():
        shutil.copyfile(source, output)
    return inspect_step(output)


def roundtrip_report(spec_path: Path, output: Path | None = None) -> dict[str, Any]:
    """Re-export a spec and compare invariant geometry with its reference."""
    import tempfile

    spec = load_spec(spec_path)
    source = _artifact_path(spec_path, spec)
    original = inspect_step(source)
    if output is None:
        with tempfile.TemporaryDirectory(prefix="component-roundtrip-") as directory:
            target = Path(directory) / "roundtrip.step"
            rebuilt = spec_to_step(spec_path, target, force_reexport=True)
    else:
        rebuilt = spec_to_step(spec_path, output, force_reexport=True)
    tolerance = float(spec.get("validation", {}).get("geometry", {}).get("dimensional_tolerance", 0.01))
    # STEP writers may re-approximate analytic/B-spline surfaces. A ppm-level
    # relative tolerance catches real geometry changes without rejecting that
    # harmless serialization noise (notably on the imported Oldham coupling).
    volume_relative_tolerance = float(
        spec.get("validation", {}).get("geometry", {}).get("volume_relative_tolerance", 1e-6)
    )
    volume_tolerance = max(1e-6, abs(original["volume_mm3"]) * volume_relative_tolerance)
    area_tolerance = max(1e-6, abs(original["surface_area_mm2"]) * volume_relative_tolerance)
    size_delta = [abs(a - b) for a, b in zip(original["bounding_box"]["size"], rebuilt["bounding_box"]["size"])]
    checks = {
        "solid_count": original["topology"]["solids"] == rebuilt["topology"]["solids"],
        "face_count": original["topology"]["faces"] == rebuilt["topology"]["faces"],
        "volume": abs(original["volume_mm3"] - rebuilt["volume_mm3"]) <= volume_tolerance,
        "surface_area": abs(original["surface_area_mm2"] - rebuilt["surface_area_mm2"]) <= area_tolerance,
        "bounding_box_size": all(delta <= tolerance for delta in size_delta),
    }
    return {"passed": all(checks.values()), "checks": checks, "size_delta_mm": size_delta,
            "volume_delta_mm3": abs(original["volume_mm3"] - rebuilt["volume_mm3"]),
            "volume_tolerance_mm3": volume_tolerance,
            "surface_area_delta_mm2": abs(original["surface_area_mm2"] - rebuilt["surface_area_mm2"]),
            "surface_area_tolerance_mm2": area_tolerance,
            "original": original, "rebuilt": rebuilt}


def _normalize(vector: Iterable[float]) -> list[float]:
    values = [float(v) for v in vector]
    length = math.sqrt(sum(v * v for v in values))
    if length < 1e-12:
        raise ValueError("端口方向向量不能为零")
    return [v / length for v in values]


def _cross(a: list[float], b: list[float]) -> list[float]:
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def _frame_matrix(frame: dict[str, Any], reverse_axis: bool = False) -> list[list[float]]:
    x = _normalize(frame["up"])
    z = _normalize(frame["axis"])
    if reverse_axis:
        z = [-v for v in z]
    y = _normalize(_cross(z, x))
    x = _normalize(_cross(y, z))
    origin = [float(v) for v in frame["origin"]]
    return [[x[r], y[r], z[r], origin[r]] for r in range(3)] + [[0.0, 0.0, 0.0, 1.0]]


def _inverse_rigid(m: list[list[float]]) -> list[list[float]]:
    result = [[m[j][i] if i < 3 and j < 3 else 0.0 for j in range(4)] for i in range(4)]
    result[3] = [0.0, 0.0, 0.0, 1.0]
    for i in range(3):
        result[i][3] = -sum(result[i][j] * m[j][3] for j in range(3))
    return result


def _matmul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def _validate_matrix(matrix: Any) -> None:
    if not isinstance(matrix, list) or len(matrix) != 4 or any(not isinstance(row, list) or len(row) != 4 for row in matrix):
        raise ValueError("必须是 4x4 矩阵")
    values = [[float(value) for value in row] for row in matrix]
    if any(abs(values[3][i] - IDENTITY_MATRIX[3][i]) > 1e-9 for i in range(4)):
        raise ValueError("最后一行必须为 [0, 0, 0, 1]")
    axes = [[values[row][column] for row in range(3)] for column in range(3)]
    for index, axis in enumerate(axes):
        if abs(sum(value * value for value in axis) - 1.0) > 1e-6:
            raise ValueError(f"旋转轴 {index} 未归一化")
    if any(abs(sum(axes[a][i] * axes[b][i] for i in range(3))) > 1e-6 for a in range(3) for b in range(a + 1, 3)):
        raise ValueError("旋转矩阵不正交")


def mate_transform(fixed_frame: dict[str, Any], moving_frame: dict[str, Any]):
    """Return an OCC transform making port origins coincide and axes oppose."""
    matrix = _matmul(_frame_matrix(fixed_frame, reverse_axis=True), _inverse_rigid(_frame_matrix(moving_frame)))
    return _trsf_from_matrix(matrix)


def _trsf_from_matrix(matrix: list[list[float]]):
    from OCP.gp import gp_Trsf

    transform = gp_Trsf()
    transform.SetValues(*[matrix[i][j] for i in range(3) for j in range(4)])
    return transform


def _port(spec: dict[str, Any], port_id: str) -> dict[str, Any]:
    for port in spec.get("ports", []):
        if port.get("id") == port_id:
            return port
    raise ValueError(f"找不到端口 {port_id}")


def assemble(
    components: list[dict[str, Any]],
    output: Path,
    *,
    application_protocol: str = "AP242",
) -> dict[str, Any]:
    """Validate and assemble ComponentSpecs through the shared assembly service."""
    from .assembly import AssemblyManifest, build_assembly

    manifest = AssemblyManifest(application_protocol=application_protocol, components=components)
    compound, report = build_assembly(manifest)
    write_shape_step(compound, output, application_protocol)
    return {**report["quality"]["measured"], "assembly_report": report}
