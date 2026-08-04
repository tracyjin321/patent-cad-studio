"""Asset-version regression for the patent prompt QA fixes.

Regression: ISSUE-004 — browsers could retain the pre-fix application bundle.
Found by /qa on 2026-08-04.
Report: .gstack/qa-reports/qa-report-127-0-0-1-2026-08-04.md
"""

from pathlib import Path


def test_index_publishes_the_patent_prompt_qa_bundle():
    index = (Path(__file__).parents[1] / "static" / "index.html").read_text(encoding="utf-8")
    assert "qa=patent-prompts-v1" in index
