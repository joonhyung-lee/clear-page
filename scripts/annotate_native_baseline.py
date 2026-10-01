"""Overlay measured end effectors and object motion on native baseline replays."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from annotate_spot_push import dashed, segments, spaced_anchors
from recording_io import read_recording, write_recording, compact_buffers

ROOT = Path(__file__).resolve().parents[1]
HAND_COLORS = [(184,92,91), (173,126,107)]
TARGET = (57,100,163)
OBSERVED = (26,115,105)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('baked', type=Path)
    p.add_argument('--scene', required=True)
    p.add_argument('--cache', type=Path, required=True)
    a = p.parse_args()
    a.cache.mkdir(parents=True, exist_ok=False)
    result = json.loads((a.baked/'result.json').read_text())
    state = np.load(a.baked/'states.npz')
    times, hands = state['time'], state['eef']
    obj = state['positions'][:,result['objectBodyId']].copy(); obj[:,2] = .018
    ref = np.asarray(result['objectReference'],dtype=float)[:,:2]
    ref = np.column_stack([ref,np.full(len(ref),.012)])
    tangent = ref[-1]-ref[0]; tangent /= np.linalg.norm(tangent)
    side = np.array([-tangent[1],tangent[0],0.])*result['objectSize'][1]/2
    corners = np.array([[-1,-1],[1,-1],[1,1],[-1,1],[-1,-1]])*np.asarray(result['objectSize'])[:2]/2
    goal = np.column_stack([corners+ref[-1,:2],np.full(5,.012)])
    target_lines = np.concatenate([dashed(v) for v in [ref,ref-side,ref+side,goal]])
    target_anchors = spaced_anchors(ref)
    hand_anchors = [spaced_anchors(hands[:,h]) for h in range(hands.shape[1])]
    recording = ROOT/f'assets/recordings/{a.scene}.viser'
    record, buffers = read_recording(recording)
    messages = record['messages']

    def array(values,dtype='<f4'):
        buffers.append(np.asarray(values,dtype=dtype).tobytes())
        return dict(__binary_index=len(buffers)-1,dtype=np.dtype(dtype).str)

    def emit(t,kind,**values):
        messages.append((float(t),dict(type=kind,**values)))

    def line(name,values,color,width,t=0.,update=False):
        attrs=dict(points=array(values),colors=array(np.broadcast_to(color,values.shape),'|u1'))
        if update: emit(t,'SceneNodeUpdateMessage',name=name,updates=attrs)
        else: emit(t,'LineSegmentsMessage',name=name,props=dict(**attrs,line_width=width,scale=1.))

    def points(name,values,color,size):
        emit(0,'PointCloudMessage',name=name,props=dict(points=array(values),
            colors=array(np.tile(color,(len(values),1)),'|u1'),point_size=size,
            point_shape='circle',precision='float32',scale=1.,point_shading='flat'))

    line('/native-overlay/object-target',target_lines,TARGET,4.)
    points('/native-overlay/object-anchors',target_anchors,TARGET,.11)
    line('/native-overlay/object-motion',segments(obj[:1]),OBSERVED,6.)
    points('/native-overlay/object-current',[[0,0,0]],OBSERVED,.14)
    for h in range(hands.shape[1]):
        color=HAND_COLORS[h]
        line(f'/native-overlay/eef-{h}',segments(hands[:1,h]),color,5.)
        points(f'/native-overlay/anchors-{h}',hand_anchors[h],color,.09)
        points(f'/native-overlay/current-{h}',[[0,0,0]],color,.11)
    for i,t in enumerate(times):
        begin=np.searchsorted(times,t-.8)
        for h in range(hands.shape[1]):
            line(f'/native-overlay/eef-{h}',segments(hands[begin:i+1,h]),HAND_COLORS[h],5.,t,True)
            emit(t,'SetPositionMessage',name=f'/native-overlay/current-{h}',position=hands[i,h].tolist())
        line('/native-overlay/object-motion',segments(obj[:i+1]),OBSERVED,6.,t,True)
        emit(t,'SetPositionMessage',name='/native-overlay/object-current',position=obj[i].tolist())
    record['messages']=sorted(messages,key=lambda v:v[0])
    record,buffers=compact_buffers(record,buffers);write_recording(recording,record,buffers)
    video=ROOT/f'assets/media/{a.scene}.mp4'
    plain=a.cache/video.name;shutil.copyfile(video,plain)
    reader=imageio_ffmpeg.read_frames(str(plain));meta=next(reader)
    w,h=meta['size'];fps=meta['fps']
    eye=np.asarray(result['camera']['position']);at=np.asarray(result['camera']['target'])
    forward=at-eye;forward/=np.linalg.norm(forward)
    right=np.cross(forward,[0.,0.,1.]);right/=np.linalg.norm(right)
    basis=np.stack([right,np.cross(right,forward),forward],axis=1)
    focal=h/(2*np.tan(result['camera']['fov']/2))
    def project(values):
        v=(values-eye)@basis
        assert np.all(v[...,2]>0)
        return np.stack([w/2+v[...,0]/v[...,2]*focal,h/2-v[...,1]/v[...,2]*focal],axis=-1)
    hand_px=project(hands);object_px=project(obj);target_px=project(target_lines)
    target_pts=project(target_anchors);anchor_px=[project(v) for v in hand_anchors]
    output=a.cache/'annotated.mp4'
    proc=subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-f','rawvideo',
        '-pixel_format','rgb24','-video_size',f'{w}x{h}','-framerate',str(fps),'-i','-',
        '-an','-map_metadata','-1','-c:v','libx264','-crf','19','-pix_fmt','yuv420p',
        '-fflags','+bitexact','-flags:v','+bitexact','-movflags','+faststart',str(output)],stdin=subprocess.PIPE)
    font=ImageFont.truetype('DejaVuSans.ttf',12)
    try:
        for frame,raw in enumerate(reader):
            image=Image.frombytes('RGB',(w,h),raw);draw=ImageDraw.Draw(image,'RGBA')
            i=min(int(np.searchsorted(times,frame/fps)),len(times)-1)
            if i and abs(times[i-1]-frame/fps)<abs(times[i]-frame/fps):i-=1
            for line_px in target_px:draw.line([tuple(v) for v in line_px],fill=TARGET,width=3)
            for x,y in target_pts:draw.ellipse((x-5,y-5,x+5,y+5),fill='white',outline=TARGET,width=2)
            if i:draw.line([tuple(v) for v in object_px[:i+1]],fill=OBSERVED,width=5)
            x,y=object_px[i];draw.ellipse((x-6,y-6,x+6,y+6),fill=OBSERVED,outline='white',width=2)
            begin=np.searchsorted(times,times[i]-.8)
            for hand in range(hands.shape[1]):
                color=HAND_COLORS[hand]
                if i>begin:draw.line([tuple(v) for v in hand_px[begin:i+1,hand]],fill=color,width=4)
                for x,y in anchor_px[hand]:draw.ellipse((x-4,y-4,x+4,y+4),fill=color,outline='white',width=1)
                x,y=hand_px[i,hand];draw.ellipse((x-6,y-6,x+6,y+6),fill=color,outline='white',width=2)
            draw.rounded_rectangle((10,h-43,w-10,h-9),radius=4,fill=(255,255,255,232))
            labels=[(20,TARGET,'Object target'),(160,OBSERVED,'Object motion'),(305,HAND_COLORS[0],'Measured EEF')]
            for x,color,label in labels:
                draw.line((x,h-25,x+14,h-25),fill=color,width=3)
                draw.text((x+20,h-32),label,font=font,fill=(50,63,61))
            draw.text((w-90,h-32),f'{times[i]:.1f} s',font=font,fill=(50,63,61))
            if frame==0:image.save(video.with_suffix('.png'))
            if frame in [0,50,100,250,500,750]:image.save(a.cache/f'frame-{frame}.png')
            proc.stdin.write(image.tobytes())
    finally:
        reader.close();proc.stdin.close();code=proc.wait()
    assert code==0;shutil.copyfile(output,video)
    print('PASS measured native overlays',a.scene,hands.shape[1],'end effectors',flush=True)


if __name__=='__main__':main()
