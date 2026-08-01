import hashlib
import shutil
from pathlib import Path

import pytest
import yaml

from app.component_spec import dump_spec, load_spec, roundtrip_report, spec_to_step, step_to_spec, validate_spec
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
