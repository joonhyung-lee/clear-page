"""Correct legacy box contact-image poses without regenerating physical replay.

This migration accepts only the known axis-aligned box face orientations. It is
idempotent and leaves all image bytes, geometry, timings and binary buffers intact.
"""
import argparse,json,re
from pathlib import Path
import numpy as np
from recording_io import read_recording,write_recording
from scipy.spatial.transform import Rotation
FACE=re.compile(r'/(?:palm-)?contact-field/surface-([012])-(-?1)$')
def repair(path,write=False):
 record,buffers=read_recording(path);count=0;found=0
 # Identity image orientations were omitted by the original serializer.
 oriented={m['name'] for _,m in record['messages'] if m['type']=='SetOrientationMessage'}
 expanded=[]
 for time,message in record['messages']:
  expanded.append((time,message));match=FACE.search(message.get('name',''))
  if match and message['type']=='ImageMessage' and message['name'] not in oriented:
   assert match.groups()==('2','1'),'Unexpected omitted nonidentity face orientation'
   expanded.append((time,dict(name=message['name'],wxyz=[1.,0.,0.,0.],owner=message.get('owner',''),type='SetOrientationMessage')))
 record['messages']=expanded
 for time,message in record['messages']:
  match=FACE.search(message.get('name',''))
  if not match or message['type']!='SetOrientationMessage':continue
  found+=1;axis,sign=map(int,match.groups());normal=np.eye(3)[axis]*sign;u=np.eye(3)[(axis+1)%3];v=np.cross(normal,u)
  old=Rotation.from_matrix(np.column_stack([u,v,normal]));fixed=old*Rotation.from_euler('x',np.pi);actual=Rotation.from_quat(message['wxyz'],scalar_first=True)
  if np.allclose(actual.as_matrix(),fixed.as_matrix(),atol=1e-10):continue
  assert np.allclose(actual.as_matrix(),old.as_matrix(),atol=1e-10),'Unexpected image basis: '+message['name']
  message['wxyz']=fixed.as_quat(scalar_first=True).tolist();count+=1
 assert found>0,'No contact surfaces in '+path.name
 if write and count:write_recording(path,record,buffers)
 print(path.name,':',count,'orientations corrected' if write else 'orientations need correction')
 return count
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('recordings',type=Path,nargs='+');p.add_argument('--write',action='store_true');args=p.parse_args()
 for path in args.recordings:repair(path,args.write)
