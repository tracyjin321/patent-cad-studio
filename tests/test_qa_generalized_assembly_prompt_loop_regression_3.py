"""Regression: ISSUE-003 — assembly prompts collapsed to one aggregate component.

Found by /qa on 2026-08-05.
Report: .gstack/qa-reports/qa-report-127-0-0-1-2026-08-05.md
"""

import json
from pathlib import Path

from app.assembly import automatic_manifest
from app.component_library import recommend_component_instances


ROOT = Path(__file__).parents[1]
CASES = json.loads((ROOT / "docs/assembly-prompts-20-2026-08-05.json").read_text(encoding="utf-8"))


def test_twenty_generalized_prompts_resolve_to_executable_multi_component_manifests():
    assert len(CASES) == 20
    for case in CASES:
        result = recommend_component_instances(case["prompt"], limit=32)
        assert len(result["component_ids"]) == case["expected_component_count"], case["id"]
        assert len(result["component_ids"]) > 1, case["id"]
        assert len(result["assembly_relations"]) == len(result["component_ids"]) - 1, case["id"]
        manifest = automatic_manifest(result["component_ids"], ROOT / "component_library")
        assert len(manifest.components) == case["expected_component_count"], case["id"]
