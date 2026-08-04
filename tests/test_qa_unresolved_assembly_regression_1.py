"""Regression guard against silently replacing an unresolved assembly.

Regression: ISSUE-003 — unsupported shaft/gear assemblies generated one bearing.
Found by /qa on 2026-08-04.
Report: .gstack/qa-reports/qa-report-127-0-0-1-2026-08-04.md
"""

from pathlib import Path


def test_unresolved_assembly_is_blocked_before_generation():
    source = (Path(__file__).parents[1] / "static" / "app.js").read_text(encoding="utf-8")
    barrier = 'if(requestsAssembly(description)&&!effectiveComponentIds().length)'
    submit = "submitGenerationTask({description"

    assert "function requestsAssembly(description)" in source
    assert barrier in source
    assert source.index(barrier) < source.index(submit)
    assert "当前装配缺少可执行的图元与端口规则" in source
