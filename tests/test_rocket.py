from pathlib import Path

from app.component_spec import inspect_shape, inspect_step, write_shape_step
from app.llm import normalize_parameters
from app.rocket import build_falcon9_components, build_falcon9_shape


def test_falcon9_component_and_vehicle_envelopes(tmp_path: Path):
    parameters = normalize_parameters("rocket", {})
    components = build_falcon9_components(parameters)
    assert set(components) == {"first_stage", "grid_fins", "interstage", "second_stage", "payload_fairing"}
    measured = inspect_shape(build_falcon9_shape(parameters))
    assert measured["bounding_box"]["min"][2] == 0
    assert measured["bounding_box"]["max"][2] == 70000
    assert measured["topology"]["solids"] >= 100
    assert measured["valid_solid"]

    step = tmp_path / "falcon9.step"
    write_shape_step(build_falcon9_shape(parameters), step, "AP214")
    assert "AUTOMOTIVE_DESIGN" in step.read_text(encoding="latin-1")[:4096]
    rebuilt = inspect_step(step)
    assert rebuilt["bounding_box"]["size"][2] == 70000
    assert rebuilt["topology"]["solids"] == measured["topology"]["solids"]
