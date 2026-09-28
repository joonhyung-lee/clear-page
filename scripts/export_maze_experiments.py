"""Export anonymous numerical scene replays. Requires the recording's MuJoCo version.

Never serialize source XML, names, source metadata, or checkpoint identifiers.
Missing execution records become explicitly labeled static planning scenes.
"""
import argparse,json
from pathlib import Path
import numpy as np
import trimesh
import mujoco
import viser
from scipy.spatial.transform import Rotation

parser=argparse.ArgumentParser()
parser.add_argument('source',type=Path)
parser.add_argument('--only',nargs='*')
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
labels={'clear':'CLEAR (ours)','clear_frozen':'CLEAR without replanning','cdgs':'CDGS','get_encoder':'GET encoder','namo_llm':'NAMO LLM','namo_sampling':'NAMO sampling','no_affordance':'Without affordance','noemb':'Without embodiment','robot_id':'Robot ID','specialist':'Specialist'}
manifest=[]
from replay_geometry import mesh, add
for exp in ['exp3','exp4']:
 for folder in sorted((args.source/exp).iterdir()):
  if not folder.is_dir():continue
  key=('maze-' if exp=='exp3' else 'horizon-')+folder.name.replace('_','-')
  if args.only and folder.name not in args.only:continue
  scene=json.loads((folder/'scene.json').read_text())
  source=json.loads((folder/'source.json').read_text()) if (folder/'source.json').exists() else {}
  episode=json.loads((folder/('episode.json' if (folder/'episode.json').exists() else 'planner.json')).read_text())
  if 'task_success' not in episode:episode={**source,**episode}
  method=source.get('method',episode.get('method','clear_frozen' if folder.name.endswith('frozen') else 'clear'))
  if folder.name.endswith('clear_frozen'):method='clear_frozen'
  label=labels.get(method,source.get('label',method))
  group=('highmass-spot-arm' if 'spot_arm' in folder.name else 'terrain-g1' if 'terrain' in folder.name else 'highmass-g1') if exp=='exp3' else ('A' if folder.name.startswith('A_') else 'B')
  server=viser.ViserServer(host='127.0.0.1',port=8099,verbose=False)
  server.gui.configure_theme(show_logo=False,show_share_button=False);server.scene.world_axes.visible=False
  w,h=scene['world_size'];server.initial_camera.position=(w*.5,-h*.12,max(w,h)*1.12);server.initial_camera.look_at=(w*.5,h*.5,0);server.initial_camera.fov=.86
  replay=(folder/'task.npz').exists() and (folder/'task.mjb').exists()
  duration=0.;frames=1
  if replay:
   m=mujoco.MjModel.from_binary_path(str(folder/'task.mjb'));data=mujoco.MjData(m);a=np.load(folder/'task.npz',allow_pickle=False)
   handles={}
   for bid in range(m.nbody):handles[bid]=server.scene.add_frame(f'/body-{bid}',show_axes=False)
   for i in range(m.ngeom):
    if m.geom_group[i]==3:continue
    rgba=m.geom_rgba[i].copy();mat=m.geom_matid[i]
    if mat>=0:rgba=m.mat_rgba[mat]
    if rgba[3]<=0:continue
    add(server,f'/body-{m.geom_bodyid[i]}/geom-{i}',mesh(m,i),m.geom_pos[i],m.geom_quat[i],tuple((rgba[:3]*255).astype(int)))
   def pose(k):
    data.qpos[:]=a['qpos'][k]
    if m.nmocap:
     data.mocap_pos[:]=a['mocap_pos'][k];data.mocap_quat[:]=a['mocap_quat'][k]
    mujoco.mj_forward(m,data)
    for bid,handle in handles.items():handle.position=data.xpos[bid].copy();handle.wxyz=data.xquat[bid].copy()
   pose(0)
   recording=server.get_scene_serializer()
   # Retain exact states at no more than 10 Hz, including the terminal state.
   times=a['time'];indices=[0]
   for i in range(1,len(times)-1):
    if times[i]-times[indices[-1]]>=.099:indices.append(i)
   if len(times)>1:indices.append(len(times)-1)
   for previous,k in zip(indices,indices[1:]):
    recording.insert_sleep(float(times[k]-times[previous]));pose(k)
   recording.insert_sleep(.1);duration=float(times[-1]-times[0]);frames=len(indices)
  else:
   for j,(x0,y0,x1,y1) in enumerate(scene['walls']):add(server,f'/wall-{j}',trimesh.creation.box(extents=(x1-x0,y1-y0,1.5)),((x0+x1)/2,(y0+y1)/2,.75))
   for j,o in enumerate(scene['objects']):
    x,y,yaw=o['pose'];q=Rotation.from_euler('z',yaw).as_quat()[[3,0,1,2]];add(server,f'/object-{j}',trimesh.creation.box(extents=o['size']),(x,y,o['size'][2]/2),q,(151,171,181))
   add(server,'/start',trimesh.creation.icosphere(subdivisions=2,radius=.23),(*scene['start'][:2],.23),color=(50,109,140))
   add(server,'/goal',trimesh.creation.cylinder(radius=.3,height=.03),(*scene['goal'][:2],.02),color=(95,143,106))
   server.scene.add_grid('/floor',width=w,height=h,position=(w/2,h/2,0));recording=server.get_scene_serializer();recording.insert_sleep(1)
  (root/'assets/recordings'/f'{key}.viser').write_bytes(recording.serialize());server.stop()
  manifest.append({'scene':key,'experiment':exp,'group':group,'method':label,'replay':replay,'success':bool(episode.get('task_success',False)),'status':str(episode.get('status','unavailable')),'duration':round(duration,2),'frames':frames})
  print(key,frames,flush=True)
path=root/'assets/maze-experiments.json'
if args.only and path.exists():
 old=json.loads(path.read_text());new={e['scene'] for e in manifest};manifest=[e for e in old if e['scene'] not in new]+manifest
path.write_text(json.dumps(manifest,indent=2)+'\n')
