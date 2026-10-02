"""Check source-frame coverage and paired refreshed G1 cameras."""
from pathlib import Path
import re
import subprocess
import tempfile
import numpy as np
import imageio_ffmpeg
from recording_io import read_recording

ROOT=Path(__file__).resolve().parents[1]

def measured(record):
    return [(t,m) for t,m in record['messages'] if m['type'] in ('SetPositionMessage','SetOrientationMessage') and re.fullmatch(r'(?:/tracking)?/body-\d+',m.get('name',''))]

for scene in ['mpc-g1-native','mpc-baseline']:
    record,_=read_recording(ROOT/f'assets/recordings/{scene}.viser')
    with tempfile.NamedTemporaryFile(suffix='.viser') as f:
        f.write(subprocess.check_output(['git','show',f'HEAD:assets/recordings/{scene}.viser'],cwd=ROOT));f.flush()
        previous,_=read_recording(f.name)
    assert measured(record)==measured(previous),'Presentation edits must preserve all measured body and object states'
    base=[(t,m['position']) for t,m in record['messages'] if m['type']=='SetPositionMessage' and m['name'].endswith('/body-1')]
    assert len(base)==2001 and np.allclose(np.diff([t for t,p in base]),.02)
    durations=[]
    for suffix in (['','-ego'] if scene=='mpc-g1-native' else ['-contact','-ego']):
        path=ROOT/f'assets/media/{scene}{suffix}.mp4';reader=imageio_ffmpeg.read_frames(str(path));meta=next(reader)
        assert meta['fps']==50,(path.name,meta['fps'],'requires one video frame per 50 Hz source pose')
        count=0;samples={}
        for raw in reader:
            if count in (0,250,750,1250,1750):samples[count]=np.frombuffer(raw,np.uint8).astype(float)
            count+=1
        assert count==len(base),(path.name,count,len(base))
        assert all(np.mean(np.abs(samples[a]-samples[b]))>.1 for a,b in [(0,250),(250,750),(750,1250),(1250,1750)]),'Frozen replay segment'
        durations.append(meta['duration'])
    assert abs(durations[0]-durations[1])<.001
    print('PASS',scene,'all 2001 measured frames, paired 50 fps cameras, source states unchanged')
