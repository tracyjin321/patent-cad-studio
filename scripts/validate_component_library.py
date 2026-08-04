#!/usr/bin/env python3
"""CI quality gate for every formal ComponentSpec and reference STEP."""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from OCP.BRepCheck import BRepCheck_Analyzer  # noqa: E402
from app.component_spec import load_spec, read_step, roundtrip_report, validate_spec  # noqa: E402
from scripts.rebuild_component_catalog import build_catalog  # noqa: E402

def main():
    library=ROOT/"component_library";failures=[];checked=0
    for spec_path in sorted(library.glob("*/component.yaml")):
        checked+=1;spec=load_spec(spec_path);validation=validate_spec(spec,spec_path=spec_path)
        if validation["errors"]: failures.append({"spec":str(spec_path),"errors":validation["errors"]});continue
        reference=spec_path.parent/spec["artifacts"]["reference_step"]["file"]
        if not BRepCheck_Analyzer(read_step(reference)).IsValid(): failures.append({"spec":str(spec_path),"errors":["B-Rep invalid"]});continue
        if not roundtrip_report(spec_path)["passed"]: failures.append({"spec":str(spec_path),"errors":["STEP roundtrip mismatch"]})
    catalog_count=len(build_catalog(library)["components"]);result={"checked":checked,"catalog_count":catalog_count,"passed":not failures,"failures":failures}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if failures or checked!=catalog_count: raise SystemExit(1)

if __name__=="__main__": main()
