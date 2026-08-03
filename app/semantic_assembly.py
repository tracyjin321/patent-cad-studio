"""XCAF semantic assembly export with definition reuse and instance names."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .assembly import AssemblyManifest
from .component_spec import IDENTITY_MATRIX, _artifact_path, _frame_matrix, _inverse_rigid, _matmul, _port, _trsf_from_matrix, load_spec, read_step


def write_xcaf_assembly(manifest: AssemblyManifest, output: Path) -> dict[str, Any]:
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDocStd import TDocStd_Document
    from OCP.TopLoc import TopLoc_Location
    from OCP.XCAFDoc import XCAFDoc_DocumentTool

    document = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
    shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(document.Main())
    assembly_label = shape_tool.NewShape()
    TDataStd_Name.Set_s(assembly_label, TCollection_ExtendedString("Patent CAD Semantic Assembly"))
    definitions: dict[str, Any] = {}
    worlds: list[list[list[float]]] = []
    tree = []
    for index, item in enumerate(manifest.components):
        spec_path, world = Path(item.spec), IDENTITY_MATRIX
        spec = load_spec(spec_path)
        component_id = item.component_id or spec["identity"]["id"]
        if item.target is not None:
            target_spec = load_spec(Path(manifest.components[item.target].spec))
            relation = _matmul(_frame_matrix(_port(target_spec, str(item.mate_to))["frame"], reverse_axis=True), _inverse_rigid(_frame_matrix(_port(spec, str(item.port))["frame"])))
            world = _matmul(worlds[item.target], relation)
        worlds.append(world)
        if component_id not in definitions:
            definition = shape_tool.AddShape(read_step(_artifact_path(spec_path, spec)), False)
            TDataStd_Name.Set_s(definition, TCollection_ExtendedString(spec["identity"].get("name") or component_id))
            definitions[component_id] = definition
        instance = shape_tool.AddComponent(assembly_label, definitions[component_id], TopLoc_Location(_trsf_from_matrix(world)))
        TDataStd_Name.Set_s(instance, TCollection_ExtendedString(f"{component_id}#{index + 1}"))
        tree.append({"instance_id": f"{component_id}#{index + 1}", "definition_id": component_id, "reused_definition": sum(1 for node in tree if node["definition_id"] == component_id) > 0,
                     "parent": "root", "transform": world})
    shape_tool.UpdateAssemblies()
    output.parent.mkdir(parents=True, exist_ok=True)
    writer = STEPCAFControl_Writer()
    if not writer.Transfer(document) or int(writer.Write(str(output)).value) != 1:
        raise RuntimeError("XCAF AP242 装配导出失败")
    return {"format": "XCAF/AP242", "root": "Patent CAD Semantic Assembly", "definitions": len(definitions), "instances": len(tree), "tree": tree}
