"""Render a continuous overview from measured physical states.

Inter-frame poses use MuJoCo's quaternion-aware position interpolation.
No dynamics or outcome is changed. Invoke with the source MuJoCo version.
"""
import argparse,json,subprocess,tempfile
from pathlib import Path
import imageio_ffmpeg,mujoco,numpy as np
from PIL import Image
p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('scene');a=p.parse_args()
root=Path(__file__).resolve().parents[1];z=dict(np.load(a.folder/'task.npz'));roll=dict(np.load(a.folder/'task.rollouts.npz'));meta=json.loads(str(roll['metadata']))
m=mujoco.MjModel.from_binary_path(str(a.folder/'task.mjb'));d=mujoco.MjData(m)
first=roll['time_s'][0];ids=np.flatnonzero(roll['object_id']==roll['object_id'][0]);last=min(z['time'][-1],roll['valid_until_s'][ids[-1]])
target=m.body(meta.get('target_body','object/box')).id
ref=np.array(json.loads(str(z['reference_paths']))[0]['poses'])[:,:2];color=np.array([.45,.62,.43,1.]) if a.scene.endswith('optimized') else np.array([.72,.45,.42,1.])
for i in range(m.ngeom):
 if m.geom_type[i]==mujoco.mjtGeom.mjGEOM_PLANE:m.geom_matid[i]=-1;m.geom_rgba[i]=[.96,.97,.95,1];m.geom_size[i,:2]=50
 if 'wall_' in m.geom(i).name:m.geom_rgba[i,3]=.22
m.vis.headlight.ambient[:]=.65;m.vis.headlight.diffuse[:]=.45
cam=mujoco.MjvCamera();cam.type=mujoco.mjtCamera.mjCAMERA_FREE;cam.distance=3.5;cam.azimuth=90;cam.elevation=-25
option=mujoco.MjvOption();option.sitegroup[:]=0;option.geomgroup[3]=0
m.vis.global_.offwidth=720;m.vis.global_.offheight=540
renderer=mujoco.Renderer(m,height=540,width=720);fps=30
out=root/'assets/media'/f'{a.scene}.mp4';tmp=Path(tempfile.mktemp(suffix='.mp4'))
proc=subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-f','rawvideo','-pixel_format','rgb24','-video_size','720x540','-framerate',str(fps),'-i','-','-an','-map_metadata','-1','-c:v','libx264','-crf','20','-pix_fmt','yuv420p','-fflags','+bitexact','-flags:v','+bitexact','-movflags','+faststart',str(tmp)],stdin=subprocess.PIPE)
vel=np.zeros(m.nv);frames=round((last-first)*fps)+1
try:
 for frame in range(frames):
  t=min(last,first+frame/fps);lo=max(0,int(np.searchsorted(z['time'],t,side='right')-1));hi=min(lo+1,len(z['time'])-1)
  dt=z['time'][hi]-z['time'][lo];u=(t-z['time'][lo])/dt if dt else 0
  d.qpos[:]=z['qpos'][lo];mujoco.mj_differentiatePos(m,vel,1.,z['qpos'][lo].astype(float),z['qpos'][hi].astype(float));mujoco.mj_integratePos(m,d.qpos,vel,u);mujoco.mj_forward(m,d)
  cam.lookat[:]=.5*d.qpos[:3]+.5*d.xpos[target];cam.lookat[2]=.65
  renderer.update_scene(d,camera=cam,scene_option=option)
  # Reference anchors are elevated above the box, outside contact geometry.
  for point in ref[np.linspace(0,len(ref)-1,5).round().astype(int)]:
   geom=renderer.scene.geoms[renderer.scene.ngeom];mujoco.mjv_initGeom(geom,mujoco.mjtGeom.mjGEOM_SPHERE,np.full(3,.028),np.r_[point,1.35],np.eye(3).ravel(),color);renderer.scene.ngeom+=1
  rgb=renderer.render().copy()
  if frame==0:Image.fromarray(rgb).save(root/'assets/media'/f'{a.scene}.png')
  proc.stdin.write(rgb.tobytes())
  if frame%300==0:print(a.scene,frame,frames,flush=True)
finally:
 proc.stdin.close();code=proc.wait();renderer.close()
assert code==0;tmp.replace(out);print('Complete',out.name,frames,flush=True)
