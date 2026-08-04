"""Regression guard for compound mechanical names choosing the wrong part.

Regression: ISSUE-001 — a valve with flanges and a flange coupling selected flange.
Found by /qa on 2026-08-04.
Report: .gstack/qa-reports/qa-report-127-0-0-1-2026-08-04.md
"""

from pathlib import Path


def test_primary_part_is_inferred_from_the_leading_subject():
    source = (Path(__file__).parents[1] / "static" / "app.js").read_text(encoding="utf-8")

    assert "function preferredPart(description,parts)" in source
    assert "state.part=preferredPart(description,[...state.recommended])" in source
    assert "state.part=[...state.recommended][0]" not in source
