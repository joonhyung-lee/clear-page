"""Render actual physical robot meshes for each displayed traversal sample."""
import argparse,json,subprocess,tempfile
from pathlib import Path
import imageio_ffmpeg,mujoco,numpy as np
from PIL import Image
p=argparse.ArgumentParser();p.add_argument('dataset',type=Path);p.add_argument('snapshot',type=Path);a=p.parse_args()
root=Path(__file__).resolve().parents[1];output=root/'assets/media/attempts';output.mkdir(exist_ok=True)
rows=[json.loads(s) for s in (a.dataset/'shared_probes.jsonl').read_text().splitlines()]
samples=json.loads((root/'assets/learning-samples.js').read_text().split('=',1)[1].rstrip(';\n'))['grounding']
def source(raw):
 path=Path(raw)
 if path.exists():return path
 if path.is_symlink():return source(path.readlink())
 candidate=path if path.is_relative_to(a.snapshot) else a.snapshot/Path(*path.parts[3:])
 return source(candidate.readlink()) if candidate.is_symlink() else candidate
manifest=[];cached=None
for index,(row,sample) in enumerate(zip(rows,samples)):
 folder=source(row['recording']);folder=folder if (folder/'task.npz').exists() else folder/'physics'
 first,last=sample['rollout'][0][0],sample['rollout'][-1][0];name=f'attempt-{index:03d}'
 if cached!=folder:
  if cached is not None:renderer.close()
  m=mujoco.MjModel.from_binary_path(str(source(folder/'task.mjb')));d=mujoco.MjData(m);z=dict(np.load(source(folder/'task.npz')))
  m.vis.global_.offwidth=560;m.vis.global_.offheight=390;m.vis.headlight.ambient[:]=.6
  for i in range(m.ngeom):
   if 'wall_' in m.geom(i).name:m.geom_rgba[i,3]=.3
   if m.geom_type[i]==mujoco.mjtGeom.mjGEOM_PLANE:m.geom_matid[i]=-1;m.geom_rgba[i]=[.96,.97,.95,1];m.geom_size[i,:2]=50
  renderer=mujoco.Renderer(m,width=560,height=390);cached=folder
 option=mujoco.MjvOption();option.sitegroup[:]=0;option.geomgroup[3]=0
 camera=mujoco.MjvCamera();camera.type=mujoco.mjtCamera.mjCAMERA_FREE;camera.distance=3.2 if sample['body']=='g1' else 3.5;camera.elevation=-32
 fps=20;frames=max(2,round((last-first)*fps)+1);temp=Path(tempfile.mktemp(suffix='.mp4'));vel=np.zeros(m.nv)
 proc=subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-f','rawvideo','-pixel_format','rgb24','-video_size','560x390','-framerate',str(fps),'-i','-','-an','-map_metadata','-1','-c:v','libx264','-crf','24','-pix_fmt','yuv420p','-fflags','+bitexact','-flags:v','+bitexact','-movflags','+faststart',str(temp)],stdin=subprocess.PIPE)
 for frame in range(frames):
  t=min(last,first+frame/fps);lo=max(0,int(np.searchsorted(z['time'],t,side='right')-1));hi=min(lo+1,len(z['time'])-1);dt=z['time'][hi]-z['time'][lo];u=(t-z['time'][lo])/dt if dt else 0
  d.qpos[:]=z['qpos'][lo];mujoco.mj_differentiatePos(m,vel,1.,z['qpos'][lo].astype(float),z['qpos'][hi].astype(float));mujoco.mj_integratePos(m,d.qpos,vel,u);mujoco.mj_forward(m,d)
  if frame==0:
   direction=np.asarray(sample['query'][1])-np.asarray(sample['query'][0]);camera.azimuth=np.degrees(np.arctan2(direction[1],direction[0]))+90
  camera.lookat[:]=d.qpos[:3];camera.lookat[2]=max(.4,camera.lookat[2]-.15)
  renderer.update_scene(d,camera=camera,scene_option=option);picture=renderer.render().copy()
  if frame==0:Image.fromarray(picture).save(output/(name+'.png'))
  proc.stdin.write(picture.tobytes())
 proc.stdin.close();assert proc.wait()==0;temp.replace(output/(name+'.mp4'))
 manifest.append(dict(id=index,start=first,end=last,frames=frames,fps=fps));print(name,frames,flush=True)
renderer.close();(root/'assets/learning-media.json').write_text(json.dumps(manifest,separators=(',',':'))+'\n')
