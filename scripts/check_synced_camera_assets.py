"""Verify paired frame counts, archived reference geometry and interpolation."""
from pathlib import Path
import json,subprocess,tempfile
import imageio_ffmpeg
import numpy as np
from recording_io import read_recording
from render_recorded_cameras import interpolate
ROOT=Path(__file__).resolve().parents[1]

def main():
 for scene in ['mpc-optimized','mpc-g1-native']:
  r,b=read_recording(ROOT/f'assets/recordings/{scene}.viser')
  meshes=[m for _,m in r['messages'] if m['type']=='LineSegmentsMessage' and '/reference-overlay/object-ghost-' in m.get('name','')]
  assert len(meshes)==2
  for m in meshes:
   ref=m['props']['points'];points=np.frombuffer(b[ref['__binary_index']],ref['dtype']).reshape(-1,2,3)
   assert points.shape==(24,2,3) and np.isfinite(points).all()
   assert np.allclose(np.ptp(points.reshape(-1,3),axis=0)[2],1.2,atol=1e-6)
  assert any(m.get('name','').endswith('/reference-overlay/lane') for _,m in r['messages'])
  assert any(m.get('name','').endswith('/reference-overlay/anchors') for _,m in r['messages'])
  print('PASS',scene,'reference lane and two corner ghosts')
 r,b=read_recording(ROOT/'assets/recordings/mpc-optimized.viser');render=interpolate(r,30)
 poses={(round(t,6),m['name'],m['type']):m for t,m in render['messages'] if m['type'] in ['SetPositionMessage','SetOrientationMessage']}
 for t,m in r['messages']:
  if m['type'] not in ['SetPositionMessage','SetOrientationMessage']:continue
  key='position' if m['type']=='SetPositionMessage' else 'wxyz';actual=poses.get((round(t,6),m['name'],m['type']))
  assert actual is not None
  v,w=np.asarray(actual[key]),np.asarray(m[key])
  assert np.allclose(v,w,atol=1e-6) or (key=='wxyz' and np.allclose(v,-w,atol=1e-6))
 print('PASS interpolation reproduces all archived G1 positions and orientations')
 for scene in ['mpc-optimized','mpc-spot-optimized','mpc-g1-native','mpc-spot-native']:
  counts=[];metadata=[]
  for suffix in (['-contact','-ego'] if scene=='mpc-optimized' else ['','-ego']):
   reader=imageio_ffmpeg.read_frames(str(ROOT/f'assets/media/{scene}{suffix}.mp4'));metadata.append(next(reader));counts.append(sum(1 for _ in reader))
  assert counts[0]==counts[1],(scene,counts)
  assert metadata[0]['fps']==metadata[1]['fps']>=25
  assert abs(metadata[0]['duration']-metadata[1]['duration'])<.01
  print('PASS',scene,'paired frames',counts[0],'fps',metadata[0]['fps'])
 # Added overlays must leave every original measured G1 pose unchanged.
 original=subprocess.check_output(['git','show','HEAD:assets/recordings/mpc-optimized.viser'],cwd=ROOT)
 with tempfile.NamedTemporaryFile(suffix='.viser') as f:
  f.write(original);f.flush();old,_=read_recording(f.name)
 def measured(record):
  return [(t,m) for t,m in record['messages'] if m['type'] in ['SetPositionMessage','SetOrientationMessage'] and '/body-' in m.get('name','')]
 assert measured(old)==measured(r)
 print('PASS published G1 measured body poses unchanged')
if __name__=='__main__':main()
