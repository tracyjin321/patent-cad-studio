from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any
import re

import yaml


ROOT = Path(__file__).resolve().parent.parent
LIBRARY = ROOT / "component_library"

CATEGORY_DEFINITIONS = (
    ("fasteners", "连接与紧固", {"fastener", "pin", "nut", "spacer"}),
    ("shaft_support", "轴系与支承", {"bearing", "shaft", "hub"}),
    ("transmission", "传动件", {"gear", "pulley", "sprocket", "screw", "coupling"}),
    ("motion", "直线运动", {"motion"}),
    ("structure", "支撑与结构", {"stock", "profile", "hardware"}),
    ("actuation", "动力与执行", {"actuator"}),
    ("aerospace", "航天器结构", {"rocket"}),
)

SUBTYPE_LABELS = {
    "nema_stepper": "步进电机", "deep_groove_ball": "深沟球轴承", "flanged_ball": "法兰轴承",
    "linear_bearing": "直线轴承", "linear_bearing_block": "直线轴承座", "linear_bearing_housing": "直线轴承座",
    "oldham": "十字滑块联轴器", "shaft_coupling": "轴联轴器", "button_head_screw": "圆头内六角螺钉",
    "countersunk_screw": "沉头内六角螺钉", "extrusion_nut": "型材锤头螺母", "flat_washer": "平垫圈",
    "hex_head_cap_screw": "六角头螺栓", "hex_nut": "六角螺母", "set_screw": "紧定螺钉",
    "socket_head_cap_screw": "圆柱头内六角螺钉", "spring_washer": "弹簧垫圈", "bevel_gear": "锥齿轮",
    "gear_rack": "齿条", "spur_gear": "直齿圆柱齿轮", "control_knob": "星形旋钮",
    "extrusion_bracket": "型材电机安装板", "shaft_hub": "夹紧式轮毂", "linear_rail": "直线导轨",
    "lead_screw_nut": "丝杠螺母", "dowel_pin": "圆柱销", "t_slot_extrusion": "T型槽铝型材",
    "v_slot_extrusion": "V型槽铝型材", "belt_pulley": "皮带轮", "timing_idler": "同步带惰轮",
    "timing_pulley": "同步带轮", "ball_screw": "滚珠丝杠", "lead_screw": "梯形丝杠",
    "ground_shaft": "精密光轴", "shaft_collar": "紧定轴环", "stepped_shaft": "阶梯轴",
    "first_stage": "一级火箭", "grid_fin_set": "栅格翼组件", "interstage": "级间段",
    "second_stage": "二级火箭", "payload_fairing": "有效载荷整流罩",
    "round_spacer": "圆柱隔离柱", "threaded_standoff": "六角隔离柱", "roller_chain": "滚子链轮",
    "roller_chain_drive": "滚子链传动轮", "angle_bar": "等边角钢", "plate_blank": "矩形板坯",
}


def _contains_chinese(value: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", value))


def _category(component_type: str) -> tuple[str, str]:
    for category_id, label, types in CATEGORY_DEFINITIONS:
        if component_type in types:
            return category_id, label
    return "other", "其他图元"


@lru_cache(maxsize=1)
def load_components() -> tuple[dict[str, Any], ...]:
    catalog = yaml.safe_load((LIBRARY / "catalog.yaml").read_text(encoding="utf-8"))
    entries = catalog.get("components", catalog) if isinstance(catalog, dict) else catalog
    components: list[dict[str, Any]] = []
    for entry in entries:
        identity: dict[str, Any] = {}
        spec_path = LIBRARY / entry["spec"]
        if spec_path.is_file():
            spec = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
            identity = spec.get("identity", {})
        component_type = str(entry.get("type") or identity.get("type") or "other")
        category_id, category_label = _category(component_type)
        original_name = identity.get("name") or entry.get("name") or entry["id"]
        display_name = original_name if _contains_chinese(original_name) else SUBTYPE_LABELS.get(str(entry.get("subtype") or identity.get("subtype")), "机械图元")
        components.append({
            "id": entry["id"],
            "name": display_name,
            "name_en": identity.get("name_en") or (original_name if original_name != display_name else None),
            "type": component_type,
            "subtype": entry.get("subtype") or identity.get("subtype"),
            "subtype_label": SUBTYPE_LABELS.get(str(entry.get("subtype") or identity.get("subtype")), "机械图元"),
            "category": category_id,
            "category_label": category_label,
            "version": entry.get("version") or identity.get("version"),
            "status": entry.get("status") or identity.get("status"),
            "description": identity.get("description"),
            "tags": identity.get("tags") or [],
        })
    return tuple(components)


def query_components(query: str = "", category: str = "") -> dict[str, Any]:
    all_components = load_components()
    category_order = {category_id: index for index, (category_id, _, _) in enumerate(CATEGORY_DEFINITIONS)}
    needle = query.strip().casefold()
    items = []
    for component in all_components:
        if category and component["category"] != category:
            continue
        searchable = " ".join(str(value) for value in (
            component["id"], component["name"], component.get("name_en") or "",
            component["type"], component.get("subtype") or "",
            component.get("description") or "", *(component.get("tags") or []),
        )).casefold()
        if needle and needle not in searchable:
            continue
        items.append(component)
    items.sort(key=lambda item: (category_order.get(item["category"], len(category_order)), item["name"].casefold(), item["id"]))

    category_counts = {category_id: 0 for category_id, _, _ in CATEGORY_DEFINITIONS}
    category_counts["other"] = 0
    for component in all_components:
        category_counts[component["category"]] += 1
    categories = [
        {"id": category_id, "label": label, "count": category_counts[category_id]}
        for category_id, label, _ in CATEGORY_DEFINITIONS
        if category_counts[category_id]
    ]
    if category_counts["other"]:
        categories.append({"id": "other", "label": "其他图元", "count": category_counts["other"]})
    return {"items": items, "categories": categories, "total": len(all_components), "filtered": len(items)}


def components_by_id(component_ids: list[str]) -> list[dict[str, Any]]:
    index = {component["id"]: component for component in load_components()}
    missing = [component_id for component_id in component_ids if component_id not in index]
    if missing:
        raise KeyError(", ".join(missing))
    return [index[component_id] for component_id in component_ids]
