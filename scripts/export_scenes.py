"""Export anonymous, multi-embodiment Viser recordings from numeric archives.

Structure: four individual translucent meshes with kinematic link graphs.
Scene: four recorded terrain views and two illustrative mesh highlight views.
Geometry and poses remain from the archive; no new physics is claimed.
"""
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
import trimesh
import viser

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
 terrain=mode.startswith('scene-');mixed=mode=='scene-maze'
 selected=([mode.removeprefix('structure-')] if structure else ['g1','spot_arm'] if mode=='highlight-accessibility' else ['g1','spot','husky'] if highlight or mixed else [{'scene-stairs':'g1','scene-steps':'spot','scene-slope':'husky'}.get(mode,'g1')])
 centered=structure or highlight
 if structure:
  name=selected[0];target=.85 if name=='g1' else .45
  server.initial_camera.position=(2.5,-3,2.0);server.initial_camera.look_at=(0,0,target);server.initial_camera.fov=.63
 elif highlight:
  server.initial_camera.position=(4,-7,4);server.initial_camera.look_at=(0,0,.6);server.initial_camera.fov=.66
 elif mixed:
  server.initial_camera.position=(19,-13,23);server.initial_camera.look_at=(5,8,0);server.initial_camera.fov=.68
 elif terrain:
  lane={'scene-stairs':2.5,'scene-steps':5.5,'scene-slope':8.5}[mode]
  server.initial_camera.position=(lane+4,2,6);server.initial_camera.look_at=(lane,7.8,.6);server.initial_camera.fov=.65
 else:
  server.initial_camera.position=(15,-9,15);server.initial_camera.look_at=(5,8,.2);server.initial_camera.fov=.8
 offsets={name:((j-(len(selected)-1)/2)*1.9,0) for j,name in enumerate(selected)}
 frames={};indices={};skeletons={};joints={};edges={}
 for name in selected:
  g,s=data[name]
  if centered:
   # A walking excerpt, with global root translation removed for inspection.
   indices[name]=np.linspace(250,950,240).astype(int)
  elif terrain and not mixed:indices[name]=terrain_indices(s)[np.linspace(0,299,240).astype(int)]
  else:indices[name]=np.linspace(0,len(s['times'])-1,240).astype(int)
  for i,b in enumerate(g['geom_body']):
   b=int(b);body_name=str(s['body_names'][b]);robot=body_name.startswith('robot/')
   if centered and not robot:continue
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
   if mode=='scene-steps' and b==0:
    # Preserve the recorded contact surface while exposing a supported bridge deck.
    top=float(geom_pos[2]+g['geom_size'][i,2])
    deck=trimesh.creation.box(extents=(1.,float(g['geom_size'][i,1])*2,.12))
    v,f=deck.vertices,deck.faces;geom_pos[2]=top-.06
    support_height=max(.03,top-.12)
    support=trimesh.creation.box(extents=(.55,.18,support_height))
    server.scene.add_mesh_simple(f'/bridge/support-{i}',vertices=support.vertices,faces=support.faces,color=(166,173,178),position=(float(geom_pos[0]),float(geom_pos[1]),support_height/2))
   color=np.clip(colors[name].get(i,g['geom_rgba'][i])[:3]*255,0,255).astype(np.uint8)
   opacity=.18 if structure else 1.0
   if highlight:
    keys=('shoulder','elbow','wrist','hand','arm_link','fngr','gripper') if mode=='highlight-accessibility' else ('hip','knee','ankle','leg','foot','wheel')
    selected_region=any(k in body_name.lower() for k in keys)
    color=((41,135,166) if mode=='highlight-accessibility' else (202,137,57)) if selected_region else (150,155,159)
    opacity=.95 if selected_region else .12
   server.scene.add_mesh_simple(f'{prefix}/mesh-{i}',vertices=v,faces=f,color=color,opacity=opacity,side='double' if centered else 'front',cast_shadow=not centered,flat_shading=int(g['geom_type'][i])!=7,position=geom_pos,wxyz=g['geom_local_quat'][i])
  if centered:
   edges[name]=parent_links(name)
   skeletons[name]=server.scene.add_line_segments(f'/{name}/kinematics',points=np.zeros((len(edges[name]),2,3),dtype=np.float32),colors=(110,115,120) if highlight else (53,73,86),line_width=2 if highlight else 3)
   joint_ids=sorted(set(edges[name].flatten().tolist()))
   joints[name]=(joint_ids,server.scene.add_point_cloud(f'/{name}/joints',points=np.zeros((len(joint_ids),3),dtype=np.float32),colors=(110,115,120) if highlight else (37,80,104),point_size=.027 if highlight else .037,point_shape='circle',precision='float32'))
 if centered:
  server.scene.add_grid('/grid',width=3.5 if structure else 6,height=3.5,cell_color=(235,235,235),section_color=(219,219,219))
 elif terrain and not mixed:
  server.scene.add_grid('/grid',width=3,height=8,position=(lane,8,-.01),cell_color=(235,235,235),section_color=(219,219,219))
 else:
  server.scene.add_grid('/grid',width=12,height=19,position=(5,8,-.02),cell_color=(235,235,235),section_color=(219,219,219))
 if mode=='objects':
  for (name,b) in frames:server.scene.add_frame(f'/{name}/body-{b}/axes',axes_length=.75,axes_radius=.025)
 def pose(step):
  for name in selected:
   _,s=data[name];idx=indices[name][step];positions=s['xpos'][idx].copy()
   if centered:positions[:,:2]+=np.asarray(offsets[name])-positions[1,:2]
   for (robot,b),h in frames.items():
    if robot==name:h.position=positions[b];h.wxyz=s['xquat'][idx,b]
   if centered:
    skeletons[name].points=positions[edges[name]].astype(np.float32)
    ids,cloud=joints[name];cloud.points=positions[ids].astype(np.float32)
 pose(0);recording=server.get_scene_serializer()
 for step in range(240):pose(step);recording.insert_sleep(.05)
 (out/f'{mode}.viser').write_bytes(recording.serialize());server.stop()
 print(mode,(out/f'{mode}.viser').stat().st_size,flush=True)
