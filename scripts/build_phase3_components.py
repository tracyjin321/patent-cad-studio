#!/usr/bin/env python3
"""Build reviewed automation and atomic Falcon 9 ComponentSpecs."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCone, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

from app.component_spec import step_to_spec, write_shape_step


def compound(shapes):
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound
    result, builder = TopoDS_Compound(), BRep_Builder(); builder.MakeCompound(result)
    for shape in shapes: builder.Add(result, shape)
    return result


def ring(outer, inner, height):
    return BRepAlgoAPI_Cut(BRepPrimAPI_MakeCylinder(outer / 2, height).Shape(), BRepPrimAPI_MakeCylinder(inner / 2, height).Shape()).Shape()


def cylinder(point, radius, height):
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(*point), gp_Dir(0, 0, 1)), radius, height).Shape()


def cone(point, radius1, radius2, height):
    return BRepPrimAPI_MakeCone(gp_Ax2(gp_Pnt(*point), gp_Dir(0, 0, 1)), radius1, radius2, height).Shape()


def shapes():
    return {
        "stepper-motor-nema23-l0056": (compound([BRepPrimAPI_MakeBox(gp_Pnt(-28.2,-28.2,0),56.4,56.4,56).Shape(), cylinder((0,0,56),3.175,20)]), "NEMA23 步进电机", "actuator", "nema_stepper", "NEMA ICS 16"),
        "servo-motor-40x20x38": (compound([BRepPrimAPI_MakeBox(gp_Pnt(-20,-10,0),40,20,38).Shape(), cylinder((0,0,38),3,10)]), "通用伺服电机", "actuator", "servo_motor", None),
        "pneumatic-cylinder-d032-l0100": (compound([BRepPrimAPI_MakeCylinder(16,100).Shape(), cylinder((0,0,100),6,80)]), "标准气缸", "actuator", "pneumatic_cylinder", "ISO 15552"),
        "falcon9-merlin-1d-sea-level": (compound([BRepPrimAPI_MakeCylinder(420,900).Shape(), cone((0,0,-1800),460,170,1800)]), "Merlin 1D 海平面发动机", "rocket", "merlin_1d_sea_level", None),
        "falcon9-merlin-1d-vacuum": (compound([BRepPrimAPI_MakeCylinder(430,900).Shape(), cone((0,0,-3100),1350,180,3100)]), "Merlin 1D 真空发动机", "rocket", "merlin_1d_vacuum", None),
        "falcon9-landing-leg": (compound([BRepPrimAPI_MakeBox(gp_Pnt(-90,-160,0),180,320,4000).Shape(), BRepPrimAPI_MakeBox(gp_Pnt(-650,-500,-180),1300,1000,180).Shape()]), "猎鹰九号着陆腿", "rocket", "landing_leg", None),
        "falcon9-grid-fin": (compound([BRepPrimAPI_MakeBox(gp_Pnt(-900,-40,0),1800,80,1500).Shape()] + [BRepPrimAPI_MakeBox(gp_Pnt(-850+i*210,-90,80),50,180,1340).Shape() for i in range(9)] + [BRepPrimAPI_MakeBox(gp_Pnt(-850,-90,80+i*170),1700,180,35).Shape() for i in range(9)]), "猎鹰九号单片栅格翼", "rocket", "grid_fin", None),
        "falcon9-octaweb": (ring(3600,2600,450), "猎鹰九号 Octaweb 发动机安装结构", "rocket", "octaweb", None),
        "falcon9-payload-adapter": (BRepPrimAPI_MakeCone(1830,2450,3000).Shape(), "猎鹰九号载荷适配器", "rocket", "payload_adapter", None),
        "falcon9-feedline": (BRepPrimAPI_MakeCylinder(85,13000).Shape(), "猎鹰九号推进剂输送管", "rocket", "feedline", None),
        "falcon9-avionics-ring": (ring(3660,3340,650), "猎鹰九号航电环", "rocket", "avionics_ring", None),
        "falcon9-fairing-half": (BRepAlgoAPI_Cut(BRepPrimAPI_MakeCone(2600,80,13000).Shape(), BRepPrimAPI_MakeBox(gp_Pnt(-3000,-3000,-100),3000,6000,13200).Shape()).Shape(), "猎鹰九号整流罩半壳", "rocket", "fairing_half", None),
    }


def main():
    for component_id, (shape, name, kind, subtype, standard) in shapes().items():
        directory = ROOT / "component_library" / component_id
        directory.mkdir(parents=True, exist_ok=True)
        step = directory / "reference.step"; spec_path = directory / "component.yaml"
        write_shape_step(shape, step, "AP242")
        spec = step_to_spec(step, spec_path, identity={"id": component_id, "name": name, "type": kind, "subtype": subtype, "family": subtype}, copy_reference=False)
        spec["identity"].update({"standard": standard, "status": "reviewed", "license": "project-generated", "description": f"阶段三新增的{name}简化实体图元。"})
        spec["provenance"].update({"source_type": "project_generated", "data_entry_method": "deterministic_occt_builder", "verified_by": "phase3-library-gate"})
        import yaml
        spec_path.write_text(yaml.safe_dump(spec, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
    from scripts.rebuild_component_catalog import build_catalog
    import yaml
    catalog = build_catalog(ROOT / "component_library")
    (ROOT / "component_library" / "catalog.yaml").write_text(yaml.safe_dump(catalog, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"components={len(catalog['components'])}")


if __name__ == "__main__": main()
