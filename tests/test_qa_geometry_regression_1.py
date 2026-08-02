"""Regression: ISSUE-002 — advanced prompts collapsed to generic geometry.

Found by /qa on 2026-08-02.
Report: .gstack/qa-reports/qa-report-127-0-0-1-2026-08-02.md
"""

from app.component_spec import inspect_shape
from app.llm import local_parse, structural_features
from app.model3d import build_shape


def measured(part_type: str, description: str):
    base = local_parse(description, part_type)
    return inspect_shape(build_shape(part_type, structural_features(description, part_type, base)))


def test_flange_hole_diameter_and_seal_groove_change_brep_topology():
    plain = measured("flange", "法兰外径120mm，内径50mm，厚度22mm，均布6孔")
    grooved = measured("flange", "真空法兰外径120mm，内径50mm，厚度22mm，密封槽宽6mm，均布6孔")
    assert grooved["topology"]["faces"] > plain["topology"]["faces"]


def test_butterfly_and_check_valves_have_distinct_valid_breps():
    butterfly = measured("valve", "电动蝶阀，公称直径DN150，阀板厚度12mm，阀杆直径24mm，法兰式安装")
    check = measured("valve", "止回阀，公称直径DN80，阀体长度260mm，旋启式阀瓣和双端连接")
    assert butterfly["valid_solid"] and check["valid_solid"]
    assert butterfly["topology"]["faces"] != check["topology"]["faces"]


def test_hollow_splined_shaft_has_bore_and_spline_faces():
    plain = measured("shaft", "传动轴总长520mm，外径80mm")
    featured = measured("shaft", "空心传动轴，总长520mm，外径80mm，内径42mm，两端设置花键")
    assert featured["volume_mm3"] < plain["volume_mm3"]
    assert featured["topology"]["faces"] > plain["topology"]["faces"] + 50
    assert featured["topology"]["solids"] == 1


def test_helical_gear_is_one_solid_and_has_axially_staggered_teeth():
    straight = measured("gear", "直齿轮，模数4，齿数42，齿宽45mm")
    helical = measured("gear", "斜齿轮，模数4，齿数42，螺旋角15度，齿宽45mm")
    assert helical["topology"]["solids"] == 1
    assert helical["topology"]["faces"] > straight["topology"]["faces"] * 2


def test_coupling_variants_and_seal_features_materialize_as_geometry():
    for description in (
        "刚性法兰联轴器，外径120mm，总长100mm，轴孔35mm，均布6个连接螺栓",
        "弹性联轴器，外径95mm，总长130mm，两端轴孔分别为28mm和32mm",
        "膜片联轴器，外径68mm，总长82mm，轴孔20mm，包含双膜片组",
    ):
        assert measured("coupling", description)["topology"]["solids"] == 1
    plain = measured("seal", "密封件外径110mm，内径65mm，宽度16mm")
    grooved = measured("seal", "轴端密封件外径110mm，内径65mm，宽度16mm，带环形密封槽宽4mm")
    assert grooved["topology"]["faces"] > plain["topology"]["faces"]
