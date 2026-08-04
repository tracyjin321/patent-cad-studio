"""Asset-version regression for the completed blur-race fix."""

from pathlib import Path


def test_index_serves_the_completed_assembly_sync_bundle():
    index = (Path(__file__).parents[1] / "static" / "index.html").read_text(encoding="utf-8")
    assert "/static/app.js?v=20260804-assembly-sync-v2" in index
