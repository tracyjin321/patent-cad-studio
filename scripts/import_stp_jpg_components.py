#!/usr/bin/env python3
"""Import the curated stp-jpg patent-mechanism sample set as ComponentSpecs."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.component_spec import step_to_spec  # noqa: E402


PARTS = [
    {"step": "680.9.1.3-1套筒.stp", "images": ["680.9.1.3-1套筒.jpg"],
     "id": "sleeve-d20-d27-l10-680-9-1-3", "name": "套筒 Φ20/Φ27×10", "name_en": "Sleeve 20/27 x 10",
     "type": "spacer", "subtype": "sleeve", "family": "shaft-spacer", "axis": 2,
     "standard": "680.9.1.3-1", "tags": ["套筒", "轴套", "spacer", "bushing", "20mm", "27mm", "10mm"],
     "prompt": "生成机械专利附图风格的轴用套筒：内孔直径20 mm、外径27 mm、轴向长度10 mm，同轴通孔、两端平齐，作为齿轮轴上的定位隔套。"},
    {"step": "680.9.1.3-2齿轮1.stp", "images": ["680.9.1.3-2齿轮1.jpg"],
     "id": "spur-gear-keyed-bore20-od48-w16-680-9-1-3", "name": "键槽孔直齿轮 Φ48×16", "name_en": "Keyed-bore spur gear 48 x 16",
     "type": "gear", "subtype": "spur_gear", "family": "power_transmission", "axis": 2,
     "standard": "680.9.1.3-2", "tags": ["直齿轮", "键槽", "spur gear", "20mm bore", "48mm OD", "16mm face width"],
     "prompt": "生成机械专利附图风格的直齿圆柱齿轮：外径约48 mm、齿宽16 mm、中心孔20 mm，孔内带普通平键键槽，轮毂与齿圈一体，用于齿轮轴传动。"},
    {"step": "680.9.1.6-1齿轮轴.stp", "images": ["680.9.1.6-1齿轮轴.jpg"],
     "id": "stepped-gear-shaft-d20-l88-680-9-1-6", "name": "阶梯齿轮轴 Φ20×88", "name_en": "Stepped gear shaft 20 x 88",
     "type": "shaft", "subtype": "stepped_shaft", "family": "transmission-shaft", "axis": 1,
     "standard": "680.9.1.6-1", "tags": ["齿轮轴", "阶梯轴", "键槽", "shaft", "20mm", "88mm"],
     "prompt": "生成机械专利附图风格的阶梯齿轮轴：主体直径约20 mm、总长约88 mm，包含轴肩、轴承安装段、挡圈槽和纵向平键键槽，各回转段保持同轴。"},
    {"step": "弹性挡圈-GB 893.1-86 - 42.stp", "images": ["弹性挡圈-GB-T893.1-1983-42.jpg"],
     "id": "circlip-internal-gbt893-1-d42", "name": "孔用弹性挡圈 42", "name_en": "Internal circlip 42",
     "type": "fastener", "subtype": "internal_retaining_ring", "family": "retaining-ring", "axis": 2,
     "standard": "GB/T 893.1-1986 42", "tags": ["孔用弹性挡圈", "circlip", "retaining ring", "42mm"],
     "prompt": "生成机械专利附图风格的孔用弹性挡圈，规格42，符合GB/T 893.1，开口环形薄片结构，厚度约1.5 mm，两端带装配钳孔，用于直径42 mm孔槽。"},
    {"step": "弹性挡圈-GB 894.1-86 - 20.stp", "images": ["弹性挡圈-GB-T894.1-1986-20.jpg"],
     "id": "circlip-external-gbt894-1-d20", "name": "轴用弹性挡圈 20", "name_en": "External circlip 20",
     "type": "fastener", "subtype": "external_retaining_ring", "family": "retaining-ring", "axis": 2,
     "standard": "GB/T 894.1-1986 20", "tags": ["轴用弹性挡圈", "circlip", "retaining ring", "20mm"],
     "prompt": "生成机械专利附图风格的轴用弹性挡圈，规格20，符合GB/T 894.1，开口环形薄片结构，厚度约1 mm，两端带装配钳孔，用于直径20 mm轴槽。"},
    {"step": "轴承 6004-2Z GB_T 276-94.stp", "images": ["轴承 6004-2Z GB_T 276-94.jpg"],
     "id": "bearing-6004-2z-gbt276", "name": "深沟球轴承 6004-2Z", "name_en": "Deep groove ball bearing 6004-2Z",
     "type": "bearing", "subtype": "deep_groove_ball", "family": "deep-groove-ball-bearing", "axis": 0,
     "standard": "GB/T 276-1994 6004-2Z", "tags": ["深沟球轴承", "6004-2Z", "bearing", "20mm bore", "42mm OD", "12mm width"],
     "prompt": "生成机械专利附图风格的深沟球轴承6004-2Z，符合GB/T 276，公称内径20 mm、外径42 mm、宽12 mm，内外圈同轴并包含钢球、保持架和双面防尘盖。"},
    {"step": "键 GB_T 1096 - A 6 x 6 x 14.stp", "images": ["键 GB_T 1096 - A 6 x 6 x 14.jpg"],
     "id": "parallel-key-gbt1096-a6x6x14", "name": "普通平键 A型 6×6×14", "name_en": "Parallel key type A 6 x 6 x 14",
     "type": "fastener", "subtype": "parallel_key", "family": "shaft-key", "axis": 0,
     "standard": "GB/T 1096 A 6×6×14", "tags": ["普通平键", "A型平键", "parallel key", "6x6x14"],
     "prompt": "生成机械专利附图风格的A型普通平键，符合GB/T 1096，宽6 mm、高6 mm、长14 mm，两端为圆头，用于20 mm轴与齿轮轮毂的周向连接。"},
    {"step": "680.9.1.6齿轮轴组合.stp", "images": ["680.9.1.6齿轮轴组合.jpg", "680.9.1.6齿轮轴组合-2.jpg", "680.9.1.6齿轮轴组合-3.jpg"],
     "id": "gear-shaft-assembly-680-9-1-6", "name": "齿轮轴组合 680.9.1.6", "name_en": "Gear shaft assembly 680.9.1.6",
     "type": "gear", "subtype": "gear_shaft_assembly", "family": "power_transmission_assembly", "axis": 1,
     "standard": "680.9.1.6", "tags": ["齿轮轴组合", "装配体", "exploded view", "bearing", "circlip", "parallel key"],
     "prompt": "生成机械专利附图风格的齿轮轴组合：以阶梯齿轮轴为中心，依次装配6004轴承、轴用与孔用弹性挡圈、20/27×10定位套筒、6×6×14 A型平键及带键槽的直齿轮；所有回转件同轴，平键连接轴与齿轮，挡圈和轴肩完成轴向定位，并提供装配图和爆炸图。"},
]


def set_axis(spec: dict, index: int) -> None:
    bbox = spec["validation"]["geometry"]["measured"]["bounding_box"]
    center = [(bbox["min"][i] + bbox["max"][i]) / 2 for i in range(3)]
    axis = [0.0, 0.0, 0.0]
    axis[index] = 1.0
    up = [1.0, 0.0, 0.0] if index != 0 else [0.0, 1.0, 0.0]
    for port, sign, edge in zip(spec["ports"], (-1, 1), (bbox["min"], bbox["max"])):
        origin = center.copy()
        origin[index] = edge[index]
        port["frame"] = {"origin": [round(v, 6) for v in origin], "axis": [sign * v for v in axis], "up": up}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--library", type=Path, default=ROOT / "component_library")
    args = parser.parse_args()
    for item in PARTS:
        source_step = args.source / item["step"]
        missing = [name for name in item["images"] if not (args.source / name).exists()]
        if not source_step.exists() or missing:
            raise FileNotFoundError(f"{item['id']}: STEP/JPG 缺失: {missing or source_step}")
        target = args.library / item["id"]
        target.mkdir(parents=True, exist_ok=True)
        identity = {key: item[key] for key in ("id", "name", "name_en", "type", "subtype", "family")}
        spec = step_to_spec(source_step, target / "component.yaml", identity=identity,
                            copy_reference=True, reference_filename="reference.step")
        spec["identity"].update({"standard": item["standard"], "status": "validated", "tags": item["tags"],
                                 "description": item["prompt"]})
        spec["provenance"].update({"source_material_directory": str(args.source),
                                   "standard_refs": [item["standard"]], "data_entry_method": "step_jpg_curated"})
        set_axis(spec, item["axis"])
        for index, image_name in enumerate(item["images"], 1):
            output_name = "preview.jpg" if index == 1 else f"preview-{index}.jpg"
            shutil.copyfile(args.source / image_name, target / output_name)
        spec["artifacts"]["thumbnail"] = {"file": "preview.jpg", "required": True, "sha256": None}
        (target / "component.yaml").write_text(yaml.safe_dump(spec, allow_unicode=True, sort_keys=False), encoding="utf-8")
        print(item["id"])


if __name__ == "__main__":
    main()
