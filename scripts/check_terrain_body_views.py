"""Check body identity, native replay synchronization and rendered camera views."""
import argparse,json
from pathlib import Path
import mujoco,numpy as np,imageio_ffmpeg
from PIL import Image
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,default=Path('attention/videos'));a=p.parse_args()
for body in ['spot','husky']:
    manifest=json.loads((a.output/f'terrain-{body}-manifest.json').read_text())
    folder=a.source/manifest['source'];poses=np.load(folder/(body+'.npz'));model=mujoco.MjModel.from_binary_path(str(folder/(body+'.mjb')));state=mujoco.MjData(model)
    if body=='spot':assert all('arm' not in (model.body(i).name or '').lower() for i in range(model.nbody))
    assert manifest['attention'].startswith('No attention')
    if body=='husky':assert manifest['dynamics']=='surface_following_prescribed_differential_kinematics'
    video=a.output/manifest['file'];frames,duration=imageio_ffmpeg.count_frames_and_secs(str(video));assert frames==manifest['frames']==len(manifest['audit']);assert abs(duration-frames/25)<.05
    for row in manifest['audit']:
        index=np.abs(poses['time']-row['time']).argmin();assert abs(poses['time'][index]-row['time'])<1e-6
        state.qpos[:]=poses['qpos'][index]
        for key in ['mocap_pos','mocap_quat']:getattr(state,key)[:]=poses[key][index]
        mujoco.mj_forward(model,state);assert np.allclose(state.xpos[1],row['bodyPosition'],atol=1e-5)
        forward=(np.asarray(row['chaseTarget'])-row['chaseEye'])[:2];forward/=np.linalg.norm(forward)
        assert forward @ np.asarray(row['heading'])[:2]>.999999
    screenshots=sorted(a.output.glob(f'terrain-{body}-frame-*.png'));assert len(screenshots)==3
    pixels=[np.asarray(Image.open(f)).astype(float) for f in screenshots]
    for image in pixels:
        for rect in [(80,400,0,880),(52,316,904,1256),(372,636,904,1256)]:
            top,bottom,left,right=rect;assert image[top:bottom,left:right].std()>10
    for y in [52,372]:assert np.abs(pixels[0][y:y+264,904:1256]-pixels[1][y:y+264,904:1256]).mean()>2
    stream=imageio_ffmpeg.read_frames(str(video));meta=next(stream);first=np.frombuffer(next(stream),dtype='uint8').reshape(720,1280,3);stream.close()
    assert np.abs(first.astype(float)-pixels[0]).mean()<3
    print('PASS',body,frames,'frames, native body poses, heading camera, moving ego and encoded image match')
