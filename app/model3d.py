import math
from pathlib import Path
from typing import Any


def primitives(part: str, p: dict[str, Any]) -> list[dict[str, Any]]:
    od = float(p.get("outer_diameter", p.get("max_diameter", p.get("diameter", 100))))
    bore = float(p.get("inner_diameter", p.get("bore", od * .35)))
    width = float(p.get("width", p.get("face_width", p.get("length", 36))))
    if part == "bearing":
        n = max(6, min(18, int(p["rolling_elements"])))
        ball_r = min(width * .29, (od - bore) * .105)
        pitch_r = (od + bore) / 4
        return [
            {"type": "tube", "r": od/2, "inner": od*.39, "depth": width, "color": "#9aa8b8"},
            {"type": "tube", "r": bore*.72, "inner": bore/2, "depth": width, "color": "#718195"},
            *[{"type":"sphere","r":ball_r,"at":[math.cos(i*2*math.pi/n)*pitch_r,math.sin(i*2*math.pi/n)*pitch_r,0],"color":"#d7dde5"} for i in range(n)],
        ]
    if part == "flange":
        count=max(4,min(16,int(p["bolt_holes"])))
        return [{"type":"flange","r":od/2,"inner":bore/2,"depth":float(p["thickness"]),"holes":count,"hole_r":max(3,od*.035),"pcd":od*.37,"color":"#929fad"}]
    if part == "valve":
        nd=float(p["nominal_diameter"]); length=float(p["body_length"]); height=float(p["height"])
        return [{"type":"sphere","r":nd*.75,"scale":[1.25,1,1],"color":"#8c9aaa"},{"type":"cylinder","r":nd/2,"depth":length,"rotate":[0,90,0],"color":"#64758a"},{"type":"flange","r":nd*.72,"inner":nd*.46,"depth":12,"at":[-length/2,0,0],"rotate":[0,90,0],"holes":6,"hole_r":3,"pcd":nd*.58,"color":"#8190a2"},{"type":"flange","r":nd*.72,"inner":nd*.46,"depth":12,"at":[length/2,0,0],"rotate":[0,90,0],"holes":6,"hole_r":3,"pcd":nd*.58,"color":"#8190a2"},{"type":"cylinder","r":nd*.13,"depth":height*.52,"at":[0,0,height*.32],"color":"#64758a"},{"type":"torus","r":nd*.57,"tube":nd*.065,"at":[0,0,height*.72],"rotate":[90,0,0],"color":"#a6b0bc"}]
    if part == "shaft":
        length=float(p["total_length"]); steps=max(3,min(6,int(p["steps"]))); maximum=float(p["max_diameter"])
        return [{"type":"cylinder","r":maximum/2*(.62+.38*math.sin(math.pi*(i+1)/(steps+1))),"depth":length/steps,"at":[-length/2+length*(i+.5)/steps,0,0],"rotate":[0,90,0],"color":"#8e9baa"} for i in range(steps)]
    if part == "gear":
        return [{"type":"gear","r":float(p["module"])*float(p["teeth"])/2,"inner":float(p["bore"])/2,"depth":float(p["face_width"]),"teeth":int(p["teeth"]),"color":"#8795a5"}]
    if part == "screw":
        diameter=float(p["diameter"]); length=float(p["length"])
        return [{"type":"cylinder","r":diameter/2,"depth":length,"rotate":[0,90,0],"color":"#8e9cab"},{"type":"helix","r":diameter*.56,"depth":length,"pitch":float(p["lead"]),"color":"#65768a"}]
    if part == "coupling":
        r=float(p["outer_diameter"])/2; length=float(p["length"]); inner=float(p["bore"])/2
        return [{"type":"tube","r":r,"inner":inner,"depth":length*.22,"at":[0,0,-length*.38],"color":"#8997a7"},{"type":"tube","r":r,"inner":inner,"depth":length*.22,"at":[0,0,length*.38],"color":"#a4afbc"},{"type":"tube","r":r*.68,"inner":inner,"depth":length*.64,"color":"#718095"}]
    return [{"type":"tube","r":float(p["outer_diameter"])/2,"inner":float(p["inner_diameter"])/2,"depth":float(p["width"]),"color":"#6f7e90"}]


def _occ_shape(part: str, p: dict[str, Any]):
    from OCP.BRep import BRep_Builder
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere, BRepPrimAPI_MakeTorus
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    from OCP.TopoDS import TopoDS_Compound

    def cylinder(r, depth, x=0, y=0, z=0, axis="z"):
        direction={"x":gp_Dir(1,0,0),"y":gp_Dir(0,1,0),"z":gp_Dir(0,0,1)}[axis]
        start={"x":gp_Pnt(x-depth/2,y,z),"y":gp_Pnt(x,y-depth/2,z),"z":gp_Pnt(x,y,z-depth/2)}[axis]
        return BRepPrimAPI_MakeCylinder(gp_Ax2(start,direction),r,depth).Shape()

    def tube(outer, inner, depth, **kwargs):
        return BRepAlgoAPI_Cut(cylinder(outer,depth,**kwargs),cylinder(inner,depth*1.1,**kwargs)).Shape()

    def compound(shapes):
        result=TopoDS_Compound();builder=BRep_Builder();builder.MakeCompound(result)
        for shape in shapes: builder.Add(result,shape)
        return result

    if part=="bearing":
        od=float(p["outer_diameter"]);bore=float(p["inner_diameter"]);width=float(p["width"]);n=int(p["rolling_elements"]);pitch=(od+bore)/4;ball=min(width*.29,(od-bore)*.105)
        shapes=[tube(od/2,od*.39,width),tube(bore*.72,bore/2,width)]
        shapes += [BRepPrimAPI_MakeSphere(gp_Pnt(math.cos(i*2*math.pi/n)*pitch,math.sin(i*2*math.pi/n)*pitch,0),ball).Shape() for i in range(n)]
        return compound(shapes)
    if part=="flange":
        od=float(p["outer_diameter"]);bore=float(p["inner_diameter"]);depth=float(p["thickness"]);count=int(p["bolt_holes"])
        shape=tube(od/2,bore/2,depth);pcd=od*.37
        for i in range(count):
            hole=cylinder(max(3,od*.035),depth*1.2,math.cos(i*2*math.pi/count)*pcd,math.sin(i*2*math.pi/count)*pcd)
            shape=BRepAlgoAPI_Cut(shape,hole).Shape()
        return shape
    if part=="valve":
        nd=float(p["nominal_diameter"]);length=float(p["body_length"]);height=float(p["height"])
        return compound([BRepPrimAPI_MakeSphere(gp_Pnt(0,0,0),nd*.75).Shape(),cylinder(nd/2,length,axis="x"),cylinder(nd*.13,height*.52,z=height*.32),BRepPrimAPI_MakeTorus(gp_Ax2(gp_Pnt(0,0,height*.72),gp_Dir(0,0,1)),nd*.57,nd*.065).Shape()])
    if part=="shaft":
        length=float(p["total_length"]);steps=max(3,min(6,int(p["steps"])));maximum=float(p["max_diameter"])
        return compound([cylinder(maximum/2*(.62+.38*math.sin(math.pi*(i+1)/(steps+1))),length/steps,x=-length/2+length*(i+.5)/steps,axis="x") for i in range(steps)])
    if part=="gear":
        module=float(p["module"]);teeth=max(10,min(64,int(p["teeth"])));outer=module*teeth/2;root=outer*.84;depth=float(p["face_width"]);bore=float(p["bore"])/2
        shapes=[tube(root,bore,depth)]
        tooth_w=2*math.pi*outer/teeth*.52
        for i in range(teeth):
            angle=i*2*math.pi/teeth;x=math.cos(angle)*(root+(outer-root)/2);y=math.sin(angle)*(root+(outer-root)/2)
            box=BRepPrimAPI_MakeBox(gp_Pnt(-tooth_w/2,-(outer-root)/2,-depth/2),tooth_w,outer-root,depth).Shape()
            from OCP.gp import gp_Trsf
            from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
            tr=gp_Trsf();tr.SetRotation(gp_Ax2(gp_Pnt(0,0,0),gp_Dir(0,0,1)).Axis(),angle-math.pi/2);rot=BRepBuilderAPI_Transform(box,tr,True).Shape()
            move=gp_Trsf();move.SetTranslation(gp_Pnt(0,0,0),gp_Pnt(x,y,0));shapes.append(BRepBuilderAPI_Transform(rot,move,True).Shape())
        return compound(shapes)
    if part=="screw":
        diameter=float(p["diameter"]);length=float(p["length"]);lead=max(2,float(p["lead"]))
        shapes=[cylinder(diameter/2,length,axis="x")]
        thread_count=min(80,max(3,int(length/lead)))
        for i in range(thread_count+1):
            x=-length/2+i*length/thread_count
            shapes.append(BRepPrimAPI_MakeTorus(gp_Ax2(gp_Pnt(x,0,0),gp_Dir(1,0,0)),diameter*.51,max(.6,diameter*.045)).Shape())
        return compound(shapes)
    if part=="coupling":
        r=float(p["outer_diameter"])/2;length=float(p["length"]);inner=float(p["bore"])/2
        return compound([tube(r,inner,length*.22,z=-length*.38),tube(r,inner,length*.22,z=length*.38),tube(r*.68,inner,length*.64)])
    return tube(float(p["outer_diameter"])/2,float(p["inner_diameter"])/2,float(p["width"]))


def _shape_mesh(shape: object) -> dict[str, Any]:
    from OCP.BRep import BRep_Tool
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS
    BRepMesh_IncrementalMesh(shape, 0.35, False, 0.22, True)
    positions: list[float] = []
    indices: list[int] = []
    explorer=TopExp_Explorer(shape,TopAbs_FACE)
    while explorer.More():
        face=TopoDS.Face_s(explorer.Current());location=TopLoc_Location()
        triangulation=BRep_Tool.Triangulation_s(face,location)
        if triangulation is None: explorer.Next();continue
        offset=len(positions)//3;transform=location.Transformation()
        for i in range(1,triangulation.NbNodes()+1):
            point=triangulation.Node(i).Transformed(transform)
            positions.extend((round(float(point.X()),5),round(float(point.Y()),5),round(float(point.Z()),5)))
        reversed_face=face.Orientation()==TopAbs_REVERSED
        for i in range(1,triangulation.NbTriangles()+1):
            a,b,c=triangulation.Triangle(i).Get()
            triangle=[offset+a-1,offset+b-1,offset+c-1]
            if reversed_face: triangle[1],triangle[2]=triangle[2],triangle[1]
            indices.extend(triangle)
        explorer.Next()
    return {"type":"mesh","positions":positions,"indices":indices,"color":"#8d9bab"}


def write_step(path: Path, title: str, part: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer
    shape=_occ_shape(part,parameters)
    writer=STEPControl_Writer()
    if writer.Transfer(shape,STEPControl_AsIs) != IFSelect_RetDone:
        raise RuntimeError(f"OpenCascade could not transfer {title}")
    if writer.Write(str(path)) != IFSelect_RetDone:
        raise RuntimeError(f"OpenCascade could not write {path.name}")
    return [_shape_mesh(shape)]
