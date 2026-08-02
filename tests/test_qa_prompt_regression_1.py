"""Regression: ISSUE-001 — explicit prompt semantics were assigned by number order.

Found by /qa on 2026-08-02.
Report: .gstack/qa-reports/qa-report-127-0-0-1-2026-08-02.md
"""

from app.llm import local_parse, structural_features


def test_all_advanced_example_prompts_preserve_named_and_structural_parameters():
    cases = [
        ("调心滚子轴承，外径180mm，内径85mm，宽度41mm", "bearing", {"variant": 1, "outer_diameter": 180, "inner_diameter": 85, "width": 41}),
        ("平焊法兰，外径160mm，内径76mm，厚度18mm，均布8个直径18mm螺栓孔", "flange", {"thickness": 18, "bolt_holes": 8, "bolt_hole_diameter": 18, "neck_height": 0}),
        ("真空法兰，外径120mm，内径50mm，密封槽宽6mm，均布6孔", "flange", {"groove_width": 6, "bolt_holes": 6, "thickness": 22}),
        ("电动蝶阀，公称直径DN150，阀板厚度12mm，阀杆直径24mm，法兰式安装", "valve", {"nominal_diameter": 150, "variant": 1, "disc_thickness": 12, "stem_diameter": 24, "actuator": 1}),
        ("止回阀，公称直径DN80，阀体长度260mm，采用旋启式阀瓣和双端连接", "valve", {"variant": 2, "body_length": 260, "ports": 2}),
        ("四段阶梯轴，总长360mm，最大直径68mm，包含轴肩、键槽", "shaft", {"steps": 4, "total_length": 360, "max_diameter": 68}),
        ("空心传动轴，总长520mm，外径80mm，内径42mm，两端设置花键", "shaft", {"total_length": 520, "max_diameter": 80, "inner_diameter": 42, "spline_ends": 2}),
        ("斜齿轮，模数4，齿数42，螺旋角15度，齿宽45mm", "gear", {"module": 4, "teeth": 42, "helix_angle": 15, "face_width": 45, "bore": 32}),
        ("太阳轮，模数2，齿数24，齿宽20mm，中心为花键孔", "gear", {"spline_bore": 1}),
        ("滚珠丝杠，长度600mm，公称直径32mm，导程10mm", "screw", {"variant": 1, "length": 600, "diameter": 32, "lead": 10}),
        ("弹性联轴器，外径95mm，总长130mm，两端轴孔分别为28mm和32mm", "coupling", {"variant": 1, "bore": 28, "bore_b": 32}),
        ("膜片联轴器，外径68mm，总长82mm，轴孔20mm，包含双膜片组", "coupling", {"variant": 2, "membrane_count": 2}),
        ("双唇骨架油封，外径72mm，内径40mm，宽度10mm", "seal", {"lip_count": 2}),
        ("轴端密封件，外径110mm，内径65mm，宽度16mm，带环形密封槽宽4mm", "seal", {"groove_width": 4}),
    ]
    for description, part_type, expected in cases:
        parsed = structural_features(description, part_type, local_parse(description, part_type))
        for key, value in expected.items():
            assert parsed[key] == value, (part_type, description, key, parsed)
