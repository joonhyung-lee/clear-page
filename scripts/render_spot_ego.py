"""Render the robot's recorded RGB camera on the exported pushing interval."""
import argparse,json,os,subprocess
os.environ.setdefault('MUJOCO_GL','egl')
from pathlib import Path
import mujoco,numpy as np,imageio_ffmpeg
from PIL import Image
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('baked',type=Path);p.add_argument('scene');a=p.parse_args()
root=Path(__file__).resolve().parents[1];record=json.loads((a.baked/'result.json').read_text());data=np.load(a.source/'task.npz');m=mujoco.MjModel.from_binary_path(str(a.source/'task.mjb'));d=mujoco.MjData(m)
assert mujoco.mj_name2id(m,mujoco.mjtObj.mjOBJ_CAMERA,'robot/ego')>=0
m.vis.global_.offwidth=480;m.vis.global_.offheight=360;renderer=mujoco.Renderer(m,height=360,width=480)
options=mujoco.MjvOption();options.geomgroup[3]=0;options.sitegroup[:]=0
out=root/'assets/media'/f'{a.scene}-ego.mp4';tmp=out.with_suffix('.tmp.mp4');fps=25
proc=subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-f','rawvideo','-pixel_format','rgb24','-video_size','480x360','-framerate',str(fps),'-i','-','-an','-map_metadata','-1','-c:v','libx264','-crf','20','-pix_fmt','yuv420p','-fflags','+bitexact','-flags:v','+bitexact','-movflags','+faststart',str(tmp)],stdin=subprocess.PIPE)
try:
 for i,t in enumerate(np.arange(0,record['duration']+1e-8,1/fps)):
  now=record['interval']['start']+t;k=min(int(np.searchsorted(data['time'],now)),len(data['time'])-1)
  if k and abs(data['time'][k-1]-now)<abs(data['time'][k]-now):k-=1
  d.qpos[:]=data['qpos'][k]
  if m.nmocap:d.mocap_pos[:]=data['mocap_pos'][k];d.mocap_quat[:]=data['mocap_quat'][k]
  mujoco.mj_forward(m,d);renderer.update_scene(d,camera='robot/ego',scene_option=options);rgb=renderer.render().copy()
  if i==0:Image.fromarray(rgb).save(out.with_suffix('.png'))
  proc.stdin.write(rgb.tobytes())
  if i%250==0:print(a.scene,i,flush=True)
finally:
 proc.stdin.close();code=proc.wait();renderer.close()
assert code==0;tmp.replace(out);print('PASS ego camera interval',a.scene,record['duration'],flush=True)
