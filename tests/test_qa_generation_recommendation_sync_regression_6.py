"""Regression for the blur-to-generate component recommendation race.

Regression: ISSUE-005 — clicking Generate blurred the description, cleared the
eight recommendations, and submitted an empty component_ids list.
Found by gstack QA on 2026-08-04.
"""

from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_generation_waits_for_recommendations_for_the_current_description():
    source = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    index = (ROOT / "static" / "index.html").read_text(encoding="utf-8")

    barrier = "if(state.recommendedComponentDescription!==description)await fetchComponentRecommendations(description);"
    submit = "component_ids:effectiveComponentIds()"
    assert barrier in source
    assert source.index(barrier) < source.index(submit, source.index("async function generate()"))
    assert "state.recommendedComponentDescription=description" in source
    assert "/static/app.js?v=20260804-semantic-assembly-v1" in index
