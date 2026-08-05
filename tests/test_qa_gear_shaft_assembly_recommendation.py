"""Regression coverage for the curated 680.9.1.6 gear-shaft assembly."""

from app.component_library import recommend_component_instances


PROMPT = (
    "生成机械专利附图风格的齿轮轴组合：以阶梯齿轮轴为中心，依次装配6004轴承、"
    "轴用与孔用弹性挡圈、20/27×10定位套筒、6×6×14 A型平键及带键槽的直齿轮；"
    "所有回转件同轴，平键连接轴与齿轮，挡圈和轴肩完成轴向定位，并提供装配图和爆炸图。"
)


def test_curated_gear_shaft_assembly_is_selected_from_natural_language():
    result = recommend_component_instances(PROMPT, limit=32)

    assert result["component_ids"] == [
        "stepped-gear-shaft-d20-l88-680-9-1-6",
        "bearing-6004-2z-gbt276",
        "circlip-external-gbt894-1-d20",
        "circlip-internal-gbt893-1-d42",
        "sleeve-d20-d27-l10-680-9-1-3",
        "parallel-key-gbt1096-a6x6x14",
        "spur-gear-keyed-bore20-od48-w16-680-9-1-3",
    ]
    assert result["capability"] == "ready"
    assert len(result["assembly_relations"]) == 6
