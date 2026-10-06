"""The full execution panel must provide robot/Ego video and native poses to 40 s."""
from pathlib import Path
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
import imageio_ffmpeg
import numpy as np
import re
from recording_io import read_recording
ROOT=Path(__file__).resolve().parents[1]

def main():
 soup=BeautifulSoup((ROOT/'index.html').read_text(),'html.parser')
 viewer=soup.select_one('[data-execution-clock="optimized"]')
 for label,path in [('robot',viewer.select_one('.preview-video source')['src']),('Ego',viewer.select_one('.ego-inset video')['src'])]:
  reader=imageio_ffmpeg.read_frames(str(ROOT/urlsplit(path).path));meta=next(reader)
  assert meta['duration']>=39.95,f'{label} video stops at {meta["duration"]} s; Full rollout requires 40 s'
  samples={};count=0
  for frame in reader:
   if count in (600,750,900,1050):
    samples[count]=np.frombuffer(frame,np.uint8).astype(float)
   count+=1
  assert count==1200 and meta['fps']==30,(label,count,meta)
  assert all(np.mean(np.abs(samples[a]-samples[b]))>1 for a,b in [(600,750),(750,900),(900,1050)]),f'{label} freezes after pushing'
  print(f'PASS {label}: 1200 frames at 30 fps; distinct rendered frames at 20, 25, 30, 35 s')
 record,_=read_recording(ROOT/f'assets/recordings/{viewer["data-scene"]}.viser')
 assert record['durationSeconds']>=39.95,'Native robot replay must include the full interval'
 poses=[(t,m['position']) for t,m in record['messages'] if t>=20 and m['type']=='SetPositionMessage' and m.get('name','').endswith('/body-1')]
 assert len(poses)>100 and len({tuple(p) for _,p in poses})>100,'Missing recorded robot motion after pushing'
 context,_=read_recording(ROOT/'assets/recordings/mpc-context-optimized.viser')
 def measured(r):
  return {(t,m['name'],m['type']):m for t,m in r['messages'] if m['type'] in ['SetPositionMessage','SetOrientationMessage'] and re.fullmatch(r'/tracking/body-\d+',m.get('name',''))}
 assert measured(record)==measured(context),'Full replay changes measured poses'
 assert len([m for _,m in record['messages'] if m['type']=='LineSegmentsMessage' and '/object-ghost-' in m['name']])==2
 initial={m['name']:m['visible'] for t,m in record['messages'] if t==0 and m['type']=='SetSceneNodeVisibilityMessage'}
 expired={m['name'] for t,m in record['messages'] if t==14.000001 and m['type']=='SetSceneNodeVisibilityMessage' and not m['visible']}
 assert expired and expired<=initial.keys(),'Expired overlays must reset on backward seeks'
 assert viewer['data-contact-side']=='false','The continuation needs its recorded camera, not the first-push side camera'
 assert soup.select_one('#spot-process'),'A separate Spot robot/EEF row must follow the G1 row'
 print('PASS full Ours robot, Ego and native replay cover 40 s with post-push motion')
if __name__=='__main__':main()
