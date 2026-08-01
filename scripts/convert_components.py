#!/usr/bin/env python3
"""Convert the bundled graphic-element STEP files to ComponentSpec v1.3 YAML."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.component_spec import inspect_step  # noqa: E402


CATALOG = {
    "链轮链条": ("sprocket", "roller_chain_drive", "链轮", "Sprocket", "power_transmission"),
    "带轮": ("pulley", "belt_pulley", "带轮", "Pulley", "power_transmission"),
    "直齿轮": ("gear", "spur_gear", "直齿圆柱齿轮", "Spur Gear", "power_transmission"),
    "传动轴": ("shaft", "stepped_shaft", "二阶形轴", "Stepped Shaft", "shafting"),
    "丝杆": ("screw", "ball_screw", "滚珠丝杆", "Ball Screw", "linear_motion"),
    "轴承": ("bearing", "deep_groove_ball", "深沟球轴承", "Deep Groove Ball Bearing", "support"),
    "联轴器": ("coupling", "oldham", "十字环联轴器", "Oldham Coupling", "shafting"),
}


def slug(text: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return result or hashlib.sha1(text.encode()).hexdigest()[:12]


def parameter(name: str, label: str, value: float | int, unit: str | None = "mm") -> dict[str, Any]:
    return {"name": name, "label": label, "type": "integer" if isinstance(value, int) else "float",
            "unit": unit, "default": value, "required": True, "editable": False, "affects_geometry": True}


def inferred_parameters(path: Path, size: list[float]) -> list[dict[str, Any]]:
    stem = path.stem
    values: list[dict[str, Any]] = []
    if "VNR41" in stem:
        values = [parameter("module", "模数", 3.0), parameter("tooth_count", "齿数", 48, None), parameter("face_width", "齿宽", 30.0), parameter("bore_diameter", "轴孔直径", 35.0)]
    elif "LCS49" in stem:
        values = [parameter("shaft_diameter", "丝杆轴径", 20.0), parameter("lead", "导程", 5.0), parameter("length", "总长", 500.0), parameter("flange_diameter", "法兰外径", 30.0), parameter("mounting_pitch", "安装孔距", 12.0)]
    elif "MCM01" in stem:
        values = [parameter("max_diameter", "最大轴径", 30.0), parameter("section_length", "中段长度", 70.0), parameter("left_extension", "左伸出长度", 45.0), parameter("right_extension", "右伸出长度", 45.0), parameter("left_end_diameter", "左端直径", 20.0), parameter("right_end_diameter", "右端直径", 20.0), parameter("left_keyway_width", "左键槽宽", 12.0), parameter("right_keyway_width", "右键槽宽", 12.0)]
    elif "DBU03" in stem:
        values = [parameter("outer_diameter", "外径", 55.0), parameter("bore_diameter", "轴孔直径", 20.0), parameter("length", "总长", round(max(size), 3))]
    elif "VLK02" in stem:
        values = [parameter("tooth_count", "齿数", 60, None), parameter("chain_number", "链条号", 28, None), parameter("bore_diameter", "轴孔直径", 35.0)]
    elif "BAU6201Z" in stem:
        values = [parameter("outer_diameter", "外径（由 STEP 实测）", round(sorted(size)[-2], 3)), parameter("width", "宽度（由 STEP 实测）", round(min(size), 3))]
    return values


def make_spec(path: Path) -> dict[str, Any]:
    category = path.parent.name
    kind, subtype, name, name_en, family = CATALOG[category]
    measured = inspect_step(path)
    bbox, size = measured["bounding_box"], measured["bounding_box"]["size"]
    axis_index = size.index(max(size)) if kind in {"shaft", "screw", "coupling"} else size.index(min(size))
    axis = [0.0, 0.0, 0.0]; axis[axis_index] = 1.0
    up = [1.0, 0.0, 0.0] if axis_index != 0 else [0.0, 1.0, 0.0]
    center = [(bbox["min"][i] + bbox["max"][i]) / 2 for i in range(3)]
    low, high = center.copy(), center.copy()
    low[axis_index], high[axis_index] = bbox["min"][axis_index], bbox["max"][axis_index]
    model_code = re.sub(r"^(?:直齿轮[AB]类型-|二阶形轴-|滚珠丝杆-|深沟球轴承-)", "", path.stem)
    variant = "-a" if "直齿轮A类型" in path.stem else "-b" if "直齿轮B类型" in path.stem else ""
    component_id = f"{subtype.replace('_', '-')}-{slug(model_code)}{variant}"
    today = date.today().isoformat()
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    port_type = "shaft_bore" if kind not in {"shaft", "screw"} else "shaft_end"
    return {
        "schema_version": "1.3", "spec_type": "component",
        "identity": {"id": component_id, "name": name, "name_en": name_en, "type": kind, "subtype": subtype,
                     "family": family, "standard": None, "description": f"由现有 {path.name} 无损转换的固定规格图元。",
                     "license": "源文件许可见 STEP 元数据", "version": "1.0.0", "created_at": today, "updated_at": today,
                     "status": "draft", "tags": [category, name, model_code], "default_preset": "reference", "default_color": "#8D9BAB"},
        "coordinate_system": {"length_unit": "mm", "angle_unit": "deg", "handedness": "right_handed",
                              "origin": [round(v, 6) for v in center], "x_axis": [1.0, 0.0, 0.0], "y_axis": [0.0, 1.0, 0.0], "z_axis": [0.0, 0.0, 1.0],
                              "origin_definition": "STEP 包围盒中心", "z_axis_definition": "沿原始 STEP +Z", "zero_rotation_definition": "沿原始 STEP +X"},
        "parameters": inferred_parameters(path, size), "derived_parameters": [],
        "constraints": {"expression_language": "CEL", "rules": []},
        "ports": [
            {"id": "end_a", "name": "轴向端口 A", "type": port_type, "role": "mechanical_connection",
             "frame": {"origin": [round(v, 6) for v in low], "axis": [-v for v in axis], "up": up},
             "interface": {}, "compatible_with": {"port_types": ["shaft_end", "shaft_bore"], "rules": []}, "allowed_mates": ["coincident_concentric"]},
            {"id": "end_b", "name": "轴向端口 B", "type": port_type, "role": "mechanical_connection",
             "frame": {"origin": [round(v, 6) for v in high], "axis": axis, "up": up},
             "interface": {}, "compatible_with": {"port_types": ["shaft_end", "shaft_bore"], "rules": []}, "allowed_mates": ["coincident_concentric"]},
        ],
        "geometry": {"representation": "reference_brep", "modeling_kernel": "OpenCascade",
                     "generator": {"mode": "reference_step", "preferred_engine": "OpenCascade", "engine_version": "7.8.x", "script_required_for_release": False},
                     "construction": [{"id": "import_reference", "operation": "import_step", "source": path.name}],
                     "output": {"format": "STEP", "application_protocol": "source_preserved", "preserve_names": True, "preserve_colors": True, "filename_template": f"{component_id}.step"}},
        "presets": [{"name": "reference", "source_ref": path.name, "verification_status": "geometry_measured", "params": {p["name"]: p["default"] for p in inferred_parameters(path, size)}}],
        "validation": {"parameter_validation": {"required_parameters_complete": True, "enum_validation": True, "constraint_validation": True},
                       "topology": {"expected_body_count": measured["topology"]["solids"], "solid_required": True, "closed_shell_required": True, "manifold_required": True, "self_intersection_allowed": False},
                       "geometry": {"dimensional_tolerance": 0.01, "angular_tolerance": 0.1, "positive_volume_required": True, "measured": measured},
                       "ports": {"validate_frame_orthogonality": True, "validate_axis_normalized": True, "validate_origin_on_interface": True},
                       "step_roundtrip": {"required": True, "application_protocol": "source_preserved", "preserve_product_name": True, "preserve_color": True, "preserve_units": True},
                       "review": {"geometry_reviewer": None, "data_reviewer": None, "reviewed_at": None, "release_blocked_when_pending": True}},
        "artifacts": {"reference_step": {"file": path.name, "role": "固定规格几何与往返转换基准", "format": "STEP", "application_protocol": "AP214", "length_unit": "mm", "sha256": sha},
                      "generator_source": {"file": None, "required": False, "sha256": None}, "preview_model": {"file": None, "required": False, "sha256": None}, "thumbnail": {"file": None, "required": False, "sha256": None}},
        "provenance": {"source_type": "imported_step", "standard_refs": [], "data_entry_method": "imported", "verified_by": None, "verified_at": None},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path, default=ROOT / "graphic_element")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    paths = sorted([*args.root.rglob("*.step"), *args.root.rglob("*.stp")])
    for source in paths:
        output = source.with_suffix(".yaml")
        if output.exists() and not args.force:
            print(f"skip {output}")
            continue
        output.write_text(yaml.safe_dump(make_spec(source), allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
        print(f"wrote {output}")


if __name__ == "__main__":
    main()
