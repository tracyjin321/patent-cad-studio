"""Data-driven natural-language templates for executable component assemblies."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class AssemblyTemplate:
    id: str
    required_patterns: tuple[str, ...]
    components: tuple[tuple[str, str], ...]
    relations: tuple[tuple[int, int, str], ...]

    def matches(self, text: str) -> bool:
        return all(re.search(pattern, text, re.I) for pattern in self.required_patterns)


ASSEMBLY_TEMPLATES = (
    AssemblyTemplate(
        id="gear-shaft-680-9-1-6",
        required_patterns=(
            r"(?:680[.．]9[.．]1[.．]6|齿轮轴组合|阶梯齿轮轴)",
            r"6004(?:-?2Z)?(?:轴承)?",
            r"(?:平键|键槽)",
            r"(?:直齿轮|圆柱齿轮)",
        ),
        components=(
            ("stepped-gear-shaft-d20-l88-680-9-1-6", "中心阶梯齿轮轴"),
            ("bearing-6004-2z-gbt276", "6004-2Z 深沟球轴承"),
            ("circlip-external-gbt894-1-d20", "20 mm 轴用弹性挡圈"),
            ("circlip-internal-gbt893-1-d42", "42 mm 孔用弹性挡圈"),
            ("sleeve-d20-d27-l10-680-9-1-3", "20/27×10 定位套筒"),
            ("parallel-key-gbt1096-a6x6x14", "6×6×14 A 型平键"),
            ("spur-gear-keyed-bore20-od48-w16-680-9-1-3", "带键槽直齿轮"),
        ),
        relations=(
            (0, 1, "轴承与阶梯轴同轴配合"),
            (0, 2, "轴用挡圈在轴槽内轴向定位"),
            (1, 3, "孔用挡圈约束轴承外圈"),
            (0, 4, "定位套筒套装于轴并抵住轴肩"),
            (0, 5, "平键装入轴键槽"),
            (5, 6, "平键连接轴与带键槽直齿轮"),
        ),
    ),
    AssemblyTemplate(
        id="micro-shaft-bearing-coupler",
        required_patterns=(
            r"(?:直径\s*3\s*mm|3\s*mm|D3|φ\s*3).*?(?:精密轴|光轴|输出轴)",
            r"608(?:深沟球)?轴承",
            r"(?:3\s*(?:mm)?\s*(?:对|到|[-/])\s*3\s*(?:mm)?|D3[-/]D3)?.*?(?:刚性|夹紧)?联轴器",
        ),
        components=(
            ("precision-shaft-d03-l0050-chamfered", "直径 3 mm 精密光轴"),
            ("bearing-608-open-simple", "608 深沟球轴承"),
            ("shaft-coupler-rigid-clamp-d03-d03-simple", "3 mm 对 3 mm 刚性夹紧联轴器"),
        ),
        relations=((0, 1, "轴承与精密轴同轴配合"), (0, 2, "联轴器夹紧精密轴端")),
    ),
    AssemblyTemplate(
        id="micro-shaft-collar-coupler",
        required_patterns=(
            r"(?:直径\s*3\s*mm|3\s*mm|D3|φ\s*3).*?(?:精密轴|光轴|传动轴)",
            r"(?:3\s*mm|D3)?.*?(?:轴环|轴用定位环|shaft\s*collar)",
            r"(?:刚性|夹紧)?.*?联轴器",
        ),
        components=(
            ("precision-shaft-d03-l0050-chamfered", "直径 3 mm 精密光轴"),
            ("shaft-collar-set-screw-bore-d03-simple", "3 mm 紧定轴环"),
            ("shaft-coupler-rigid-clamp-d03-d03-simple", "3 mm 对 3 mm 刚性夹紧联轴器"),
        ),
        relations=((0, 1, "轴环套装于轴并轴向定位"), (0, 2, "联轴器夹紧精密轴端")),
    ),
)


def match_assembly_template(text: str) -> AssemblyTemplate | None:
    return next((template for template in ASSEMBLY_TEMPLATES if template.matches(text)), None)
