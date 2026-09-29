"""Render a recorded native SUMO rollout without modifying physical states."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

import imageio_ffmpeg
import mujoco
import numpy as np
from PIL import Image
import viser

from replay_geometry import mesh, add
from scene_annotations import outlined_anchors, path_anchors

p=argparse.ArgumentParser(description=__doc__);p.add_argument('recording',type=Path);args=p.parse_args()
root=Path(__file__).resolve().parents[1];folder=args.recording
states=dict(np.load(folder/'task.npz'));roll=dict(np.load(folder/'task.rollouts.npz'));meta=json.loads(str(roll['metadata']))
assert meta['runtime']=='SUMO native G1 C++ and Judo CEM' and meta['task']=='g1_box'
m=mujoco.MjModel.from_binary_path(str(folder/'task.mjb'));d=mujoco.MjData(m)
target=m.body(meta['target_body']).id;target_geoms=np.flatnonzero(m.geom_bodyid==target)
reference=np.asarray(json.loads(str(states['reference_paths']))[0]['poses'])[:,:2]
server=viser.ViserServer(host='127.0.0.1',port=8103,verbose=False);server.gui.configure_theme(show_logo=False,show_share_button=False);server.scene.world_axes.visible=False
server.initial_camera.position=(2.7,-2.2,2.4);server.initial_camera.look_at=(.7,0,.7);server.initial_camera.fov=.85
tracking=server.scene.add_frame('/tracking',show_axes=False)
bodies={i:server.scene.add_frame(f'/tracking/body-{i}',show_axes=False) for i in range(m.nbody)}
for i in range(m.ngeom):
 if m.geom_group[i]==3:continue
 rgba=m.geom_rgba[i].copy();mat=m.geom_matid[i]
 if mat>=0:rgba=m.mat_rgba[mat]
 if rgba[3]<=0:continue
 h=add(server,f'/tracking/body-{m.geom_bodyid[i]}/geom-{i}',mesh(m,i),m.geom_pos[i],m.geom_quat[i],tuple((rgba[:3]*255).astype(int)))
 if m.geom_bodyid[i]==0 and int(m.geom_type[i])!=0:h.opacity=.18
color=np.array([207,154,151],np.uint8)
anchors=path_anchors(reference,5,1.32);outlined_anchors(server,'/tracking/waypoint-anchors',anchors,tuple(color),.065)
path=np.column_stack([reference,np.full(len(reference),1.32)])
server.scene.add_line_segments('/tracking/reference-path',points=np.stack([path[:-1],path[1:]],axis=1),colors=tuple(color),line_width=4)
candidates=[server.scene.add_line_segments(f'/tracking/candidate-{i}',points=np.zeros((2,2,3),np.float32),colors=tuple(color),line_width=1) for i in range(roll['eef_world'].shape[1])]
selected=server.scene.add_line_segments('/tracking/applied-candidate',points=np.zeros((2,2,3),np.float32),colors=tuple(color),line_width=4)
contact_markers=outlined_anchors(server,'/tracking/body-contacts',np.zeros((1,3)),tuple(color),.045)
width,height=480,360
# A side view exposes thigh and torso contacts that an onboard camera cannot
# see. These are rendering choices only, applied after the main scene meshes.
m.vis.map.znear=.0005;m.vis.headlight.ambient[:]=.65;m.vis.headlight.diffuse[:]=.4
for i in range(m.ngeom):
 if m.geom(i).name.startswith('wall_'):m.geom_group[i]=5
 if m.geom_type[i]==mujoco.mjtGeom.mjGEOM_PLANE:m.geom_matid[i]=-1;m.geom_rgba[i]=[.95,.96,.94,1]
detail_camera=mujoco.MjvCamera();detail_camera.type=mujoco.mjtCamera.mjCAMERA_FREE;detail_camera.distance=2.4;detail_camera.elevation=-25;detail_camera.azimuth=90
renderer=mujoco.Renderer(m,height=height,width=width);option=mujoco.MjvOption();option.sitegroup[:]=0;option.geomgroup[3]=0;option.geomgroup[5]=0
temporary=Path(tempfile.mktemp(suffix='.mp4',prefix='clear-sumo-ego-'))
proc=subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-f','rawvideo','-pixel_format','rgb24','-video_size',f'{width}x{height}','-framerate','50','-i','-','-an','-map_metadata','-1','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-fflags','+bitexact','-flags:v','+bitexact','-movflags','+faststart',str(temporary)],stdin=subprocess.PIPE)
record=None;visible_frames=0;last_candidate=-1
# Keep physical poses at 50 Hz. Candidate populations are a display
# subsample at 10 Hz, retaining the first segment and the full horizon endpoint.
future_ids=np.unique(np.r_[0,1,np.arange(2,roll['eef_world'].shape[2],2),roll['eef_world'].shape[2]-1])
try:
 for frame,(now,qpos) in enumerate(zip(states['time'],states['qpos'])):
  if record is not None:record.insert_sleep(float(now-states['time'][frame-1]))
  d.qpos[:]=qpos
  if 'qvel' in states:d.qvel[:]=states['qvel'][frame]
  mujoco.mj_forward(m,d);tracking.position=(-float(qpos[0]),-float(qpos[1]),0)
  for i,h in bodies.items():h.position=d.xpos[i].copy();h.wxyz=d.xquat[i].copy()
  index=max(0,int(np.searchsorted(roll['time_s'],now+1e-7,side='right')-1))
  if last_candidate<0 or index//2!=last_candidate//2:
   for i,h in enumerate(candidates):
    points=roll['eef_world'][index,i,future_ids];h.points=np.stack([points[:-1],points[1:]],axis=2).reshape(-1,2,3).astype(np.float32)
    elite=i in roll['elite_indices'][index];c=color if elite else np.round(.35*color+.65*245).astype(np.uint8);h.colors=np.broadcast_to(c,h.points.shape).copy();h.line_width=2 if elite else 1
   selected.points=candidates[int(roll['applied_candidate'][index])].points.copy();last_candidate=index
  points=[]
  for contact in d.contact:
   bodyids=[int(m.geom_bodyid[g]) for g in contact.geom]
   if target in bodyids:
    other=bodyids[1-bodyids.index(target)];name=m.body(other).name
    if other!=0 and name not in ('terrain','table') and not name.startswith('object_') and contact.dist<=.001:points.append(contact.pos.copy())
  for h in contact_markers:
   h.visible=bool(points)
   if points:h.points=np.asarray(points,dtype=np.float32)
  detail_camera.lookat[:]=.6*d.qpos[:3]+.4*d.xpos[target];detail_camera.lookat[2]=.7
  renderer.update_scene(d,camera=detail_camera,scene_option=option)
  for point in points:
   geometry=renderer.scene.geoms[renderer.scene.ngeom]
   mujoco.mjv_initGeom(geometry,mujoco.mjtGeom.mjGEOM_SPHERE,np.full(3,.023),point,np.eye(3).ravel(),np.r_[color/255.,1.])
   renderer.scene.ngeom+=1
  picture=Image.fromarray(renderer.render().copy())
  if points:visible_frames+=1
  if frame==0:
   record=server.get_scene_serializer();picture.save(root/'assets/media/mpc-baseline-ego.png')
  proc.stdin.write(np.asarray(picture).tobytes())
  if frame%200==0:print('Native SUMO export',frame,'/',len(states['time']),flush=True)
 record.insert_sleep(.02)
 (root/'assets/recordings/mpc-baseline.viser').write_bytes(record.serialize())
finally:
 proc.stdin.close();code=proc.wait();renderer.close();server.stop()
assert code==0;temporary.replace(root/'assets/media/mpc-baseline-ego.mp4')
manifest=json.loads((root/'assets/mpc-comparison.json').read_text())
outcome=json.loads((folder/'result.json').read_text())
entry=dict(scene='mpc-baseline',controller='SUMO native G1 box MPC',selector='topk',searchCandidates=24,executionPreviewRows=1,elites=2,horizon=meta['horizon_s'],step=meta['step_s'],seed=outcome['seed'],duration=float(states['time'][-1]+.02),recordedPopulations=len(roll['time_s']),displayAnchors=5,frames=len(states['time']),contactVisibleFrames=visible_frames,candidateDisplayHz=10,candidateFutureSamples=len(future_ids),objectDisplacement=outcome['displacement_m'],goalError=outcome['goal_error_m'],goalReached=outcome['goal_reached'],contactField='Contact locations reconstructed from recorded physical states. Whole-body target contacts are permitted.',scope=meta['scope'])
manifest=[entry if row['scene']=='mpc-baseline' else row for row in manifest]
entry['insetView']='A reconstructed side view follows body contact. Walls are hidden in this detail view for visibility.'
(root/'assets/mpc-comparison.json').write_text(json.dumps(manifest,indent=2)+'\n');print('Native SUMO export complete',entry['duration'],flush=True)
