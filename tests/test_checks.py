import pytest


VALID_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 794 1123">
<defs><style>.o{fill:none;stroke:#000;stroke-width:2.15}.h{fill:none;stroke:#000;stroke-width:1.05;stroke-dasharray:6 5}.f{font:16px serif;fill:#000}.p{font:14px serif;fill:#000}</style></defs>
<rect width="794" height="1123" fill="#fff"/>
<path class="o" d="M120 220L674 220L674 800L120 800Z"/>
<path class="h" d="M150 500L644 500"/>
<text class="f" x="397" y="850" text-anchor="middle">图1</text>
<text class="p" x="397" y="1080" text-anchor="middle">1</text>
</svg>'''


def test_patent_precheck_passes_when_all_automatic_rules_pass():
    from app.checks import manual_patent_review_checks, patent_drawing_precheck

    status, checks = patent_drawing_precheck(VALID_SVG)
    by_code = {item["code"]: item for item in checks}
    manual_checks = manual_patent_review_checks()

    assert status == "pass"
    assert by_code["vector_drawing"]["status"] == "pass"
    assert by_code["page_layout"]["status"] == "pass"
    assert by_code["black_white"]["status"] == "pass"
    assert by_code["line_quality"]["status"] == "pass"
    assert by_code["unrelated_frame"]["status"] == "pass"
    assert by_code["figure_number"]["status"] == "pass"
    assert by_code["annotation_language"]["status"] == "pass"
    assert by_code["page_number"]["status"] == "pass"
    assert by_code["scaled_legibility"]["status"] == "pass"
    assert not {"protected_subject", "reference_consistency", "view_adequacy"} & set(by_code)
    assert [item["code"] for item in manual_checks] == [
        "protected_subject", "reference_consistency", "view_adequacy",
    ]
    assert all(item["status"] == "review" for item in manual_checks)
    assert all(set(item) == {"code", "name", "status", "detail", "basis"} for item in checks)


@pytest.mark.parametrize(
    ("svg", "failed_code"),
    [
        (VALID_SVG.replace('viewBox="0 0 794 1123"', 'viewBox="0 0 1123 794"'), "page_layout"),
        (VALID_SVG.replace("stroke:#000", "stroke:#bbb", 1), "black_white"),
        (VALID_SVG.replace("stroke-width:1.05", "stroke-width:0.2"), "scaled_legibility"),
        (VALID_SVG.replace('<rect width="794" height="1123" fill="#fff"/>', '<rect width="794" height="1123" fill="#fff" stroke="#000"/>'), "unrelated_frame"),
        (VALID_SVG.replace(">图1</text>", ">Figure 1</text>"), "figure_number"),
        (VALID_SVG.replace(">图1</text>", ">图1 Valve</text>"), "annotation_language"),
        (VALID_SVG.replace('<text class="p" x="397" y="1080" text-anchor="middle">1</text>', ""), "page_number"),
    ],
)
def test_patent_precheck_fails_clear_form_defects(svg: str, failed_code: str):
    from app.checks import patent_drawing_precheck

    status, checks = patent_drawing_precheck(svg)

    assert status == "fail"
    assert next(item for item in checks if item["code"] == failed_code)["status"] == "fail"


@pytest.mark.parametrize(
    "svg",
    [
        VALID_SVG.replace('<path class="o" ', '<path class="o" transform="translate(5 0)" ', 1),
        VALID_SVG.replace(
            'd="M120 220L674 220L674 800L120 800Z"',
            'd="M120 220C260 180 530 180 674 220L674 800L120 800Z"',
        ),
    ],
)
def test_patent_precheck_reviews_geometry_it_cannot_measure_reliably(svg: str):
    from app.checks import patent_drawing_precheck

    status, checks = patent_drawing_precheck(svg)

    assert status == "review"
    assert next(item for item in checks if item["code"] == "page_layout")["status"] == "review"


def test_mesh_multiview_includes_page_number_separate_from_figure_number():
    from app.cad import _mesh_view_svg

    svg = _mesh_view_svg(
        {"positions": [0, 0, 0, 10, 0, 0, 0, 10, 0], "indices": [0, 1, 2]},
        "测试零件",
        "front",
    )

    assert '>图1</text>' in svg
    assert '<text class="p" x="397" y="1080" text-anchor="middle">1</text>' in svg
