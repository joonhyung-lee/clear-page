from scene_annotations import outlined_anchors
"""Export anonymous, multi-embodiment Viser recordings from numeric archives.

Structure: four individual translucent meshes with kinematic link graphs.
Scene: archived terrain replays and a constructed two-block bridge.
Object states and the retargeted bridge gait are illustrative. No new physics
or experiment result is claimed by these explanatory views.
"""
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
import trimesh
import viser
from scipy.spatial.transform import Rotation

p=argparse.ArgumentParser()
p.add_argument('source',type=Path)
p.add_argument('--scenes',nargs='+')
a=p.parse_args()
out=Path(__file__).resolve().parents[1]/'assets/recordings'
out.mkdir(exist_ok=True)
names=['g1','spot','spot_arm','husky']
data={name:(dict(np.load(a.source/f'{name}__geometry.npz',allow_pickle=False)),dict(np.load(a.source/f'{name}__states.npz',allow_pickle=False))) for name in names}
cache={}
xml_roots={}

def visual_colors(name):
 # MuJoCo stores material color separately from geom_rgba. Resolve the archived
 # material declarations without loading or copying any XML filesystem paths.
 folders={'g1':'g1__push','spot':'spot__stairs','spot_arm':'spot_arm__push','husky':'husky__ramp'}
 xml=ET.parse(a.source.parent/'replays'/folders[name]/f'{name}.xml').getroot()
 xml_roots[name]=xml
 materials={m.get('name'):np.fromstring(m.get('rgba','1 1 1 1'),sep=' ') for m in xml.findall('./asset/material')}
 defaults={}
 def visit_defaults(node,inherited):
  attrs=dict(inherited)
  if node.find('geom') is not None:attrs.update(node.find('geom').attrib)
  defaults[node.get('class','')]=attrs
  for child in node.findall('default'):visit_defaults(child,attrs)
 for node in xml.findall('default'):visit_defaults(node,{})
 ordered=[]
 def visit_body(node):
  ordered.extend(node.findall('geom'))
  for child in node.findall('body'):visit_body(child)
 visit_body(xml.find('worldbody'))
 by_name={geom.get('name'):geom for geom in ordered if geom.get('name')}
 result={}
 g,_=data[name]
 for i,raw_name in enumerate(g['geom_name']):
  geom_name=str(raw_name)
  geom=by_name.get(geom_name)
  if geom is None and geom_name.startswith('geom') and geom_name[4:].isdigit():
   geom=ordered[int(geom_name[4:])]
  if geom is None:continue
  attrs={**defaults.get(geom.get('class',''),{}),**geom.attrib}
  material=attrs.get('material','')
  if material not in materials and 'robot/'+material in materials:material='robot/'+material
  if 'rgba' in geom.attrib:result[i]=np.fromstring(geom.get('rgba'),sep=' ')
  elif material in materials:result[i]=materials[material]
 return result
colors={name:visual_colors(name) for name in names}

def mesh(name,i):
 if (name,i) in cache:return cache[name,i]
 g,_=data[name];typ=int(g['geom_type'][i]);size=g['geom_size'][i]
 if typ==7:
  v,n=g['mesh_vert_range'][i];f,m=g['mesh_face_range'][i]
  t=trimesh.Trimesh(vertices=g['mesh_vert'][v:v+n],faces=g['mesh_face'][f:f+m],process=True)
  if len(t.faces)>6000:t=t.simplify_quadric_decimation(face_count=6000)
 elif typ==6:t=trimesh.creation.box(extents=size*2)
 elif typ==2:t=trimesh.creation.icosphere(subdivisions=2,radius=size[0])
 elif typ==3:t=trimesh.creation.capsule(radius=size[0],height=size[1]*2,count=[8,8])
 elif typ==5:t=trimesh.creation.cylinder(radius=size[0],height=size[1]*2,sections=16)
 elif typ==4:
  t=trimesh.creation.icosphere(subdivisions=2);t.vertices*=size
 else:return None
 cache[name,i]=(t.vertices,t.faces)
 return cache[name,i]

def terrain_indices(s):
 y=s['xpos'][:,1,1]
 start=int(np.flatnonzero(y>=5.6)[0]);end=int(np.flatnonzero(y>=10.1)[0])
 return np.linspace(start,end,300).astype(int)

def parent_links(name):
 _,s=data[name]
 lookup={str(n):i for i,n in enumerate(s['body_names'])}
 edges=[]
 def visit(node,parent=0):
  for child in node.findall('body'):
   b=lookup.get(child.get('name'),0)
   if b and parent and str(s['body_names'][b]).startswith('robot/'):
    edges.append((parent,b))
   visit(child,b)
 visit(xml_roots[name].find('worldbody'))
 return np.asarray(edges,dtype=int)

modes=a.scenes or [*[f'structure-{n}' for n in names],'objects','scene-stairs','scene-steps','scene-slope','scene-maze','highlight-accessibility','highlight-capability']
for mode in modes:
 server=viser.ViserServer(host='127.0.0.1',port=8099,verbose=False)
 server.gui.configure_theme(show_logo=False,show_share_button=False,control_layout='collapsible',brand_color=(90,90,90))
 server.scene.world_axes.visible=False;server.scene.set_up_direction('+z')
 structure=mode.startswith('structure-');highlight=mode.startswith('highlight-')
 affordance=mode.startswith('affordance-');traversal=mode.startswith('affordance-traversability-')
 terrain=mode.startswith('scene-');mixed=mode=='scene-maze'
 selected=([mode.removeprefix('structure-')] if structure else ['g1','spot_arm'] if mode=='highlight-capability' else ['g1','spot','husky'] if highlight or mixed else [{'scene-stairs':'g1','scene-steps':'spot','scene-slope':'husky'}.get(mode,'g1')])
 if affordance:selected=[mode.split("-",2)[2]]
 centered=structure or highlight or affordance
 frame_count=720 if structure or highlight else 2 if affordance else 240
 frame_dt=1/60 if structure or highlight else .5 if affordance else .05
 bridge=mode=='scene-steps'
 if mode=='objects':
  server.initial_camera.position=(2.65,-3.45,2.85);server.initial_camera.look_at=(0,0,.18);server.initial_camera.fov=.66
  handles=[];corners=[];palette=[(173,207,213),(232,197,173),(191,213,177),(208,191,218)]
  for j in range(4):
   shape=trimesh.creation.box(extents=(.46,.42,.40)) if j%2==0 else trimesh.creation.cylinder(radius=.22,height=.46,sections=40)
   item=server.scene.add_frame(f'/object-{j}',show_axes=False)
   server.scene.add_mesh_simple(f'/object-{j}/shape',vertices=shape.vertices,faces=shape.faces,color=palette[j],flat_shading=j%2==0);handles.append(item)
   # Sparse corner strokes preserve the outline without a triangulated wireframe.
   strokes=[]
   if j%2==0:
    half=np.array([.23,.21,.20])
    for signs in np.array(np.meshgrid([-1,1],[-1,1],[-1,1])).T.reshape(-1,3):
     corner=half*signs
     for axis in range(3):
      endpoint=corner.copy();endpoint[axis]-=signs[axis]*.075;strokes.append([corner,endpoint])
   else:
    for z in [-.23,.23]:
     for angle in np.linspace(0,2*np.pi,8,endpoint=False):
      corner=np.array([.22*np.cos(angle),.22*np.sin(angle),z])
      tangent=np.array([-.22*np.sin(angle),.22*np.cos(angle),0])*.28
      strokes.extend([[corner-tangent,corner+tangent],[corner,corner+np.array([0,0,-np.sign(z)*.07])]])
   corners.append(np.asarray(strokes,dtype=np.float32))
   base=np.array([(j%2-.5)*1.45,(j//2-.5)*1.35,.20 if j%2==0 else .23]);delta=np.array([.36*(-1)**j,.32*(-1)**(j//2),0])
   anchors=np.linspace(base-delta,base+delta,5);anchors[:,2]=.018
   outlined_anchors(server,f'/waypoints-{j}',anchors,palette[j],.045 if j%2==0 else .075)
   server.scene.add_line_segments(f'/lane-{j}',points=np.stack([anchors[:-1],anchors[1:]],axis=1).astype(np.float32),colors=palette[j],line_width=5)
  ghosts=[]
  for j in range(2):
   base=np.array([(j%2-.5)*1.45,(j//2-.5)*1.35,.20 if j%2==0 else .23]);delta=np.array([.36*(-1)**j,.32*(-1)**(j//2),0])
   ghosts.append(server.scene.add_line_segments(f'/future-{j}',points=corners[j],colors=palette[j],line_width=2,position=base+delta,wxyz=Rotation.from_euler('z',.32).as_quat(scalar_first=True)))
  server.scene.add_grid('/grid',width=5,height=5,cell_size=.5,section_size=1,cell_color=(241,241,241),section_color=(229,229,229))
  def object_pose(k):
   # Overlapping continuous motions, not a turn-taking sequence.
   for j,item in enumerate(handles):
    period=[6.,12.,6.,12.][j];phase=((k/60)/period+[0,.12,.25,.38][j])%1
    progress=.5-.5*np.cos(2*np.pi*phase)
    base=np.array([(j%2-.5)*1.45,(j//2-.5)*1.35,.20 if j%2==0 else .23]);delta=np.array([.36*(-1)**j,.32*(-1)**(j//2),0])
    item.position=base-delta+2*delta*progress
    item.wxyz=Rotation.from_euler('z',-.32+.64*progress).as_quat(scalar_first=True)
    if j<2:ghosts[j].visible=phase<.5
  object_pose(0);recording=server.get_scene_serializer()
  for k in range(720):object_pose(k);recording.insert_sleep(1/60)
  (out/f'{mode}.viser').write_bytes(recording.serialize());server.stop();print(mode,flush=True);continue
 if structure or affordance:
  name=selected[0];target=.85 if name=='g1' else .45
  server.initial_camera.position=(1.75,-2.1,1.55) if name=='g1' else (1.35,-1.65,1.2);server.initial_camera.look_at=(0,0,target);server.initial_camera.fov=.63
 elif highlight:
  server.initial_camera.position=(3.3,-5.5,3.0);server.initial_camera.look_at=(0,0,.6);server.initial_camera.fov=.66
 elif mixed:
  server.initial_camera.position=(13,-3.2,13.7);server.initial_camera.look_at=(5,8,.4);server.initial_camera.fov=.68
 elif terrain:
  lane={'scene-stairs':2.5,'scene-steps':5.5,'scene-slope':8.5}[mode]
  server.initial_camera.position=(lane+2.5,4.3,3.6);server.initial_camera.look_at=(lane,8,.7);server.initial_camera.fov=.65
  if mode in ['scene-slope','scene-stairs']:
   server.initial_camera.position=(lane+4.8,4.4,4.6);server.initial_camera.look_at=(lane,7.8,.6);server.initial_camera.fov=.8
 else:
  server.initial_camera.position=(15,-9,15);server.initial_camera.look_at=(5,8,.2);server.initial_camera.fov=.8
 if bridge:
  server.initial_camera.position=(2.9,-4.0,2.75);server.initial_camera.look_at=(0,0,.55);server.initial_camera.fov=.67
  for j,y in enumerate([-1.9,1.9]):
   block=trimesh.creation.box(extents=(1.15,.9,.24))
   server.scene.add_mesh_simple(f'/bridge/block-{j}',vertices=block.vertices,faces=block.faces,color=(166,175,183),position=(0,y,.12))
  board=trimesh.creation.box(extents=(.8,3.4,.10))
  server.scene.add_mesh_simple('/bridge/plank',vertices=board.vertices,faces=board.faces,color=(195,170,127),position=(0,0,.29))
 offsets={name:((j-(len(selected)-1)/2)*1.9,0) for j,name in enumerate(selected)}
 frames={};indices={};skeletons={};joints={};edges={}
 for name in selected:
  g,s=data[name]
  if centered:
   # A walking excerpt, with global root translation removed for inspection.
   start=900 if name=='g1' and structure else 250
   indices[name]=np.full(frame_count,250,dtype=int) if affordance else np.linspace(start,start+600,frame_count)
  elif bridge:indices[name]=np.linspace(250,950,240).astype(int)
  elif terrain and not mixed:indices[name]=terrain_indices(s)[np.linspace(0,299,240).astype(int)]
  else:indices[name]=np.linspace(0,len(s['times'])-1,240).astype(int)
  for i,b in enumerate(g['geom_body']):
   b=int(b);body_name=str(s['body_names'][b]);robot=body_name.startswith('robot/')
   if (centered or bridge) and not robot and not (highlight and body_name=='object/box'):continue
   if mode=='objects' and not body_name.startswith('object'):continue
   if terrain and not robot:
    if name!=selected[0]:continue
    if not mixed:
     if b!=0:continue
     gn=str(g['geom_name'][i]);pos=g['geom_local_pos'][i]
     margin=.1 if mode=='scene-steps' else 1.0
     if not (abs(pos[0]-lane)<margin and 5.8<=pos[1]<=11.6 and not gn.startswith('maze/border')):continue
    elif b!=0 and name!='g1':continue
   geom=mesh(name,i)
   if geom is None:continue
   key=(name,b);prefix=f'/{name}/body-{b}'
   if key not in frames:frames[key]=server.scene.add_frame(prefix,show_axes=False)
   v,f=geom
   geom_pos=g['geom_local_pos'][i].copy()
   color=np.clip(colors[name].get(i,g['geom_rgba'][i])[:3]*255,0,255).astype(np.uint8)
   opacity=.42 if structure else 1.0
   if highlight:
    keys=('shoulder','elbow','wrist','hand','arm_link','fngr','gripper') if mode=='highlight-capability' else ('hip','knee','ankle','leg','foot','wheel')
    selected_region=any(k in body_name.lower() for k in keys)
    color=(159,198,151) if selected_region else (150,155,159)
    opacity=.85 if selected_region else .16
    if not robot:color=(225,193,166);opacity=.85
   if affordance:
    keys=('hip','knee','ankle','leg','foot','wheel') if traversal else ('shoulder','elbow','wrist','hand','arm_link','gripper')
    selected_region=any(k in body_name.lower() for k in keys) or (not traversal and name in ['spot','husky'] and b==1)
    color=(159,198,151) if selected_region else (163,170,168);opacity=.8 if selected_region else .16
   server.scene.add_mesh_simple(f'{prefix}/mesh-{i}',vertices=v,faces=f,color=color,opacity=opacity,side='double' if centered else 'front',cast_shadow=not centered,flat_shading=int(g['geom_type'][i])!=7,position=geom_pos,wxyz=g['geom_local_quat'][i])
  if name=='husky':
   theta=np.linspace(0,2*np.pi,65)
   circle=np.column_stack([.17775*np.cos(theta),np.zeros_like(theta),.17775*np.sin(theta)])
   segments=np.stack([circle[:-1],circle[1:]],axis=1).astype(np.float32)
   for b in range(2,6):
    if centered:server.scene.add_line_segments(f'/husky/body-{b}/wheel-outline',points=segments,colors=(75,87,90),line_width=2)
    for side in [-.065,.065]:
     spokes=np.array([[[-.145,side,0],[.145,side,0]],[[0,side,-.145],[0,side,.145]]],dtype=np.float32)
     server.scene.add_line_segments(f'/husky/body-{b}/spokes-{side}',points=spokes,colors=(181,190,193),line_width=3)
     # An asymmetric sidewall stripe makes rolling legible at thumbnail size.
     stripe=trimesh.creation.box(extents=(.105,.007,.029))
     server.scene.add_mesh_simple(f'/husky/body-{b}/roll-marker-{side}',vertices=stripe.vertices,faces=stripe.faces,position=(.076,side*1.08,0),color=(239,225,181),flat_shading=True)

  if centered:
   edges[name]=parent_links(name)
   skeletons[name]=server.scene.add_line_segments(f'/{name}/kinematics',points=np.zeros((len(edges[name]),2,3),dtype=np.float32),colors=(110,115,120) if highlight else (53,73,86),line_width=2 if highlight else 3)
   joint_ids=sorted(set(edges[name].flatten().tolist()))
   joints[name]=(joint_ids,server.scene.add_point_cloud(f'/{name}/joints',points=np.zeros((len(joint_ids),3),dtype=np.float32),colors=(110,115,120) if highlight else (37,80,104),point_size=.027 if highlight else .037,point_shape='circle',precision='float32'))
 if affordance or structure:
  name=selected[0]
  if traversal or structure:
   # An explanatory support neighborhood, not a learned terrain score.
   for ring in range(3):
    field=trimesh.creation.cylinder(radius=.62+.18*ring,height=.008,sections=64)
    field.vertices[:,1]*=.72
    server.scene.add_mesh_simple(f'/field/support-{ring}',vertices=field.vertices,faces=field.faces,color=(173,211,163),opacity=.12,position=(0,0,.009+ring*.01),visible=not structure)
  if not traversal or structure:
   contacts={'g1':[23,30],'spot_arm':[20],'spot':[1],'husky':[1]}[name]
   for j,b in enumerate(contacts):
    field=trimesh.creation.icosphere(subdivisions=2,radius=.19)
    position=(0,0,0) if name in ['g1','spot_arm'] else (.48,0,.04 if name=='spot' else .25)
    server.scene.add_mesh_simple(f'/{name}/body-{b}/contact-field',vertices=field.vertices,faces=field.faces,color=(173,211,163),opacity=.22,position=position,visible=not structure)
 floor=None
 if centered:
  floor=server.scene.add_grid('/grid',width=20 if structure else 6,height=20 if structure else 3.5,cell_color=(235,235,235),section_color=(219,219,219))
 elif bridge:
  server.scene.add_grid('/grid',width=4,height=6,cell_color=(235,235,235),section_color=(219,219,219))
 elif terrain and not mixed:
  server.scene.add_grid('/grid',width=3,height=8,position=(lane,8,-.01),cell_color=(235,235,235),section_color=(219,219,219))
 else:
  server.scene.add_grid('/grid',width=12,height=19,position=(5,8,-.02),cell_color=(235,235,235),section_color=(219,219,219))
 # Roll angle comes from signed root travel, because archived wheel poses are fixed.
 wheel_distance={}
 for name in selected:
  if name!='husky':continue
  st=data[name][1];directions=Rotation.from_quat(st['xquat'][:-1,1],scalar_first=True).apply(np.tile([1.,0,0],(len(st['times'])-1,1)))
  wheel_distance[name]=np.r_[0,np.cumsum(np.sum(np.diff(st['xpos'][:,1],axis=0)*directions,axis=1))]/.17775
 def pose(step):
  for name in selected:
   _,s=data[name];idx=indices[name][step]
   if structure or highlight:
    lower=int(np.floor(idx));upper=min(lower+1,len(s['xpos'])-1);fraction=float(idx-lower)
    positions=(1-fraction)*s['xpos'][lower]+fraction*s['xpos'][upper]
    qa=s['xquat'][lower];qb=s['xquat'][upper].copy();qb[np.sum(qa*qb,axis=-1)<0]*=-1
    quats=(1-fraction)*qa+fraction*qb;quats/=np.linalg.norm(quats,axis=-1,keepdims=True)
    root_xy=positions[1,:2].copy()
   else:positions=s['xpos'][idx].copy();quats=s['xquat'][idx].copy();root_xy=positions[1,:2].copy()
   if structure and name=='spot_arm':
    # Shared Spot body and leg geometry permits a walking-gait display retarget.
    # Preserve the folded arm, with a small free yaw swing rather than pushing.
    gait=data['spot'][1];lo=int(np.floor(idx));hi=lo+1;u=float(idx-lo)
    positions[:14]=(1-u)*gait['xpos'][lo,:14]+u*gait['xpos'][hi,:14]
    qa=gait['xquat'][lo,:14];qb=gait['xquat'][hi,:14].copy();qb[np.sum(qa*qb,axis=-1)<0]*=-1
    quats[:14]=(1-u)*qa+u*qb;quats[:14]/=np.linalg.norm(quats[:14],axis=-1,keepdims=True)
    initial=Rotation.from_quat(s['xquat'][0,1],scalar_first=True);current=Rotation.from_quat(quats[1],scalar_first=True)
    relative=initial.inv().apply(s['xpos'][0,14:21]-s['xpos'][0,1]);pivot=relative[0].copy();sway=Rotation.from_euler('z',.15*np.sin(step*frame_dt*2))
    positions[14:21]=current.apply(sway.apply(relative-pivot)+pivot)+positions[1]
    quats[14:21]=(current*sway*initial.inv()*Rotation.from_quat(s['xquat'][0,14:21],scalar_first=True)).as_quat(scalar_first=True)
    root_xy=positions[1,:2].copy()
   if name=='husky':
    angle=float(np.interp(float(idx),np.arange(len(wheel_distance[name])),wheel_distance[name]))
    base=Rotation.from_quat(quats[1],scalar_first=True);initial=Rotation.from_quat(s['xquat'][0,1],scalar_first=True)
    for b in range(2,6):quats[b]=(base*Rotation.from_euler('y',angle)*initial.inv()*Rotation.from_quat(s['xquat'][0,b],scalar_first=True)).as_quat(scalar_first=True)
   if bridge:
    root=positions[1].copy();yaw=Rotation.from_quat(quats[1],scalar_first=True).as_euler('xyz')[2]
    turn=Rotation.from_euler('z',np.pi/2-yaw)
    positions=turn.apply(positions-root)+root
    y=-1.95+3.9*step/239
    transition=np.clip((1.82-abs(y))/.22,0,1);height=.24+.10*transition*transition*(3-2*transition)
    positions[:,:2]+=np.array([0,y])-root[:2];positions[:,2]+=height
    quats=(turn*Rotation.from_quat(quats,scalar_first=True)).as_quat(scalar_first=True)
   if centered:positions[:,:2]+=np.asarray(offsets[name])-positions[1,:2]
   for (robot,b),h in frames.items():
    if robot==name:h.position=positions[b];h.wxyz=quats[b]
   if (structure or highlight) and floor is not None and name==selected[0]:
    reference=data['spot'][1] if structure and name=='spot_arm' else s
    displacement=root_xy-reference['xpos'][int(indices[name][0]),1,:2]
    floor.position=(-float(displacement[0]),-float(displacement[1]),0)
   if centered:
    # Husky archives use a ground-referenced mocap origin. Display the base
    # graph at the chassis center, without moving wheels off the contact plane.
    if name=='husky':positions[1]+=Rotation.from_quat(quats[1],scalar_first=True).apply([0,0,.25])
    skeletons[name].points=positions[edges[name]].astype(np.float32)
    ids,cloud=joints[name];cloud.points=positions[ids].astype(np.float32)
 pose(0);recording=server.get_scene_serializer()
 for step in range(frame_count):pose(step);recording.insert_sleep(frame_dt)
 (out/f'{mode}.viser').write_bytes(recording.serialize());server.stop()
 print(mode,(out/f'{mode}.viser').stat().st_size,flush=True)
