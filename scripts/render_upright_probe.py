"""Render a clearly labeled physical posture probe from measured MuJoCo states."""
import argparse
import json
import os
from pathlib import Path
import subprocess
os.environ.setdefault('MUJOCO_GL', 'egl')
import imageio_ffmpeg
import mujoco
import numpy as np
from PIL import Image, ImageDraw, ImageFont

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--probe', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a=p.parse_args()
a.output.parent.mkdir(parents=True, exist_ok=True)
m=mujoco.MjModel.from_binary_path(str(a.probe/'physics/task.mjb'))
d=mujoco.MjData(m)
states=np.load(a.probe/'physics/task.npz')
result=json.loads((a.probe/'probe-result.json').read_text())
root=m.body('robot/pelvis').id
torso=m.body('robot/torso_link').id
rgba=m.geom_rgba.copy()
walls=[i for i in range(m.ngeom) if 'wall' in (m.geom(i).name+' '+m.body(m.geom_bodyid[i]).name).lower()]
boxes=[i for i in range(m.ngeom) if m.body(m.geom_bodyid[i]).name.startswith('object')]
m.vis.global_.offwidth,m.vis.global_.offheight=960,720
m.vis.headlight.active=1
m.vis.headlight.ambient[:]=.6
m.vis.headlight.diffuse[:]=.4
opt=mujoco.MjvOption()
opt.geomgroup[3]=0
opt.sitegroup[:]=0
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',17)
def camera(eye, target):
    delta=np.asarray(eye)-np.asarray(target)
    cam=mujoco.MjvCamera()
    cam.lookat[:]=target
    cam.distance=np.linalg.norm(delta)
    cam.azimuth=np.rad2deg(np.arctan2(delta[1],delta[0]))+180
    cam.elevation=-np.rad2deg(np.arctan2(delta[2],np.linalg.norm(delta[:2])))
    return cam
def label(image, box, text):
    dr=ImageDraw.Draw(image)
    x,y,w=box
    dr.rectangle((x,y,x+w,y+28),fill='#fafbf8')
    dr.text((x+8,y+4),text,fill='#35443e',font=font)
proc=subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-f','rawvideo','-pix_fmt','rgb24',
    '-s','1280x720','-r','20','-i','-','-an','-map_metadata','-1','-c:v','libx264','-crf','19','-pix_fmt','yuv420p',
    '-movflags','+faststart',str(a.output)],stdin=subprocess.PIPE)
try:
    with mujoco.Renderer(m,height=720,width=960) as renderer:
        for i,q in enumerate(states['qpos']):
            d.qpos[:]=q
            mujoco.mj_forward(m,d)
            base=d.xpos[root].copy()
            rotation=d.xmat[torso].reshape(3,3)
            forward=rotation[:,0].copy();forward[2]=0;forward/=np.linalg.norm(forward)
            side=np.cross(forward,[0,0,1])
            m.geom_rgba[:]=rgba
            renderer.update_scene(d,camera=camera(base-2.8*forward+1.1*side+[0,0,3.1],base+.7*forward),scene_option=opt)
            image=Image.new('RGB',(1280,720),'#fafbf8')
            image.paste(Image.fromarray(renderer.render()),(0,0))
            eye=d.xpos[torso]+rotation @ np.array([.14,0,.30])
            renderer.update_scene(d,camera=camera(eye,eye+rotation @ np.array([1.,0,-.36])),scene_option=opt)
            image.paste(Image.fromarray(renderer.render()).resize((320,240)),(960,0))
            m.geom_rgba[walls,3]=.08
            m.geom_rgba[boxes,3]=.20
            renderer.update_scene(d,camera=camera(base+2.3*side+[0,0,.65],base+[0,0,.05]),scene_option=opt)
            image.paste(Image.fromarray(renderer.render()).resize((320,240)),(960,240))
            m.geom_rgba[:]=rgba
            target=np.array([7.75,6.,0.])
            renderer.update_scene(d,camera=camera(target+[0,-.01,20],target),scene_option=opt)
            image.paste(Image.fromarray(renderer.render()).resize((320,240)),(960,480))
            label(image,(0,0,960),'Upright palm physical probe · prescribed path · 2×')
            label(image,(960,0,320),'Ego RGB')
            label(image,(960,240,320),'Palm posture · cutaway')
            label(image,(960,480,320),'Minimap')
            if i == len(states['qpos'])-1:
                label(image,(0,692,960),'Probe ended · '+('complete' if result['success'] else result['failure_type'].replace('_',' ').lower()))
            proc.stdin.write(image.tobytes())
            if i%100==0: print('frame',i,'/',len(states['qpos']),flush=True)
        for _ in range(40):proc.stdin.write(image.tobytes())
    proc.stdin.close()
    assert proc.wait()==0
except BaseException:
    proc.kill()
    raise
print('PASS physical probe video',a.output,flush=True)
