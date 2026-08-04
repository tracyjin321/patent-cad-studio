import hashlib
import json
import shutil
from pathlib import Path

import pytest
import yaml

from app.component_spec import dump_spec, geometry_signatures, inspect_step, load_spec, roundtrip_report, spec_to_step, step_to_spec, validate_spec
from app.parametric_spec import resolve_parametric_component
from scripts.rebuild_component_catalog import build_catalog


ROOT = Path(__file__).resolve().parents[1]


def component_yamls():
    return sorted((ROOT / "component_library").glob("*/component.yaml"))


def test_all_step_files_have_component_specs():
    steps = sorted((ROOT / "component_library").glob("*/reference.step"))
    assert steps
    assert {path.parent / "component.yaml" for path in steps} == set(component_yamls())


@pytest.mark.parametrize("spec_path", component_yamls(), ids=lambda path: path.stem)
def test_component_spec_roundtrip_is_lossless(spec_path, tmp_path):
    spec = load_spec(spec_path)
    output = tmp_path / (spec_path.stem + ".step")
    measured = spec_to_step(spec_path, output)
    source = spec_path.parent / spec["artifacts"]["reference_step"]["file"]
    assert hashlib.sha256(output.read_bytes()).digest() == hashlib.sha256(source.read_bytes()).digest()
    assert measured["topology"]["solids"] == spec["validation"]["topology"]["expected_body_count"]
    assert measured["volume_mm3"] > 0


def test_component_ids_are_unique():
    specs = [yaml.safe_load(path.read_text(encoding="utf-8")) for path in component_yamls()]
    ids = [item["identity"]["id"] for item in specs]
    assert len(ids) == len(set(ids))


def test_component_catalog_is_current():
    catalog_path = ROOT / "component_library" / "catalog.yaml"
    actual = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    assert actual == build_catalog(catalog_path.parent)


def test_stale_exact_geometry_hash_is_warning_when_engineering_geometry_matches():
    path = ROOT / "component_library" / "bevel-gear-45deg-m0-8-16t" / "component.yaml"
    spec = load_spec(path)
    spec["validation"]["geometry"]["signatures"]["strict_topology_sha256"] = "0" * 64

    result = validate_spec(spec, spec_path=path)

    assert result["errors"] == []
    assert result["warnings"] == [
        "reference STEP 精确几何签名不匹配；工程几何仍在声明公差内"
    ]


def test_engineering_volume_drift_remains_blocking():
    path = ROOT / "component_library" / "deep-groove-ball-bau6201z" / "component.yaml"
    spec = load_spec(path)
    spec["validation"]["geometry"]["measured"]["volume_mm3"] *= 1.1

    result = validate_spec(spec, spec_path=path)

    assert "reference STEP 工程几何体积超出声明公差" in result["errors"]


def test_engineering_topology_drift_remains_blocking():
    path = ROOT / "component_library" / "deep-groove-ball-bau6201z" / "component.yaml"
    spec = load_spec(path)
    spec["validation"]["geometry"]["measured"]["topology"]["faces"] += 1

    result = validate_spec(spec, spec_path=path)

    assert "reference STEP 工程拓扑与记录不一致" in result["errors"]


def test_engineering_bounding_box_drift_remains_blocking():
    path = ROOT / "component_library" / "deep-groove-ball-bau6201z" / "component.yaml"
    spec = load_spec(path)
    spec["validation"]["geometry"]["measured"]["bounding_box"]["max"][0] += 0.02

    result = validate_spec(spec, spec_path=path)

    assert "reference STEP 工程几何包围盒超出声明公差" in result["errors"]


def test_engineering_center_of_mass_drift_remains_blocking():
    path = ROOT / "component_library" / "deep-groove-ball-bau6201z" / "component.yaml"
    spec = load_spec(path)
    spec["validation"]["geometry"]["measured"]["center_of_mass"][0] += 0.02

    result = validate_spec(spec, spec_path=path)

    assert "reference STEP 工程几何重心超出声明公差" in result["errors"]


def test_stored_surface_area_drift_remains_blocking():
    path = ROOT / "component_library" / "deep-groove-ball-bau6201z" / "component.yaml"
    spec = load_spec(path)
    spec["validation"]["geometry"]["measured"]["surface_area_mm2"] = 5200.0

    result = validate_spec(spec, spec_path=path)

    assert "reference STEP 工程几何表面积超出声明公差" in result["errors"]


def test_malformed_engineering_measurement_is_blocking():
    path = ROOT / "component_library" / "deep-groove-ball-bau6201z" / "component.yaml"
    spec = load_spec(path)
    spec["validation"]["geometry"]["measured"]["center_of_mass"] = [0.0, 0.0]

    result = validate_spec(spec, spec_path=path)

    assert "reference STEP 工程几何测量基准无效" in result["errors"]


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_engineering_measurement_is_blocking(bad_value):
    path = ROOT / "component_library" / "deep-groove-ball-bau6201z" / "component.yaml"
    spec = load_spec(path)
    spec["validation"]["geometry"]["measured"]["center_of_mass"][0] = bad_value

    result = validate_spec(spec, spec_path=path)

    assert "reference STEP 工程几何测量基准无效" in result["errors"]


@pytest.mark.parametrize("bad_count", [True, 1.5])
def test_invalid_engineering_topology_count_is_blocking(bad_count):
    path = ROOT / "component_library" / "deep-groove-ball-bau6201z" / "component.yaml"
    spec = load_spec(path)
    spec["validation"]["geometry"]["measured"]["topology"]["solids"] = bad_count

    result = validate_spec(spec, spec_path=path)

    assert "reference STEP 工程几何测量基准无效" in result["errors"]


def test_nonfinite_engineering_tolerance_is_blocking():
    path = ROOT / "component_library" / "deep-groove-ball-bau6201z" / "component.yaml"
    spec = load_spec(path)
    spec["validation"]["geometry"]["dimensional_tolerance"] = float("nan")

    result = validate_spec(spec, spec_path=path)

    assert "reference STEP 工程几何测量基准无效" in result["errors"]


def test_overflowing_engineering_measurement_is_blocking():
    path = ROOT / "component_library" / "deep-groove-ball-bau6201z" / "component.yaml"
    spec = load_spec(path)
    spec["validation"]["geometry"]["measured"]["volume_mm3"] = 10 ** 10000

    result = validate_spec(spec, spec_path=path)

    assert "reference STEP 工程几何测量基准无效" in result["errors"]


def test_component_library_gate_reports_geometry_warnings(tmp_path, monkeypatch, capsys):
    from scripts import validate_component_library as gate

    spec_path = tmp_path / "component_library" / "sample" / "component.yaml"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("schema_version: '1.3'\n", encoding="utf-8")
    warning = "reference STEP 精确几何签名不匹配；工程几何仍在声明公差内"

    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "load_spec", lambda _: {"artifacts": {"reference_step": {"file": "reference.step"}}})
    monkeypatch.setattr(gate, "validate_spec", lambda *args, **kwargs: {"errors": [], "warnings": [warning]})
    monkeypatch.setattr(gate, "read_step", lambda _: object())
    monkeypatch.setattr(gate, "BRepCheck_Analyzer", lambda _: type("Analyzer", (), {"IsValid": lambda self: True})())
    monkeypatch.setattr(gate, "roundtrip_report", lambda _: {"passed": True})
    monkeypatch.setattr(gate, "build_catalog", lambda _: {"components": [{}]})

    gate.main()

    result = json.loads(capsys.readouterr().out)
    assert result["warnings"] == [{"spec": str(spec_path), "warnings": [warning]}]


def test_generic_step_to_yaml_and_ap242_roundtrip(tmp_path):
    source = next((ROOT / "component_library").glob("*/reference.step"))
    yaml_path = tmp_path / "generic.yaml"
    spec = step_to_spec(source, yaml_path, identity={"id": "generic-test", "name": "通用测试件"})
    assert yaml_path.with_suffix(source.suffix).exists()
    assert spec["identity"]["id"] == "generic-test"
    assert validate_spec(load_spec(yaml_path), spec_path=yaml_path)["errors"] == []
    report = roundtrip_report(yaml_path)
    assert report["passed"], report


def test_yaml_placement_translates_exported_geometry(tmp_path):
    source = ROOT / "component_library" / "deep-groove-ball-bau6201z" / "reference.step"
    yaml_path = tmp_path / "placed.yaml"
    spec = step_to_spec(source, yaml_path)
    original = spec["validation"]["geometry"]["measured"]["bounding_box"]
    spec["geometry"]["placement"] = [
        [1.0, 0.0, 0.0, 10.0],
        [0.0, 1.0, 0.0, 20.0],
        [0.0, 0.0, 1.0, 30.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
    dump_spec(spec, yaml_path)
    measured = spec_to_step(yaml_path, tmp_path / "placed.step")
    assert measured["bounding_box"]["min"] == pytest.approx(
        [original["min"][0] + 10, original["min"][1] + 20, original["min"][2] + 30], abs=1e-5
    )


def test_invalid_port_frame_is_rejected():
    spec = load_spec(component_yamls()[0])
    spec["ports"][0]["frame"]["up"] = spec["ports"][0]["frame"]["axis"]
    result = validate_spec(spec)
    assert any("正交" in message for message in result["errors"])


def test_parametric_yaml_materializes_and_rebuilds_step(tmp_path):
    generated_library = tmp_path / "generated-library"
    resolved = resolve_parametric_component(
        "flange",
        {"outer_diameter": 220, "inner_diameter": 100, "thickness": 22, "bolt_holes": 8, "neck_height": 62},
        "设计 DN100 带颈对焊法兰",
        formal_library=tmp_path / "empty-library",
        generated_library=generated_library,
    )
    assert resolved.source == "generated"
    assert resolved.spec_path.exists()
    assert resolved.reference_step.exists()
    spec = load_spec(resolved.spec_path)
    assert spec["geometry"]["generator"] == {
        "mode": "parametric",
        "generator_id": "flange",
        "generator_version": "1.1.0",
        "preferred_engine": "OpenCascade",
        "parameters_source": "parameters[].default",
    }
    assert validate_spec(spec, spec_path=resolved.spec_path)["errors"] == []
    assert spec["ports"][0]["frame"]["axis"] == [0.0, 0.0, -1.0]
    assert spec["ports"][1]["frame"]["axis"] == [0.0, 0.0, 1.0]
    rebuilt = tmp_path / "rebuilt.step"
    measured = spec_to_step(resolved.spec_path, rebuilt)
    assert rebuilt.read_bytes().startswith(b"ISO-10303-21;")
    assert measured["bounding_box"]["size"] == pytest.approx(
        spec["validation"]["geometry"]["measured"]["bounding_box"]["size"], abs=1e-5
    )
    cached = resolve_parametric_component(
        "flange",
        {"outer_diameter": 220, "inner_diameter": 100, "thickness": 22, "bolt_holes": 8, "neck_height": 62},
        "不同表述但参数相同",
        formal_library=tmp_path / "empty-library",
        generated_library=generated_library,
    )
    assert cached.source == "cache"
    assert cached.component_id == resolved.component_id
    formal_library = tmp_path / "formal-library"
    shutil.copytree(resolved.spec_path.parent, formal_library / resolved.component_id)
    library_hit = resolve_parametric_component(
        "flange",
        {"outer_diameter": 220, "inner_diameter": 100, "thickness": 22, "bolt_holes": 8, "neck_height": 62},
        "正式库命中",
        formal_library=formal_library,
        generated_library=tmp_path / "unused-cache",
    )
    assert library_hit.source == "library"
    assert library_hit.component_id == resolved.component_id


def test_linked_step_to_yaml_preserves_authoritative_semantics(tmp_path):
    source_spec = component_yamls()[0]
    original = load_spec(source_spec)
    exported = tmp_path / "exported.step"
    spec_to_step(source_spec, exported, force_reexport=True)
    output = tmp_path / "linked.yaml"
    linked = step_to_spec(exported, output, copy_reference=False, source_spec_path=source_spec)
    for key in ("parameters", "constraints", "ports", "presets"):
        assert linked[key] == original[key]
    assert linked["provenance"]["semantic_recovery"] == "authoritative_sidecar"
    assert linked["validation"]["geometry"]["signatures"] == geometry_signatures(inspect_step(exported))
    assert validate_spec(linked, spec_path=output)["errors"] == []
