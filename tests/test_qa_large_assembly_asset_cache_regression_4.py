"""Regression coverage for serving the large-assembly frontend bundle.

Regression: ISSUE-003 — browsers retained the five-instance JavaScript bundle
after the server was updated. Found by gstack QA on 2026-08-04.
Report: .gstack/qa-reports/qa-report-large-assembly-2026-08-04.md
"""

from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_index_references_the_large_assembly_bundle_version():
    index = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    app_js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

    assert "/static/app.js?v=20260804-semantic-assembly-v1" in index
    assert 'JSON.stringify({description,limit:32,use_ai:$("#use-ai").checked})' in app_js
