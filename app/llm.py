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

    if part_type in {"bearing", "flange", "seal"}:
        normalized["inner_diameter"] = min(normalized["inner_diameter"], normalized["outer_diameter"] * .9)
    elif part_type == "coupling":
        normalized["bore"] = min(normalized["bore"], normalized["outer_diameter"] * .82)
    elif part_type == "gear":
        root_diameter = normalized["module"] * normalized["teeth"] * .84
        normalized["bore"] = min(normalized["bore"], root_diameter * .8)
    return normalized


def local_recommend(description: str) -> list[str]:
    return [key for key, pattern in ELEMENT_PATTERNS.items() if re.search(pattern, description, re.I)]


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
                json={"model": os.getenv("MOONSHOT_MODEL", "kimi-k2.6"), "messages": [{"role": "user", "content": prompt}], "response_format": {"type": "json_object"}},
            )
            response.raise_for_status()
            parsed = json.loads(response.json()["choices"][0]["message"]["content"])
            allowed = set(LABELS)
            elements = [item for item in parsed.get("elements", []) if item in allowed]
            return list(dict.fromkeys(elements)), "moonshot", None
    except httpx.TimeoutException:
        return fallback, "local-fallback", "Kimi 分类请求超时"
    except httpx.HTTPStatusError as exc:
        return fallback, "local-fallback", f"Kimi API 返回 {exc.response.status_code}"
    except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
        return fallback, "local-fallback", f"分类响应解析失败（{type(exc).__name__}）"


def local_parse(description: str, part_type: str) -> dict[str, Any]:
    params = dict(DEFAULTS[part_type])
    numbers = [float(v) for v in re.findall(r"(?<![A-Za-z0-9])(\d+(?:\.\d+)?)(?:\s*(?:mm|毫米))?(?![A-Za-z0-9])", description, re.I)]
    keys = list(params)
    for key, value in zip(keys, numbers):
        params[key] = int(value) if float(value).is_integer() else value
    patterns = {
        "outer_diameter": r"(?:外径|外圆直径)[^\d]*(\d+(?:\.\d+)?)",
        "inner_diameter": r"(?:内径|孔径)[^\d]*(\d+(?:\.\d+)?)",
        "thickness": r"(?:厚度|盘厚|厚)[^\d]*(\d+(?:\.\d+)?)",
        "length": r"(?:长度|总长)[^\d]*(\d+(?:\.\d+)?)",
        "total_length": r"(?:长度|总长)[^\d]*(\d+(?:\.\d+)?)",
        "teeth": r"(?:齿数|(\d+)\s*齿)[^\d]*(\d+)?",
        "bolt_holes": r"(?:(?:螺栓孔|连接孔|安装孔|孔数)[^\d]*(\d+)|(\d+)\s*个?(?:螺栓孔|连接孔|安装孔|孔))",
    }
    for key, pattern in patterns.items():
        if key in params and (match := re.search(pattern, description)):
            value = next(group for group in match.groups() if group is not None)
            params[key] = int(float(value))
    if part_type == "flange":
        if match := re.search(r"(?:公称直径\s*(?:DN)?|DN)\s*(\d+(?:\.\d+)?)", description, re.I):
            params["inner_diameter"] = float(match.group(1))
        if re.search(r"带颈|对焊|高颈|weld\s*neck", description, re.I):
            params["neck_height"] = max(float(params["thickness"]) * 2.5, float(params["outer_diameter"]) * .28)
    return normalize_parameters(part_type, params)


async def parse_parameters(description: str, part_type: str, use_ai: bool) -> tuple[dict[str, Any], str, str | None]:
    fallback = local_parse(description, part_type)
    api_key = os.getenv("MOONSHOT_API_KEY")
    if not use_ai or not api_key:
        return fallback, "local", "用户关闭智能解析" if not use_ai else "未配置 API Key"
    prompt = (
        f"你是机械设计参数提取器。零件类型：{LABELS[part_type]}。"
        f"只返回 JSON 对象，字段必须且只能是：{list(fallback)}。"
        f"缺失值使用这些默认值：{json.dumps(fallback, ensure_ascii=False)}。"
        "所有尺寸单位统一为 mm，数量为整数。描述如下：\n" + description
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
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            extracted = {key: parsed.get(key, value) for key, value in fallback.items()}
            normalized = normalize_parameters(part_type, extracted)
            if part_type == "flange" and fallback.get("neck_height", 0) > 0:
                normalized["neck_height"] = max(normalized["neck_height"], fallback["neck_height"])
            return normalized, "moonshot", None
    except httpx.TimeoutException as exc:
        logger.warning("Moonshot parameter parsing timed out: %s", type(exc).__name__)
        return fallback, "local-fallback", "Kimi 请求超时"
    except httpx.HTTPStatusError as exc:
        logger.warning("Moonshot parameter parsing HTTP %s", exc.response.status_code)
        return fallback, "local-fallback", f"Kimi API 返回 {exc.response.status_code}"
    except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
        logger.warning("Moonshot parameter parsing failed: %s", type(exc).__name__)
        return fallback, "local-fallback", f"响应解析失败（{type(exc).__name__}）"
