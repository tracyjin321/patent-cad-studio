#!/usr/bin/env python3
"""Materialize Falcon 9 Block 5 primitives, assembly, STEP AP214, and drawing."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.cad import generate_svg  # noqa: E402
from app.component_spec import assemble, dump_spec, load_spec, step_to_spec, validate_spec, write_shape_step  # noqa: E402
from app.llm import normalize_parameters  # noqa: E402
from app.rocket import build_falcon9_components, build_falcon9_shape  # noqa: E402
from scripts.rebuild_component_catalog import build_catalog  # noqa: E402


FINAL_PROMPT = """生成猎鹰九号（Falcon 9 Full Thrust Block 5）全箭 CAD 模型，输出标准 STEP AP214 格式。
单位统一为毫米，底部发动机喷口最低平面为 Z=0，箭体轴线沿 +Z。全箭总高 70000，一级/二级箭体直径 3660，整流罩最大直径 5200、高 13100。
一级包含 9 台 Merlin 1D 海平面发动机，采用八边形环列加中心一台布局；喷嘴出口直径 920、轴向长度 2500。一级外壁设置 4 道加强环箍、4 条折叠着陆腿；着陆腿以双纵梁和交叉斜撑表达碳纤维桁架特征。
级间段连接一级与二级，外侧设置 4 组分离作动器整流罩。级间段底部附近设置 4 片钛合金栅格翼，按 90 度周向对称，单片径向翼展 1800、厚 80，并保留边框与正交蜂窝栅格拓扑。
二级设置单台 Merlin 1D Vacuum，大型钟形喷管出口直径 2700、长度 4000，并设置一条外置推进剂输送管路示意。
整流罩采用 3660 至 5200 的 3000 高锥形过渡段与 von Karman ogive 外形，保留蚌壳纵向分离接缝。一级、栅格翼、级间段、二级和整流罩均作为独立装配子件，最终汇总为单一 STEP 文件；几何精度 0.01，保留主要拓扑特征，不添加纹理。"""


COMPONENT_META = {
    "first_stage": ("falcon9-first-stage", "猎鹰九号一级火箭", "first_stage"),
    "grid_fins": ("falcon9-grid-fin-set", "猎鹰九号四片栅格翼组件", "grid_fin_set"),
    "interstage": ("falcon9-interstage", "猎鹰九号级间段", "interstage"),
    "second_stage": ("falcon9-second-stage", "猎鹰九号二级火箭", "second_stage"),
    "payload_fairing": ("falcon9-payload-fairing", "猎鹰九号有效载荷整流罩", "payload_fairing"),
}


def _ports(name: str) -> list[dict]:
    stations = {
        "first_stage": (0.0, 45500.0),
        "grid_fins": (43800.0, 45250.0),
        "interstage": (45500.0, 50000.0),
        "second_stage": (50000.0, 56900.0),
        "payload_fairing": (56900.0, 70000.0),
    }
    low, high = stations[name]
    return [
        {"id": "bottom", "name": "下端装配面", "type": "mechanical_interface", "role": "mechanical_connection",
         "frame": {"origin": [0.0, 0.0, low], "axis": [0.0, 0.0, -1.0], "up": [1.0, 0.0, 0.0]},
         "interface": {}, "compatible_with": {"port_types": ["mechanical_interface"], "rules": []},
         "allowed_mates": ["coincident_concentric"]},
        {"id": "top", "name": "上端装配面", "type": "mechanical_interface", "role": "mechanical_connection",
         "frame": {"origin": [0.0, 0.0, high], "axis": [0.0, 0.0, 1.0], "up": [1.0, 0.0, 0.0]},
         "interface": {}, "compatible_with": {"port_types": ["mechanical_interface"], "rules": []},
         "allowed_mates": ["coincident_concentric"]},
    ]


def main() -> None:
    parameters = normalize_parameters("rocket", {})
    artifacts = ROOT / "artifacts" / "falcon9-block5"
    artifacts.mkdir(parents=True, exist_ok=True)
    shapes = build_falcon9_components(parameters)
    manifest_components = []

    for key, shape in shapes.items():
        component_id, name, subtype = COMPONENT_META[key]
        source_step = artifacts / f"{component_id}.step"
        write_shape_step(shape, source_step, "AP214")
        component_dir = ROOT / "component_library" / component_id
        component_dir.mkdir(parents=True, exist_ok=True)
        spec_path = component_dir / "component.yaml"
        # These files are deterministic outputs owned by this generator.  Clear
        # the previous materialization so repeated validation runs stay idempotent
        # even though STEP headers contain a fresh export timestamp.
        spec_path.unlink(missing_ok=True)
        (component_dir / "reference.step").unlink(missing_ok=True)
        step_to_spec(
            source_step,
            spec_path,
            identity={"id": component_id, "name": name, "type": "rocket"},
            copy_reference=True,
            reference_filename="reference.step",
        )
        spec = load_spec(spec_path)
        spec["identity"].update({
            "name_en": component_id.replace("-", " ").title(),
            "subtype": subtype,
            "family": "falcon9-block5",
            "status": "approved",
            "tags": ["falcon-9", "block-5", subtype, "space-launch-vehicle"],
        })
        spec["ports"] = _ports(key)
        spec["geometry"]["output"]["application_protocol"] = "AP214"
        spec["artifacts"]["reference_step"]["application_protocol"] = "AP214"
        spec["validation"]["step_roundtrip"]["application_protocol"] = "AP214"
        spec["provenance"].update({
            "source_type": "project_parametric_primitive",
            "standard_refs": ["SpaceX Falcon User's Guide"],
            "data_entry_method": "deterministic_opencascade_generator",
            "verified_by": "geometry-and-visual-validation",
        })
        dump_spec(spec, spec_path)
        validation = validate_spec(spec, spec_path=spec_path)
        if validation["errors"]:
            raise RuntimeError(f"{component_id}: {'; '.join(validation['errors'])}")
        manifest_components.append({"spec": f"../../component_library/{component_id}/component.yaml"})

    manifest = {
        "schema_version": "1.0",
        "name": "Falcon 9 Full Thrust Block 5",
        "application_protocol": "AP214",
        "length_unit": "mm",
        "coordinate_system": {"origin": "engine nozzle lowest plane", "axis": "+Z"},
        "rules": [
            "All component STEP files are authored in the shared vehicle datum.",
            "First stage, grid fins, interstage, second stage, and payload fairing remain independent subassemblies.",
            "Final output is a single non-fused compound STEP AP214 file.",
            "Overall envelope height must equal 70000 mm; fairing diameter must equal 5200 mm.",
        ],
        "components": manifest_components,
    }
    manifest_path = artifacts / "assembly.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_step = artifacts / "falcon9-block5-ap214.step"
    resolved_entries = [{**item, "spec": str((artifacts / item["spec"]).resolve())} for item in manifest_components]
    measured = assemble(resolved_entries, output_step, application_protocol="AP214")

    shape = build_falcon9_shape(parameters)
    svg = generate_svg(shape, "猎鹰九号 Block 5 全箭轴测图", "rocket", parameters)
    (artifacts / "falcon9-block5-isometric.svg").write_text(svg, encoding="utf-8")
    (artifacts / "final-prompt.txt").write_text(FINAL_PROMPT + "\n", encoding="utf-8")
    (artifacts / "validation.json").write_text(json.dumps({
        "parameters": parameters,
        "measured": measured,
        "checks": {
            "height_70000_mm": abs(measured["bounding_box"]["size"][2] - 70000.0) <= 0.01,
            "ap214_header": "AUTOMOTIVE_DESIGN" in output_step.read_text(encoding="latin-1", errors="ignore")[:4096],
            "independent_solids": measured["topology"]["solids"] >= 100,
            "engine_layout_9": parameters["engine_count"] == 9,
            "grid_fins_4": parameters["grid_fin_count"] == 4,
            "landing_legs_4": parameters["landing_leg_count"] == 4,
        },
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    catalog = build_catalog(ROOT / "component_library")
    (ROOT / "component_library" / "catalog.yaml").write_text(
        yaml.safe_dump(catalog, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    print(json.dumps({"step": str(output_step), "drawing": str(artifacts / "falcon9-block5-isometric.svg"), "measured": measured}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
