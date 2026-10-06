"""Verify lower-corridor geometry, wheel dynamics and the encoded Husky replay."""
import argparse,json
from pathlib import Path
import numpy as np,mujoco,imageio_ffmpeg
from PIL import Image
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--original-scene',type=Path,required=True);p.add_argument('--output',type=Path,default=Path('attention/videos'));a=p.parse_args()
original=json.loads(a.original_scene.read_text());meta=json.loads((a.output/'mixed-terrain-husky-manifest.json').read_text());scene=meta['scene'];result=meta['physics']
assert result['task_success'] and result['status']=='goal_reached'
assert result['maximum_wall_penetration']==0 and not result['forbidden_object_contact']
assert result['maximum_object_displacement']<.001 and result['final_goal_distance']<.15
assert len(scene['terrain'])==len(original['terrain']) and len(scene['objects'])==len(original['objects'])
for before,after in zip(original['terrain'],scene['terrain'],strict=True):
    expected=dict(before);expected['bounds']=np.asarray(before['bounds'])+[0,2.4,0,2.4]
    assert np.allclose(expected['bounds'],after['bounds'])
    for key in set(before)-{'bounds'}:assert before[key]==after[key]
for before,after in zip(original['objects'],scene['objects'],strict=True):assert np.allclose(np.asarray(before['pose'])+[0,2.4,0],after['pose']) and before['size']==after['size']
model=mujoco.MjModel.from_binary_path(str(a.source/'task.mjb'));poses=np.load(a.source/'task.npz')
assert model.nmocap==0 and model.nu==4
joint=model.joint('base_husky_joint').id;qa=model.jnt_qposadr[joint];assert model.jnt_type[joint]==mujoco.mjtJoint.mjJNT_FREE
wheel_adrs=[model.jnt_qposadr[model.joint(n+'_wheel').id] for n in ['front_left','front_right','rear_left','rear_right']]
assert (np.ptp(poses['qpos'][:,wheel_adrs],axis=0)>50).all(), 'Wheels are not rotating'
assert np.isfinite(poses['qpos']).all() and np.all(np.diff(poses['time'])>0)
for row in meta['audit']:
    actual=[np.interp(row['time'],poses['time'],poses['qpos'][:,k]) for k in wheel_adrs]
    assert np.allclose(actual,row['wheels'],atol=1e-6)
    position=[np.interp(row['time'],poses['time'],poses['qpos'][:,qa+k]) for k in range(3)]
    assert np.allclose(position,row['position'],atol=1e-6)
    x,y=row['position'][:2]
    for l,b,r,t in scene['walls']+[tile['bounds'] for tile in scene['terrain']]:assert np.hypot(max(l-x,x-r,0),max(b-y,y-t,0))>.65
frames,seconds=imageio_ffmpeg.count_frames_and_secs(str(a.output/meta['file']))
assert frames==meta['frames']==len(meta['audit']) and abs(seconds-frames/meta['fps'])<.05
images=sorted(a.output.glob('mixed-terrain-husky-frame-*.png'));assert len(images)==3
arrays=[np.asarray(Image.open(p)).astype(float) for p in images]
stream=imageio_ffmpeg.read_frames(str(a.output/meta['file']));next(stream);decoded=np.frombuffer(next(stream),dtype='uint8').reshape(720,1280,3);stream.close()
assert np.abs(decoded-arrays[0]).mean()<3
assert np.abs(arrays[1][52:316,904:1256]-arrays[0][52:316,904:1256]).mean()>3
assert 'not a learned' in meta['route']['source']
print('PASS preserved terrain layout, free-root four-wheel dynamics, safe flat bypass, actual wheel/pose synchronization and encoded video')
