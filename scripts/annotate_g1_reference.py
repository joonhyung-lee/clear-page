"""Show the saved object reference, anchors and exactly two corner ghosts.

Adds presentation geometry only. The naive reference is task context, not a
Cartesian target supplied to its controller. All measured body poses stay intact.
"""
import argparse,json,shutil,subprocess
import imageio_ffmpeg
from PIL import Image,ImageDraw
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from recording_io import read_recording,write_recording,compact_buffers
from annotate_spot_push import spaced_anchors,segments
ROOT=Path(__file__).resolve().parents[1]
COLOR=[57,100,163]

def geometry(scene,baked=None):
 r,b=read_recording(ROOT/f'assets/recordings/{scene}.viser')
 if baked:
  result=json.loads((baked/'result.json').read_text())
  ref=np.asarray(result['objectReference'])[:,:2];size=np.asarray(result['objectSize'])
  states=np.load(baked/'states.npz');quat=states['quaternions'][0,result['objectBodyId']]
  prefix=''
 else:
  m=next(m for t,m in r['messages'] if m.get('name')=='/tracking/reference-path' and m['type']=='LineSegmentsMessage')
  a=m['props']['points'];v=np.frombuffer(b[a['__binary_index']],a['dtype']).reshape(-1,3)
  ref=v[np.r_[True,np.linalg.norm(np.diff(v,axis=0),axis=1)>1e-7],:2]
  size=np.array([.88,.88,1.2]);quat=[1,0,0,0];prefix='/tracking'
 ref=np.column_stack([ref,np.full(len(ref),.02)])
 anchors=spaced_anchors(ref)
 direction=ref[-1]-ref[0];direction/=np.linalg.norm(direction)
 side=np.cross(direction,[0,0,1])*size[1]/2
 rails=np.concatenate([segments(ref-side),segments(ref),segments(ref+side)])
 centers=spaced_anchors(ref,3)[1:];centers[:,2]=size[2]/2
 corners=np.array([[x,y,z] for x in [-1,1] for y in [-1,1] for z in [-1,1]])*size/2
 rotation=Rotation.from_quat(quat,scalar_first=True)
 ghosts=[]
 for center in centers:
  edges=[]
  for corner in corners:
   for axis in range(3):
    end=corner.copy();end[axis]-=np.sign(corner[axis])*size[axis]*.23
    edges.append(rotation.apply([corner,end])+center)
  ghosts.append(np.asarray(edges))
 return r,b,prefix,rails,anchors,ghosts

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--scene',required=True);p.add_argument('--baked',type=Path);p.add_argument('--video-cache',type=Path);a=p.parse_args()
 r,b,prefix,rails,anchors,ghosts=geometry(a.scene,a.baked)
 namespace=prefix+'/reference-overlay'
 r['messages']=[(t,m) for t,m in r['messages'] if not m.get('name','').startswith(namespace)]
 def binary(v,dtype='<f4'):
  b.append(np.asarray(v,dtype=dtype).tobytes());return dict(__binary_index=len(b)-1,dtype=np.dtype(dtype).str)
 def line(name,values,width):
  r['messages'].append((0.,dict(type='LineSegmentsMessage',name=namespace+'/'+name,props=dict(points=binary(values),colors=binary(np.broadcast_to(COLOR,values.shape),'|u1'),line_width=width,scale=1.))))
 line('lane',rails,3.)
 r['messages'].append((0.,dict(type='PointCloudMessage',name=namespace+'/anchors',props=dict(points=binary(anchors),colors=binary(np.tile(COLOR,(len(anchors),1)),'|u1'),point_size=.10,point_shape='circle',precision='float32',scale=1.,point_shading='flat'))))
 for i,ghost in enumerate(ghosts):line(f'object-ghost-{i}',ghost,3.)
 r['messages'].sort(key=lambda item:item[0]);r,b=compact_buffers(r,b);write_recording(ROOT/f'assets/recordings/{a.scene}.viser',r,b)
 if a.video_cache:
  assert a.baked, 'Video projection requires the saved native camera'
  a.video_cache.mkdir(parents=True,exist_ok=True)
  video=ROOT/f'assets/media/{a.scene}.mp4';plain=a.video_cache/'source.mp4'
  if not plain.exists():shutil.copyfile(video,plain)
  result=json.loads((a.baked/'result.json').read_text());camera=result['camera']
  eye=np.asarray(camera['position']);forward=np.asarray(camera['target'])-eye;forward/=np.linalg.norm(forward)
  right=np.cross(forward,[0,0,1]);right/=np.linalg.norm(right);basis=np.stack([right,np.cross(right,forward),forward],axis=1)
  reader=imageio_ffmpeg.read_frames(str(plain));meta=next(reader);w,h=meta['size'];focal=h/(2*np.tan(camera['fov']/2))
  projected=[]
  for ghost in ghosts:
   local=(ghost-eye)@basis;assert np.all(local[...,2]>0)
   projected.append(np.stack([w/2+local[...,0]/local[...,2]*focal,h/2-local[...,1]/local[...,2]*focal],axis=-1))
  temp=a.video_cache/'overlay.mp4'
  proc=subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-f','rawvideo','-pixel_format','rgb24','-video_size',f'{w}x{h}','-framerate',str(meta['fps']),'-i','-','-an','-map_metadata','-1','-c:v','libx264','-crf','19','-pix_fmt','yuv420p','-fflags','+bitexact','-flags:v','+bitexact','-movflags','+faststart',str(temp)],stdin=subprocess.PIPE)
  try:
   for i,raw in enumerate(reader):
    image=Image.frombytes('RGB',(w,h),raw);draw=ImageDraw.Draw(image,'RGBA')
    for ghost in projected:
     for edge in ghost:draw.line([tuple(v) for v in edge],fill=(*COLOR,185),width=3)
    if i==0:image.save(video.with_suffix('.png'))
    if i in [0,125,500]:image.save(a.video_cache/f'frame-{i}.png')
    proc.stdin.write(image.tobytes())
  finally:reader.close();proc.stdin.close();code=proc.wait()
  assert code==0;shutil.copyfile(temp,video)
 print('PASS reference overlay' ,a.scene,'five anchors, two box corner ghosts')
if __name__=='__main__':main()
