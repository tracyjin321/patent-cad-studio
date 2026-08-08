# Stable STEP Bounds Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make STEP round-trip and multi-round validation use the same tolerance-independent geometric bounds while retaining the 0.01 mm quality threshold.

**Architecture:** `app.component_spec` owns canonical geometry measurement and comparison. OpenCascade `AddOptimal_s` computes bounds without entity-tolerance padding; all validation callers reuse the same comparator instead of maintaining independent thresholds.

**Tech Stack:** Python 3.12, cadquery-ocp/OpenCascade 7.8, pytest, ComponentSpec YAML.

## Global Constraints

- Keep dimensional tolerance at 0.01 mm and relative volume/area tolerance at 1e-6.
- Do not add component-specific exceptions.
- Do not modify assembly, rendering, or component recommendation behavior.
- Run the exact GitHub Actions validation commands before push.

---

### Task 1: Reproduce tolerance-padding drift in an automated test

**Files:**
- Modify: `tests/test_component_spec.py`

**Interfaces:**
- Consumes: `inspect_shape(shape) -> dict[str, Any]`, `roundtrip_report(spec_path) -> dict[str, Any]`
- Produces: regression coverage for stable bounds and the two imported fixtures

- [ ] Add a test that creates a box, assigns edge/face tolerance, and asserts measured size remains its exact geometric dimensions.
- [ ] Add a parametrized test for the two imported gear ComponentSpecs that asserts `roundtrip_report(path)["passed"]` at their declared 0.01 mm tolerance.
- [ ] Run the new tests and confirm they fail specifically on tolerance-expanded bounds.

### Task 2: Implement canonical bounds and shared engineering comparison

**Files:**
- Modify: `app/component_spec.py`
- Modify: `scripts/multiround_roundtrip.py`

**Interfaces:**
- Produces: `_engineering_geometry_errors(stored, actual, dimensional_tolerance, relative_tolerance) -> list[str]`
- Produces: tolerance-independent `inspect_shape()` bounding-box values

- [ ] Replace tolerance-expanded `BRepBndLib.Add_s` bounds with `BRepBndLib.AddOptimal_s(shape, box, False, False)` in a named helper.
- [ ] Extend the shared comparator to cover the fields used by round-trip validation and expose structured check results without duplicating thresholds.
- [ ] Make `roundtrip_report()` use the shared comparator while preserving its diagnostic delta fields.
- [ ] Make `scripts/multiround_roundtrip.py` use the shared policy and remove `BBOX_ENGINEERING_TOLERANCE_MM = 0.02`.
- [ ] Run the new tests and existing ComponentSpec tests until green.

### Task 3: Migrate measured bounds and validate the repository

**Files:**
- Modify only affected `component_library/*/component.yaml` measurement/signature fields

**Interfaces:**
- Consumes: canonical `inspect_step()` measurements and `geometry_signatures()`
- Produces: checked-in YAML baselines consistent with canonical measurement

- [ ] Generate a before/after report for all formal ComponentSpecs.
- [ ] Update only canonical measured fields and signatures that changed.
- [ ] Review the YAML diff for unexpected topology, volume, area, or center changes.
- [ ] Run `PYTHONPATH=. python scripts/validate_component_library.py` and require exit 0.
- [ ] Run `PYTHONPATH=. pytest -q` and require exit 0.
- [ ] Review `git diff --check`, working-tree status, and the final diff.
- [ ] Commit the focused change and push `main` to `origin` only after every gate passes.
