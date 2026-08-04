"""Regression for blur/debounce cancellation racing the Generate click.

Regression: ISSUE-005 follow-up — pending blur and debounce callbacks could
abort the recommendation barrier and still submit an empty component list.
Found by gstack QA on 2026-08-04.
"""

from pathlib import Path


def test_generate_owns_the_recommendation_request_without_blur_races():
    source = (Path(__file__).parents[1] / "static" / "app.js").read_text(encoding="utf-8")
    start = source.index("async function generate()")
    barrier = source.index(
        "if(state.recommendedComponentDescription!==description)await fetchComponentRecommendations(description);",
        start,
    )

    assert "clearTimeout(state.recommendationTimer);" in source[start:barrier]
    assert 'if(e.relatedTarget?.id!=="generate")' in source
    assert 'state.recommendedComponentIds=[];state.recommendedComponentDescription="";' in source
