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
            "standard": identity.get("standard"),
            "port_types": sorted({str(port.get("type")) for port in spec.get("ports", []) if port.get("type")}),
            "description": identity.get("description"),
            "tags": identity.get("tags") or [],
        })
    return tuple(components)


def query_components(query: str = "", category: str = "") -> dict[str, Any]:
    return structured_query_components(query=query, category=category)


def parse_structured_query(query: str) -> dict[str, Any]:
    """Extract common engineering designations without inventing dimensions."""
    text = query.strip()
    result: dict[str, Any] = {"raw": text, "tokens": re.findall(r"[a-z0-9.]+|[\u3400-\u9fff]+", text.casefold())}
    metric = re.search(r"\bM\s*(\d+(?:\.\d+)?)\s*[x×*]\s*(\d+(?:\.\d+)?)", text, re.I)
    if metric:
        result.update({"metric_thread": f"M{metric.group(1)}", "diameter_mm": float(metric.group(1)), "length_mm": float(metric.group(2))})
    bearing = re.search(r"(?<!\d)(6[0-3]\d{2}|60[0-9]|62[0-9]|63[0-9])(?!\d)", text)
    if bearing:
        result["bearing_series"] = bearing.group(1)
    nema = re.search(r"\bNEMA\s*(\d+)\b", text, re.I)
    if nema:
        result["nema_frame"] = f"NEMA{nema.group(1)}"
    dn = re.search(r"\bDN\s*(\d+)\b", text, re.I)
    if dn:
        result["nominal_diameter"] = f"DN{dn.group(1)}"
    return result


def structured_query_components(
    query: str = "", category: str = "", *, component_type: str = "", subtype: str = "",
    status: str = "", standard: str = "", port_type: str = "", limit: int = 100,
) -> dict[str, Any]:
    all_components = load_components()
    category_order = {category_id: index for index, (category_id, _, _) in enumerate(CATEGORY_DEFINITIONS)}
    parsed = parse_structured_query(query)
    needle = query.strip().casefold()
    items = []
    for component in all_components:
        if category and component["category"] != category:
            continue
        if component_type and component["type"] != component_type:
            continue
        if subtype and component.get("subtype") != subtype:
            continue
        if status and component.get("status") != status:
            continue
        if standard and standard.casefold() not in str(component.get("standard") or "").casefold():
            continue
        if port_type and port_type not in component.get("port_types", []):
            continue
        fields = {
            "id": component["id"], "standard": component.get("standard") or "", "name": component["name"],
            "name_en": component.get("name_en") or "", "subtype": component.get("subtype") or "",
            "tags": " ".join(component.get("tags") or []), "description": component.get("description") or "",
            "type": component["type"],
        }
        searchable = " ".join(str(value) for value in (
            component["id"], component["name"], component.get("name_en") or "",
            component["type"], component.get("subtype") or "",
            component.get("description") or "", *(component.get("tags") or []),
        )).casefold()
        matched = []
        score = 0.0
        if needle:
            for field, weight in (("id", 1.0), ("standard", .95), ("name", .85), ("name_en", .8), ("subtype", .7), ("tags", .55), ("description", .35), ("type", .3)):
                value = str(fields[field]).casefold()
                if needle == value:
                    score, matched = max(score, weight), [f"{field}:exact"]
                elif needle in value:
                    score += weight * .72
                    matched.append(field)
            for token in parsed["tokens"]:
                if token in searchable:
                    score += .08
                    matched.append(token)
        if needle and not matched:
            continue
        item = dict(component)
        item.update({"score": round(min(score if needle else 1.0, 1.0), 4), "matched": list(dict.fromkeys(matched)), "warnings": []})
        items.append(item)
    items.sort(key=lambda item: (-item["score"], category_order.get(item["category"], len(category_order)), item["name"].casefold(), item["id"]))

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
    disposition = "exact_match" if items and items[0]["score"] >= .7 else "candidate_match" if items else "parametric_generation" if any(key in parsed for key in ("metric_thread", "bearing_series", "nema_frame", "nominal_diameter")) else "backlog_required"
    return {"items": items[:max(1, min(limit, 200))], "categories": categories, "total": len(all_components), "filtered": len(items), "parsed_query": parsed, "disposition": disposition,
            "recommendation": {"reason": "按 ID、标准号、名称、子类型、标签和描述加权排序", "next_action": disposition}}


def components_by_id(component_ids: list[str]) -> list[dict[str, Any]]:
    index = {component["id"]: component for component in load_components()}
    missing = [component_id for component_id in component_ids if component_id not in index]
    if missing:
        raise KeyError(", ".join(missing))
    return [index[component_id] for component_id in component_ids]


def recommend_component_instances(description: str, limit: int = 16) -> dict[str, Any]:
    """Resolve explicit standard-part mentions into concrete library instances."""
    text = description.strip()
    parsed = parse_structured_query(text)
    thread = parsed.get("metric_thread")
    length = parsed.get("length_mm")
    index = {component["id"]: component for component in load_components()}
    recommendations: list[dict[str, Any]] = []

    def quantity_near(pattern: str, default: int = 1) -> int:
        # Do not reinterpret the numeric part of a designation such as ``M4``
        # as the requested quantity when the count follows the component name.
        match = re.search(rf"(?<![A-Za-z0-9.])(\d+)\s*(?:个|枚|件)?\s*(?:{pattern})", text, re.I)
        if not match:
            match = re.search(rf"(?:{pattern})\s*(\d+)\s*(?:个|枚|件)", text, re.I)
        return max(1, min(int(match.group(1)), limit)) if match else default

    def add(component_id: str, quantity: int, reason: str) -> None:
        if component_id not in index or quantity < 1:
            return
        remaining = limit - sum(item["quantity"] for item in recommendations)
        if remaining > 0:
            recommendations.append({"component": index[component_id], "quantity": min(quantity, remaining), "reason": reason})

    if thread and length is not None and re.search(r"内六角圆柱头|圆柱头内六角|ISO\s*4762|GB/?T\s*70\.1", text, re.I):
        size = thread[1:].replace(".", "p")
        add(
            f"gbt70-1-shcs-m{size}-l{int(length):04d}",
            quantity_near(rf"(?:GB/?T\s*70\.1\s*/?\s*)?(?:ISO\s*4762\s*)?(?:{re.escape(thread)}\s*[x×*]\s*{int(length)}\s*)?(?:内六角圆柱头螺钉|内六角螺钉|螺钉)", 1),
            f"标准号与规格精确命中 {thread}×{int(length)}",
        )
    if thread == "M4" and re.search(r"平垫圈|平垫|flat\s*washer", text, re.I):
        add(
            f"flat-washer-normal-{thread.casefold()}-simple",
            quantity_near(rf"(?:{re.escape(thread)}\s*)?(?:平垫圈|平垫|flat\s*washer)", 1),
            f"同螺纹规格平垫圈 {thread}",
        )
    if thread == "M4" and re.search(r"六角螺母|hex\s*nut", text, re.I):
        add(
            f"iso4032-hex-nut-{thread.casefold()}",
            quantity_near(rf"(?:{re.escape(thread)}\s*)?(?:六角螺母|hex\s*nut)", 1),
            f"同螺纹规格六角螺母 {thread}",
        )

    component_ids = [item["component"]["id"] for item in recommendations for _ in range(item["quantity"])]
    relations = []
    if len(component_ids) > 1:
        relations = [
            {"source": component_ids[index - 1], "target": component_id, "relation": "按描述顺序相邻装配"}
            for index, component_id in enumerate(component_ids[1:], 1)
        ]
    return {
        "component_ids": component_ids,
        "items": recommendations,
        "parser": "structured-library",
        "limit": limit,
        "missing_components": [],
        "assembly_relations": relations,
        "capability": "ready" if component_ids else "parametric_generation",
        "parser_detail": None,
    }
