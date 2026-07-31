import json
import logging
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
    "flange": {"outer_diameter": 180, "inner_diameter": 80, "thickness": 22, "bolt_holes": 8},
    "valve": {"nominal_diameter": 80, "body_length": 210, "height": 240, "ports": 2},
    "shaft": {"total_length": 280, "max_diameter": 70, "steps": 4, "keyway_width": 12},
    "gear": {"module": 3, "teeth": 24, "bore": 32, "face_width": 28},
    "screw": {"length": 300, "diameter": 32, "lead": 10, "starts": 1},
    "coupling": {"outer_diameter": 96, "length": 120, "bore": 32, "bolts": 6},
    "seal": {"outer_diameter": 85, "inner_diameter": 55, "width": 12, "lip_count": 2},
}


def local_parse(description: str, part_type: str) -> dict[str, Any]:
    params = dict(DEFAULTS[part_type])
    numbers = [float(v) for v in re.findall(r"(?<![A-Za-z])(\d+(?:\.\d+)?)\s*(?:mm|毫米)?", description, re.I)]
    keys = list(params)
    for key, value in zip(keys, numbers):
        params[key] = int(value) if float(value).is_integer() else value
    patterns = {
        "outer_diameter": r"(?:外径|外圆直径)[^\d]*(\d+(?:\.\d+)?)",
        "inner_diameter": r"(?:内径|孔径)[^\d]*(\d+(?:\.\d+)?)",
        "length": r"(?:长度|总长)[^\d]*(\d+(?:\.\d+)?)",
        "total_length": r"(?:长度|总长)[^\d]*(\d+(?:\.\d+)?)",
        "teeth": r"(?:齿数|(\d+)\s*齿)[^\d]*(\d+)?",
        "bolt_holes": r"(?:螺栓孔|孔数)[^\d]*(\d+)",
    }
    for key, pattern in patterns.items():
        if key in params and (match := re.search(pattern, description)):
            value = next(group for group in match.groups() if group is not None)
            params[key] = int(float(value))
    return params


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
            return {key: parsed.get(key, value) for key, value in fallback.items()}, "moonshot", None
    except httpx.TimeoutException as exc:
        logger.warning("Moonshot parameter parsing timed out: %s", type(exc).__name__)
        return fallback, "local-fallback", "Kimi 请求超时"
    except httpx.HTTPStatusError as exc:
        logger.warning("Moonshot parameter parsing HTTP %s", exc.response.status_code)
        return fallback, "local-fallback", f"Kimi API 返回 {exc.response.status_code}"
    except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
        logger.warning("Moonshot parameter parsing failed: %s", type(exc).__name__)
        return fallback, "local-fallback", f"响应解析失败（{type(exc).__name__}）"
