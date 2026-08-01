import hashlib
from pathlib import Path

import pytest
import yaml

from app.component_spec import dump_spec, load_spec, roundtrip_report, spec_to_step, step_to_spec, validate_spec


ROOT = Path(__file__).resolve().parents[1]


def component_yamls():
    return sorted((ROOT / "graphic_element").rglob("*.yaml"))


def test_all_step_files_have_component_specs():
    steps = sorted([*(ROOT / "graphic_element").rglob("*.step"), *(ROOT / "graphic_element").rglob("*.stp")])
    assert steps
    assert {path.with_suffix(".yaml") for path in steps} == set(component_yamls())


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


def test_generic_step_to_yaml_and_ap242_roundtrip(tmp_path):
    source = next((ROOT / "graphic_element").rglob("*.stp"))
    yaml_path = tmp_path / "generic.yaml"
    spec = step_to_spec(source, yaml_path, identity={"id": "generic-test", "name": "通用测试件"})
    assert yaml_path.with_suffix(source.suffix).exists()
    assert spec["identity"]["id"] == "generic-test"
    assert validate_spec(load_spec(yaml_path), spec_path=yaml_path)["errors"] == []
    report = roundtrip_report(yaml_path)
    assert report["passed"], report


def test_yaml_placement_translates_exported_geometry(tmp_path):
    source = next((ROOT / "graphic_element" / "轴承").glob("*.stp"))
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
