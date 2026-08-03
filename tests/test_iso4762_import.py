from pathlib import Path

import yaml

from app.assembly import _compatible, automatic_manifest, build_assembly
from app.component_spec import roundtrip_report, validate_spec
from scripts.import_iso4762_gbt70_1 import HIGH_FREQUENCY, _slug, select_candidates


def test_iso4762_candidate_selection_is_explicit_and_high_frequency():
    items = [
        {"id": "keep", "attributes": {"thread": "M6", "lengthMm": 20}},
        {"id": "long", "attributes": {"thread": "M6", "lengthMm": 200}},
        {"id": "large", "attributes": {"thread": "M24", "lengthMm": 60}},
    ]
    assert [item["id"] for item in select_candidates(items)] == ["keep"]
    assert sum(map(len, HIGH_FREQUENCY.values())) == 45
    assert _slug("M2.5", 12) == "gbt70-1-shcs-m2p5-l0012"


def test_imported_gbt70_1_component_roundtrips_and_assembles():
    library = Path(__file__).parents[1] / "component_library"
    component_id = "gbt70-1-shcs-m6-l0020"
    spec_path = library / component_id / "component.yaml"
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    assert not validate_spec(spec, spec_path=spec_path)["errors"]
    assert roundtrip_report(spec_path)["passed"]
    assert {port["type"] for port in spec["ports"]} == {"threaded_connection"}
    shape, report = build_assembly(automatic_manifest([component_id], library))
    assert report["quality"]["valid_brep"] and not shape.IsNull()


def test_threaded_ports_require_same_thread_and_opposite_gender():
    def threaded(thread: str, gender: str) -> dict:
        return {
            "type": "threaded_connection",
            "allowed_mates": ["coincident_concentric"],
            "interface": {"thread": thread, "pitch_mm": 1.0, "gender": gender},
            "compatible_with": {
                "port_types": ["threaded_connection"],
                "rules": ["same_thread", "opposite_gender"],
            },
        }

    assert not _compatible(threaded("M6", "female"), threaded("M6", "male"), "coincident_concentric")
    assert any("thread" in error for error in _compatible(
        threaded("M8", "female"), threaded("M6", "male"), "coincident_concentric"
    ))
    assert any("gender" in error for error in _compatible(
        threaded("M6", "male"), threaded("M6", "male"), "coincident_concentric"
    ))
