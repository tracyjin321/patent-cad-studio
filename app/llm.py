import json
import logging
import math
import os
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)


LABELS = {
    "bearing": "轴承",
    "flange": "法兰",
    "valve": "阀门",
    "shaft": "轴系",
    "gear": "齿轮",
    "screw": "丝杠",
    "coupling": "联轴器",
    "seal": "密封件",
    "rocket": "运载火箭",
}

DEFAULTS: dict[str, dict[str, float | int | str]] = {
    "bearing": {"outer_diameter": 100, "inner_diameter": 45, "width": 25, "rolling_elements": 10},
    "flange": {"outer_diameter": 180, "inner_diameter": 80, "thickness": 22, "bolt_holes": 8, "neck_height": 0},
    "valve": {"nominal_diameter": 80, "body_length": 210, "height": 240, "ports": 2},
    "shaft": {"total_length": 280, "max_diameter": 70, "steps": 4, "keyway_width": 12},
    "gear": {"module": 3, "teeth": 24, "bore": 32, "face_width": 28},
    "screw": {"length": 300, "diameter": 32, "lead": 10, "starts": 1},
    "coupling": {"outer_diameter": 96, "length": 120, "bore": 32, "bolts": 6},
    "seal": {"outer_diameter": 85, "inner_diameter": 55, "width": 12, "lip_count": 2},
    "rocket": {
        "total_height": 70000.0, "body_diameter": 3660.0, "fairing_diameter": 5200.0,
        "fairing_height": 13100.0, "engine_count": 9, "engine_nozzle_diameter": 920.0,
        "grid_fin_count": 4, "landing_leg_count": 4, "ring_count": 4,
    },
}

FEATURE_DEFAULTS = {
    "bearing": {"variant": 0}, "flange": {"bolt_hole_diameter": 0, "groove_width": 0},
    "valve": {"variant": 0, "disc_thickness": 0, "stem_diameter": 0, "actuator": 0},
    "shaft": {"inner_diameter": 0, "spline_ends": 0, "keyway_present": 0},
    "gear": {"helix_angle": 0, "keyway_width": 0, "spline_bore": 0},
    "screw": {"variant": 0}, "coupling": {"variant": 0, "bore_b": 32, "membrane_count": 0},
    "seal": {"groove_width": 0},
    "rocket": {},
}

ELEMENT_PATTERNS = {
    "bearing": r"轴承|滚珠|滚子|轴瓦|支承座|bearing",
    "flange": r"法兰|法兰盘|连接盘|突缘|flange",
    "valve": r"阀门|阀体|闸阀|截止阀|蝶阀|球阀|止回阀|调节阀|valve",
    "shaft": r"轴系|主轴|传动轴|输入轴|输出轴|阶梯轴|转轴|轴肩|shaft",
    "gear": r"齿轮|齿圈|轮齿|齿数|模数|gear",
    "screw": r"丝杠|丝杆|螺杆|导程|滚珠丝杠|screw",
    "coupling": r"联轴器|联轴节|轴联接|coupling",
    "seal": r"密封件|密封圈|油封|密封环|密封唇|seal",
    "rocket": r"猎鹰九号|猎鹰9号|Falcon\s*9|运载火箭|火箭",
}

COUNT_LIMITS = {
    "rolling_elements": (6, 18),
    "bolt_holes": (4, 16),
    "ports": (2, 8),
    "steps": (3, 6),
    "teeth": (10, 64),
    "starts": (1, 3),
    "bolts": (4, 12),
    "lip_count": (1, 3),
    "engine_count": (1, 9),
    "grid_fin_count": (0, 4),
    "landing_leg_count": (0, 4),
    "ring_count": (0, 6),
}


def normalize_parameters(part_type: str, values: dict[str, Any]) -> dict[str, Any]:
    """Return the exact safe dimensions used by SVG, mesh and STEP generation."""
    defaults = DEFAULTS[part_type]
    normalized: dict[str, Any] = {}
    for key, default in defaults.items():
        candidate = values.get(key, default)
        try:
            number = float(candidate)
        except (TypeError, ValueError):
            number = float(default)
        if not math.isfinite(number) or number <= 0:
            number = float(default)
        if key in COUNT_LIMITS:
            lower, upper = COUNT_LIMITS[key]
            normalized[key] = max(lower, min(upper, int(round(number))))
        elif isinstance(default, int):
            normalized[key] = int(round(number))
        else:
            normalized[key] = round(number, 6)
    for key, default in FEATURE_DEFAULTS.get(part_type, {}).items():
        if key not in values:
            continue
        try: number = float(values[key])
        except (TypeError, ValueError): number = float(default)
        if not math.isfinite(number) or number < 0: number = float(default)
        normalized[key] = int(round(number)) if isinstance(default, int) else round(number, 6)

    if part_type in {"bearing", "flange", "seal"}:
        normalized["inner_diameter"] = min(normalized["inner_diameter"], normalized["outer_diameter"] * .9)
    elif part_type == "coupling":
        normalized["bore"] = min(normalized["bore"], normalized["outer_diameter"] * .82)
    elif part_type == "gear":
        root_diameter = normalized["module"] * normalized["teeth"] * .84
        normalized["bore"] = min(normalized["bore"], root_diameter * .8)
    elif part_type == "rocket":
        normalized["total_height"] = max(20000.0, min(100000.0, normalized["total_height"]))
        normalized["body_diameter"] = max(1000.0, min(10000.0, normalized["body_diameter"]))
        normalized["fairing_diameter"] = max(normalized["body_diameter"], normalized["fairing_diameter"])
        normalized["fairing_height"] = min(normalized["fairing_height"], normalized["total_height"] * .35)
        normalized["engine_nozzle_diameter"] = min(normalized["engine_nozzle_diameter"], normalized["body_diameter"] * .32)
    return normalized


def local_recommend(description: str) -> list[str]:
    return [key for key, pattern in ELEMENT_PATTERNS.items() if re.search(pattern, description, re.I)]


def _json_schema_format(name: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    """Return the Kimi Structured Output envelope for a strict JSON object."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "strict": True,
            "schema": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


def _completion_object(response: httpx.Response) -> dict[str, Any]:
    response.raise_for_status()
    payload = response.json()
    choice = payload["choices"][0]
    if choice.get("finish_reason") != "stop":
        raise ValueError(f"Kimi 未完整结束响应: {choice.get('finish_reason')}")
    content = choice["message"]["content"]
    if not isinstance(content, str):
        raise TypeError("Kimi content 必须是字符串")
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise TypeError("Kimi Structured Output 必须是 JSON 对象")
    return parsed


def _fallback_detail(exc: Exception, feature: str) -> str:
    if isinstance(exc, httpx.ConnectTimeout):
        return f"{feature}连接超时，已自动回退"
    if isinstance(exc, httpx.ReadTimeout):
        return f"{feature}响应超时，已自动回退"
    if isinstance(exc, httpx.RemoteProtocolError):
        return f"{feature}服务通信异常，已自动回退"
    if isinstance(exc, httpx.ConnectError):
        return f"无法连接{feature}服务，已自动回退"
    if isinstance(exc, httpx.HTTPStatusError):
        return f"{feature}服务暂不可用，已自动回退"
    if isinstance(exc, httpx.HTTPError):
        return f"{feature}服务通信异常，已自动回退"
    return f"{feature}结果格式异常，已自动回退"


async def recommend_core_elements(description: str, use_ai: bool) -> tuple[list[str], str, str | None]:
    fallback = local_recommend(description)
    api_key = os.getenv("MOONSHOT_API_KEY")
    if not use_ai or not api_key:
        return fallback, "local", "用户关闭智能识别" if not use_ai else "未配置 API Key"
    prompt = (
        "你是机械专利方案的核心图元分类器。根据技术描述，从下列类别中选择所有明确出现或结构上必要的类别："
        + json.dumps(LABELS, ensure_ascii=False)
        + "。只返回JSON对象，格式为 {\"elements\":[\"bearing\"]}。不得返回列表外的值；不确定时宁缺毋滥。描述：\n"
        + description
    )
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(40, connect=10)) as client:
            response = await client.post(
                f"{os.getenv('MOONSHOT_BASE_URL', 'https://api.moonshot.cn/v1').rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": os.getenv("MOONSHOT_MODEL", "kimi-k2.6"),
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": _json_schema_format(
                        "core_elements",
                        {"elements": {"type": "array", "items": {"type": "string", "enum": list(LABELS)}}},
                        ["elements"],
                    ),
                    "thinking": {"type": "disabled"},
                    "max_completion_tokens": 128,
                },
            )
            parsed = _completion_object(response)
            if set(parsed) != {"elements"} or not isinstance(parsed["elements"], list):
                raise ValueError("核心图元响应字段不完整")
            allowed = set(LABELS)
            if any(not isinstance(item, str) or item not in allowed for item in parsed["elements"]):
                raise ValueError("核心图元响应包含未注册类别")
            elements = parsed["elements"]
            return list(dict.fromkeys(elements)), "moonshot", None
    except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as exc:
        logger.warning("Moonshot core-element recommendation failed: %r", exc, exc_info=True)
        return fallback, "local-fallback", _fallback_detail(exc, "智能识别")


def local_parse(description: str, part_type: str) -> dict[str, Any]:
    params = dict(DEFAULTS[part_type])
    patterns = {
        "outer_diameter": r"(?:外径|外圆直径)[^\d]*(\d+(?:\.\d+)?)",
        "inner_diameter": r"(?:内径|孔径)[^\d]*(\d+(?:\.\d+)?)",
        "thickness": r"(?:厚度|盘厚|厚)[^\d]*(\d+(?:\.\d+)?)",
        "length": r"(?:长度|总长)[^\d]*(\d+(?:\.\d+)?)",
        "total_length": r"(?:长度|总长)[^\d]*(\d+(?:\.\d+)?)",
        "body_length": r"(?:阀体长度|结构长度|连接长度)[^\d]*(\d+(?:\.\d+)?)",
        "height": r"(?:总高度|阀门高度|阀高|高度)[^\d]*(\d+(?:\.\d+)?)",
        "width": r"(?:宽度|宽)[^\d]*(\d+(?:\.\d+)?)",
        "rolling_elements": r"(?:包含|配置|设有)?\s*(\d+)\s*个?(?:滚珠|滚子)",
        "module": r"模数[^\d]*(\d+(?:\.\d+)?)",
        "teeth": r"(?:齿数|(\d+)\s*齿)[^\d]*(\d+)?",
        "face_width": r"齿宽[^\d]*(\d+(?:\.\d+)?)",
        "bore": r"(?:中心孔直径|轴孔|孔径)[^\d]*(\d+(?:\.\d+)?)",
        "diameter": r"(?:公称直径|直径)[^\d]*(\d+(?:\.\d+)?)",
        "lead": r"导程[^\d]*(\d+(?:\.\d+)?)",
        "max_diameter": r"(?:最大直径|外径)[^\d]*(\d+(?:\.\d+)?)",
        "steps": r"(?:生成|设计|构造)?\s*([三四五六]|\d+)\s*段(?:阶梯轴)?",
        "keyway_width": r"键槽(?:宽度|宽)?[^\d]*(\d+(?:\.\d+)?)",
        "inner_diameter": r"内径[^\d]*(\d+(?:\.\d+)?)",
        "bolt_hole_diameter": r"(?:直径|孔径)\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)?\s*(?:螺栓孔|连接孔|安装孔)",
        "groove_width": r"(?:密封槽|环形密封槽)(?:宽度|宽)?[^\d]*(\d+(?:\.\d+)?)",
        "disc_thickness": r"阀板厚度[^\d]*(\d+(?:\.\d+)?)",
        "stem_diameter": r"阀杆直径[^\d]*(\d+(?:\.\d+)?)",
        "helix_angle": r"螺旋角[^\d]*(\d+(?:\.\d+)?)",
        "bolt_holes": r"(?:(?:螺栓孔|连接孔|安装孔|孔数)[^\d]*(\d+)|(\d+)\s*个?(?:螺栓孔|连接孔|安装孔|孔))",
    }
    for key, pattern in patterns.items():
        if key in params and (match := re.search(pattern, description)):
            value = next(group for group in match.groups() if group is not None)
            chinese = {"三": 3, "四": 4, "五": 5, "六": 6}
            params[key] = chinese[value] if value in chinese else int(float(value))
    if part_type == "flange":
        if match := re.search(r"(?:公称直径\s*(?:DN)?|DN)\s*(\d+(?:\.\d+)?)", description, re.I):
            params["inner_diameter"] = float(match.group(1))
        if re.search(r"带颈|对焊|高颈|weld\s*neck", description, re.I):
            params["neck_height"] = max(float(params["thickness"]) * 2.5, float(params["outer_diameter"]) * .28)
    elif part_type == "valve":
        if match := re.search(r"(?:公称直径\s*(?:DN)?|DN)\s*(\d+(?:\.\d+)?)", description, re.I):
            params["nominal_diameter"] = float(match.group(1))
        if re.search(r"双端|两端|进出口", description):
            params["ports"] = 2
    elif part_type == "shaft":
        if re.search(r"键槽", description) and params["keyway_width"] == DEFAULTS["shaft"]["keyway_width"]:
            params["keyway_width"] = max(2, float(params["max_diameter"]) * .16)
    elif part_type == "screw":
        if re.search(r"单头", description):
            params["starts"] = 1
    elif part_type == "seal":
        if re.search(r"双唇|主密封唇.*防尘唇", description):
            params["lip_count"] = 2
    elif part_type == "rocket":
        rocket_patterns = {
            "total_height": r"(?:全箭总高度|总高度|箭高)[^\d]*(\d+(?:\.\d+)?)\s*(米|m|mm|毫米)?",
            "body_diameter": r"(?:一级/二级箭体|箭体|芯级)(?:外径|直径)[^\d]*(\d+(?:\.\d+)?)\s*(米|m|mm|毫米)?",
            "fairing_diameter": r"整流罩(?:最大)?直径[^\d]*(\d+(?:\.\d+)?)\s*(米|m|mm|毫米)?",
            "fairing_height": r"整流罩(?:总长|高度|长)[^\d]*(\d+(?:\.\d+)?)\s*(米|m|mm|毫米)?",
            "engine_nozzle_diameter": r"喷嘴(?:外径|出口直径)[^\d]*(\d+(?:\.\d+)?)\s*(米|m|mm|毫米)?",
            "engine_count": r"(?:安装|配置)?\s*(\d+)\s*台\s*Merlin",
            "grid_fin_count": r"(?:设有|安装)?\s*(\d+)\s*片[^。；\n]*栅格翼",
            "landing_leg_count": r"(?:设有|安装)?\s*(\d+)\s*(?:条|根)[^。；\n]*着陆腿",
        }
        for key, pattern in rocket_patterns.items():
            if match := re.search(pattern, description, re.I):
                value = float(match.group(1))
                unit = match.group(2) if match.lastindex and match.lastindex >= 2 else None
                if unit and unit.lower() in {"米", "m"}:
                    value *= 1000
                params[key] = int(round(value)) if key in COUNT_LIMITS else value
    return normalize_parameters(part_type, params)


def structural_features(description: str, part_type: str, base: dict[str, Any]) -> dict[str, Any]:
    features = dict(FEATURE_DEFAULTS.get(part_type, {}))
    patterns = {
        "bolt_hole_diameter": r"(?:直径|孔径)\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)?\s*(?:螺栓孔|连接孔|安装孔)",
        "groove_width": r"(?:密封槽|环形密封槽)(?:宽度|宽)?[^\d]*(\d+(?:\.\d+)?)",
        "disc_thickness": r"阀板厚度[^\d]*(\d+(?:\.\d+)?)", "stem_diameter": r"阀杆直径[^\d]*(\d+(?:\.\d+)?)",
        "inner_diameter": r"内径[^\d]*(\d+(?:\.\d+)?)", "helix_angle": r"螺旋角[^\d]*(\d+(?:\.\d+)?)",
    }
    for key, pattern in patterns.items():
        if key in features and (match := re.search(pattern, description, re.I)): features[key] = float(match.group(1))
    if "groove_width" in features and re.search(r"密封槽|环形密封槽", description) and not features["groove_width"]:
        reference = float(base.get("width", base.get("thickness", 10)))
        features["groove_width"] = max(2, reference * .2)
    if part_type == "bearing": features["variant"] = int(bool(re.search(r"调心|滚子", description)))
    elif part_type == "valve":
        features["variant"] = 1 if re.search(r"蝶阀", description) else 2 if re.search(r"止回阀|旋启式", description) else 0
        features["actuator"] = int(bool(re.search(r"电动|执行器|电机", description)))
    elif part_type == "shaft":
        features["spline_ends"] = 2 if re.search(r"两端.*花键|花键.*两端", description) else int(bool(re.search(r"花键", description)))
        features["keyway_present"] = int(bool(re.search(r"键槽", description)))
    elif part_type == "gear":
        features["spline_bore"] = int(bool(re.search(r"花键孔|中心.*花键", description)))
        if re.search(r"键槽", description): features["keyway_width"] = max(2, float(base["bore"]) * .22)
    elif part_type == "screw": features["variant"] = int(bool(re.search(r"滚珠丝杠|滚珠丝杆", description)))
    elif part_type == "coupling":
        features["bore_b"] = base["bore"]
        if match := re.search(r"两端轴孔分别为\s*(\d+(?:\.\d+)?)\s*(?:mm)?\s*和\s*(\d+(?:\.\d+)?)", description, re.I): base["bore"], features["bore_b"] = map(float, match.groups())
        features["variant"] = 1 if re.search(r"弹性", description) else 2 if re.search(r"膜片", description) else 0
        features["membrane_count"] = 2 if re.search(r"双膜片|两组膜片", description) else int(bool(re.search(r"膜片", description)))
    return normalize_parameters(part_type, {**base, **features})


async def parse_parameters(description: str, part_type: str, use_ai: bool) -> tuple[dict[str, Any], str, str | None]:
    fallback = local_parse(description, part_type)
    api_key = os.getenv("MOONSHOT_API_KEY")
    if not use_ai or not api_key:
        return structural_features(description, part_type, fallback), "local", "用户关闭智能解析" if not use_ai else "未配置 API Key"
    prompt = (
        f"你是机械设计参数提取器。零件类型：{LABELS[part_type]}。"
        f"只返回 JSON 对象，字段必须且只能是：{list(fallback)}。"
        f"缺失值使用这些默认值：{json.dumps(fallback, ensure_ascii=False)}。"
        "所有尺寸单位统一为 mm，数量为整数。描述如下：\n" + description
    )
    response_format = _json_schema_format(
        f"{part_type}_parameters",
        {
            key: {"type": "integer" if key in COUNT_LIMITS else "number"}
            for key in fallback
        },
        list(fallback),
    )
    try:
        timeout = httpx.Timeout(65, connect=10)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{os.getenv('MOONSHOT_BASE_URL', 'https://api.moonshot.cn/v1').rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": os.getenv("MOONSHOT_MODEL", "kimi-k2.6"),
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": response_format,
                    "thinking": {"type": "disabled"},
                    "max_completion_tokens": 256,
                },
            )
            parsed = _completion_object(response)
            if set(parsed) != set(fallback):
                raise ValueError("参数响应字段与生成器不匹配")
            if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in parsed.values()):
                raise TypeError("参数响应必须全部为数值")
            normalized = normalize_parameters(part_type, parsed)
            # Explicit deterministic extraction is authoritative for every value
            # named in the prompt, including structural variant flags.
            for key, fallback_value in fallback.items():
                if fallback_value != DEFAULTS[part_type][key]:
                    normalized[key] = fallback_value
            if part_type == "flange" and re.search(r"平焊", description):
                normalized["neck_height"] = 0
            if part_type == "flange" and fallback.get("neck_height", 0) > 0:
                normalized["neck_height"] = max(normalized["neck_height"], fallback["neck_height"])
            elif part_type == "valve":
                # Deterministically parsed explicit dimensions are authoritative;
                # the model may fill only values absent from the prompt.
                explicit_patterns = {
                    "nominal_diameter": r"(?:公称直径\s*(?:DN)?|DN)\s*\d",
                    "body_length": r"(?:阀体长度|结构长度|连接长度)\D*\d",
                    "height": r"(?:总高度|阀门高度|阀高|高度)\D*\d",
                    "ports": r"双端|两端|进出口",
                }
                for key, pattern in explicit_patterns.items():
                    if re.search(pattern, description, re.I):
                        normalized[key] = fallback[key]
            return structural_features(description, part_type, normalized), "moonshot", None
    except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as exc:
        logger.warning("Moonshot parameter parsing failed: %r", exc, exc_info=True)
        return structural_features(description, part_type, fallback), "local-fallback", _fallback_detail(exc, "智能解析")
