"""Native 3D ordering context and actual flow states with optional refinement."""
import argparse,json
from pathlib import Path
import numpy as np
import trimesh,mujoco,viser
from scipy.spatial.transform import Rotation
from replay_geometry import mesh
from scene_annotations import outlined_anchors,set_anchors,path_anchors
from maze_geometry_refinement import Clearance
p=argparse.ArgumentParser();p.add_argument('case',type=Path);p.add_argument('--order-only',action='store_true');a=p.parse_args()
root=Path(__file__).resolve().parents[1];raw=(root/'assets/maze-method-trace.js').read_text();d=json.loads(raw.split(' = ',1)[1].rstrip(';\n'));scene=d['scene']
model=mujoco.MjModel.from_binary_path(str(a.case/'task.mjb'));state=mujoco.MjData(model);record=np.load(a.case/'task.npz');state.qpos[:]=record['qpos'][0]
if model.nmocap:state.mocap_pos[:]=record['mocap_pos'][0];state.mocap_quat[:]=record['mocap_quat'][0]
mujoco.mj_forward(model,state)
palette=[(184,190,187),(170,207,158),(164,193,214)]
def dashed_box(size):
 half=np.asarray(size)/2;vertices=np.array(np.meshgrid(*[[-v,v] for v in half])).T.reshape(-1,3);segments=[]
 for i,x in enumerate(vertices):
  for y in vertices[i+1:]:
   if np.count_nonzero(x!=y)!=1:continue
   for k in range(0,10,2):segments.append([x+(y-x)*k/10,x+(y-x)*(k+1)/10])
 return np.asarray(segments,dtype=np.float32)
def setup():
 server=viser.ViserServer(host='127.0.0.1',port=8099,verbose=False);server.gui.configure_theme(show_logo=False,show_share_button=False);server.scene.world_axes.visible=False
 server.initial_camera.position=(6,-3.2,13.8);server.initial_camera.look_at=(6,5.5,.1);server.initial_camera.fov=.86
 for i,(x0,y0,x1,y1) in enumerate(scene['walls']):
  box=trimesh.creation.box(extents=(x1-x0,y1-y0,.8));server.scene.add_mesh_simple(f'/wall-{i}',vertices=box.vertices,faces=box.faces,position=((x0+x1)/2,(y0+y1)/2,.4),color=(215,219,216),opacity=.7)
 for o,color in zip(scene['objects'],palette):
  i=o['object_id'];box=trimesh.creation.box(extents=o['size']);server.scene.add_mesh_simple(f'/observed-{i}',vertices=box.vertices,faces=box.faces,color=color,position=(*o['pose'][:2],o['size'][2]/2))
  server.scene.add_label(f'/label-{i}',text=f'Object {i} · {o["mass_kg"]:g} kg',position=(o['pose'][0]-1.0,o['pose'][1]-.35,o['size'][2]+.25))
 for i in range(model.ngeom):
  bid=model.geom_bodyid[i]
  if not model.body(bid).name.startswith('robot/') or model.geom_group[i]==3:continue
  rgba=model.geom_rgba[i];mat=model.geom_matid[i]
  if mat>=0:rgba=model.mat_rgba[mat]
  if rgba[3]<=0:continue
  geom=mesh(model,i);rot=Rotation.from_matrix(state.geom_xmat[i].reshape(3,3))
  server.scene.add_mesh_simple(f'/robot/mesh-{i}',vertices=geom.vertices,faces=geom.faces,position=state.geom_xpos[i],wxyz=rot.as_quat(scalar_first=True),color=tuple((rgba[:3]*255).astype(int)))
 goal=trimesh.creation.cylinder(radius=.25,height=.025,sections=32);server.scene.add_mesh_simple('/goal',vertices=goal.vertices,faces=goal.faces,position=(*scene['goal'][:2],.02),color=(141,180,143))
 server.scene.add_grid('/floor',width=12,height=12,position=(6,6,-.015),cell_size=.5,cell_color=(236,239,237),section_color=(223,228,224))
 return server
server=setup()
# All explanation stages share one scene and camera. The browser toggles the
# groups without loading a new recording or pretending to show optimizer steps.
server.scene.add_frame('/order',show_axes=False)
stages=['context','supervision','prediction']+[f'sample-{i}' for i in range(len(d['traces']))]
for stage in stages:server.scene.add_frame('/order/'+stage,show_axes=False,visible=stage=='context')
server.scene.add_label('/order/context/context',text='Body + object states + scene → context H',position=(6,5.5,2.5))
for i,o in enumerate(scene['objects']):
 pos=(o['pose'][0]-.85,o['pose'][1],o['size'][2]+.5);rank=d['supervision']['rank'][i]
 server.scene.add_label(f'/order/supervision/target-{i}',text=f'Object {i} · '+('omit' if rank<0 else f'select · rank {rank+1}'),position=pos)
 server.scene.add_label(f'/order/prediction/prediction-{i}',text=f'Object {i} · q={d["selection"][i]:.3f}\nμ={d["mu"][i]:.2f} · σ={d["sigma"][i]:.2f}',position=pos)
 for sample,trace in enumerate(d['traces']):
  rank=trace['rank'][i]
  server.scene.add_label(f'/order/sample-{sample}/rank-{i}',text=f'Object {i} · '+('omit' if rank<0 else f'rank {rank+1}\nu={trace["priority"][i]:.2f}'),position=pos)
  if rank>=0:
   ring=trimesh.creation.annulus(r_min=.48,r_max=.57,height=.015,sections=48)
   server.scene.add_mesh_simple(f'/order/sample-{sample}/ring-{i}',vertices=ring.vertices,faces=ring.faces,position=(*o['pose'][:2],.05),color=palette[i])
# A common priority axis connects the learned Gaussians to actual saved draws.
for group,draw in [('prediction',None)]+[(f'sample-{j}',trace) for j,trace in enumerate(d['traces'])]:
 prefix='/order/'+group
 server.scene.add_line_segments(prefix+'/priority-axis',points=np.array([[[2,6.2,1.5],[10,6.2,1.5]]],np.float32),colors=(100,110,103),line_width=2)
 server.scene.add_label(prefix+'/axis-title',text='Priority distributions · lower comes first',position=(2,5.55,1.5))
 for value in [-8,0,8]:server.scene.add_label(prefix+'/tick-'+str(value),text=str(value),position=(2+(value+8)/2,5.95,1.5))
 for i,(mu,sigma) in enumerate(zip(d['mu'],d['sigma'])):
  values=np.linspace(mu-3.5*sigma,mu+3.5*sigma,80);density=np.exp(-.5*((values-mu)/sigma)**2)
  curve=np.column_stack([2+(values+8)/2,6.2+1.15*density,np.full(len(values),1.5)]).astype(np.float32)
  server.scene.add_line_segments(prefix+f'/distribution-{i}',points=np.stack([curve[:-1],curve[1:]],axis=1),colors=palette[i],line_width=4)
  server.scene.add_label(prefix+f'/distribution-label-{i}',text=f'Object {i}',position=(2+(mu+8)/2-.4,7.65,1.5))
  if draw is not None:
   x=2+(draw['priority'][i]+8)/2
   server.scene.add_line_segments(prefix+f'/draw-{i}',points=np.array([[[x,6.15,1.5],[x,7.35,1.5]]],np.float32),colors=palette[i],line_width=2)
   outlined_anchors(server,prefix+f'/draw-anchor-{i}',[[x,6.2,1.51]],palette[i],.10)
teachers=[]
for path in d['supervision']['paths']:
 i=path['object'];poses=np.asarray(path['poses']);points=np.column_stack([poses[:,:2],np.full(len(poses),.08)]).astype(np.float32)
 server.scene.add_line_segments(f'/order/supervision/reference-{i}',points=np.stack([points[:-1],points[1:]],axis=1),colors=palette[i],line_width=5)
 outlined_anchors(server,f'/order/supervision/anchors-{i}',path_anchors(points[:,:2],4),palette[i],.14)
 teachers.append((server.scene.add_line_segments(f'/order/supervision/ghost-{i}',points=dashed_box(scene['objects'][i]['size']),colors=palette[i],line_width=2),poses,i))
for sample,trace in enumerate(d['traces']):
 ids=sorted([i for i,r in enumerate(trace['rank']) if r>=0],key=lambda i:trace['rank'][i])
 points=np.array([[*scene['objects'][i]['pose'][:2],1.6] for i in ids],np.float32)
 server.scene.add_line_segments(f'/order/sample-{sample}/sequence',points=np.stack([points[:-1],points[1:]],axis=1),colors=(110,130,119),line_width=4)
def teacher_pose(t):
 for j,(ghost,poses,i) in enumerate(teachers):
  progress=np.clip((t-j*.5)*2,0,1)*(len(poses)-1);lo=int(progress);hi=min(lo+1,len(poses)-1);u=progress-lo;pose=(1-u)*poses[lo]+u*poses[hi]
  ghost.position=(*pose[:2],scene['objects'][i]['size'][2]/2);ghost.wxyz=Rotation.from_euler('z',pose[2]).as_quat(scalar_first=True)
teacher_pose(0);recording=server.get_scene_serializer()
for frame in range(240):teacher_pose(frame/239);recording.insert_sleep(1/30)
(root/'assets/recordings/method-order-maze.viser').write_bytes(recording.serialize());server.stop()
if a.order_only:raise SystemExit(0)
for sample,trace in enumerate(d['traces']):
 for refined in [False,True]:
  key=f'method-flow-{sample}-'+('refined' if refined else 'raw');server=setup();ghosts={};lines={};anchors={}
  for path in trace['states'][0]:
   i=path['object'];o=scene['objects'][i];ghosts[i]=server.scene.add_line_segments(f'/ghost-{i}',points=dashed_box(o['size']),colors=palette[i],line_width=2)
   lines[i]=server.scene.add_line_segments(f'/path-{i}',points=np.zeros((7,2,3),dtype=np.float32),colors=palette[i],line_width=6)
   anchors[i]=outlined_anchors(server,f'/anchor-{i}',np.zeros((4,3)),palette[i],.15)
  def pose(frame):
   t=frame/359;f=t*30;lo=int(f);hi=min(lo+1,30);u=f-lo;placed={}
   for p0,p1 in zip(trace['states'][lo],trace['states'][hi]):
    i=p0['object'];poses=(1-u)*np.asarray(p0['poses'])+u*np.asarray(p1['poses']);xy=Clearance(scene,i,placed).refine(poses) if refined else poses[:,:2]
    placed[i]=xy[-1];z=scene['objects'][i]['size'][2]/2
    points=np.column_stack([xy,np.full(len(xy),scene['objects'][i]['size'][2]+.12)]).astype(np.float32);lines[i].points=np.stack([points[:-1],points[1:]],axis=1)
    set_anchors(anchors[i],path_anchors(xy,4,scene['objects'][i]['size'][2]+.12))
    ghosts[i].position=(*xy[-1],z);ghosts[i].wxyz=Rotation.from_euler('z',poses[-1,2]).as_quat(scalar_first=True)
  pose(0);recording=server.get_scene_serializer()
  for k in range(360):pose(k);recording.insert_sleep(1/60)
  (root/'assets/recordings'/f'{key}.viser').write_bytes(recording.serialize());server.stop();print(key,flush=True)
