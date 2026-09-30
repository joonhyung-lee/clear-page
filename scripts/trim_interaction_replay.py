"""Trim an existing physical replay and its videos to a recorded contact interval."""
import argparse
import copy
from pathlib import Path
import subprocess
import imageio_ffmpeg
from recording_io import read_recording, write_recording, compact_buffers
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('scene');p.add_argument('--start',type=float,required=True);p.add_argument('--end',type=float,required=True)
a=p.parse_args();root=Path(__file__).resolve().parents[1]
record,buffers=read_recording(root/f'assets/recordings/{a.scene}.viser')
assert 0<=a.start<a.end<=record['durationSeconds']
initial=[];updates={};tail=[]
for time,message in record['messages']:
 if time==0:initial.append([0,message])
 elif time<=a.start:
  assert message['type'] in ['SetPositionMessage','SetOrientationMessage','SetSceneNodeVisibilityMessage','SceneNodeUpdateMessage'],message['type']
  key=(message['type'],message['name'])
  if message['type']=='SceneNodeUpdateMessage' and key in updates:updates[key]['updates'].update(message['updates'])
  else:updates[key]=copy.deepcopy(message)
 elif time<=a.end:tail.append([time-a.start,message])
record['messages']=initial+[[0,m] for m in updates.values()]+tail
record['durationSeconds']=a.end-a.start
record,buffers=compact_buffers(record,buffers)
out=root/f'assets/recordings/{a.scene}-push.viser';write_recording(out,record,buffers);out.unlink()
ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
for suffix in ['', '-ego']:
 source=root/f'assets/media/{a.scene}{suffix}.mp4';target=root/f'assets/media/{a.scene}-push{suffix}.mp4'
 subprocess.run([ffmpeg,'-y','-v','error','-ss',str(a.start),'-i',str(source),'-t',str(a.end-a.start),'-an','-map_metadata','-1','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(target)],check=True)
 subprocess.run([ffmpeg,'-y','-v','error','-i',str(target),'-frames:v','1','-map_metadata','-1',str(target.with_suffix('.png'))],check=True)
print('Wrote',a.scene+'-push',f'{a.end-a.start:.3f} s','from unchanged physical frames')
