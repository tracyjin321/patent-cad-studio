"""Build a reproducible 75-case prompt suite for large M4 assemblies."""

from __future__ import annotations

import json
from pathlib import Path


LENGTHS = (8, 10, 12, 16, 20)
WASHER_COUNTS = (4, 5, 6, 7, 8)
PROMPT_FORMS = (
    "生成一套 {total} 图元 M4 紧固组件：1 个 ISO 4762 M4×{length} 内六角圆柱头螺钉、{washers} 个 M4 平垫圈和 1 个 M4 六角螺母，按轴向顺序装配。",
    "装配 ISO 4762 / GB/T 70.1 M4x{length} 内六角螺钉 1 个，M4 flat washer {washers} 个，M4 hex nut 1 个；共 {total} 件并同轴贴合。",
    "需要 1 件 GB/T 70.1 M4*{length} 内六角圆柱头螺钉；{washers} 枚 M4 平垫；1 枚 M4 六角螺母。请按螺钉→垫圈→螺母形成 {total} 图元装配。",
)


def build_cases() -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    sequence = 0
    for length in LENGTHS:
        for washers in WASHER_COUNTS:
            expected = [
                f"gbt70-1-shcs-m4-l{length:04d}",
                *(["flat-washer-normal-m4-simple"] * washers),
                "iso4032-hex-nut-m4",
            ]
            for form_index, form in enumerate(PROMPT_FORMS, 1):
                sequence += 1
                cases.append(
                    {
                        "id": f"LARGE-M4-{sequence:03d}",
                        "prompt_form": form_index,
                        "prompt": form.format(length=length, washers=washers, total=washers + 2),
                        "expected_component_ids": expected,
                        "expected_instance_count": washers + 2,
                    }
                )
    return cases


def main() -> None:
    output = Path(__file__).parents[1] / "docs" / "assembly-prompts-over-5-components-2026-08-04.json"
    output.write_text(json.dumps(build_cases(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(build_cases())} prompts to {output}")


if __name__ == "__main__":
    main()
