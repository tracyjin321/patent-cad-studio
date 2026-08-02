"""Regression: ISSUE-003 — five simultaneous heavy CAD jobs killed workers.

Found by /qa on 2026-08-02.
Report: .gstack/qa-reports/qa-report-127-0-0-1-2026-08-02.md
"""

from app.main import HEAVY_CAD_SLOTS, cad_resource_slot


def test_heavy_cad_admission_keeps_at_least_two_parallel_slots():
    assert HEAVY_CAD_SLOTS >= 2
    with cad_resource_slot("gear"):
        pass


def test_normal_cad_does_not_consume_heavy_slot():
    with cad_resource_slot("valve"):
        pass
