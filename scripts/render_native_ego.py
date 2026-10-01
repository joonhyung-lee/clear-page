"""Render a body-mounted camera from saved native states without resimulation."""
import argparse
import os
os.environ.setdefault('MUJOCO_GL','egl')
import json
from pathlib import Path
import subprocess
import mujoco
import numpy as np
import imageio_ffmpeg
from PIL import Image

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('source',type=Path);p.add_argument('--scene',required=True)
a=p.parse_args();root=Path(__file__).resolve().parents[1]
r=json.loads((a.source/'result.json').read_text());s=np.load(a.source/'states.npz')
m=mujoco.MjModel.from_binary_path(str(a.source/'task.mjb'));d=mujoco.MjData(m)
m.vis.headlight.active=1
m.vis.headlight.ambient[:]=.75
m.vis.headlight.diffuse[:]=.35
m.vis.headlight.specular[:]=.05
for geom in range(m.ngeom):
    if m.geom_type[geom]==mujoco.mjtGeom.mjGEOM_PLANE:
        # Native collision groups hide the plane along with collision proxies.
        # Make only that physical floor visible in the reconstructed camera.
        m.geom_group[geom]=0
        m.geom_matid[geom]=-1
        m.geom_rgba[geom]=[.93,.945,.92,1.]
body=m.body('torso_link' if r['robot']=='g1' else 'body').id
offset=np.array([.14,0,.30] if r['robot']=='g1' else [.38,0,.10])
m.vis.global_.offwidth=480;m.vis.global_.offheight=360
renderer=mujoco.Renderer(m,height=360,width=480);option=mujoco.MjvOption()
option.geomgroup[3]=0;option.sitegroup[:]=0
path=root/f'assets/media/{a.scene}-ego.mp4';tmp=path.with_suffix('.tmp.mp4')
proc=subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-f','rawvideo',
    '-pixel_format','rgb24','-video_size','480x360','-framerate','25','-i','-',
    '-an','-map_metadata','-1','-c:v','libx264','-crf','20','-pix_fmt','yuv420p',
    '-fflags','+bitexact','-flags:v','+bitexact','-movflags','+faststart',str(tmp)],stdin=subprocess.PIPE)
try:
    for i,t in enumerate(np.arange(0,s['time'][-1]+1e-8,.04)):
        k=min(int(np.searchsorted(s['time'],t)),len(s['time'])-1)
        if k and abs(s['time'][k-1]-t)<abs(s['time'][k]-t):k-=1
        d.qpos[:]=s['qpos'][k];mujoco.mj_forward(m,d)
        renderer.update_scene(d,scene_option=option)
        rotation=d.xmat[body].reshape(3,3)
        for cam in renderer.scene.camera:
            cam.pos[:]=d.xpos[body]+rotation@offset
            cam.forward[:]=rotation[:,0];cam.up[:]=rotation[:,2]
            cam.frustum_near=.01;cam.frustum_far=100.
            cam.frustum_top=.01*np.tan(np.pi/6);cam.frustum_bottom=-cam.frustum_top
            cam.frustum_center=0.;cam.frustum_width=2*cam.frustum_top*4/3
        rgb=renderer.render().copy()
        if i==0:Image.fromarray(rgb).save(path.with_suffix('.png'))
        proc.stdin.write(rgb.tobytes())
        if i%250==0:print(a.scene,'ego',i,flush=True)
finally:
    proc.stdin.close();code=proc.wait();renderer.close()
assert code==0;tmp.replace(path)
print('PASS reconstructed native ego',a.scene,flush=True)
