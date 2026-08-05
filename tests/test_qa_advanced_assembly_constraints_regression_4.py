"""Regression: advanced assembly constraints were previously unsupported.

Found by /qa on 2026-08-05.
Report: .gstack/qa-reports/qa-report-127-0-0-1-2026-08-05-advanced-constraints.md
"""

from pathlib import Path

import pytest

from app.assembly import automatic_manifest, build_assembly
from app.component_library import recommend_component_instances
from app.model3d import assembly_to_model


ROOT = Path(__file__).parents[1]
LIBRARY = ROOT / "component_library"


CASES = (
    ("gear", "生成模数1的20齿和40齿直齿轮啮合，计算中心距", 2, "gear_mesh"),
    ("gear", "设计m=1、20齿主动轮和40齿从动轮的外啮合传动并标注中心距", 2, "gear_mesh"),
    ("gear", "绘制模数 1 的 20 齿与 40 齿圆柱齿轮啮合装配", 2, "gear_mesh"),
    ("belt", "生成GT2同步带传动，20齿和40齿同步带轮带张紧轮，计算闭合包络和中心距", 3, "belt_envelope"),
    ("belt", "设计20齿主动同步带轮、40齿从动轮及惰轮组成的GT2闭合包络", 3, "belt_envelope"),
    ("belt", "绘制同步带机构：GT2 20齿轮、40齿轮和张紧轮，标示同步带包络", 3, "belt_envelope"),
    ("chain", "生成25号链轮与链条闭合包络装配", 2, "chain_envelope"),
    ("chain", "设计两个25号sprocket并计算roller chain闭合包络", 2, "chain_envelope"),
    ("chain", "绘制25 号链轮链条传动，要求链条正确包络并闭合", 2, "chain_envelope"),
    ("branch", "生成空间分支装配，包含NEMA17步进电机、安装板、联轴器和同步带轮", 4, "spatial_branch"),
    ("branch", "以安装板为根建立空间分支：NEMA 17电机、刚性联轴器和同步带轮分别布置", 4, "spatial_branch"),
    ("branch", "绘制步进电机空间分支组件，安装板连接电机、联轴器及同步带轮", 4, "spatial_branch"),
)


@pytest.mark.parametrize(("family", "prompt", "count", "constraint_type"), CASES)
def test_natural_language_resolves_to_solved_constraint_manifest(family, prompt, count, constraint_type):
    recommendation = recommend_component_instances(prompt, limit=32)
    assert len(recommendation["component_ids"]) == count, family
    manifest = automatic_manifest(recommendation["component_ids"], LIBRARY, description=prompt)
    assert manifest.solved_constraints[0]["type"] == constraint_type
    assert len({str(component.placement) for component in manifest.components}) == count


def test_gear_mesh_uses_pitch_circle_center_distance_and_expected_contact():
    prompt = CASES[0][1]
    ids = recommend_component_instances(prompt, 32)["component_ids"]
    _, report = build_assembly(automatic_manifest(ids, LIBRARY, description=prompt))
    constraint = report["solved_constraints"][0]
    assert {key: constraint[key] for key in ("type", "module", "teeth", "center_distance_mm", "ratio")} == {
        "type": "gear_mesh", "module": 1.0, "teeth": [20, 40], "center_distance_mm": 30.0, "ratio": 2.0,
    }
    assert report["instances"][1]["transform"][0][3] == 30.0
    assert report["quality"]["pair_checks"][0]["expected_contact"] is True
    assert report["quality"]["interference_free"] is True


@pytest.mark.parametrize(("index", "virtual_id"), ((3, "gt2-timing-belt-envelope"), (6, "roller-chain-envelope")))
def test_belt_and_chain_envelopes_are_closed_and_enter_3d_model(index, virtual_id):
    prompt = CASES[index][1]
    ids = recommend_component_instances(prompt, 32)["component_ids"]
    _, report = build_assembly(automatic_manifest(ids, LIBRARY, description=prompt))
    assert report["envelopes"][0]["closed_length_mm"] > 0
    assert report["solved_constraints"][0]["tangent_segments"] == 2
    assert assembly_to_model(report)[-1]["component_id"] == virtual_id


def test_spatial_branch_has_one_root_and_three_independent_targets():
    prompt = CASES[9][1]
    ids = recommend_component_instances(prompt, 32)["component_ids"]
    _, report = build_assembly(automatic_manifest(ids, LIBRARY, description=prompt))
    constraint = report["solved_constraints"][0]
    assert constraint["root"] == 0
    assert constraint["targets"] == [1, 2, 3]
    assert constraint["axes"] == ["Z", "X", "Y"]
