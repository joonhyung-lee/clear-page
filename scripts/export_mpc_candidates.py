"""Export the same recorded candidate populations in a close, palm-centered view."""
import argparse,json
from pathlib import Path
import numpy as np
import viser
p=argparse.ArgumentParser();p.add_argument('baseline',type=Path);p.add_argument('optimized',type=Path);a=p.parse_args();root=Path(__file__).resolve().parents[1]
for key,folder in [('mpc-baseline',a.baseline),('mpc-optimized',a.optimized)]:
 r=dict(np.load(folder/'task.rollouts.npz',allow_pickle=False));ids=np.flatnonzero(r['object_id']==r['object_id'][0]);server=viser.ViserServer(host='127.0.0.1',port=8102,verbose=False);server.gui.configure_theme(show_logo=False,show_share_button=False);server.scene.world_axes.visible=False
 server.initial_camera.position=(.65,-.8,.65);server.initial_camera.look_at=(0,.08,0);server.initial_camera.fov=.8
 server.scene.add_grid('/plane',width=1.6,height=1.6,cell_size=.1,section_size=.5,position=(0,0,-.25),cell_color=(225,225,225),section_color=(190,190,190))
 handles=[];segments=(r['eef_world'].shape[2]-1)*2
 for n in range(r['eef_world'].shape[1]):handles.append(server.scene.add_line_segments(f'/candidate-{n}',points=np.zeros((segments,2,3),np.float32),colors=(170,178,187),line_width=1))
 chosen=server.scene.add_line_segments('/applied',points=np.zeros((segments,2,3),np.float32),colors=(188,104,45),line_width=4)
 def update(j):
  center=r['eef_world'][j,0,0].mean(0);elite=set(r['elite_indices'][j].tolist())
  for n,h in enumerate(handles):
   points=r['eef_world'][j,n]-center;h.points=np.stack([points[:-1],points[1:]],axis=2).reshape(-1,2,3).astype(np.float32);h.colors=np.broadcast_to(np.array((52,125,130) if n in elite else (170,178,187),np.uint8),(segments,2,3)).copy();h.line_width=2 if n in elite else 1
  chosen.points=handles[int(r['applied_candidate'][j])].points.copy()
 update(ids[0]);recording=server.get_scene_serializer()
 for previous,j in zip(ids,ids[1:]):recording.insert_sleep(float(r['time_s'][j]-r['time_s'][previous]));update(j)
 recording.insert_sleep(float(r['valid_until_s'][ids[-1]]-r['time_s'][ids[-1]]));(root/'assets/recordings'/f'{key}-candidates.viser').write_bytes(recording.serialize());server.stop();print(key,flush=True)
