"""Replay the stored ordered manipulation qpos and button-state streams."""
import argparse,json
from pathlib import Path
import numpy as np
import mujoco
import viser
from replay_geometry import mesh,add
parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
labels={'bc':'Behavior cloning','bc_shared':'Behavior cloning with shared encoder','classical':'Classical planner','clear':'CLEAR (ours)','clear_noaffordance':'Without affordance','clear_nocausal':'Without causal masking'}
visual=json.loads((args.source/'scene_visual.json').read_text());manifest=[]
for folder in sorted(args.source.iterdir()):
 if not folder.is_dir() or not (folder/'task.npz').exists():continue
 method=folder.name.split('ur5e_',1)[1];key='manipulation-'+method.replace('_','-');a=np.load(folder/'task.npz');metadata=json.loads((folder/'task.json').read_text())
 m=mujoco.MjModel.from_binary_path(str(args.source/'scene.mjb'));data=mujoco.MjData(m)
 server=viser.ViserServer(host='127.0.0.1',port=8100,verbose=False);server.gui.configure_theme(show_logo=False,show_share_button=False);server.scene.world_axes.visible=False
 server.initial_camera.position=(1.15,-1.3,1.3);server.initial_camera.look_at=(.35,0,.08);server.initial_camera.fov=.85
 bodies={i:server.scene.add_frame(f'/body-{i}',show_axes=False) for i in range(m.nbody)};geoms={}
 for i in range(m.ngeom):
  if m.geom_group[i] not in [1,2]:continue
  rgba=m.geom_rgba[i].copy();mat=m.geom_matid[i]
  if mat>=0:rgba=m.mat_rgba[mat]
  if rgba[3]<=0:continue
  geoms[i]=add(server,f'/body-{m.geom_bodyid[i]}/geom-{i}',mesh(m,i),m.geom_pos[i],m.geom_quat[i],tuple((rgba[:3]*255).astype(int)))
 def pose(k):
  data.qpos[:]=a['qpos'][k];mujoco.mj_forward(m,data)
  for i,handle in bodies.items():handle.position=data.xpos[i].copy();handle.wxyz=data.xquat[i].copy()
  for j,ids in enumerate(visual['button_geom_ids']):
   color=visual['red'] if a['buttons'][k,j] else visual['white']
   for i in ids:
    if i in geoms:geoms[i].color=tuple(int(v*255) for v in color[:3])
 pose(0);recording=server.get_scene_serializer();times=a['time']
 for k in range(1,len(times)):
  recording.insert_sleep(float(times[k]-times[k-1]));pose(k)
 recording.insert_sleep(.15);(root/'assets/recordings'/f'{key}.viser').write_bytes(recording.serialize());server.stop()
 manifest.append({'scene':key,'method':labels[method],'success':bool(metadata['success']),'duration':round(float(times[-1]-times[0]),2),'decisions':int(metadata['decisions']),'violations':int(metadata['violations']),'frames':len(times)})
 print(key,flush=True)
(root/'assets/manipulation-experiments.json').write_text(json.dumps(manifest,indent=2)+'\n')
