import math
from pathlib import Path
from typing import Any


GENERATOR_VERSIONS = {
    "bearing": "2.0.0",
    "flange": "1.1.0",
    "valve": "2.0.0",
    "shaft": "2.0.0",
    "gear": "2.1.0",
    "screw": "2.1.0",
    "coupling": "2.0.0",
    "seal": "2.0.0",
    "rocket": "1.0.0",
}


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
        depth=float(p["thickness"]);neck_height=float(p.get("neck_height",0));radial=(od-bore)/2
        hole_r=max(3,min(od*.035,radial*.18));pcd=bore/2+radial*.62
        items=[{"type":"flange","r":od/2,"inner":bore/2,"depth":depth,"holes":count,"hole_r":hole_r,"pcd":pcd,"color":"#929fad"}]
        if neck_height>0:
            items.append({"type":"tube","r":min(pcd-hole_r*1.8,max(bore*.68,bore/2+depth*.55)),"inner":bore/2,"depth":neck_height,"at":[0,0,(depth+neck_height)/2],"color":"#8795a5"})
        return items
    if part == "valve":
        nd=float(p["nominal_diameter"]); length=float(p["body_length"]); height=float(p["height"])
        wheel_r=nd*.57;wheel_tube=nd*.065
        wheel_z=max(height-nd*.75-max(wheel_tube,nd*.08),nd*1.55);stem_start=nd*.5;stem_depth=wheel_z-stem_start+nd*.08
        return [{"type":"sphere","r":nd*.75,"scale":[1.25,1,1],"color":"#8c9aaa"},{"type":"cylinder","r":nd/2,"depth":length,"rotate":[0,90,0],"color":"#64758a"},{"type":"flange","r":nd*.72,"inner":nd*.46,"depth":12,"at":[-length/2,0,0],"rotate":[0,90,0],"holes":6,"hole_r":3,"pcd":nd*.58,"color":"#8190a2"},{"type":"flange","r":nd*.72,"inner":nd*.46,"depth":12,"at":[length/2,0,0],"rotate":[0,90,0],"holes":6,"hole_r":3,"pcd":nd*.58,"color":"#8190a2"},{"type":"cylinder","r":nd*.3,"depth":nd*.42,"at":[0,0,nd*.66],"color":"#8190a2"},{"type":"cylinder","r":nd*.105,"depth":stem_depth,"at":[0,0,stem_start+stem_depth/2],"color":"#64758a"},{"type":"cylinder","r":nd*.18,"depth":nd*.16,"at":[0,0,wheel_z],"color":"#738297"},{"type":"cylinder","r":nd*.045,"depth":wheel_r*2,"at":[0,0,wheel_z],"rotate":[0,90,0],"color":"#8997a8"},{"type":"cylinder","r":nd*.045,"depth":wheel_r*2,"at":[0,0,wheel_z],"rotate":[90,0,0],"color":"#8997a8"},{"type":"torus","r":wheel_r,"tube":nd*.065,"at":[0,0,wheel_z],"color":"#a6b0bc"}]
    if part == "shaft":
        length=float(p["total_length"]); steps=max(3,min(6,int(p["steps"]))); maximum=float(p["max_diameter"])
        return [{"type":"cylinder","r":maximum/2*(.62+.38*math.sin(math.pi*(i+1)/(steps+1))),"depth":length/steps,"at":[-length/2+length*(i+.5)/steps,0,0],"rotate":[0,90,0],"color":"#8e9baa"} for i in range(steps)]
    if part == "gear":
        return [{"type":"gear","r":float(p["module"])*float(p["teeth"])/2,"inner":float(p["bore"])/2,"depth":float(p["face_width"]),"teeth":int(p["teeth"]),"color":"#8795a5"}]
    if part == "screw":
        diameter=float(p["diameter"]); length=float(p["length"])
        journal_length=min(length*.12,max(diameter*1.35,length*.08));thread_length=length-2*journal_length
        journal_r=diameter*.32;shoulder_width=max(diameter*.12,min(diameter*.3,journal_length*.16))
        return [
            {"type":"cylinder","r":diameter/2,"depth":thread_length,"rotate":[0,90,0],"color":"#8e9cab"},
            {"type":"helix","r":diameter*.56,"depth":thread_length,"pitch":float(p["lead"]),"starts":int(p.get("starts",1)),"handedness":"right","profile":"trapezoidal","color":"#65768a"},
            {"type":"cylinder","r":diameter*.56,"depth":shoulder_width,"at":[-thread_length/2,0,0],"rotate":[0,90,0],"color":"#77879a"},
            {"type":"cylinder","r":diameter*.56,"depth":shoulder_width,"at":[thread_length/2,0,0],"rotate":[0,90,0],"color":"#77879a"},
            {"type":"cylinder","r":journal_r,"depth":journal_length,"at":[-(thread_length+journal_length)/2,0,0],"rotate":[0,90,0],"color":"#9aa6b4"},
            {"type":"cylinder","r":journal_r,"depth":journal_length,"at":[(thread_length+journal_length)/2,0,0],"rotate":[0,90,0],"color":"#9aa6b4"},
        ]
    if part == "coupling":
        r=float(p["outer_diameter"])/2; length=float(p["length"]); inner=float(p["bore"])/2
        return [{"type":"tube","r":r,"inner":inner,"depth":length*.22,"at":[0,0,-length*.38],"color":"#8997a7"},{"type":"tube","r":r,"inner":inner,"depth":length*.22,"at":[0,0,length*.38],"color":"#a4afbc"},{"type":"tube","r":r*.68,"inner":inner,"depth":length*.64,"color":"#718095"}]
    return [{"type":"tube","r":float(p["outer_diameter"])/2,"inner":float(p["inner_diameter"])/2,"depth":float(p["width"]),"color":"#6f7e90"}]


def build_shape(part: str, p: dict[str, Any]):
    if part not in GENERATOR_VERSIONS:
        raise ValueError(f"未注册的参数化生成器: {part}")
    if part == "rocket":
        from .rocket import build_falcon9_shape

        return build_falcon9_shape(p)
    from OCP.BRep import BRep_Builder
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCone, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere, BRepPrimAPI_MakeTorus
    from OCP.gp import gp_Ax1, gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
    from OCP.TopoDS import TopoDS_Compound

    def cylinder(r, depth, x=0, y=0, z=0, axis="z"):
        direction={"x":gp_Dir(1,0,0),"y":gp_Dir(0,1,0),"z":gp_Dir(0,0,1)}[axis]
        start={"x":gp_Pnt(x-depth/2,y,z),"y":gp_Pnt(x,y-depth/2,z),"z":gp_Pnt(x,y,z-depth/2)}[axis]
        return BRepPrimAPI_MakeCylinder(gp_Ax2(start,direction),r,depth).Shape()

    def tube(outer, inner, depth, **kwargs):
        return BRepAlgoAPI_Cut(cylinder(outer,depth,**kwargs),cylinder(inner,depth*1.1,**kwargs)).Shape()

    def moved(shape, x=0, y=0, z=0, axis=None, angle=0):
        result = shape
        if axis and angle:
            rotation=gp_Trsf();rotation.SetRotation(gp_Ax1(gp_Pnt(0,0,0),gp_Dir(*axis)),angle)
            result=BRepBuilderAPI_Transform(result,rotation,True).Shape()
        if x or y or z:
            translation=gp_Trsf();translation.SetTranslation(gp_Vec(x,y,z))
            result=BRepBuilderAPI_Transform(result,translation,True).Shape()
        return result

    def compound(shapes):
        result=TopoDS_Compound();builder=BRep_Builder();builder.MakeCompound(result)
        for shape in shapes: builder.Add(result,shape)
        return result

    def fuse(shapes):
        """Build a single B-Rep where primitives overlap; fail loudly on bad geometry."""
        iterator = iter(shapes)
        result = next(iterator)
        for item in iterator:
            operation = BRepAlgoAPI_Fuse(result, item)
            operation.Build()
            if not operation.IsDone():
                raise RuntimeError("OpenCascade boolean fuse failed")
            result = operation.Shape()
        return result

    def trapezoidal_helix(radius, length, lead, starts=1, axis_start=0):
        """Sweep right-hand trapezoidal thread ridges around the +X axis."""
        from OCP.BRepAdaptor import BRepAdaptor_Curve
        from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeWire
        from OCP.BRepLib import BRepLib
        from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipe
        from OCP.Geom import Geom_CylindricalSurface
        from OCP.Geom2d import Geom2d_Line, Geom2d_TrimmedCurve
        from OCP.gp import gp_Ax3, gp_Dir2d, gp_Pnt2d, gp_Vec

        turns=length/lead;thread_height=min(radius*.18,lead*.38);root_half_width=lead*.22;crest_half_width=lead*.1
        surface=Geom_CylindricalSurface(gp_Ax3(gp_Pnt(axis_start,0,0),gp_Dir(1,0,0)),radius)
        direction=gp_Dir2d(2*math.pi,lead);parameter_per_turn=math.hypot(2*math.pi,lead)
        ridges=[]
        for start in range(max(1,int(starts))):
            line=Geom2d_Line(gp_Pnt2d(start*2*math.pi/max(1,int(starts)),0),direction)
            segment_count=max(1,math.ceil(turns/8))
            for segment in range(segment_count):
                first_turn=turns*segment/segment_count;last_turn=turns*(segment+1)/segment_count
                curve=Geom2d_TrimmedCurve(line,first_turn*parameter_per_turn,last_turn*parameter_per_turn)
                edge=BRepBuilderAPI_MakeEdge(curve,surface).Edge();BRepLib.BuildCurves3d_s(edge)
                adaptor=BRepAdaptor_Curve(edge);point=gp_Pnt();tangent=gp_Vec()
                adaptor.D1(adaptor.FirstParameter(),point,tangent);tangent.Normalize()
                radial=gp_Vec(0,point.Y(),point.Z());radial.Normalize();side=tangent.Crossed(radial);side.Normalize()
                polygon=BRepBuilderAPI_MakePolygon()
                for radial_offset,side_offset in ((0,root_half_width),(thread_height,crest_half_width),(thread_height,-crest_half_width),(0,-root_half_width)):
                    polygon.Add(point.Translated(radial.Multiplied(radial_offset).Added(side.Multiplied(side_offset))))
                polygon.Close()
                profile=BRepBuilderAPI_MakeFace(polygon.Wire()).Face();spine=BRepBuilderAPI_MakeWire(edge).Wire()
                pipe=BRepOffsetAPI_MakePipe(spine,profile)
                if not pipe.IsDone():
                    raise RuntimeError("OpenCascade trapezoidal thread sweep failed")
                ridges.append(pipe.Shape())
        return compound(ridges)

    if part=="bearing":
        od=float(p["outer_diameter"]);bore=float(p["inner_diameter"]);width=float(p["width"]);n=int(p["rolling_elements"]);pitch=(od+bore)/4;ball=min(width*.29,(od-bore)*.105)
        shapes=[tube(od/2,od*.39,width),tube(bore*.72,bore/2,width)]
        if int(p.get("variant",0)) == 1:
            roller_length=min(width*.62,(od-bore)*.22);roller_r=min(width*.18,(od-bore)*.075)
            shapes += [cylinder(roller_r,roller_length,math.cos(i*2*math.pi/n)*pitch,math.sin(i*2*math.pi/n)*pitch) for i in range(n)]
        else:
            shapes += [BRepPrimAPI_MakeSphere(gp_Pnt(math.cos(i*2*math.pi/n)*pitch,math.sin(i*2*math.pi/n)*pitch,0),ball).Shape() for i in range(n)]
        return compound(shapes)
    if part=="flange":
        od=float(p["outer_diameter"]);bore=float(p["inner_diameter"]);depth=float(p["thickness"]);count=int(p["bolt_holes"]);neck_height=float(p.get("neck_height",0))
        outer_r=od/2;bore_r=bore/2;radial=max(outer_r-bore_r,1);requested_hole=float(p.get("bolt_hole_diameter",0));hole_r=requested_hole/2 if requested_hole>0 else max(3,min(od*.035,radial*.18));pcd=bore_r+radial*.62
        body=cylinder(outer_r,depth)
        if neck_height>0:
            neck_base=min(pcd-hole_r*1.8,max(bore_r*1.36,bore_r+depth*.55))
            neck_top=min(neck_base*.84,max(bore_r*1.12,bore_r+depth*.18))
            neck=BRepPrimAPI_MakeCone(gp_Ax2(gp_Pnt(0,0,depth/2-.05),gp_Dir(0,0,1)),neck_base,neck_top,neck_height+.05).Shape()
            body=fuse([body,neck])
        bore_depth=depth+neck_height+2
        shape=BRepAlgoAPI_Cut(body,cylinder(bore_r,bore_depth,z=neck_height/2)).Shape()
        for i in range(count):
            hole=cylinder(hole_r,depth*1.2,math.cos(i*2*math.pi/count)*pcd,math.sin(i*2*math.pi/count)*pcd)
            shape=BRepAlgoAPI_Cut(shape,hole).Shape()
        groove=float(p.get("groove_width",0))
        if groove>0:
            groove_center=bore_r+max(groove*.9,radial*.28);groove_outer=min(outer_r*.88,groove_center+groove/2);groove_inner=max(bore_r+groove*.25,groove_center-groove/2)
            cutter=tube(groove_outer,groove_inner,min(depth*.22,max(1,groove*.35)),z=depth/2)
            shape=BRepAlgoAPI_Cut(shape,cutter).Shape()
        return shape
    if part=="valve":
        nd=float(p["nominal_diameter"]);length=float(p["body_length"]);height=float(p["height"]);variant=int(p.get("variant",0))
        flange_depth=max(10,nd*.08);flange_outer=nd*.72;flow_r=nd*.46
        if variant == 1:
            disc=max(float(p.get("disc_thickness",0)),nd*.08);stem=max(float(p.get("stem_diameter",0)),nd*.1)
            body=tube(nd*.62,flow_r,length,axis="x")
            shapes=[body,tube(flange_outer,flow_r,flange_depth,x=-length/2,axis="x"),tube(flange_outer,flow_r,flange_depth,x=length/2,axis="x"),cylinder(flow_r*.98,disc,axis="x"),cylinder(stem,height*.58,z=height*.29)]
            if int(p.get("actuator",0)):
                motor=BRepPrimAPI_MakeBox(gp_Pnt(-nd*.42,-nd*.3,height*.52),nd*.84,nd*.6,nd*.4).Shape();shapes.append(motor)
            return fuse(shapes)
        if variant == 2:
            body=fuse([BRepPrimAPI_MakeSphere(gp_Pnt(0,0,0),nd*.75).Shape(),cylinder(nd/2,length,axis="x"),tube(flange_outer,flow_r,flange_depth,x=-length/2,axis="x"),tube(flange_outer,flow_r,flange_depth,x=length/2,axis="x"),cylinder(nd*.42,nd*.22,z=nd*.62)])
            return body
        wheel_r=nd*.57;wheel_tube=nd*.065
        wheel_z=max(height-nd*.75-max(wheel_tube,nd*.08),nd*1.55);stem_start=nd*.5
        stem_depth=wheel_z-stem_start+nd*.08
        shapes=[
            BRepPrimAPI_MakeSphere(gp_Pnt(0,0,0),nd*.75).Shape(),
            cylinder(nd/2,length,axis="x"),
            tube(nd*.72,nd*.46,12,x=-length/2,axis="x"),
            tube(nd*.72,nd*.46,12,x=length/2,axis="x"),
            cylinder(nd*.3,nd*.42,z=nd*.66),
            cylinder(nd*.105,stem_depth,z=stem_start+stem_depth/2),
            cylinder(nd*.18,nd*.16,z=wheel_z),
            cylinder(nd*.045,wheel_r*2,z=wheel_z,axis="x"),
            cylinder(nd*.045,wheel_r*2,z=wheel_z,axis="y"),
            BRepPrimAPI_MakeTorus(gp_Ax2(gp_Pnt(0,0,wheel_z),gp_Dir(0,0,1)),wheel_r,nd*.065).Shape(),
        ]
        return fuse(shapes)
    if part=="shaft":
        length=float(p["total_length"]);steps=max(3,min(6,int(p["steps"])));maximum=float(p["max_diameter"])
        # Tiny overlap avoids coincident-face compounds and yields one machinable solid.
        overlap = min(0.02, length / steps * 0.001)
        shape=fuse([cylinder(maximum/2*(.62+.38*math.sin(math.pi*(i+1)/(steps+1))),length/steps+2*overlap,x=-length/2+length*(i+.5)/steps,axis="x") for i in range(steps)])
        inner=float(p.get("inner_diameter",0))
        if inner>0:
            shape=BRepAlgoAPI_Cut(shape,cylinder(inner/2,length*1.02,axis="x")).Shape()
        keyway=float(p.get("keyway_width",0))
        if keyway>0 and int(p.get("keyway_present",0)):
            cutter=BRepPrimAPI_MakeBox(gp_Pnt(-length*.28,-keyway/2,maximum*.34),length*.56,keyway,maximum*.22).Shape();shape=BRepAlgoAPI_Cut(shape,cutter).Shape()
        spline_ends=int(p.get("spline_ends",0))
        if spline_ends:
            end_length=min(length*.12,maximum*.8);rib_r=maximum*.34;rib_h=maximum*.09;rib_w=maximum*.09;ribs=[]
            centers=[-length/2+end_length/2] + ([length/2-end_length/2] if spline_ends>1 else [])
            for center in centers:
                for i in range(12):
                    base=BRepPrimAPI_MakeBox(gp_Pnt(center-end_length/2,rib_r,-rib_w/2),end_length,rib_h,rib_w).Shape()
                    ribs.append(moved(base,axis=(1,0,0),angle=i*2*math.pi/12))
            shape=fuse([shape,compound(ribs)])
            if inner>0: shape=BRepAlgoAPI_Cut(shape,cylinder(inner/2,length*1.02,axis="x")).Shape()
        return shape
    if part=="gear":
        module=float(p["module"]);teeth=max(10,min(64,int(p["teeth"])));outer=module*teeth/2;root=outer*.84;depth=float(p["face_width"]);bore=float(p["bore"])/2
        core=cylinder(root,depth)
        teeth_shapes=[];helix=math.radians(float(p.get("helix_angle",0)));segments=3 if abs(helix)>.01 else 1
        tooth_w=2*math.pi*outer/teeth*.52
        tooth_depth=(outer-root)+module*.2
        for i in range(teeth):
            for segment in range(segments):
                z=-depth/2+(segment+.5)*depth/segments;twist=helix*((segment+.5)/segments-.5)
                angle=i*2*math.pi/teeth+twist;x=math.cos(angle)*(root+(outer-root)/2);y=math.sin(angle)*(root+(outer-root)/2)
                box=BRepPrimAPI_MakeBox(gp_Pnt(-tooth_w/2,-tooth_depth/2,-depth/segments*.52),tooth_w,tooth_depth,depth/segments*1.04).Shape()
                teeth_shapes.append(moved(box,x=x,y=y,z=z,axis=(0,0,1),angle=angle-math.pi/2))
        body=fuse([core,*teeth_shapes])
        shape=BRepAlgoAPI_Cut(body,cylinder(bore,depth*1.1)).Shape()
        keyway=float(p.get("keyway_width",0))
        if keyway>0:
            shape=BRepAlgoAPI_Cut(shape,BRepPrimAPI_MakeBox(gp_Pnt(bore*.65,-keyway/2,-depth),root,keyway,depth*2).Shape()).Shape()
        if int(p.get("spline_bore",0)):
            slots=[]
            for i in range(12):
                slot=BRepPrimAPI_MakeBox(gp_Pnt(bore*.72,-bore*.11,-depth),bore*.32,bore*.22,depth*2).Shape();slots.append(moved(slot,axis=(0,0,1),angle=i*2*math.pi/12))
            shape=BRepAlgoAPI_Cut(shape,compound(slots)).Shape()
        return shape
    if part=="screw":
        diameter=float(p["diameter"]);length=float(p["length"]);lead=max(2,float(p["lead"]))
        journal_length=min(length*.12,max(diameter*1.35,length*.08));thread_length=length-2*journal_length
        journal_r=diameter*.32;overlap=min(.08,journal_length*.01);shoulder_width=max(diameter*.12,min(diameter*.3,journal_length*.16))
        core=fuse([
            cylinder(diameter/2,thread_length+2*overlap,axis="x"),
            cylinder(journal_r,journal_length+overlap,x=-(thread_length+journal_length)/2,axis="x"),
            cylinder(journal_r,journal_length+overlap,x=(thread_length+journal_length)/2,axis="x"),
            cylinder(diameter*.56,shoulder_width,x=-thread_length/2,axis="x"),
            cylinder(diameter*.56,shoulder_width,x=thread_length/2,axis="x"),
        ])
        if int(p.get("variant",0)) == 1:
            ring_count=max(3,int(thread_length/lead));tube_r=min(lead*.08,diameter*.04)
            races=[BRepPrimAPI_MakeTorus(gp_Ax2(gp_Pnt(-thread_length/2+(i+.5)*thread_length/ring_count,0,0),gp_Dir(1,0,0)),diameter*.49,tube_r).Shape() for i in range(ring_count)]
            return fuse([core,compound(races)])
        thread=trapezoidal_helix(diameter/2*.985,thread_length,lead,int(p.get("starts",1)),-thread_length/2)
        return fuse([core,thread])
    if part=="coupling":
        r=float(p["outer_diameter"])/2;length=float(p["length"]);inner=min(float(p["bore"])/2,r*.82);inner_b=min(float(p.get("bore_b",p["bore"]))/2,r*.82);variant=int(p.get("variant",0))
        if variant == 0:
            flange_t=length*.18;hub_r=r*.58;shapes=[tube(r,inner,flange_t,z=-length*.16),tube(r,inner_b,flange_t,z=length*.16),tube(hub_r,inner,length*.5,z=-length*.25),tube(hub_r,inner_b,length*.5,z=length*.25)]
            for i in range(max(4,int(p.get("bolts",6)))):
                angle=i*2*math.pi/max(4,int(p.get("bolts",6)));shapes.append(cylinder(r*.055,length*.46,math.cos(angle)*r*.76,math.sin(angle)*r*.76))
            return fuse(shapes)
        if variant == 1:
            hub_len=length*.3;elastic=tube(r*.82,min(inner,inner_b)*.9,length*.44)
            return fuse([tube(r,inner,hub_len,z=-length*.35),tube(r,inner_b,hub_len,z=length*.35),elastic])
        membrane_t=max(1,length*.025);gap=length*.2
        return fuse([tube(r*.72,inner,length*.34,z=-length*.33),tube(r*.72,inner_b,length*.34,z=length*.33),tube(r,inner*.85,membrane_t,z=-gap),tube(r,inner_b*.85,membrane_t,z=gap),tube(r*.38,min(inner,inner_b)*.82,gap*2.05)])
    outer=float(p["outer_diameter"])/2;inner=float(p["inner_diameter"])/2;width=float(p["width"]);shape=tube(outer,inner,width)
    lips=int(p.get("lip_count",0))
    if lips:
        lip_t=max(.8,width*.14);lip_outer=min(outer*.88,inner+max(2,(outer-inner)*.34))
        lip_shapes=[tube(lip_outer,inner*.98,lip_t,z=-width/2+lip_t/2)]
        if lips>1: lip_shapes.append(tube(lip_outer*.92,inner*.98,lip_t,z=width/2-lip_t/2))
        shape=fuse([shape,*lip_shapes])
    groove=float(p.get("groove_width",0))
    if groove>0:
        cutter=tube(outer*1.02,outer-groove,min(width*.3,max(1,groove*.35)))
        shape=BRepAlgoAPI_Cut(shape,cutter).Shape()
    return shape


def _shape_mesh(shape: object) -> dict[str, Any]:
    from OCP.BRep import BRep_Tool
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    box=Bnd_Box();BRepBndLib.Add_s(shape,box)
    bounds=box.Get();diagonal=math.sqrt(sum((bounds[i+3]-bounds[i])**2 for i in range(3)))
    # Preserve small-part detail while bounding triangle counts for metre-scale assemblies.
    deflection=max(0.05,min(5.0,diagonal*0.0002))
    BRepMesh_IncrementalMesh(shape,deflection,False,0.22,True)
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


def write_step(path: Path, title: str, shape: object) -> list[dict[str, Any]]:
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer
    writer=STEPControl_Writer()
    if writer.Transfer(shape,STEPControl_AsIs) != IFSelect_RetDone:
        raise RuntimeError(f"OpenCascade could not transfer {title}")
    if writer.Write(str(path)) != IFSelect_RetDone:
        raise RuntimeError(f"OpenCascade could not write {path.name}")
    return shape_to_model(shape)


def shape_to_model(shape: object) -> list[dict[str, Any]]:
    return [_shape_mesh(shape)]


COMPONENT_COLORS = ("#6f7fd8", "#d47b52", "#48a58b", "#b36ac7", "#d4a43f", "#4b9cc8", "#c85f7d", "#82934b")


def assembly_to_model(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Triangulate each assembly instance separately for semantic coloring."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from .component_spec import _artifact_path, _trsf_from_matrix, load_spec, read_step

    result = []
    color_by_component: dict[str, str] = {}
    constraints = report.get("solved_constraints") or []
    exploded_offsets = constraints[0].get("exploded_offsets_mm") if constraints else None
    for instance in report.get("instances", []):
        spec_path = Path(instance["spec"])
        spec = load_spec(spec_path)
        shape = read_step(_artifact_path(spec_path, spec))
        shape = BRepBuilderAPI_Transform(shape, _trsf_from_matrix(instance["transform"]), True).Shape()
        component_id = str(instance["component_id"])
        color = color_by_component.setdefault(component_id, COMPONENT_COLORS[len(color_by_component) % len(COMPONENT_COLORS)])
        mesh = _shape_mesh(shape)
        instance_index = int(instance["index"])
        if exploded_offsets and instance_index < len(exploded_offsets):
            explode_vector = [0.0, float(exploded_offsets[instance_index]), 0.0]
        else:
            rank = instance_index - (len(report.get("instances", [])) - 1) / 2
            explode_vector = [0.0, 0.0, float(rank * 18.0)]
        mesh.update({"color": color, "component_id": component_id, "instance_index": instance_index, "explode_vector": explode_vector})
        result.append(mesh)
    if report.get("envelopes"):
        from .assembly import envelope_shape
        for offset, envelope in enumerate(report["envelopes"], len(result)):
            mesh = _shape_mesh(envelope_shape(envelope))
            mesh.update({"color": "#303846", "component_id": envelope["component_id"], "instance_index": offset})
            result.append(mesh)
    return result
